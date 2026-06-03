"""CommandAGI Python SDK — launch cloud computers and 3D robot simulations and control them.

A developer with an API key can spin up a real environment (a PyBullet 3D world with a robot, or an
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

The control vocabulary for a simulated/real robot: move (speed), back (speed), turn (dir, rate),
stop, reset. For a computer world: click (x, y), type (text), key (key), move (x, y), scroll.
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

# The built-in 3D simulation worlds (PyBullet). Each is a scene a mobile robot is dropped into.
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

    def __init__(self, client: "CommandAGI", session_id: str, device_id: str, kind: str):
        self._client = client
        self.session_id = session_id
        self.device_id = device_id
        self.kind = kind  # "robot" | "computer"
        self._frames: dict[str, bytes] = {}
        self._latest: Optional[bytes] = None
        self._lock = threading.Lock()
        self._open = threading.Event()
        self._closed = False
        self._ws = websocket.WebSocketApp(
            self._ws_url(),
            on_open=self._on_open,
            on_message=self._on_message,
        )
        # ping_interval keeps the long-lived channel alive; reconnect transparently re-establishes it
        # (and _on_open re-takes control) if the edge drops it mid-session.
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
        return f"{base}/rt/session/{self.session_id}?role=owner&name=sdk"

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

    def _send(self, msg: dict) -> None:
        self._ws.send(json.dumps(msg))

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

    # ── lifecycle ──────────────────────────────────────────────────────────────
    def close(self) -> None:
        """Stop the world and release the cloud VM. Safe to call more than once."""
        self._closed = True
        try:
            self._client._stop(self.session_id)
        finally:
            try:
                self._ws.close()  # stops run_forever's reconnect loop
            except Exception:
                pass

    def __enter__(self) -> "World":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


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

    def _stop(self, session_id: str) -> None:
        try:
            self._post(f"/sessions/{session_id}/stop")
        except CommandAGIError:
            pass

    # ── public ───────────────────────────────────────────────────────────────
    def launch(self, template: str, *, wait: bool = True, timeout: float = 600.0) -> World:
        """Launch a world and return it (live, ready to control).

        ``template`` is a catalog id — a 3D sim (``simulation/warehouse``) or a computer
        (``computer/software-engineer``). With ``wait=True`` (default) this blocks until the world's
        device is streaming. The world has NO agent — you drive it. Always ``close()`` it (or use a
        ``with`` block) to release the VM.
        """
        is_robot = template.startswith("simulation/") or template.startswith("physical/")
        session_id = self._post("/machines", {"title": template})["sessionId"]
        try:
            res = self._post(f"/sessions/{session_id}/{'robots' if is_robot else 'computers'}", {"templateId": template})
        except CommandAGIError:
            self._stop(session_id)
            raise
        if res.get("status") != "granted":
            self._stop(session_id)
            raise CommandAGIError(f"launch was not granted: {res}")
        world = World(self, session_id, res["deviceId"], "robot" if is_robot else "computer")
        if wait:
            self._wait_until_live(session_id, timeout)
        return world

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

        Creates an agentless machine + a bring-your-own robot device, then hands you a bridge: call
        ``bridge.run(camera=..., on_action=...)`` to publish your robot's camera and receive control
        actions. Watch/drive it at ``bridge.session_url``.
        """
        from .bridge import RobotBridge

        session_id = self._post("/machines", {"title": name})["sessionId"]
        try:
            dev = self._post(f"/sessions/{session_id}/connect-device", {"kind": "robot", "name": name})
        except CommandAGIError:
            self._stop(session_id)
            raise
        return RobotBridge(
            dev["controlUrl"],
            dev["token"],
            dev["deviceId"],
            session_id=session_id,
            session_url=f"{self._web_url()}/machine/{session_id}",
            client=self,
        )

    def _wait_until_live(self, session_id: str, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            devices = self._get(f"/sessions/{session_id}").get("devices", [])
            if any(d.get("status") == "live" for d in devices):
                return
            time.sleep(3)
        # Not fatal: the first observe() will surface a clearer timeout if nothing ever streams.
