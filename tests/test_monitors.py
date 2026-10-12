"""A monitor declared in Python gives what the TypeScript SDK's JSX gives (monitors.test.ts there): a class is a
function, an instance one call, and the run gives the MonitorDoc; what the vocabulary has no words for is refused.
Run: python -m unittest discover -s tests"""
import re
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.monitors import follows, monitor, monitor_with_defaults, source, wake


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

    def test_paths_and_their_fields(self):
        def one(**attrs):
            return declare_document(monitor(source(id="s", adapter="x-profile", every="1h", **attrs)))["document"]["sources"][0]
        page = one(via="browser", host="studio", session="../../../infra/sessions/x-web/session.tsx")
        self.assertEqual(page, {"id": "s", "adapter": "x-profile", "every": "1h", "via": "browser", "host": "studio",
                                "session": "../../../infra/sessions/x-web/session.tsx"})
        vm = one(via="vm", snapshot="x-logged-in", keep="10m", max_cost_per_day=2.5)
        self.assertEqual(vm["maxCostPerDay"], 2.5)
        phone = one(via="phone", unit="../../../worlds/fleet/world.tsx#android-01")
        full = monitor_with_defaults({"sources": [phone], "follows": [], "wakes": []})["sources"][0]
        self.assertEqual(full, {"id": "s", "adapter": "x-profile", "params": {}, "every": "1h", "via": "phone", "exit": None,
                                "host": None, "mode": "poll", "retain": None, "since": None, "session": None,
                                "snapshot": None, "profile": None, "keep": None, "maxCostPerDay": None,
                                "unit": "../../../worlds/fleet/world.tsx#android-01"})
        refused = [
            (dict(via="vm", snapshot="s"), "costs money: it says maxCostPerDay"),
            (dict(via="vm", max_cost_per_day=1), "launches from a snapshot: it names a session or a snapshot"),
            (dict(via="android-vm", snapshot="s", max_cost_per_day=0), "maxCostPerDay is a price in USD"),
            (dict(via="worker", max_cost_per_day=1), "maxCostPerDay bounds what"),
            (dict(via="vm", snapshot="s", session="a/session.tsx", max_cost_per_day=1), "a session or a snapshot"),
            (dict(via="browser", profile="p", session="a/session.tsx"), "a session or a profile"),
            (dict(via="host", profile="p"), 'for via="browser" only'),
            (dict(via="vpn", exit="DE", host="h"), "host names the host that reads it"),
            (dict(via="browser", snapshot="s"), "snapshot is what"),
            (dict(via="host", session="a/session.tsx"), "session names a logged-in state"),
            (dict(via="vm", snapshot="s", max_cost_per_day=1, keep="5s"), "keep is a duration"),
            (dict(via="browser", keep="10m"), "keep is how long"),
            (dict(via="phone"), 'names its phone: unit="<world.tsx>#<uid>"'),
            (dict(via="phone", unit="android-01"), 'unit is "<world.tsx ref>#<uid>"'),
            (dict(via="worker", unit="../w/world.tsx#a"), "unit names the phone"),
            (dict(via="browser", mode="stream"), 'mode="stream" holds a connection open'),
            (dict(via="ssh"), 'via is "worker", "host", "vpn", "browser", "vm", "android-vm", "phone"'),
        ]
        for attrs, words in refused:
            with self.subTest(attrs=attrs), self.assertRaisesRegex(ValueError, re.escape(words)):
                one(**attrs)


if __name__ == "__main__":
    unittest.main()
