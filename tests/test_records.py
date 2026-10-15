"""Signed records declared in Python give what the TypeScript SDK's JSX gives (records.test.ts there): a contract's terms
verbatim (None inside them is null), parties in order; an instance's chain oldest first, genesis prev kept as null.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.records import check, contract, event, file, instance, output, party, release

TERMS = {"subject": {"kind": "data_stream", "resourceType": "device", "resourceId": "dev-1"}, "title": "Bench camera",
         "description": "", "price": {"type": "metered", "rate": 1, "unit": "minute"}, "schedule": None, "takeRateBps": 1000,
         "channels": ["screen"]}


class RecordTests(unittest.TestCase):
    def test_a_contract_is_its_body(self):
        d = declare_document(contract(party(principal="u-1", role="offeror", sig="ed25519:k:abc", signed_at=1780765664000),
                                      party(principal="acct:org:o-2", role="acceptor", acted_by="u-3"),
                                      id="c-1", terms=TERMS, created_at=1780765664000))
        self.assertEqual(d, {"format": "contract", "sources": {}, "document": {
            "id": "c-1", "terms": TERMS, "createdAt": 1780765664000,
            "parties": [{"principal": "u-1", "role": "offeror", "sig": "ed25519:k:abc", "signedAt": 1780765664000},
                        {"principal": "acct:org:o-2", "role": "acceptor", "actedBy": "u-3"}]}})
        self.assertIsNone(d["document"]["terms"]["schedule"])
        with self.assertRaisesRegex(ValueError, "<contract> needs createdAt"):
            declare_document(contract(id="c", terms=TERMS))
        with self.assertRaisesRegex(ValueError, "title is not read"):
            declare_document(contract(id="c", terms=TERMS, created_at=1, title="x"))

    def test_an_instance(self):
        d = declare_document(instance(event(seq=0, kind="manufacture", at=1, prev=None, by="org-acme", sig="s0"),
                                      event(seq=1, kind="transfer", at=2, prev="h0", by="org-acme", to="u-2"),
                                      serial="SN-1", product_id="fleet-unit"))
        self.assertEqual(d["document"], {"serial": "SN-1", "productId": "fleet-unit", "events": [
            {"seq": 0, "kind": "manufacture", "at": 1, "prev": None, "by": "org-acme", "sig": "s0"},
            {"seq": 1, "kind": "transfer", "at": 2, "prev": "h0", "by": "org-acme", "to": "u-2"}]})
        with self.assertRaisesRegex(ValueError, "oldest first"):
            declare_document(instance(event(seq=1, kind="service", at=1, by="x"), serial="S", product_id="p"))

    def test_a_release(self):
        a, b = "a" * 64, "b" * 64
        d = declare_document(release(
            file(path="cad/Plate.3d.py", digest=a),
            check(file="cad/Plate.3d.py", id="interference", kind="interference", status="passed"),
            output(path="outputs/Plate.step", digest=b, from_="cad/Plate.3d.py", kind="step"),
            id="plate-A", rev="A", of="../..", created_at=1792000000000, note="README.md"))
        self.assertEqual(d["document"], {
            "id": "plate-A", "rev": "A", "of": "../..", "createdAt": 1792000000000, "note": "README.md",
            "files": [{"path": "cad/Plate.3d.py", "digest": a}],
            "checks": [{"file": "cad/Plate.3d.py", "id": "interference", "kind": "interference", "status": "passed"}],
            "outputs": [{"path": "outputs/Plate.step", "digest": b, "from": "cad/Plate.3d.py", "kind": "step"}]})
        with self.assertRaisesRegex(ValueError, "digest is its content's SHA-256"):
            declare_document(release(file(path="x", digest="abc"), id="r", rev="A", of="."))
        with self.assertRaisesRegex(ValueError, "status is passed, failed, skipped, accepted"):
            declare_document(release(check(file="x", id="i", kind="k", status="ok"), id="r", rev="A", of="."))
        unit = declare_document(instance(serial="S", product_id="p", release="../releases/A/A.release.py"))
        self.assertEqual(unit["document"]["release"], "../releases/A/A.release.py")

    def test_a_run_names_each_record_by_its_call(self):
        out = run_module(
            "from commandagi.design.records import event, instance\n"
            "result = instance(\n"
            "    event(seq=0, kind=\"manufacture\", at=1, by=\"org-acme\"),\n"
            "    serial=\"SN-2\",\n"
            "    product_id=\"p\",\n"
            ")\n", "Kit/Unit.instance.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["document"], {"serial": "SN-2", "productId": "p",
                                                       "events": [{"seq": 0, "kind": "manufacture", "at": 1, "by": "org-acme"}]})
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "event#0"])
        self.assertEqual((sources[""]["tag"], sources[""]["line"]), ("instance", 2))
        self.assertEqual((sources["event#0"]["tag"], sources["event#0"]["line"]), ("event", 3))
        self.assertEqual(sources[""]["props"]["product_id"]["value"], "p")


if __name__ == "__main__":
    unittest.main()
