"""Autonomous multi-robot agent runner.

One agent, many robots. :class:`RobotAgent` drives a whole set of robot devices in a single thread
toward a natural-language goal: each step it gathers every device's world description and a fresh
camera frame, asks the platform's reasoning model (``POST /agent/robot-act``) what to do next, and
applies the returned tool calls back to the right device over the generic control vocabulary
(``ctrl`` / ``actuator`` / ``ik`` / ``trajectory``). It stops when the model emits a ``done`` call or
``max_steps`` is reached.

    from commandagi import CommandAGI
    from commandagi.agent import RobotAgent, attach_robots

    cagi = CommandAGI(api_key="cagi_…")
    sim = cagi.launch_sim(scene="warehouse")
    devices = attach_robots(cagi, sim, kinds=["rover", "arm"])   # two robots, one thread

    agent = RobotAgent(cagi, sim.thread_id, devices, goal="bring the red box to the arm")
    result = agent.run(max_steps=25)                              # blocks; prints each step
    print("done:", result["done"], "in", result["steps"], "steps")
    sim.stop()
"""
from __future__ import annotations

import base64
from typing import Optional

from .client import CommandAGI, World

# Maps a returned tool name to how its call is applied on a World. ``done`` is terminal (handled
# specially). Anything else is forwarded as a raw action, so the runner keeps working if the API
# grows the vocabulary.
_GENERIC_TOOLS = {"ctrl", "actuator", "ik", "trajectory", "describe"}


def attach_robots(client: CommandAGI, sim, kinds: list[str]) -> list[dict]:
    """Spawn several robots into one :class:`~commandagi.client.SimInstance` and return their devices.

    Returns a list of ``{deviceId, robotId, kind}`` — one per requested kind — all on
    ``sim.thread_id``. This is the convenience wrapper for building a multi-robot thread to hand to
    :class:`RobotAgent`.
    """
    devices: list[dict] = []
    for kind in kinds:
        info = sim.join_robot(kind=kind)
        devices.append({"deviceId": info["deviceId"], "robotId": info.get("robotId", ""), "kind": kind})
    return devices


def _frame_data_url(frame: bytes) -> str:
    mime = "image/png" if frame[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(frame).decode()


class RobotAgent:
    """An autonomous runner that drives many robot devices in one thread toward ``goal``.

    Parameters
    ----------
    client:
        A :class:`~commandagi.client.CommandAGI` client.
    thread_id:
        The thread the robot devices live on (e.g. ``sim.thread_id``).
    devices:
        A list of ``{deviceId, robotId?, kind?}`` describing the robots to drive (e.g. the output of
        :func:`attach_robots`).
    goal:
        The natural-language objective handed to ``/agent/robot-act`` each step.
    model:
        Optional model id override for the reasoning call.
    """

    def __init__(self, client: CommandAGI, thread_id: str, devices: list[dict], goal: str,
                 *, model: Optional[str] = None):
        self.client = client
        self.thread_id = thread_id
        self.goal = goal
        self.model = model
        self._device_meta = {d["deviceId"]: d for d in devices}
        # One control channel per device, all on the same thread. The agent addresses robots by
        # deviceId; a single World per device carries its observe()/describe()/control.
        self.worlds: dict[str, World] = {
            d["deviceId"]: client.connect_world(thread_id, d["deviceId"], kind="robot")
            for d in devices
        }
        self.history: list[dict] = []

    # ── per-step pieces ────────────────────────────────────────────────────────
    def _gather(self) -> list[dict]:
        """Collect ``{deviceId, world, camera}`` for every device (description + a fresh frame)."""
        payload: list[dict] = []
        for device_id, world in self.worlds.items():
            try:
                description = world.describe(robot_id=self._device_meta[device_id].get("robotId", ""))
            except Exception:
                description = {}
            try:
                camera = _frame_data_url(world.observe(timeout=15.0))
            except Exception:
                camera = None
            payload.append({"deviceId": device_id, "world": description, "camera": camera})
        return payload

    def _apply(self, call: dict) -> None:
        """Apply one returned tool call to the addressed device's :class:`World`."""
        tool = call.get("tool")
        device_id = call.get("deviceId")
        robot_id = call.get("robotId", "")
        world = self.worlds.get(device_id)
        if world is None or tool in (None, "done"):
            return
        if tool == "ctrl":
            world.ctrl(call.get("targets", {}), robot_id=robot_id)
        elif tool == "actuator":
            world.actuator(call.get("name", ""), call.get("value", 0.0), robot_id=robot_id)
        elif tool == "ik":
            world.ik(call.get("target", []), site=call.get("site"),
                     relative=bool(call.get("relative", False)), robot_id=robot_id)
        elif tool == "trajectory":
            world.trajectory(call.get("waypoints", []), robot_id=robot_id)
        elif tool == "describe":
            world.describe(robot_id=robot_id)
        else:
            # Unknown/extended tool: forward generically with whatever fields came back.
            extra = {k: v for k, v in call.items() if k not in ("tool", "deviceId", "robotId")}
            world.act(tool, robotId=robot_id, **extra)

    # ── main loop ──────────────────────────────────────────────────────────────
    def step(self) -> dict:
        """Run a single perceive→reason→act cycle. Returns ``{reasoning, calls, done}``."""
        devices = self._gather()
        res = self.client.robot_act(self.goal, devices, model=self.model, history=self.history or None)
        reasoning = res.get("reasoning", "")
        calls = res.get("calls", []) or []
        done = any(c.get("tool") == "done" for c in calls)
        for call in calls:
            self._apply(call)
        self.history.append({"reasoning": reasoning, "calls": calls})
        return {"reasoning": reasoning, "calls": calls, "done": done}

    def run(self, max_steps: int = 50, *, verbose: bool = True) -> dict:
        """Loop :meth:`step` until a ``done`` call or ``max_steps``.

        Returns ``{done, steps, history}``. With ``verbose`` (default), prints the reasoning and the
        applied calls each step.
        """
        steps = 0
        done = False
        for i in range(max_steps):
            out = self.step()
            steps = i + 1
            if verbose:
                print(f"[step {steps}] {out['reasoning']}")
                for call in out["calls"]:
                    print(f"    → {call.get('tool')} on {call.get('deviceId')} {call.get('robotId', '')}".rstrip())
            if out["done"]:
                done = True
                break
        return {"done": done, "steps": steps, "history": self.history}

    def close(self) -> None:
        """Close every device control channel (does not stop the thread). Safe to call twice."""
        for world in self.worlds.values():
            try:
                world._ws.close()
            except Exception:
                pass

    def __enter__(self) -> "RobotAgent":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
