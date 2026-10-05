"""Signed records declared in Python give what the TypeScript SDK's JSX gives (records.test.ts there): a contract's terms
verbatim (None inside them is null), parties in order; an instance's chain oldest first, genesis prev kept as null.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import contract, contract_party, instance_event, product_instance, run_module
from commandagi.design.records import declare_record_document

TERMS = {"subject": {"kind": "data_stream", "resourceType": "device", "resourceId": "dev-1"}, "title": "Bench camera",
         "description": "", "price": {"type": "metered", "rate": 1, "unit": "minute"}, "schedule": None, "takeRateBps": 1000,
         "channels": ["screen"]}


class RecordTests(unittest.TestCase):
    def test_a_contract_is_its_body(self):
        d = declare_record_document(contract("c-1", contract_party(principal="u-1", role="offeror", sig="ed25519:k:abc", signedAt=1780765664000),
                                             contract_party(principal="acct:org:o-2", role="acceptor", actedBy="u-3"),
                                             terms=TERMS, createdAt=1780765664000))
        self.assertEqual(d, {"format": "contract", "sources": {}, "document": {
            "id": "c-1", "terms": TERMS, "createdAt": 1780765664000,
            "parties": [{"principal": "u-1", "role": "offeror", "sig": "ed25519:k:abc", "signedAt": 1780765664000},
                        {"principal": "acct:org:o-2", "role": "acceptor", "actedBy": "u-3"}]}})
        self.assertIsNone(d["document"]["terms"]["schedule"])
        with self.assertRaisesRegex(ValueError, "<contract> needs createdAt"):
            declare_record_document(contract("c", terms=TERMS))
        with self.assertRaisesRegex(ValueError, "title is not read"):
            declare_record_document(contract("c", terms=TERMS, createdAt=1, title="x"))

    def test_an_instance_and_a_run(self):
        d = declare_record_document(product_instance("SN-1", instance_event(seq=0, kind="manufacture", at=1, prev=None, by="org-acme", sig="s0"),
                                                     instance_event(seq=1, kind="transfer", at=2, prev="h0", by="org-acme", to="u-2"), productId="fleet-unit"))
        self.assertEqual(d["document"], {"serial": "SN-1", "productId": "fleet-unit", "events": [
            {"seq": 0, "kind": "manufacture", "at": 1, "prev": None, "by": "org-acme", "sig": "s0"},
            {"seq": 1, "kind": "transfer", "at": 2, "prev": "h0", "by": "org-acme", "to": "u-2"}]})
        with self.assertRaisesRegex(ValueError, "oldest first"):
            declare_record_document(product_instance("S", instance_event(seq=1, kind="service", at=1, by="x"), productId="p"))
        out = run_module('from commandagi.design import product_instance\nresult = product_instance("SN-2", productId="p")', "Kit/Unit.instance.py")
        self.assertEqual(out["graph"], {"id": "Unit", "nodes": {}})
        self.assertEqual(out["document"], {"format": "instance", "document": {"serial": "SN-2", "productId": "p", "events": []}, "sources": {}})


if __name__ == "__main__":
    unittest.main()
