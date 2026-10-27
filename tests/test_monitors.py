"""A monitor declared in Python gives what the TypeScript SDK's JSX gives (monitors.test.ts there): a class is a
function, an instance one call, and the run gives the MonitorDoc; what the vocabulary has no words for is refused.
Run: python -m unittest discover -s tests"""
import re
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.monitors import derive, discover, follows, monitor, monitor_with_defaults, source, wake


def corporation(cik, ticker, name):
    return monitor(source(id="filings", adapter="sec-filings", params={"cik": cik}, every="15m"),
                   follows(monitor="../../central-banks/fed", where={"class": "fomc.*"}),
                   wake(match="sec.filing.8-k*", prompt="Say what the report changes."),
                   title=f"{name} ({ticker})", class_="corporation", about=f"cik:{cik}", same_as=[f"ticker:{ticker}"])


class MonitorTests(unittest.TestCase):
    def test_a_monitor_is_its_parts(self):
        d = declare_document(corporation("0001045810", "NVDA", "NVIDIA"))
        self.assertEqual(d["format"], "monitor")
        self.assertEqual(d["document"], {
            "title": "NVIDIA (NVDA)", "class": "corporation", "about": "cik:0001045810", "sameAs": ["ticker:NVDA"],
            "sources": [{"id": "filings", "adapter": "sec-filings", "params": {"cik": "0001045810"}, "every": "15m"}],
            "follows": [{"monitor": "../../central-banks/fed", "where": {"class": "fomc.*"}}],
            "derives": [],
            "wakes": [{"match": "sec.filing.8-k*", "prompt": "Say what the report changes."}],
            "discovers": []})
        self.assertEqual(monitor_with_defaults(d["document"])["follows"], [{"monitor": "../../central-banks/fed", "where": {"class": "fomc.*"}}])
        with self.assertRaisesRegex(ValueError, "sameAs is a list of subjects"):
            declare_document(monitor(same_as=["NVDA"]))

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
        self.assertEqual(monitor_with_defaults(d["document"])["derives"][0]["since"], None)
        with self.assertRaisesRegex(ValueError, "inputs maps each port"):
            declare_document(monitor(derive(id="d", op="last", inputs={})))
        # A port may name this monitor (an exploit's lifecycle from its own reads), as in the TypeScript SDK.
        own = declare_document(monitor(derive(id="d", op="consolidate", inputs={"own": "./"})))
        self.assertEqual(own["document"]["derives"][0]["inputs"], {"own": "./"})

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
        self.assertEqual(full.pop("vantage"), None)
        self.assertEqual(full.pop("connection"), None)
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

    def test_a_mirror_discovers_its_conversations(self):
        """The TypeScript SDK's mirror case: a source names its vantage, a follow filters, a discover writes one folder
        per conversation; the exploit's discover reads three feeds and says when in data."""
        def conversation(conv, title):
            return monitor(follows(monitor="../", where={"class": "message.*", "data.conversation": conv}), title=title, class_="conversation")
        mirror = declare_document(monitor(
            source(id="user-api", adapter="telegram-user", params={"account": "commandagi"}, every="1m", via="host",
                   vantage="../../../infra/vantages/laptop-linux"),
            discover(when={"class": "message.*"}, slug="conversation", class_="../../conversation.tsx#Conversation",
                     props={"conversation": "conversation", "title": "fromName"}, name="fromName", max=5),
            title="Telegram: commandagi", class_="mirror"))["document"]
        full = monitor_with_defaults(mirror)
        self.assertEqual(full["discovers"], [{"into": "./", "of": [], "when": {"class": "message.*"}, "slug": "conversation",
                                              "class": "../../conversation.tsx#Conversation",
                                              "props": {"conversation": "conversation", "title": "fromName"}, "name": "fromName", "max": 5,
                                              "visibility": None}])
        self.assertEqual(full["sources"][0]["vantage"], "../../../infra/vantages/laptop-linux")
        # A discover says the visibility its folders take; absent, the platform writes them private.
        public = monitor_with_defaults(declare_document(monitor(discover(
            slug="cve", class_="../c.tsx#Exploit", visibility="public")))["document"])["discovers"][0]
        self.assertEqual(public["visibility"], "public")
        self.assertEqual(declare_document(conversation("4412", "Alice"))["document"]["follows"],
                         [{"monitor": "../", "where": {"class": "message.*", "data.conversation": "4412"}}])

        def refuse(**attrs):
            return declare_document(monitor(discover(**{"slug": "conversation", "class_": "../c.tsx#Conversation", **attrs})))
        refuse()
        refuse(of=["./kev", "./cve-feed"], into="./exploits",
               when=[{"class": "security.kev"}, {"class": "security.cve", "data.cvss3": {"gte": 9}}],
               slug={"paths": ["data.cve", "data.id", "data.aliases"], "pattern": "^CVE-"})
        refused = [
            (dict(class_="../c.tsx#conversation"), "class is the class file and its exported name"),
            (dict(class_="../c.md#Conversation"), "class is the class file and its exported name"),
            (dict(slug="data[0]"), "slug is a data path"),
            (dict(slug={"paths": [], "pattern": "x"}), "slug is a data path"),
            (dict(when={"cvss": 9}), 'when: "cvss" is class, about, key, title or a data path'),
            (dict(when={"data.cvss": {"above": 9}}), "when: data.cvss: above is not an operator"),
            (dict(of=[]), "of is a monitor's folder or a list of them"),
            (dict(props={"title": "a b"}), "props.title is a data path"),
            (dict(max=500), "max is a whole number from 1 to 50"),
            (dict(visibility="shared"), "visibility is private, unlisted, public"),
            (dict(delete=True), "delete is not read"),
        ]
        for attrs, words in refused:
            with self.subTest(attrs=attrs), self.assertRaisesRegex(ValueError, re.escape(words)):
                refuse(**attrs)
        with self.assertRaisesRegex(ValueError, "where: a condition is an object of terms"):
            declare_document(monitor(follows(monitor="../x", where="conversation")))
        with self.assertRaisesRegex(ValueError, 'where: "bogus" is class, about, key, title or a data path'):
            declare_document(monitor(follows(monitor="../x", where={"bogus": 1})))


if __name__ == "__main__":
    unittest.main()
