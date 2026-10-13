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
                answers = {"/export": {"content": "ISO-10303-21;"}, "/sheet": {"sheet": "sheet1", "format": "pdf", "contentBase64": "JVBERg=="},
                           "/bom": {"lines": [], "csv": "item\n"}, "/observe": {"observation": {"bodies": [], "errors": {}}, "meshes": [], "meshTris": 0}}
                self.send_response(200 if self.path in answers else 422)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(answers.get(self.path, {"error": "no such body"})).encode())

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
                # A drawing sheet, a bill of materials with an assembly's linked part, and an observation with the
                # caller's own materials table (the density a body's mass uses).
                mine = [{"id": "6061-T6", "densityGCm3": 2.71, "source": "mill certificate 4711"}]
                self.assertEqual(kernel.sheet("{}", sheet="sheet1", format="pdf")["contentBase64"], "JVBERg==")
                self.assertEqual(kernel.bom("{}", parts={"plate.3d.py": plate}, materials=mine)["csv"], "item\n")
                kernel.observe("{}", materials=mine)
            self.assertEqual(refused.exception.status, 422)
            self.assertIn("no such body", str(refused.exception))
            self.assertEqual(seen[2], ("/sheet", "Bearer service-bearer", {"docText": "{}", "sheet": "sheet1", "format": "pdf"}))
            self.assertEqual((seen[3][0], seen[3][2]["materials"], json.loads(seen[3][2]["parts"]["plate.3d.py"])["nodes"]["plate"]["type"]), ("/bom", mine, "box"))
            self.assertEqual(seen[4], ("/observe", "Bearer service-bearer", {"docText": "{}", "digest": "", "materials": mine}))
            (path, auth, body), (path2, auth2, body2) = seen[:2]
            self.assertEqual((path, auth, body["format"], body["bodies"]), ("/export", "Bearer service-bearer", "step", ["body_0"]))
            # What a file declares goes as its graph: the plate is a node of it.
            self.assertEqual(json.loads(body["docText"])["nodes"]["plate"]["type"], "box")
            self.assertEqual((path2, auth2, body2), ("/measure", "Bearer service-bearer", {"docText": "{}", "op": "radius", "a": {"body": "body_9", "kind": "edge", "index": 0}}))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
