"""The Python client's TRANSPORT — the only hand-written half of the SDK.

Every typed method (``cagi.threads.create``, ``cagi.embodiments.act``, …) and every control vocabulary
(``session.desktop.click``, ``session.sim.ik``, …) is GENERATED from the CommandAGI SDK schema into
``_generated.py``, identically for every language. What lives here is what cannot be generated: ``call``
(JSON-RPC over ``POST /mcp``), reading the environment, and opening a live :class:`Session`.

Quickstart::

    from commandagi import CommandAGI

    cagi = CommandAGI()                                   # reads COMMANDAGI_API_KEY
    with cagi.launch("simulation/warehouse") as world:    # a world YOU drive (no agent)
        world.sim.ik(target=[0.3, 0.0, 0.4])
        jpeg = world.observe(fresh=True)
    # leaving the block stops the world and releases the machine
"""
from __future__ import annotations

import base64
import itertools
import json
import os
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

import requests
import websocket  # from the `websocket-client` package

from ._generated import (
    DEFAULT_BASE_URL,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_THREAD_ID,
    DesktopControls,
    GeneratedClient,
    RobotControls,
    SimControls,
)


class CommandAGIError(Exception):
    """A tool call that failed — carries the tool name and the platform's error detail."""

    def __init__(self, tool: str, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.tool = tool
        self.detail = detail


class CommandAGI(GeneratedClient):
    """Client for the CommandAGI platform. One surface for developers and agents alike — an API key's
    scopes are the only difference. ``call(tool, args)`` reaches any platform tool by name."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        thread_id: Optional[str] = None,
        http: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get(ENV_API_KEY)
        if not self.api_key:
            raise CommandAGIError("", f"pass api_key or set {ENV_API_KEY}")
        self.base_url = (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        self.thread_id = thread_id or os.environ.get(ENV_THREAD_ID) or None
        self._http = http or requests.Session()
        self._ids = itertools.count(1)
        self._bind_namespaces()

    # ── transport ────────────────────────────────────────────────────────────────────────────────
    def call(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run ANY platform tool by name — the universal escape hatch. Returns its parsed JSON result."""
        r = self._http.post(
            self.base_url + "/mcp",
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "mcp-protocol-version": "2025-06-18",
            },
            data=json.dumps({
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "tools/call",
                "params": {"name": tool, "arguments": args or {}},
            }),
            timeout=120,
        )
        try:
            j = r.json()
        except ValueError:
            raise CommandAGIError(tool, f"{tool}: non-JSON response (HTTP {r.status_code})")
        if j.get("error"):
            raise CommandAGIError(tool, f"{tool}: {j['error'].get('message', 'tool error')}", j["error"])
        result = j.get("result") or {}
        text = "\n".join(c.get("text", "") for c in result.get("content") or [])
        if result.get("isError"):
            raise CommandAGIError(tool, f"{tool}: {text}", text)
        try:
            return json.loads(text)
        except ValueError:
            return text

    def _with_thread(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Default ``threadId`` to the client's own thread when the caller didn't name one."""
        if self.thread_id and args.get("threadId") is None:
            return {**args, "threadId": self.thread_id}
        return args

    # ── sessions ─────────────────────────────────────────────────────────────────────────────────
    def session(self, thread_id: str, embodiment_id: str) -> "Session":
        """Open a live session on an embodiment that already exists: its frames, and typed control."""
        return Session(self, thread_id, embodiment_id, owns_thread=False)

    def launch(
        self,
        snapshot_id: str,
        *,
        title: Optional[str] = None,
        wait: bool = True,
        timeout: float = 600.0,
    ) -> "Session":
        """Launch a world YOU drive — a computer (``computer/…``) or a sim/robot (``simulation/…``)
        snapshot — in a new agentless thread, and return its live session. Waits until the world
        declares its controls (booted and connected) unless ``wait=False``. Use it as a context manager
        (or call ``stop()``) to release the machine."""
        created = self.threads.create(agentless=True, snapshot_id=snapshot_id, title=title or snapshot_id)
        launched = (created or {}).get("launched") or {}
        embodiment_id = launched.get("embodimentId")
        if not embodiment_id:
            raise CommandAGIError("create_thread", f"launch of {snapshot_id} started no embodiment", created)
        session = Session(self, created["threadId"], embodiment_id, owns_thread=True)
        if wait:
            session.ready(timeout=timeout)
        return session


class Session:
    """A LIVE SESSION on one embodiment — a computer, a robot or a sim.

    Control is a tool call: every action is ``embodiments.act(embodiment_id, action, payload)``, resolved
    by the thread against what the embodiment live-declares. ``desktop`` / ``robot`` / ``sim`` are the
    generated typed vocabularies over that one method; :meth:`act` is the untyped form. Frames arrive
    over the thread's WebSocket as ``frame`` messages; the socket opens on the first frame request.
    """

    def __init__(self, client: CommandAGI, thread_id: str, embodiment_id: str, *, owns_thread: bool) -> None:
        self._client = client
        self.thread_id = thread_id
        self.embodiment_id = embodiment_id
        self._owns_thread = owns_thread
        #: Computers: pointer, keyboard, waits.
        self.desktop = DesktopControls(self)
        #: Physical robots driven through a robot driver.
        self.robot = RobotControls(self)
        #: Simulated worlds and the robots inside them.
        self.sim = SimControls(self)
        self._lock = threading.Condition()
        self._latest: Optional[Dict[str, Any]] = None
        self._ws: Optional[websocket.WebSocketApp] = None
        self._closed = False

    # ── control ──────────────────────────────────────────────────────────────────────────────────
    def act(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        """Send one declared action to this embodiment. Refusals (undeclared, invalid payload) raise."""
        return self._client.embodiments.act(self.embodiment_id, action, payload or {}, self.thread_id)

    def controls(self) -> List[Dict[str, Any]]:
        """The controls this embodiment declares right now. Empty until its runtime has connected."""
        return (self._client.embodiments.controls(self.embodiment_id, self.thread_id) or {}).get("controls") or []

    def describe(self) -> Dict[str, Any]:
        """The live world a sim/robot runtime reports: robots, objects, poses."""
        return self._client.embodiments.describe(self.thread_id) or {}

    def ready(self, *, timeout: float = 600.0, poll: float = 3.0) -> List[Dict[str, Any]]:
        """Block until the embodiment is connected and declaring controls (a booting machine is not)."""
        deadline = time.time() + timeout
        while True:
            controls = self.controls()
            if controls:
                return controls
            if time.time() > deadline:
                raise CommandAGIError("list_controls", f"{self.embodiment_id} declared no controls within {timeout}s — is it running?")
            time.sleep(poll)

    # ── frames ───────────────────────────────────────────────────────────────────────────────────
    def _open(self) -> None:
        if self._ws is not None or self._closed:
            return
        base = self._client.base_url.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{base}/rt/thread/{self.thread_id}?token={self._client.api_key}"

        def on_message(_ws: Any, raw: str) -> None:
            try:
                m = json.loads(raw)
            except (TypeError, ValueError):
                return
            if m.get("t") != "frame" or m.get("embodimentId") != self.embodiment_id or not isinstance(m.get("url"), str):
                return
            with self._lock:
                self._latest = {
                    "embodiment_id": m["embodimentId"],
                    "channel_id": m.get("channelId", ""),
                    "url": m["url"],
                    "at": m.get("at") or int(time.time() * 1000),
                }
                self._lock.notify_all()

        self._ws = websocket.WebSocketApp(url, on_message=on_message)
        threading.Thread(
            target=lambda: self._ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=3),
            daemon=True,
        ).start()

    def frame(self, *, fresh: bool = False, timeout: float = 30.0) -> Dict[str, Any]:
        """The latest frame ``{embodiment_id, channel_id, url, at}``. ``fresh=True`` waits for one that
        arrives AFTER this call — what you want right after acting."""
        self._open()
        after = int(time.time() * 1000) if fresh else 0
        deadline = time.time() + timeout
        with self._lock:
            while not (self._latest and self._latest["at"] > after):
                left = deadline - time.time()
                if left <= 0:
                    raise CommandAGIError("frame", f"no frame from {self.embodiment_id} within {timeout}s")
                self._lock.wait(left)
            return dict(self._latest)

    def observe(self, *, fresh: bool = False, timeout: float = 30.0) -> bytes:
        """The latest frame's image bytes (JPEG/PNG), decoding a data: URL or fetching an https one."""
        url = self.frame(fresh=fresh, timeout=timeout)["url"]
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
        r = self._client._http.get(url, headers={"authorization": f"Bearer {self._client.api_key}"}, timeout=60)
        r.raise_for_status()
        return r.content

    def observe_array(self, **kw: Any) -> Any:
        """Observe and decode to a numpy HxWx3 uint8 array (``pip install "commandagi[vision]"``)."""
        try:
            import io

            import numpy as np
            from PIL import Image
        except ImportError as e:  # pragma: no cover
            raise CommandAGIError("observe_array", "observe_array needs `pillow` and `numpy` installed") from e
        return np.asarray(Image.open(io.BytesIO(self.observe(**kw))).convert("RGB"))

    def frames(self) -> Iterator[Dict[str, Any]]:
        """Yield every new frame as it arrives."""
        while not self._closed:
            yield self.frame(fresh=True, timeout=3600)

    # ── lifecycle ────────────────────────────────────────────────────────────────────────────────
    def close(self) -> None:
        """Stop watching (closes the frame socket). The embodiment keeps running."""
        self._closed = True
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None

    def stop(self) -> None:
        """Close, and if this session LAUNCHED its world, stop the world's run and release the machine."""
        self.close()
        if self._owns_thread:
            self._client.threads.kill(self.thread_id)

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.stop()
