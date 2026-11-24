"""A session's frames by channel, and the Gymnasium environment over a simulation — no network.

The thread's socket is spoken for (`Session._take` is what its socket calls with each message). The environment
runs over a session whose tool calls are scripted with what a simulation on a thread answers: `describe` (its robots'
joints, speeds and ranges) and a camera picture of 320 x 240 on `cam-head`.
Run: python -m unittest discover -s tests"""
import base64
import io
import json
import threading
import time
import unittest

from commandagi import CommandAGI, CommandAGIError


def jpeg(colour=(200, 100, 50), size=(320, 240)):
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, "JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


def depth_png(mm=760, size=(320, 240)):
    import numpy as np
    from PIL import Image

    out = io.BytesIO()
    Image.fromarray(np.full((size[1], size[0]), mm, dtype=np.uint16)).save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


class Http:
    """Answers each tools/call from `replies[tool]` (a callable of the arguments), and records it."""

    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def post(self, url, headers=None, data=None, timeout=None):
        body = json.loads(data)
        name, args = body["params"]["name"], body["params"]["arguments"]
        self.calls.append((name, args))
        reply = self.replies.get(name, lambda a: {})(args)

        class R:
            status_code = 200

            def json(self):
                return {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": json.dumps(reply)}]}}

        return R()


def session(replies=None):
    http = Http(replies or {})
    s = CommandAGI(api_key="cagi_test", base_url="https://api.example.com", http=http).session("th_world", "emb_sim")
    s._open = lambda: None  # the socket is the test's: `_take` is what it would call
    return s, http


def say(s, **m):
    s._take(json.dumps({"embodimentId": "emb_sim", **m}))


class Frames(unittest.TestCase):
    def setUp(self):
        try:
            import numpy  # noqa: F401
            import PIL  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("pillow and numpy are not installed (pip install 'commandagi[vision]')")

    def test_each_channel_keeps_its_newest_and_a_plain_frame_is_a_picture(self):
        s, _ = session()
        say(s, t="data", channelId="depth", kind="depth", format="image/png", url=depth_png(), at=1)
        say(s, t="frame", channelId="cam-head", url=jpeg(), at=2, embodimentId="emb_other")
        with self.assertRaises(CommandAGIError):
            s.frame(timeout=0.05)  # a depth image is no picture, and another embodiment's frame is not this one's
        say(s, t="frame", channelId="cam-head", url=jpeg(), at=3)
        say(s, t="frame", channelId="top", url=jpeg((0, 0, 255)), at=4)
        self.assertEqual(s.frame()["channel_id"], "top")
        self.assertEqual(s.frame(channel="cam-head")["at"], 3)
        self.assertEqual(s.observe_array(channel="cam-head").shape, (240, 320, 3))
        d = s.depth_array()
        self.assertEqual((d.shape, str(d.dtype), int(d[120, 160])), ((240, 320), "uint16", 760))

    def test_fresh_waits_for_the_next_frame_of_its_channel(self):
        s, _ = session()
        say(s, t="frame", channelId="cam-head", url=jpeg(), at=1)
        threading.Timer(0.1, lambda: say(s, t="frame", channelId="top", url=jpeg(), at=2)).start()
        threading.Timer(0.2, lambda: say(s, t="frame", channelId="cam-head", url=jpeg(), at=3)).start()
        self.assertEqual(s.frame(fresh=True, channel="cam-head", timeout=2)["at"], 3)
        with self.assertRaisesRegex(CommandAGIError, "no frame from emb_sim on cam-head within 0.05s"):
            s.frame(fresh=True, channel="cam-head", timeout=0.05)


class Gym(unittest.TestCase):
    """The environment's spaces come from what the simulation says; each step's picture is one after its command."""

    def setUp(self):
        try:
            import gymnasium  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("gymnasium is not installed (pip install 'commandagi[gym]')")
        self.q = {"shoulder_pan": 0.0, "gripper": 1.0}

        def describe(_a):
            return {"threadId": "th_world", "world": {"robots": [{"id": "arm", "joints": dict(self.q), "velocities": {"shoulder_pan": 0.5, "gripper": 0.0}, "ranges": {"shoulder_pan": [-1.9, 1.9], "gripper": [-0.17, 1.75]}}]}}

        def act(a):
            if a["action"] == "ctrl":
                self.q.update(a["payload"]["targets"])
                # The camera draws the moved arm a moment later.
                threading.Timer(0.02, lambda: say(self.s, t="frame", channelId="cam-head", url=jpeg((10, 10, 10)), at=int(time.time() * 1000))).start()
            if a["action"] == "reset":
                threading.Timer(0.02, lambda: say(self.s, t="frame", channelId="cam-head", url=jpeg(), at=int(time.time() * 1000))).start()
            return {"ok": True}

        self.s, self.http = session({"describe_world": describe, "act": act})
        say(self.s, t="frame", channelId="cam-head", url=jpeg(), at=1)
        say(self.s, t="data", channelId="depth", format="image/png", url=depth_png(), at=1)

    def test_reset_and_step_give_observations_in_their_spaces(self):
        from commandagi.gym_env import CommandAGIEnv

        env = CommandAGIEnv(self.s, max_steps=2, control_dt=0.01)
        self.assertEqual(env.action_space.shape, (2,))
        self.assertEqual([round(float(x), 2) for x in env.action_space.low], [-1.9, -0.17])
        obs, info = env.reset()
        self.assertEqual(obs["image"].shape, (240, 320, 3))
        self.assertTrue(env.observation_space.contains(obs))
        obs, reward, terminated, truncated, info = env.step([0.3, 0.5])
        self.assertEqual([round(float(x), 2) for x in obs["qpos"]], [0.3, 0.5])
        self.assertLess(int(obs["image"].mean()), 40, "the picture is the one taken after the command")
        self.assertEqual((reward, terminated, truncated), (0.0, False, False))
        *_, truncated, _ = env.step(env.action_space.sample())
        self.assertTrue(truncated)
        names = [c[1].get("action") for c in self.http.calls if c[1].get("action")]
        self.assertEqual(names[:2], ["reset", "run"], "a reset starts the simulation again and runs it")
        ctrl = next(c[1] for c in self.http.calls if c[1].get("action") == "ctrl")
        self.assertEqual(ctrl["payload"], {"robotId": "arm", "targets": {"shoulder_pan": 0.3, "gripper": 0.5}})


if __name__ == "__main__":
    unittest.main()
