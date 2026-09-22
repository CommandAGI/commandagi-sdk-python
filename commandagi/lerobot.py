"""Record CommandAGI sim episodes as a LeRobot-style dataset — observation (camera + joint state),
action, and timestamps per step, written to disk in the LeRobot on-disk layout (parquet per episode
+ frames + meta/info.json) so it loads into imitation/VLA training pipelines.

Two ways to use it:

1. Wrap a Gym env — every ``step`` is recorded automatically::

       from commandagi.gym_env import CommandAGIEnv
       from commandagi.lerobot import RecordingWrapper
       env = RecordingWrapper(CommandAGIEnv(world), root="./datasets/pick", task="pick up the cube")
       obs, _ = env.reset()
       for _ in range(200):
           obs, *_ = env.step(policy(obs))
       env.save()            # flush the dataset to ./datasets/pick

2. Hand-drive and log directly with :class:`EpisodeRecorder` (e.g. while teleoperating in Sim Studio).

This writes the LeRobot v2.1/3.0 directory shape (``meta/info.json``, ``data/chunk-000/episode_*.parquet``,
``images/observation.image/episode_*/frame_*.jpg``). Requires ``pyarrow`` + ``numpy`` + ``pillow``
(``pip install "commandagi[lerobot]"``). Stats consolidation (``meta/stats.json``) is left to the
``lerobot`` tooling; everything needed to compute it is on disk.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from typing import Any, Optional

try:
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from PIL import Image
except ImportError as e:  # pragma: no cover
    raise ImportError("commandagi.lerobot needs `pyarrow`, `numpy`, `pillow` — pip install 'commandagi[lerobot]'") from e

CODEBASE_VERSION = "v2.1"


class EpisodeRecorder:
    """Accumulates steps for one or more episodes and writes a LeRobot-layout dataset.

    Each step is ``(state, action, image)`` where ``state``/``action`` are 1-D float arrays and
    ``image`` is an HxWx3 uint8 array (optional). Call :meth:`add` per step, :meth:`end_episode` to
    close the current episode, and :meth:`save` to write everything out.
    """

    def __init__(self, root: str, *, fps: float = 10.0, task: str = "", image_key: str = "observation.image"):
        self.root = Path(root)
        self.fps = float(fps)
        self.task = task
        self.image_key = image_key
        self._ep: list[dict[str, Any]] = []  # steps in the current episode
        self._episodes: list[list[dict[str, Any]]] = []  # completed episodes
        self._state_dim: Optional[int] = None
        self._action_dim: Optional[int] = None
        self._img_shape: Optional[tuple[int, int, int]] = None
        self._t0 = time.time()

    def start_episode(self) -> None:
        if self._ep:
            self.end_episode()
        self._ep = []
        self._t0 = time.time()

    def add(self, state, action, image=None, *, reward: float = 0.0) -> None:
        state = np.asarray(state, dtype=np.float32).reshape(-1)
        action = np.asarray(action, dtype=np.float32).reshape(-1)
        self._state_dim = self._state_dim or state.shape[0]
        self._action_dim = self._action_dim or action.shape[0]
        step: dict[str, Any] = {
            "observation.state": state,
            "action": action,
            "timestamp": time.time() - self._t0,
            "reward": float(reward),
        }
        if image is not None:
            img = np.asarray(image, dtype=np.uint8)
            self._img_shape = self._img_shape or tuple(img.shape)  # type: ignore[assignment]
            step["_image"] = img
        self._ep.append(step)

    def end_episode(self) -> None:
        if self._ep:
            self._episodes.append(self._ep)
            self._ep = []

    def save(self) -> Path:
        """Write the dataset (all completed episodes + the current one) to disk; returns the root."""
        self.end_episode()
        if not self._episodes:
            raise ValueError("nothing to save — record at least one step")
        (self.root / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
        (self.root / "meta").mkdir(parents=True, exist_ok=True)

        total_frames = 0
        global_index = 0
        for ep_idx, steps in enumerate(self._episodes):
            cols: dict[str, list] = {
                "observation.state": [], "action": [], "timestamp": [], "reward": [],
                "frame_index": [], "episode_index": [], "index": [], "next.done": [],
            }
            has_image = any("_image" in s for s in steps)
            if has_image:
                cols[self.image_key] = []
                img_dir = self.root / "images" / self.image_key / f"episode_{ep_idx:06d}"
                img_dir.mkdir(parents=True, exist_ok=True)
            for f_idx, s in enumerate(steps):
                cols["observation.state"].append(s["observation.state"].tolist())
                cols["action"].append(s["action"].tolist())
                cols["timestamp"].append(float(s["timestamp"]))
                cols["reward"].append(float(s["reward"]))
                cols["frame_index"].append(f_idx)
                cols["episode_index"].append(ep_idx)
                cols["index"].append(global_index)
                cols["next.done"].append(f_idx == len(steps) - 1)
                if has_image:
                    rel = f"images/{self.image_key}/episode_{ep_idx:06d}/frame_{f_idx:06d}.jpg"
                    if "_image" in s:
                        Image.fromarray(s["_image"]).save(self.root / rel, format="JPEG", quality=90)
                    cols[self.image_key].append(rel)
                global_index += 1
            total_frames += len(steps)
            pq.write_table(pa.table(cols), self.root / "data" / "chunk-000" / f"episode_{ep_idx:06d}.parquet")

        self._write_info(total_frames)
        self._write_episodes_meta()
        self._write_tasks_meta()
        return self.root

    def _features(self) -> dict:
        feats: dict[str, Any] = {
            "observation.state": {"dtype": "float32", "shape": [self._state_dim or 0], "names": None},
            "action": {"dtype": "float32", "shape": [self._action_dim or 0], "names": None},
            "timestamp": {"dtype": "float32", "shape": [1], "names": None},
            "reward": {"dtype": "float32", "shape": [1], "names": None},
            "frame_index": {"dtype": "int64", "shape": [1], "names": None},
            "episode_index": {"dtype": "int64", "shape": [1], "names": None},
            "index": {"dtype": "int64", "shape": [1], "names": None},
            "next.done": {"dtype": "bool", "shape": [1], "names": None},
        }
        if self._img_shape is not None:
            feats[self.image_key] = {"dtype": "image", "shape": list(self._img_shape), "names": ["height", "width", "channel"]}
        return feats

    def _write_info(self, total_frames: int) -> None:
        info = {
            "codebase_version": CODEBASE_VERSION,
            "robot_type": "commandagi-sim",
            "total_episodes": len(self._episodes),
            "total_frames": total_frames,
            "total_tasks": 1,
            "total_chunks": 1,
            "chunks_size": 1000,
            "fps": self.fps,
            "splits": {"train": f"0:{len(self._episodes)}"},
            "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
            "features": self._features(),
        }
        (self.root / "meta" / "info.json").write_text(json.dumps(info, indent=2))

    def _write_episodes_meta(self) -> None:
        lines = []
        for ep_idx, steps in enumerate(self._episodes):
            lines.append(json.dumps({"episode_index": ep_idx, "tasks": [self.task] if self.task else [], "length": len(steps)}))
        (self.root / "meta" / "episodes.jsonl").write_text("\n".join(lines) + "\n")

    def _write_tasks_meta(self) -> None:
        (self.root / "meta" / "tasks.jsonl").write_text(json.dumps({"task_index": 0, "task": self.task}) + "\n")


class RecordingWrapper:
    """Wrap a :class:`commandagi.gym_env.CommandAGIEnv` so every ``reset``/``step`` is logged.

    The observation's ``qpos``+``qvel`` become ``observation.state``; ``image`` (if present) is the
    camera frame; the action passed to ``step`` is recorded verbatim. Call :meth:`save` when done.
    """

    def __init__(self, env, root: str, *, task: str = "", fps: Optional[float] = None):
        self.env = env
        self.recorder = EpisodeRecorder(root, fps=fps or (1.0 / getattr(env, "control_dt", 0.1)), task=task)
        self.action_space = env.action_space
        self.observation_space = env.observation_space

    @staticmethod
    def _state(obs: dict) -> np.ndarray:
        return np.concatenate([np.asarray(obs.get("qpos", []), dtype=np.float32), np.asarray(obs.get("qvel", []), dtype=np.float32)])

    def reset(self, **kw):
        obs, info = self.env.reset(**kw)
        self.recorder.start_episode()
        self._last_obs = obs
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        # Record the transition: the observation we acted on + the action + the reward received.
        self.recorder.add(self._state(self._last_obs), action, self._last_obs.get("image"), reward=reward)
        self._last_obs = obs
        if terminated or truncated:
            self.recorder.end_episode()
        return obs, reward, terminated, truncated, info

    def save(self):
        return self.recorder.save()

    def close(self):
        self.env.close()
