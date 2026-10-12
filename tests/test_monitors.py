"""A monitor declared in Python gives what the TypeScript SDK's JSX gives (monitors.test.ts there): a class is a
function, an instance one call, and the run gives the MonitorDoc; what the vocabulary has no words for is refused.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.monitors import derive, follows, monitor, source, wake


def corporation(cik, ticker, name):
    return monitor(source(id="filings", adapter="sec-filings", params={"cik": cik}, every="15m"),
                   follows(monitor="../../central-banks/fed", match="fomc.*"),
                   wake(match="sec.filing.8-k*", prompt="Say what the report changes."),
                   title=f"{name} ({ticker})", class_="corporation", about=f"cik:{cik}")


class MonitorTests(unittest.TestCase):
    def test_a_monitor_is_its_parts(self):
        d = declare_document(corporation("0001045810", "NVDA", "NVIDIA"))
        self.assertEqual(d["format"], "monitor")
        self.assertEqual(d["document"], {
            "title": "NVIDIA (NVDA)", "class": "corporation", "about": "cik:0001045810",
            "sources": [{"id": "filings", "adapter": "sec-filings", "params": {"cik": "0001045810"}, "every": "15m"}],
            "follows": [{"monitor": "../../central-banks/fed", "match": "fomc.*"}],
            "derives": [],
            "wakes": [{"match": "sec.filing.8-k*", "prompt": "Say what the report changes."}]})

    def test_refusals(self):
        def one(*children):
            return declare_document(monitor(*children))
        with self.assertRaisesRegex(ValueError, 'two <source> in <monitor> have id "s"'):
            one(source(id="s", adapter="fred", every="1h"), source(id="s", adapter="fred", every="1h"))
        with self.assertRaisesRegex(ValueError, "every is from 30s to 7d"):
            one(source(id="s", adapter="fred", every="10s"))
        with self.assertRaisesRegex(ValueError, "every is a duration"):
            one(source(id="s", adapter="fred", every="hourly"))
        with self.assertRaisesRegex(ValueError, "names this monitor"):
            one(follows(monitor="."))
        with self.assertRaisesRegex(ValueError, "visibility is not read"):
            declare_document(monitor(visibility="public"))

    def test_a_derive_names_its_operator_and_its_inputs_by_folder(self):
        d = declare_document(monitor(derive(id="vwap", op="vwap", inputs={"trades": "../trades"}, params={"window": "1m"})))
        self.assertEqual(d["document"]["derives"], [{"id": "vwap", "op": "vwap", "inputs": {"trades": "../trades"}, "params": {"window": "1m"}}])
        with self.assertRaisesRegex(ValueError, "inputs maps each port"):
            declare_document(monitor(derive(id="d", op="last", inputs={})))
        with self.assertRaisesRegex(ValueError, "names this monitor"):
            declare_document(monitor(derive(id="d", op="last", inputs={"records": "."})))


if __name__ == "__main__":
    unittest.main()
