"""A Gymnasium environment over a CommandAGI sim — drive a robot in a hosted 3D physics world with the
standard ``reset`` / ``step`` RL loop.

The action space is the robot's actuators (a ``Box`` over each actuator's ctrlrange, read from
:meth:`Session.describe`); the observation is the head-camera image plus proprioception (joint
positions/velocities). Rewards are user-supplied (a callback over the description), since "reward" is
task-specific — the env gives you the faithful physics + observations and you decide the objective.

    from commandagi import CommandAGI
    from commandagi.gym_env import CommandAGIEnv

    cagi = CommandAGI()                              # reads COMMANDAGI_API_KEY
    with cagi.launch("simulation/warehouse") as world:
        env = CommandAGIEnv(world, reward_fn=lambda d: 0.0)
        obs, info = env.reset()
        for _ in range(100):
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


def _actuators(desc: dict, robot_id: str) -> list[dict]:
    """Flatten the actuators of the target robot (or the first robot) from a describe payload."""
    robots = desc.get("robots") or []
    if not robots:
        return []
    robot = next((r for r in robots if r.get("id") == robot_id), robots[0]) if robot_id else robots[0]
    return list(robot.get("actuators") or [])


def _joint_state(desc: dict, robot_id: str) -> tuple[np.ndarray, np.ndarray]:
    """(qpos, qvel) vectors over the target robot's joints, in describe() order."""
    robots = desc.get("robots") or []
    robot = next((r for r in robots if r.get("id") == robot_id), robots[0] if robots else {}) if robot_id else (robots[0] if robots else {})
    qpos, qvel = [], []
    for j in robot.get("joints") or []:
        p, v = j.get("pos", 0.0), j.get("vel", 0.0)
        qpos.extend(p if isinstance(p, list) else [p])
        qvel.extend(v if isinstance(v, list) else [v])
    return np.asarray(qpos, dtype=np.float32), np.asarray(qvel, dtype=np.float32)


class CommandAGIEnv(gym.Env):
    """Gymnasium env wrapping a live sim :class:`Session`. One robot, morphology-agnostic.

    Args:
        world: a live sim Session (from ``CommandAGI.launch`` or ``CommandAGI.session``).
        robot_id: which robot to drive (default: the world's only/first robot).
        reward_fn: ``description -> float`` reward; defaults to constant 0.
        terminated_fn / truncated_fn: ``description -> bool`` episode-end predicates.
        control_dt: seconds to let physics advance per step (the sim runs ~250 Hz server-side).
        image_obs: include the camera frame in the observation dict (needs Pillow).
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
        max_steps: Optional[int] = None,
    ):
        super().__init__()
        self.world = world
        self.robot_id = robot_id
        self.reward_fn = reward_fn or (lambda _d: 0.0)
        self.terminated_fn = terminated_fn or (lambda _d: False)
        self.truncated_fn = truncated_fn or (lambda _d: False)
        self.control_dt = control_dt
        self.image_obs = image_obs
        self.max_steps = max_steps
        self._steps = 0

        desc = world.describe()
        acts = _actuators(desc, robot_id)
        if not acts:
            raise CommandAGIError("no actuators found — is this a robot sim and is it live yet?")
        self._act_names = [a["name"] for a in acts]
        lo = np.asarray([a.get("ctrlrange", [-1, 1])[0] for a in acts], dtype=np.float32)
        hi = np.asarray([a.get("ctrlrange", [-1, 1])[1] for a in acts], dtype=np.float32)
        self.action_space = spaces.Box(low=lo, high=hi, dtype=np.float32)

        qpos, qvel = _joint_state(desc, robot_id)
        obs_spaces: dict[str, spaces.Space] = {
            "qpos": spaces.Box(-np.inf, np.inf, shape=qpos.shape, dtype=np.float32),
            "qvel": spaces.Box(-np.inf, np.inf, shape=qvel.shape, dtype=np.float32),
        }
        if image_obs:
            img = world.observe_array()
            obs_spaces["image"] = spaces.Box(0, 255, shape=img.shape, dtype=np.uint8)
        self.observation_space = spaces.Dict(obs_spaces)

    def _obs(self, desc: dict) -> dict:
        qpos, qvel = _joint_state(desc, self.robot_id)
        obs: dict[str, Any] = {"qpos": qpos, "qvel": qvel}
        if self.image_obs:
            obs["image"] = self.world.observe_array()
        return obs

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.world.sim.reset()
        self._steps = 0
        desc = self.world.describe()
        return self._obs(desc), {"description": desc}

    def step(self, action):
        targets = {name: float(v) for name, v in zip(self._act_names, np.asarray(action).reshape(-1))}
        self.world.sim.ctrl(targets=targets, robot_id=self.robot_id or None)
        time.sleep(self.control_dt)
        desc = self.world.describe()
        obs = self._obs(desc)
        reward = float(self.reward_fn(desc))
        terminated = bool(self.terminated_fn(desc))
        self._steps += 1
        truncated = bool(self.truncated_fn(desc)) or (self.max_steps is not None and self._steps >= self.max_steps)
        return obs, reward, terminated, truncated, {"description": desc, "actuators": self._act_names}

    def render(self):
        return self.world.observe_array() if self.image_obs else None

    def close(self):
        self.world.close()
