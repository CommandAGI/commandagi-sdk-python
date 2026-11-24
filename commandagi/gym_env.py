"""A Gymnasium environment over a CommandAGI sim — drive a robot in a hosted 3D physics world with the
standard ``reset`` / ``step`` RL loop.

The action space is the robot's joint targets (a ``Box`` over each joint's range, read from
:meth:`Session.describe`: a target out of range is refused, never clamped); the observation is the
simulation's camera image plus proprioception (joint positions and velocities). Rewards are
user-supplied (a callback over the description), since "reward" is task-specific — the env gives you the
physics and the observations, and you decide the objective.

    from commandagi import CommandAGI
    from commandagi.gym_env import CommandAGIEnv

    cagi = CommandAGI()                              # reads COMMANDAGI_API_KEY
    with cagi.launch("simulation/arm-cell") as world:
        env = CommandAGIEnv(world, reward_fn=lambda d: 0.0, max_steps=20)
        obs, info = env.reset()
        print(obs["image"].shape)                    # (240, 320, 3): the arm cell's camera
        for _ in range(20):
            obs, reward, terminated, truncated, info = env.step(env.action_space.sample())

Requires ``gymnasium`` and ``numpy`` (``pip install "commandagi[gym]"``). Designed to pair with
:mod:`commandagi.lerobot` to record demonstrations/rollouts as LeRobot-3.0 datasets.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

try:
    import gymnasium as gym
    import numpy as np
    from gymnasium import spaces
except ImportError as e:  # pragma: no cover
    raise ImportError("commandagi.gym_env needs `gymnasium` and `numpy` — pip install 'commandagi[gym]'") from e

from .client import CommandAGIError, Session


def _world(desc: dict) -> dict:
    """The world of a describe answer (``{threadId, embodimentId, world}``), or the answer itself."""
    return desc.get("world") if isinstance(desc.get("world"), dict) else desc


def _robot(desc: dict, robot_id: str) -> Optional[dict]:
    """The target robot (or the first robot) of a describe answer."""
    robots = _world(desc).get("robots") or []
    if robot_id:
        return next((r for r in robots if r.get("id") == robot_id), None)
    return robots[0] if robots else None


def _bound(v: Any, fallback: float) -> float:
    return fallback if v is None else float(v)


class CommandAGIEnv(gym.Env):
    """Gymnasium env wrapping a live sim :class:`Session`. One robot, morphology-agnostic.

    Args:
        world: a live sim Session (from ``CommandAGI.launch`` or ``CommandAGI.session``).
        robot_id: which robot to drive (default: the world's only/first robot).
        reward_fn: ``description -> float`` reward; defaults to constant 0.
        terminated_fn / truncated_fn: ``description -> bool`` episode-end predicates.
        control_dt: seconds the running simulation advances between a step's command and its observation.
        image_obs: include the camera's picture in the observation dict (needs Pillow).
        camera: the camera channel the picture is read from (a simulation's first camera is ``cam-head``).
        max_steps: auto-truncate after this many steps (None = unbounded).
    """

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(
        self,
        world: Session,
        *,
        robot_id: str = "",
        reward_fn: Optional[Callable[[dict], float]] = None,
        terminated_fn: Optional[Callable[[dict], bool]] = None,
        truncated_fn: Optional[Callable[[dict], bool]] = None,
        control_dt: float = 0.1,
        image_obs: bool = True,
        camera: str = "cam-head",
        max_steps: Optional[int] = None,
    ):
        super().__init__()
        self.world = world
        self.reward_fn = reward_fn or (lambda _d: 0.0)
        self.terminated_fn = terminated_fn or (lambda _d: False)
        self.truncated_fn = truncated_fn or (lambda _d: False)
        self.control_dt = control_dt
        self.image_obs = image_obs
        self.camera = camera
        self.max_steps = max_steps
        self._steps = 0

        robot = _robot(world.describe(), robot_id)
        if not robot or not robot.get("joints"):
            raise CommandAGIError("describe", f"no robot{f' {robot_id}' if robot_id else ''} with joints in this world — is it a robot sim, and is it live yet?")
        self.robot_id = robot["id"]
        self._joints = list(robot["joints"].keys())
        ranges = robot.get("ranges") or {}
        lo = np.asarray([_bound((ranges.get(j) or [None, None])[0], -np.pi) for j in self._joints], dtype=np.float32)
        hi = np.asarray([_bound((ranges.get(j) or [None, None])[1], np.pi) for j in self._joints], dtype=np.float32)
        self.action_space = spaces.Box(low=lo, high=hi, dtype=np.float32)

        n = len(self._joints)
        obs_spaces: dict[str, spaces.Space] = {
            "qpos": spaces.Box(-np.inf, np.inf, shape=(n,), dtype=np.float32),
            "qvel": spaces.Box(-np.inf, np.inf, shape=(n,), dtype=np.float32),
        }
        if image_obs:
            img = world.observe_array(channel=camera, timeout=60)
            obs_spaces["image"] = spaces.Box(0, 255, shape=img.shape, dtype=np.uint8)
        self.observation_space = spaces.Dict(obs_spaces)

    def _obs(self, desc: dict, fresh: bool) -> dict:
        robot = _robot(desc, self.robot_id) or {}
        joints, velocities = robot.get("joints") or {}, robot.get("velocities") or {}
        obs: dict[str, Any] = {
            "qpos": np.asarray([joints.get(j, 0.0) for j in self._joints], dtype=np.float32),
            "qvel": np.asarray([velocities.get(j, 0.0) for j in self._joints], dtype=np.float32),
        }
        if self.image_obs:
            obs["image"] = self.world.observe_array(channel=self.camera, fresh=fresh)
        return obs

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.world.sim.reset()
        self.world.sim.run()
        self._steps = 0
        desc = self.world.describe()
        return self._obs(desc, fresh=True), {"description": desc}

    def step(self, action):
        targets = {name: float(v) for name, v in zip(self._joints, np.asarray(action).reshape(-1))}
        self.world.sim.ctrl(targets=targets, robot_id=self.robot_id)
        time.sleep(self.control_dt)
        desc = self.world.describe()
        # The picture is one taken after the command: a camera of the simulation draws a few times a second.
        obs = self._obs(desc, fresh=True)
        reward = float(self.reward_fn(desc))
        terminated = bool(self.terminated_fn(desc))
        self._steps += 1
        truncated = bool(self.truncated_fn(desc)) or (self.max_steps is not None and self._steps >= self.max_steps)
        return obs, reward, terminated, truncated, {"description": desc, "joints": self._joints}

    def render(self):
        return self.world.observe_array(channel=self.camera) if self.image_obs else None

    def close(self):
        self.world.close()
