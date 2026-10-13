"""Which 3D service a Kernel calls, and with whose credential. The calls themselves are checked against the real
service, from the built package (the CommandAGI repository's scripts/release/sdk-check.mjs)."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from commandagi.design.threed import box, part
from commandagi.kernel import Kernel, KernelError, where_of


class Where(unittest.TestCase):
    def test_one_setting_chooses_the_service(self):
        self.assertEqual(where_of(None, {}), "platform")
        self.assertEqual(where_of(None, {"COMMANDAGI_THREED": "local"}), "local")
        self.assertEqual(where_of(None, {"COMMANDAGI_THREED": "local", "COMMANDAGI_THREED_URL": "http://127.0.0.1:8091/"}), "http://127.0.0.1:8091")
        self.assertEqual(where_of("platform", {"COMMANDAGI_THREED": "local"}), "platform")
        with self.assertRaisesRegex(ValueError, '"platform", "local" or the URL'):
            where_of(None, {"COMMANDAGI_THREED": "cloud"})

    def test_the_platform_refuses_by_name_without_a_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(KernelError, "needs an API key.*COMMANDAGI_THREED=local"):
                Kernel()


class RunningService(unittest.TestCase):
    def test_it_gets_its_own_bearer_and_the_documents_graph(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                seen.append((self.path, self.headers["authorization"], body))
                ok = self.path == "/export"
                self.send_response(200 if ok else 422)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"content": "ISO-10303-21;"} if ok else {"error": "no such body"}).encode())

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            env = {"COMMANDAGI_API_KEY": "cagi_account", "COMMANDAGI_THREED_URL": f"http://127.0.0.1:{server.server_port}", "COMMANDAGI_THREED_TOKEN": "service-bearer"}
            with mock.patch.dict(os.environ, env, clear=True):
                kernel = Kernel()
                plate = part(box(id="plate", center=[0, 0, 4], size=[60, 40, 8], operation="new"), name="Plate")
                self.assertEqual(kernel.export(plate, "step", bodies=["body_0"]), "ISO-10303-21;")
                with self.assertRaises(KernelError) as refused:
                    kernel.measure("{}", "radius", {"body": "body_9", "kind": "edge", "index": 0})
            self.assertEqual(refused.exception.status, 422)
            self.assertIn("no such body", str(refused.exception))
            (path, auth, body), (path2, auth2, body2) = seen
            self.assertEqual((path, auth, body["format"], body["bodies"]), ("/export", "Bearer service-bearer", "step", ["body_0"]))
            # What a file declares goes as its graph: the plate is a node of it.
            self.assertEqual(json.loads(body["docText"])["nodes"]["plate"]["type"], "box")
            self.assertEqual((path2, auth2, body2), ("/measure", "Bearer service-bearer", {"docText": "{}", "op": "radius", "a": {"body": "body_9", "kind": "edge", "index": 0}}))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
