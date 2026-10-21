"""Where a Kernel runs, with whose credential, and what it records of where it ran. The calls themselves are checked
against the real service, from the built package (the CommandAGI repository's scripts/release/sdk-check.mjs)."""
import base64
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from commandagi.design.threed import box, part
from commandagi.kernel import Kernel, KernelError, _Local, call_kernel, kernel_places, linked_parts, where_of

FAILED = {"error": "build_failed", "status": "failed", "reason": "the build failed in 1 feature, so its geometry is not whole: cbore, a hole: hole face not found",
          "failures": [{"feature": "cbore", "type": "hole", "message": "hole face not found"}]}


def serve(answer):
    """A fake kernel: `answer(path, auth, body)` → (status, body). Returns (server, url, seen)."""
    seen = []
    agents = []

    class Handler(BaseHTTPRequestHandler):
        def reply(self, body):
            seen.append((self.path, self.headers["authorization"], body))
            agents.append(self.headers["user-agent"])
            status, out = answer(self.path, self.headers["authorization"], body)
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(out).encode())

        def do_POST(self):
            self.reply(json.loads(self.rfile.read(int(self.headers["content-length"]))))

        def do_GET(self):
            self.reply(None)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.agents = agents
    return server, f"http://127.0.0.1:{server.server_port}", seen


def doc_of(body):
    data = base64.b64decode(body["inputs"]["doc"]["bytes"])
    assert hashlib.sha256(data).hexdigest() == body["inputs"]["doc"]["id"]
    return data.decode()


class Places(unittest.TestCase):
    def test_one_setting_chooses_the_places(self):
        self.assertEqual(where_of(None, {}), (["page", "local", "cloud"], None))
        self.assertEqual(where_of(None, {"COMMANDAGI_THREED": "cloud"}), (["cloud"], None))
        self.assertEqual(where_of(None, {"COMMANDAGI_THREED": "cloud, local", "COMMANDAGI_THREED_URL": "http://127.0.0.1:8091/"}), (["cloud", "local"], "http://127.0.0.1:8091"))
        self.assertEqual(where_of("http://127.0.0.1:8091/", {"COMMANDAGI_THREED": "cloud"}), (["local"], "http://127.0.0.1:8091"))
        for bad in ("platform", "local,local", "moon"):
            with self.assertRaisesRegex(ValueError, '"page", "local" and "cloud"'):
                where_of(None, {"COMMANDAGI_THREED": bad})
        self.assertEqual(kernel_places("3d", ["cloud"]), ["cloud"])

    def test_the_rule_of_placement(self):
        def answers(status, body):
            return lambda path, request: (status, body)

        # A place that is not here, then one that has no such op, then the answer: placed where it was sent.
        status, body = call_kernel("3d", "measure", ["local", "cloud"], {"local": None, "cloud": answers(200, {"result": 1, "ran": {"build": "b1", "place": "local"}})}, {"doc": "{}"})
        self.assertEqual((status, body["ran"]), (200, {"kernel": "3d", "build": "b1", "place": "cloud"}))
        status, body = call_kernel("3d", "x", ["local", "cloud"], {"local": answers(404, {"error": "no_such_op"}), "cloud": answers(503, {"error": "kernel_unavailable", "reason": "off"})}, {"doc": "{}"})
        self.assertEqual((status, body["error"]), (503, "kernel_unavailable"))
        self.assertIn('local: no op "x"; cloud: off', body["reason"])
        # A refusal of the op is the answer: it is not asked elsewhere.
        asked = []
        status, body = call_kernel("3d", "export", ["local", "cloud"], {"local": answers(422, FAILED), "cloud": lambda p, r: asked.append(p) or (200, {})}, {"doc": "{}"})
        self.assertEqual((status, body["error"], body["ran"]["place"], asked), (422, "build_failed", "local", []))


class Placed(unittest.TestCase):
    def tearDown(self):
        _Local.installed = None

    def test_a_running_service_gets_its_own_bearer_and_the_contract(self):
        def answer(path, auth, body):
            return {"/v1/export": (200, {"outputs": {}, "result": {"content": "ISO-10303-21;"}, "ran": {"kernel": "3d", "build": "sha256:abc", "place": "cloud"}}),
                    "/v1/measure": (422, {"error": "measures[0]: no such body"}),
                    "/v1/interference": (200, {"result": {"clashes": [], "engagements": [], "close": [], "pairs": 1}}),
                    "/v1/tessellate": (422, FAILED),
                    "/v1/sheet": (200, {"result": {"sheet": "sheet1", "format": "pdf", "contentBase64": "JVBERg=="}}),
                    "/v1/bom": (200, {"result": {"lines": [], "csv": "item\n"}}),
                    "/v1/observe": (200, {"result": {"observation": {"bodies": [], "errors": {}}, "meshes": [], "meshTris": 0}}),
                    "/v1/health": (200, {"kernel": "3d", "build": "sha256:abc"}),
                    "/v1/check": (200, {"result": {"declared": True, "checks": [{"id": "clash", "kind": "interference", "status": "passed"}], "findings": [], "problems": 0}}),
                    "/v1/dfm": (200, {"result": {"process": "mill", "part": "plate", "verdict": "fail", "findings": [
                        {"check": "mill.depth", "status": "fail", "value": 3.78, "limit": 3, "unit": "xD", "where": [{"body": "body_0", "faces": [4], "at": [0, 0, 3]}], "message": "too deep"}]}})}[path]

        server, url, seen = serve(answer)
        try:
            env = {"COMMANDAGI_API_KEY": "cagi_account", "COMMANDAGI_THREED_URL": url, "COMMANDAGI_THREED_TOKEN": "service-bearer"}
            with mock.patch.dict(os.environ, env, clear=True):
                kernel = Kernel()
                plate = part(box(id="plate", center=[0, 0, 4], size=[60, 40, 8], operation="new"), name="Plate")
                self.assertEqual(kernel.export(plate, "step", bodies=["body_0"]), "ISO-10303-21;")
                # The service said "cloud"; it ran here, and that is what is recorded.
                self.assertEqual(kernel.last_ran, {"kernel": "3d", "build": "sha256:abc", "place": "local"})
                with self.assertRaises(KernelError) as refused:
                    kernel.measure("{}", "radius", {"body": "body_9", "kind": "edge", "index": 0})
                bolt = part(box(id="bolt", size=[3, 3, 10], operation="new"), name="Bolt")
                self.assertEqual(kernel.interference(plate, clearance=0.5, parts=linked_parts({"bolt.3d.py": bolt}))["pairs"], 1)
                with self.assertRaises(KernelError) as partial:
                    kernel.tessellate(plate, 0.1)
                mine = [{"id": "6061-T6", "densityGCm3": 2.71, "source": "mill certificate 4711"}]
                self.assertEqual(kernel.sheet("{}", sheet="sheet1", format="pdf")["contentBase64"], "JVBERg==")
                self.assertEqual(kernel.bom("{}", parts=linked_parts({"plate.3d.py": plate}), materials=mine)["csv"], "item\n")
                kernel.observe("{}", materials=mine)
                self.assertEqual(kernel.call("health")["build"], "sha256:abc")
                self.assertEqual(kernel.check(plate)["checks"][0]["status"], "passed")
                router = {"process": {"mill": {"travel_mm": [300, 180, 45], "max_depth_to_diameter": 3}}}
                kernel.check(plate, devices={"devices/router/definition.tsx": router})
                made = kernel.dfm(plate, process="mill", limits=router["process"]["mill"], setup={"tools": [{"diameter_mm": 3.175}]}, part="plate")
                self.assertEqual((made["verdict"], made["findings"][0]["where"][0]["faces"]), ("fail", [4]))
                with self.assertRaises(ValueError):
                    kernel.dfm(plate, process="laser", limits={})
            self.assertEqual(seen[8][0], "/v1/check")
            self.assertEqual(seen[9][2]["params"], {"devices": {"devices/router/definition.tsx": router}})
            self.assertEqual((seen[10][0], seen[10][2]["params"]), ("/v1/dfm", {"process": "mill", "limits": router["process"]["mill"], "setup": {"tools": [{"diameter_mm": 3.175}]}, "part": "plate"}))
            self.assertEqual(len(seen), 11, "a process the checks do not know is refused before anything is sent")
            self.assertEqual(refused.exception.status, 422)
            self.assertIn("no such body", str(refused.exception))
            self.assertEqual(partial.exception.failures, FAILED["failures"])
            self.assertIn("the build failed in 1 feature", str(partial.exception))
            self.assertTrue(all(auth == "Bearer service-bearer" for _, auth, _ in seen))
            path, _, body = seen[0]
            self.assertEqual((path, body["params"]), ("/v1/export", {"format": "step", "bodies": ["body_0"]}))
            self.assertEqual(json.loads(doc_of(body))["nodes"]["plate"]["type"], "box")
            self.assertEqual(seen[1][2]["params"], {"measures": [{"quantity": "radius", "a": {"body": "body_9", "kind": "edge", "index": 0}}]})
            self.assertEqual(list(seen[2][2]["params"]["parts"]), ["3d:name:bolt.3d.py"])
            self.assertEqual(seen[4][2]["params"], {"sheet": "sheet1", "format": "pdf"})
            self.assertEqual(seen[6][2]["params"], {"digest": "", "materials": mine})
            self.assertEqual(seen[7][:2], ("/v1/health", "Bearer service-bearer"))
        finally:
            server.shutdown()
            server.server_close()

    def test_no_local_kernel_falls_to_the_cloud_door_with_the_api_key(self):
        server, url, seen = serve(lambda path, auth, body: (200, {"outputs": {}, "result": {"content": "ISO-10303-21;"}, "ran": {"kernel": "3d", "build": "sha256:c", "place": "cloud"}}))
        try:
            _Local.installed = "the local 3D kernel is not installed (commandagi threed install)"
            with mock.patch.dict(os.environ, {"COMMANDAGI_API_KEY": "cagi_account", "COMMANDAGI_BASE_URL": url}, clear=True):
                kernel = Kernel()
                self.assertEqual(kernel.export("{}"), "ISO-10303-21;")
                self.assertEqual(kernel.last_ran["place"], "cloud")
            self.assertEqual(seen[0][:2], ("/kernels/3d/v1/export", "Bearer cagi_account"))
            self.assertEqual(doc_of(seen[0][2]), "{}")
        finally:
            server.shutdown()
            server.server_close()

    def test_a_refusal_here_is_not_asked_of_the_cloud(self):
        local, local_url, _ = serve(lambda path, auth, body: (422, FAILED))
        cloud, cloud_url, cloud_seen = serve(lambda path, auth, body: (200, {"result": {"content": "x"}}))
        try:
            env = {"COMMANDAGI_API_KEY": "cagi_account", "COMMANDAGI_BASE_URL": cloud_url, "COMMANDAGI_THREED_URL": local_url, "COMMANDAGI_THREED_TOKEN": "t"}
            with mock.patch.dict(os.environ, env, clear=True):
                kernel = Kernel()
                with self.assertRaises(KernelError) as refused:
                    kernel.export("{}")
            self.assertEqual((refused.exception.status, kernel.last_ran["place"], cloud_seen), (422, "local", []))
        finally:
            for s in (local, cloud):
                s.shutdown()
                s.server_close()

    def test_nowhere_to_run_says_why_for_each_place(self):
        _Local.installed = "no `commandagi` command is on PATH"
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KernelError) as nowhere:
                Kernel().export("{}")
        self.assertEqual(nowhere.exception.status, 503)
        self.assertIn("local: no `commandagi` command is on PATH; cloud: no such place here", str(nowhere.exception))

    def test_the_local_kernel_is_found_from_what_commandagi_threed_status_prints(self):
        # @commandagi/host's `commandagi threed status` prints one JSON object over several lines (cli.mjs: print).
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        cli = os.path.join(folder, "commandagi")

        def status_says(printed):
            with open(cli, "w") as f:
                f.write(f"#!{sys.executable}\nimport sys\nsys.stdout.write({printed!r})\n")
            os.chmod(cli, os.stat(cli).st_mode | stat.S_IEXEC)
            _Local.installed = None
            with mock.patch.dict(os.environ, {"PATH": folder}, clear=True):
                return _Local.absent()

        here = {"dir": "/x/3d-design/eval", "installed": True, "available": True, "via": "local"}
        self.assertEqual(status_says(json.dumps(here, indent=2) + "\n"), "")
        self.assertIn("commandagi threed install", status_says(json.dumps({**here, "installed": False}, indent=2) + "\n"))
        self.assertIn("commandagi threed install", status_says("Usage: commandagi\n"))
        with mock.patch.dict(os.environ, {"PATH": folder}, clear=True):
            with self.assertRaises(KernelError) as nowhere:
                Kernel().export("{}")
        self.assertIn("commandagi threed install", str(nowhere.exception))
        self.assertNotIn("Expecting value", str(nowhere.exception))


class Edge(unittest.TestCase):
    """The platform's CDN refuses urllib's own User-Agent (Cloudflare 1010, microfab CORE-30): every request names the SDK."""

    def test_every_request_names_the_sdk_and_its_version(self):
        import commandagi
        from commandagi import CommandAGI

        server, url, _ = serve(lambda path, auth, body: (200, {"result": {"observation": {"bodies": [], "errors": {}}, "meshes": [], "meshTris": 0},
                                                              "jsonrpc": "2.0", "id": 1}))
        try:
            with mock.patch.dict(os.environ, {"COMMANDAGI_THREED": "cloud"}, clear=True):
                Kernel(api_key="cagi_account", base_url=url).observe("{}")
            CommandAGI(api_key="cagi_account", base_url=url).call("whoami")
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(server.agents, [f"commandagi-python/{commandagi.__version__}"] * 2)


if __name__ == "__main__":
    unittest.main()
