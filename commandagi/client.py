"""CommandAGI Python SDK — launch cloud computers and 3D robot simulations and control them.

A developer with an API key can spin up a real environment (a 3D physics world with a robot, or an
Ubuntu desktop), stream its observations (the robot's head camera / the screen), and send actions —
the same control plane the web app uses, wrapped in a small, Gym-flavored client.

Quickstart (robot testing):

    from commandagi import CommandAGI

    cagi = CommandAGI(api_key="cagi_...")            # or set COMMANDAGI_API_KEY
    with cagi.launch("simulation/warehouse") as world:
        obs = world.observe()                        # JPEG bytes from the robot's head camera
        for _ in range(10):
            obs = world.step("move", speed=0.8)      # drive forward, get the next frame
        world.reset()                                # back to the episode start pose
    # leaving the `with` block stops the world and releases the cloud VM

The control vocabulary for a computer world: click (x, y), type (text), key (key), move (x, y),
scroll. Robots in a (morphology-agnostic) simulator are driven by a small GENERIC vocabulary —
``ctrl`` (set actuator targets), ``actuator`` (one named actuator), ``ik`` (inverse-kinematics to a
Cartesian target), ``trajectory`` (waypoints), ``describe`` — see :class:`World`'s generic-control
methods. Spin up your own simulator instance with :meth:`CommandAGI.launch_sim`.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Iterator, Optional

import requests
import websocket  # from the `websocket-client` package

DEFAULT_BASE_URL = "https://api.commandagi.com"

# The built-in 3D simulation worlds. Each is a scene a mobile robot is dropped into.
SIMULATIONS = ["simulation/warehouse", "simulation/house-on-fire", "simulation/school"]
COMPUTERS = ["computer/software-engineer", "computer/robots-engineer", "computer/video-professional"]


class CommandAGIError(Exception):
    """Any SDK-level error (HTTP failure, launch rejected, timeout)."""


class World:
    """A live world you control. Created by :meth:`CommandAGI.launch`; not constructed directly.

    Observations are the latest sensor frame (the robot's head camera for sims, the screen for
    computers) as encoded image bytes. Actions are sent over the same realtime channel the web UI
    uses. Use it as a context manager so the cloud VM is always released.
    """

    def __init__(self, client: "CommandAGI", thread_id: str, device_id: str, kind: str):
        self._client = client
        self.thread_id = thread_id
        self.device_id = device_id
        self.kind = kind  # "robot" | "computer"
        self._frames: dict[str, bytes] = {}
        self._latest: Optional[bytes] = None
        self._descriptions: dict[str, dict] = {}  # robot_id -> last describe payload
        self._results: dict[str, dict] = {}  # requestId -> action_result payload (answering controls)
        self._lock = threading.Lock()
        self._open = threading.Event()
        self._closed = False
        self._ws = websocket.WebSocketApp(
            self._ws_url(),
            on_open=self._on_open,
            on_message=self._on_message,
        )
        # ping_interval keeps the long-lived channel alive; reconnect transparently re-establishes it
        # (and _on_open re-takes control) if the edge drops it mid-thread.
        self._thread = threading.Thread(
            target=lambda: self._ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=3),
            daemon=True,
        )
        self._thread.start()
        if not self._open.wait(timeout=15):
            raise CommandAGIError("could not open the realtime control channel")

    def _on_open(self, _ws) -> None:
        # Re-take manual control on every (re)connect so our actions always drive the device.
        self._open.set()
        try:
            self._send({"t": "remote.request", "deviceId": self.device_id, "on": True})
        except Exception:
            pass

    # ── realtime plumbing ────────────────────────────────────────────────────
    def _ws_url(self) -> str:
        base = self._client.base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/rt/thread/{self.thread_id}?role=owner&name=sdk"

    def _on_message(self, _ws, raw: str) -> None:
        try:
            m = json.loads(raw)
        except (ValueError, TypeError):
            return
        if m.get("t") == "frame" and isinstance(m.get("url"), str) and m["url"].startswith("data:"):
            try:
                data = base64.b64decode(m["url"].split(",", 1)[1])
            except Exception:
                return
            with self._lock:
                self._frames[m.get("channelId", "default")] = data
                self._latest = data
        elif m.get("t") in ("describe", "description") and isinstance(m.get("description"), dict):
            # Best-effort: the runtime may echo a world/robot description back over the channel.
            with self._lock:
                self._descriptions[m.get("robotId", "")] = m["description"]
        elif m.get("t") == "action_result" and isinstance(m.get("requestId"), str):
            # An answering control (describe / scene_graph / pick / transform …) — match by requestId.
            with self._lock:
                self._results[m["requestId"]] = m.get("result")

    def _send(self, msg: dict) -> None:
        self._ws.send(json.dumps(msg))

    def request(self, action: str, *, timeout: float = 5.0, **payload):
        """Send an *answering* control action and block for the runtime's result (matched by a
        requestId via the platform's action_result relay). Used by :meth:`describe` / Gym proprioception.
        Returns the result dict, or raises on timeout."""
        request_id = f"req-{threading.get_ident()}-{int(time.time()*1000)}"
        with self._lock:
            self._results.pop(request_id, None)
        self._send({"t": "control", "deviceId": self.device_id, "action": action, "payload": payload, "requestId": request_id})
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if request_id in self._results:
                    return self._results.pop(request_id)
            time.sleep(0.05)
        raise CommandAGIError(f"control '{action}' timed out after {timeout}s")

    # ── observations ─────────────────────────────────────────────────────────
    def observe(self, *, fresh: bool = False, timeout: float = 30.0) -> bytes:
        """Return the latest observation as encoded image bytes (JPEG for sims, PNG for computers).

        Blocks until a frame is available. With ``fresh=True``, waits for a frame that arrives
        *after* this call (useful right after an action).
        """
        if fresh:
            with self._lock:
                self._latest = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None:
                    return self._latest
            time.sleep(0.1)
        raise CommandAGIError("no observation within timeout — is the world still live?")

    def observe_array(self, **kw):
        """Observe and decode to a numpy HxWx3 uint8 array (requires Pillow + numpy)."""
        try:
            import io

            import numpy as np
            from PIL import Image
        except ImportError as e:  # pragma: no cover
            raise CommandAGIError("observe_array needs `pillow` and `numpy` installed") from e
        return np.asarray(Image.open(io.BytesIO(self.observe(**kw))).convert("RGB"))

    def stream(self) -> Iterator[bytes]:
        """Yield observations as they arrive (roughly the device frame rate)."""
        last = object()
        while True:
            with self._lock:
                cur = self._latest
            if cur is not None and cur is not last:
                last = cur
                yield cur
            time.sleep(0.05)

    # ── actions ──────────────────────────────────────────────────────────────
    def act(self, action: str, **payload) -> None:
        """Send a control action without waiting. E.g. ``act("move", speed=0.8)``."""
        self._send({"t": "control", "deviceId": self.device_id, "action": action, "payload": payload})

    def step(self, action: str, *, settle: float = 0.8, **payload) -> bytes:
        """Send an action, let the world advance ``settle`` seconds, and return the next observation."""
        self.act(action, **payload)
        time.sleep(settle)
        return self.observe(fresh=True)

    def reset(self, *, settle: float = 1.0) -> bytes:
        """Reset the episode (robot back to its start pose) and return the first observation."""
        self.act("reset")
        time.sleep(settle)
        return self.observe(fresh=True)

    # ── generic (morphology-agnostic) robot control ──────────────────────────
    # The simulator is morphology-agnostic: a robot is described by its actuators and sites, and is
    # driven by a small GENERIC vocabulary — ctrl / actuator / ik / trajectory / describe. There is
    # deliberately NO drive / gripper here; "move forward" or "close the gripper" is just particular
    # actuator targets on a particular morphology. All of these go through the same `control` channel
    # as :meth:`act`, and address one robot within a (possibly multi-robot) device via ``robot_id``.
    def ctrl(self, targets: dict, robot_id: str = "") -> None:
        """Set actuator targets directly: ``{actuator_name: value, ...}``.

        ``targets`` maps named actuators (joints/motors as exposed by :meth:`describe`) to their
        target value. This is the lowest-level, fully generic control primitive.
        """
        self.act("ctrl", targets=targets, robotId=robot_id)

    def actuator(self, name: str, value: float, robot_id: str = "") -> None:
        """Set a single named actuator to ``value`` (sugar over :meth:`ctrl`)."""
        self.act("actuator", name=name, value=value, robotId=robot_id)

    def ik(self, target, site: Optional[str] = None, relative: bool = False, robot_id: str = "") -> None:
        """Drive an end-effector ``site`` to a Cartesian ``target`` ``[x, y, z]`` via inverse kinematics.

        ``site`` names the body/site to move (default: the robot's primary end-effector). With
        ``relative=True`` the target is an offset from the site's current pose rather than absolute
        world coordinates.
        """
        self.act("ik", target=list(target), site=site, relative=relative, robotId=robot_id)

    def trajectory(self, waypoints, robot_id: str = "") -> None:
        """Follow a sequence of ``waypoints`` (each an actuator-target dict or a Cartesian point).

        Waypoints are interpreted by the runtime in order; this is the generic way to express a
        multi-step motion plan for any morphology.
        """
        self.act("trajectory", waypoints=list(waypoints), robotId=robot_id)

    def describe(self, robot_id: str = "") -> dict:
        """Return a description of the world / robot(s): morphology, actuators, sites, objects.

        Best-effort. The runtime answers a ``describe`` request over the thread control channel,
        but there is currently no *synchronous* describe HTTP endpoint, so this issues the describe
        action and then tries to read a description the runtime echoes back over the realtime
        channel (see ``_descriptions``). If none arrives in time, returns ``{}`` — callers (e.g. the
        agent runner) should also be able to obtain a description via the ``/agent/robot-act`` flow,
        which inspects the live world server-side.
        """
        # Preferred: the `describe` action answers with the full world description (incl. live joint
        # pos/vel) via the action_result relay. Falls back to the legacy echo path if unavailable.
        try:
            res = self.request("describe", robotId=robot_id)
            if isinstance(res, dict) and res.get("robots") is not None:
                return res
        except CommandAGIError:
            pass
        with self._lock:
            self._descriptions.pop(robot_id, None)
        self.act("describe", robotId=robot_id)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            with self._lock:
                desc = self._descriptions.get(robot_id)
            if desc is not None:
                return desc
            time.sleep(0.1)
        return {}

    # ── lifecycle ──────────────────────────────────────────────────────────────
    def close(self) -> None:
        """Stop the world and release the cloud VM. Safe to call more than once."""
        self._closed = True
        try:
            self._client._stop(self.thread_id)
        finally:
            try:
                self._ws.close()  # stops run_forever's reconnect loop
            except Exception:
                pass

    def __enter__(self) -> "World":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class SimInstance:
    """A live simulator instance — a hosted morphology-agnostic 3D world you can populate with
    robots, share, and (with the agent runner) drive autonomously.

    Created by :meth:`CommandAGI.launch_sim` (or rehydrated via :meth:`CommandAGI.get_sim`); not
    constructed directly. A sim instance owns one realtime **thread** (``thread_id``); robots you
    :meth:`join_robot` become devices on that thread. Use :meth:`grant` to let other users view it
    or launch their own robots into it.
    """

    def __init__(self, client: "CommandAGI", instance_id: str, thread_id: str,
                 world_id: str = "", view: Optional[dict] = None):
        self._client = client
        self.id = instance_id
        self.thread_id = thread_id
        self.world_id = world_id
        self._view = view or {}

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"SimInstance(id={self.id!r}, thread_id={self.thread_id!r})"

    def view(self) -> dict:
        """Fetch the current instance view (metadata + attached devices) from the API."""
        self._view = self._client._get(f"/sims/{self.id}")
        return self._view

    def devices(self) -> list:
        """The robot devices currently attached to this instance (from the latest :meth:`view`)."""
        return self.view().get("devices", [])

    def join_robot(self, kind: str = "rover") -> dict:
        """Spawn a robot of ``kind`` into the world and return ``{robotId, deviceId, threadId}``.

        The robot becomes a device on this instance's thread; address it later via its ``deviceId``
        (for control) and ``robotId`` (to target a specific robot within a multi-robot device).
        """
        res = self._client._post(f"/sims/{self.id}/join", {"kind": kind})
        return {
            "robotId": res.get("robotId"),
            "deviceId": res.get("deviceId"),
            "threadId": res.get("threadId", self.thread_id),
        }

    def grant(self, subject_id: str, capability: str = "operator", subject_type: str = "user") -> dict:
        """Grant ``subject_id`` a capability on this instance.

        ``capability``: ``"viewer"`` (may watch the stream) or ``"operator"`` (may also launch
        robots into the world). ``subject_type`` is usually ``"user"``.
        """
        return self._client._post(
            f"/sims/{self.id}/grants",
            {"subjectType": subject_type, "subjectId": subject_id, "capability": capability},
        )

    def stop(self) -> None:
        """Stop the simulator instance and release its resources. Safe to call more than once."""
        try:
            self._client._post(f"/sims/{self.id}/stop")
        except CommandAGIError:
            pass

    def __enter__(self) -> "SimInstance":
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()


class CommandAGI:
    """Client for the CommandAGI API. Authenticate with an API key (create one in the dashboard or
    via ``POST /me/api-keys`` with an ``operator`` scope)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("COMMANDAGI_API_KEY")
        if not self.api_key:
            raise CommandAGIError("api_key is required (pass it or set COMMANDAGI_API_KEY)")
        self.base_url = (base_url or os.environ.get("COMMANDAGI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

    # ── http ─────────────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}

    def _post(self, path: str, body: Optional[dict] = None) -> dict:
        r = requests.post(self.base_url + path, headers=self._headers(), json=body or {}, timeout=60)
        if not r.ok:
            raise CommandAGIError(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.text else {}

    def _get(self, path: str) -> dict:
        r = requests.get(self.base_url + path, headers=self._headers(), timeout=60)
        if not r.ok:
            raise CommandAGIError(f"GET {path} -> {r.status_code}: {r.text}")
        return r.json()

    def _stop(self, thread_id: str) -> None:
        try:
            self._post(f"/threads/{thread_id}/stop")
        except CommandAGIError:
            pass

    # ── public ───────────────────────────────────────────────────────────────
    def launch(self, snapshot: str, *, wait: bool = True, timeout: float = 600.0) -> World:
        """Launch a world and return it (live, ready to control).

        ``snapshot`` is a catalog id — a 3D sim (``simulation/warehouse``) or a computer
        (``computer/software-engineer``). With ``wait=True`` (default) this blocks until the world's
        device is streaming. The world has NO agent — you drive it. Always ``close()`` it (or use a
        ``with`` block) to release the VM.
        """
        is_robot = snapshot.startswith("simulation/") or snapshot.startswith("physical/")
        thread_id = self._post("/worlds", {"title": snapshot})["threadId"]
        try:
            res = self._post(f"/threads/{thread_id}/{'robots' if is_robot else 'computers'}", {"snapshotId": snapshot})
        except CommandAGIError:
            self._stop(thread_id)
            raise
        if res.get("status") != "granted":
            self._stop(thread_id)
            raise CommandAGIError(f"launch was not granted: {res}")
        world = World(self, thread_id, res["deviceId"], "robot" if is_robot else "computer")
        if wait:
            self._wait_until_live(thread_id, timeout)
        return world

    def connect_world(self, thread_id: str, device_id: str, kind: str = "robot") -> World:
        """Open a control channel to an *existing* device on a thread and return a :class:`World`.

        Unlike :meth:`launch`, this does not provision anything — it attaches to a device that already
        exists (e.g. a robot you added to a :class:`SimInstance` via
        :meth:`SimInstance.join_robot`). Calling ``world.close()`` on it stops the whole thread, so
        prefer :meth:`SimInstance.stop` for lifecycle and use this purely to observe/control.
        """
        return World(self, thread_id, device_id, kind)

    def _web_url(self) -> str:
        # api.commandagi.com → commandagi.com ; api-dev.commandagi.com → dev.commandagi.com
        host = self.base_url.split("://", 1)[-1]
        if host.startswith("api-dev."):
            return "https://dev.commandagi.com"
        if host.startswith("api."):
            return "https://commandagi.com"
        return self.base_url

    def register_robot(self, name: str = "my-robot"):
        """Register YOUR robot as a device and return a :class:`RobotBridge` to stream it.

        Creates an agentless world + a bring-your-own robot device, then hands you a bridge: call
        ``bridge.run(camera=..., on_action=...)`` to publish your robot's camera and receive control
        actions. Watch/drive it at ``bridge.thread_url``.
        """
        from .bridge import RobotBridge

        thread_id = self._post("/worlds", {"title": name})["threadId"]
        try:
            dev = self._post(f"/threads/{thread_id}/connect-device", {"kind": "robot", "name": name})
        except CommandAGIError:
            self._stop(thread_id)
            raise
        return RobotBridge(
            dev["controlUrl"],
            dev["token"],
            dev["deviceId"],
            thread_id=thread_id,
            thread_url=f"{self._web_url()}/world/{thread_id}",
            client=self,
        )

    # ── simulator instances ───────────────────────────────────────────────────
    def launch_sim(self, scene: str = "the-matrix", visibility: str = "private",
                   title: Optional[str] = None) -> SimInstance:
        """Launch a new simulator instance for ``scene`` and return a :class:`SimInstance`.

        ``visibility`` is ``"private"`` | ``"unlisted"`` | ``"public"``. The instance starts empty —
        add robots with :meth:`SimInstance.join_robot`. Use it as a context manager (or call
        :meth:`SimInstance.stop`) to release it.
        """
        body: dict = {"scene": scene, "visibility": visibility}
        if title is not None:
            body["title"] = title
        res = self._post("/sims", body)
        return SimInstance(
            self,
            instance_id=res.get("instanceId") or res.get("id", ""),
            thread_id=res.get("threadId", ""),
            world_id=res.get("worldId", ""),
        )

    def sims(self) -> list:
        """List the simulator instances visible to you (``[{id, title, scene, visibility, ...}]``)."""
        return self._get("/sims").get("sims", [])

    def get_sim(self, sim_id: str) -> SimInstance:
        """Rehydrate a :class:`SimInstance` for an existing instance ``sim_id``."""
        view = self._get(f"/sims/{sim_id}")
        return SimInstance(
            self,
            instance_id=view.get("id", sim_id),
            thread_id=view.get("threadId", ""),
            world_id=view.get("worldId", ""),
            view=view,
        )

    def robot_act(self, goal: str, devices: list, *, model: Optional[str] = None,
                  history: Optional[list] = None) -> dict:
        """Ask the platform's agent for the next robot tool calls toward ``goal``.

        ``devices`` is a list of ``{deviceId, world, camera}`` — one entry per robot device, where
        ``world`` is that device's description (from :meth:`World.describe`) and ``camera`` is a
        recent frame (a ``data:`` URL or base64 string). Returns
        ``{reasoning, calls: [{tool, deviceId, robotId, ...}]}``. This is the building block the
        :class:`~commandagi.agent.RobotAgent` runner loops over.
        """
        body: dict = {"goal": goal, "devices": devices}
        if model is not None:
            body["model"] = model
        if history is not None:
            body["history"] = history
        return self._post("/agent/robot-act", body)

    def _wait_until_live(self, thread_id: str, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            devices = self._get(f"/threads/{thread_id}").get("devices", [])
            if any(d.get("status") == "live" for d in devices):
                return
            time.sleep(3)
        # Not fatal: the first observe() will surface a clearer timeout if nothing ever streams.
