"""Bring-your-own-robot: stream YOUR robot's camera into CommandAGI and receive actions.

This is the *producer* side of the platform (the mirror of `World`, which is the consumer side that
drives a hosted world). You register a robot, then run a bridge that publishes its camera frames and
hands incoming control actions to your hardware. Anyone with access to the thread — a person in the
web UI, an agent, or another developer's `World` client — then sees your robot's camera and can drive
it, exactly like a first-party simulation.

    from commandagi import CommandAGI

    cagi = CommandAGI(api_key="cagi_…")
    bridge = cagi.register_robot("my-rover")
    print("watch + drive it at:", bridge.thread_url)

    bridge.run(
        camera=lambda: my_robot.jpeg_frame(),          # -> bytes (JPEG/PNG)
        on_action=lambda action, payload: my_robot.do(action, payload),
        fps=10,
    )                                                  # blocks; Ctrl-C to stop + release
"""
from __future__ import annotations

import base64
import json
import threading
import time
from typing import Callable, Optional

import websocket  # websocket-client


def _data_url(frame: bytes) -> str:
    mime = "image/png" if frame[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(frame).decode()


class RobotBridge:
    """A live bridge between your robot and a CommandAGI thread. Create it with
    :meth:`CommandAGI.register_robot`; then call :meth:`run`."""

    def __init__(self, control_url: str, token: str, device_id: str, *, thread_id: str, thread_url: str, client=None):
        self.control_url = control_url
        self.token = token
        self.device_id = device_id
        self.thread_id = thread_id
        self.thread_url = thread_url
        self._client = client
        self._camera: Optional[Callable[[], bytes]] = None
        self._on_action: Optional[Callable[[str, dict], None]] = None
        self._channel = "cam-head"
        self._fps = 10.0
        self._ws: Optional[websocket.WebSocketApp] = None
        self._stop = threading.Event()

    def _ws_url(self) -> str:
        base = self.control_url.replace("https://", "wss://").replace("http://", "ws://")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}runtime=1&role=agent&token={self.token}"

    def _on_open(self, ws) -> None:
        # Announce we're live and which camera channel we publish, then start streaming frames.
        ws.send(json.dumps({"type": "status", "status": "live"}))
        ws.send(json.dumps({"type": "channels", "channels": [{"channelId": self._channel, "label": "Camera", "kind": "camera"}]}))
        threading.Thread(target=self._frame_loop, args=(ws,), daemon=True).start()

    def _frame_loop(self, ws) -> None:
        interval = 1.0 / max(0.5, self._fps)
        while not self._stop.is_set():
            try:
                frame = self._camera()
                if frame:
                    ws.send(json.dumps({"type": "frame", "channelId": self._channel, "url": _data_url(frame)}))
            except Exception as e:  # keep streaming; surface the error in chat
                try:
                    ws.send(json.dumps({"type": "agent_message", "text": f"[camera error] {e}"}))
                except Exception:
                    pass
            time.sleep(interval)

    def _on_message(self, _ws, raw: str) -> None:
        try:
            m = json.loads(raw)
        except (ValueError, TypeError):
            return
        if m.get("type") == "control" and self._on_action:
            try:
                self._on_action(m.get("action", ""), m.get("payload") or {})
            except Exception:
                pass

    def run(
        self,
        camera: Callable[[], bytes],
        on_action: Callable[[str, dict], None],
        *,
        fps: float = 10.0,
        channel: str = "cam-head",
        block: bool = True,
    ) -> "RobotBridge":
        """Start streaming. ``camera()`` returns the latest frame as JPEG/PNG bytes; ``on_action(action,
        payload)`` is called for each control message (e.g. ``("move", {"speed": 0.8})``). Blocks until
        interrupted unless ``block=False``."""
        self._camera = camera
        self._on_action = on_action
        self._fps = fps
        self._channel = channel
        self._ws = websocket.WebSocketApp(self._ws_url(), on_open=self._on_open, on_message=self._on_message)
        run = lambda: self._ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=3)
        if block:
            try:
                run()
            except KeyboardInterrupt:
                pass
            finally:
                self.close()
        else:
            threading.Thread(target=run, daemon=True).start()
        return self

    def stop(self) -> None:
        """Stop streaming (without releasing the robot's thread)."""
        self._stop.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def close(self) -> None:
        """Stop streaming and release the thread (the robot goes offline)."""
        self.stop()
        if self._client:
            self._client._stop(self.thread_id)
