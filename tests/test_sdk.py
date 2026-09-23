"""The Python SDK against a scripted /mcp — no network. Run: python -m unittest discover -s tests"""
import json
import unittest

from commandagi import SDK_SCHEMA, CommandAGI, CommandAGIError


class FakeResponse:
    def __init__(self, reply, is_error=False):
        self._body = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"isError": is_error, "content": [{"type": "text", "text": json.dumps(reply)}]},
        }
        self.status_code = 200

    def json(self):
        return self._body


class FakeHttp:
    """Records every tools/call and answers from `replies[tool]`."""

    def __init__(self, replies=None, error_tools=()):
        self.replies = replies or {}
        self.error_tools = set(error_tools)
        self.calls = []
        self.urls = []

    def post(self, url, headers=None, data=None, timeout=None):
        body = json.loads(data)
        tool = body["params"]["name"]
        self.urls.append((url, headers["authorization"]))
        self.calls.append((tool, body["params"]["arguments"]))
        return FakeResponse(self.replies.get(tool, {}), is_error=tool in self.error_tools)


def client(replies=None, error_tools=(), thread_id="th_self"):
    http = FakeHttp(replies, error_tools)
    return CommandAGI(api_key="cagi_test", base_url="https://api.example.com/", thread_id=thread_id, http=http), http


class ToolCalls(unittest.TestCase):
    def test_call_posts_json_rpc_to_mcp_with_the_bearer(self):
        cagi, http = client({"whoami": {"id": "u_1"}})
        self.assertEqual(cagi.whoami(), {"id": "u_1"})
        self.assertEqual(http.urls[0], ("https://api.example.com/mcp", "Bearer cagi_test"))

    def test_named_params_prefix_and_self_thread_default(self):
        cagi, http = client()
        cagi.threads.send("thr_1", "hello")
        cagi.threads.kill("thr_1")
        cagi.embodiments.act("emb_1", "click", {"x": 10, "y": 20})
        self.assertEqual(http.calls, [
            ("send_message", {"threadId": "thr_1", "text": "hello"}),
            ("kill_process", {"pid": "thread:thr_1"}),
            ("act", {"embodimentId": "emb_1", "action": "click", "payload": {"x": 10, "y": 20}, "threadId": "th_self"}),
        ])

    def test_options_arrive_snake_case_and_travel_camel_case(self):
        cagi, http = client()
        cagi.threads.create(intent="x", snapshot_id="simulation/warehouse", agentless=True)
        self.assertEqual(http.calls[0], ("create_thread", {"intent": "x", "snapshotId": "simulation/warehouse", "agentless": True}))

    def test_an_omitted_optional_never_travels_as_null(self):
        cagi, http = client(thread_id=None)
        cagi.threads.list()
        cagi.search("robots")
        self.assertEqual(http.calls, [("list_threads", {}), ("search_tools", {"query": "robots"})])

    def test_factory_namespace_binds_its_params(self):
        cagi, http = client()
        cagi.social("tiktok", "@brand").post("file_9", caption="hi")
        self.assertEqual(http.calls[0], ("post", {"integration": "tiktok", "account": "@brand", "fileId": "file_9", "caption": "hi"}))

    def test_a_tool_error_raises_naming_the_tool(self):
        cagi, _ = client(error_tools={"get_thread"})
        with self.assertRaises(CommandAGIError) as e:
            cagi.threads.get("thr_1")
        self.assertEqual(e.exception.tool, "get_thread")

    def test_every_schema_method_exists_on_the_client(self):
        cagi, _ = client()
        for m in SDK_SCHEMA["tools"]["root"]:
            self.assertTrue(callable(getattr(cagi, _snake(m["name"]))), m["name"])
        for ns in SDK_SCHEMA["tools"]["namespaces"]:
            owner = getattr(cagi, ns["name"])
            if ns["factory"]:
                owner = owner(*["x" for p in ns["factory"] if p["required"]])
            for m in ns["methods"]:
                self.assertTrue(callable(getattr(owner, _snake(m["name"]))), f"{ns['name']}.{m['name']}")


class Sessions(unittest.TestCase):
    def test_launch_creates_an_agentless_thread_and_binds_what_it_started(self):
        cagi, http = client({"create_thread": {"threadId": "th_world", "launched": {"status": "granted", "embodimentId": "emb_sim"}}})
        world = cagi.launch("simulation/warehouse", wait=False)
        self.assertEqual(http.calls[0], ("create_thread", {"agentless": True, "snapshotId": "simulation/warehouse", "title": "simulation/warehouse"}))
        self.assertEqual((world.thread_id, world.embodiment_id), ("th_world", "emb_sim"))

    def test_a_launch_that_starts_nothing_raises(self):
        cagi, _ = client({"create_thread": {"threadId": "th_world", "launched": None}})
        with self.assertRaises(CommandAGIError):
            cagi.launch("simulation/warehouse", wait=False)

    def test_vocabulary_methods_act_on_the_sessions_own_thread_and_embodiment(self):
        cagi, http = client()
        s = cagi.session("th_world", "emb_1")
        s.sim.ik(target=[0.3, 0.0, 0.4], robot_id="arm")
        s.desktop.click(x=10, y=20)
        s.sim.reset()
        self.assertEqual([c[1] for c in http.calls], [
            {"embodimentId": "emb_1", "action": "ik", "payload": {"robotId": "arm", "target": [0.3, 0.0, 0.4]}, "threadId": "th_world"},
            {"embodimentId": "emb_1", "action": "click", "payload": {"x": 10, "y": 20}, "threadId": "th_world"},
            {"embodimentId": "emb_1", "action": "reset", "payload": {}, "threadId": "th_world"},
        ])

    def test_stop_kills_only_a_world_the_session_launched(self):
        cagi, http = client({"create_thread": {"threadId": "th_world", "launched": {"embodimentId": "emb_sim"}}})
        cagi.session("th_other", "emb_x").stop()
        self.assertEqual(http.calls, [])
        with cagi.launch("simulation/warehouse", wait=False):
            pass
        self.assertEqual(http.calls[-1], ("kill_process", {"pid": "thread:th_world"}))


def _snake(name):
    import re

    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


if __name__ == "__main__":
    unittest.main()
