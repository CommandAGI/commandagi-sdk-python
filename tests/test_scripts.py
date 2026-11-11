"""A script declared in Python gives what the TypeScript SDK's JSX gives (scripts.test.ts there): a class is a
function, an instance one call, and the run gives the ScriptDoc; a tail names a file, never a folder; what the
vocabulary has no words for is refused by name.
Run: python -m unittest discover -s tests"""
import json
import pathlib
import re
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.element import Element
from commandagi.design.scripts import (SCRIPT_FILE, SCRIPTS, derive, discover, judge, param, script, script_with_defaults,
                                       publish, source, tail, tail_ref_problem, wake)

V = SCRIPTS["script"]


def snake(attrs):
    """The golden writes TypeScript names; a keyword is the snake_case of one."""
    return {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): v for k, v in attrs.items()}


def corporation(cik, ticker, name):
    return script(source(id="filings", adapter="sec-filings", params={"cik": cik}, every="30m"),
                  tail(of="../../central-banks/fed/fed.script.tsx", when={"class": "fomc.*"}),
                  wake(when={"class": "sec.filing.8-k*"}, prompt="Say what the report changes."),
                  title=f"{name} ({ticker})", class_="corporation", about=f"cik:{cik}", same_as=[f"ticker:{ticker}"])


def doc(*children, **attrs):
    return declare_document(script(*children, **attrs))["document"]


class ScriptTests(unittest.TestCase):
    def test_a_script_is_its_parts_both_ways(self):
        d = declare_document(corporation("0001045810", "NVDA", "NVIDIA"))
        self.assertEqual(d["format"], "script")
        m = d["document"]
        self.assertEqual(m, {
            "title": "NVIDIA (NVDA)", "class": "corporation", "about": "cik:0001045810", "sameAs": ["ticker:NVDA"],
            "sources": [{"id": "filings", "adapter": "sec-filings", "params": {"cik": "0001045810"}, "every": "30m"}],
            "tails": [{"of": "../../central-banks/fed/fed.script.tsx", "when": {"class": "fomc.*"}}],
            "derives": [],
            "wakes": [{"when": {"class": "sec.filing.8-k*"}, "prompt": "Say what the report changes."}],
            "discovers": [], "judges": [], "params": [], "publishes": []})
        self.assertEqual(V.from_tree(V.to_tree(m)), m, "both ways")
        full = script_with_defaults(m)
        self.assertEqual(full["sources"][0], {
            "id": "filings", "adapter": "sec-filings", "params": {"cik": "0001045810"}, "every": "30m", "via": "worker",
            "exit": None, "host": None, "mode": "poll", "retain": None, "since": None, "session": None, "snapshot": None,
            "profile": None, "keep": None, "maxCostPerDay": None, "unit": None, "vantage": None, "connection": None,
            "stream": "records"})
        self.assertEqual(full["tails"], [{"of": "../../central-banks/fed/fed.script.tsx", "when": {"class": "fomc.*"}, "stream": "records"}])
        self.assertEqual(full["wakes"], [{"when": {"class": "sec.filing.8-k*"}, "every": None, "prompt": "Say what the report changes.", "agent": None, "maxSpend": None}])

    def test_an_empty_script_its_file_name_and_a_part_that_names_another_stream(self):
        empty = {"sources": [], "tails": [], "derives": [], "wakes": [], "discovers": [], "judges": [], "params": [], "publishes": []}
        self.assertEqual(doc(), empty)
        self.assertEqual(V.empty("script"), empty)
        for name in ["nvidia.script.tsx", "a.script.jsx", "b.script.py", "c.script.rs"]:
            self.assertTrue(SCRIPT_FILE.match(name), name)
        for name in ["monitor.tsx", "script.tsx", "nvidia.tsx"]:
            self.assertFalse(SCRIPT_FILE.match(name), name)
        ticks = doc(source(id="q", adapter="fred", every="1h", stream="ticks"))
        self.assertEqual(script_with_defaults(ticks)["sources"][0]["stream"], "ticks")
        with self.assertRaisesRegex(ValueError, "stream is a word"):
            doc(source(id="q", adapter="fred", every="1h", stream="Ticks!"))

    def test_a_tail_names_a_file_never_a_folder(self):
        for of in ["../nvidia/nvidia.script.tsx", "cloud://home/user-commandagi/entities/fed/fed.script.tsx",
                   "../x/runs/thread-1/streams/records@cloud/records.jsonl", "fred:DGS10", "ecb:FM.D.U2.EUR.4F.KR.DFR.LEV"]:
            with self.subTest(of=of):
                doc(tail(of=of))
        with self.assertRaisesRegex(ValueError, re.escape('<tail of="../nvidia"> names a file: a script ("../nvidia/nvidia.script.tsx")')):
            doc(tail(of="../nvidia"))
        with self.assertRaisesRegex(ValueError, "names this script's folder"):
            doc(tail(of="./"))
        with self.assertRaisesRegex(ValueError, "names a file"):
            doc(tail(of="../nvidia/monitor.tsx"))
        self.assertIsNone(tail_ref_problem("fred:DGS10"))
        with self.assertRaisesRegex(ValueError, re.escape("match is not read (of, when, stream)")):
            doc(tail(of="../x/x.script.tsx", match="a.*"))
        with self.assertRaisesRegex(ValueError, "follows"):
            doc(Element("follows", {"monitor": "../x"}, [], None, "scripts"))
        with self.assertRaisesRegex(ValueError, re.escape("when: data.n: above is not an operator")):
            doc(tail(of="../x/x.script.tsx", when={"data.n": {"above": 1}}))

    def test_a_source_refuses_by_name_what_it_has_no_words_for(self):
        def src(**attrs):
            return source(**{"id": "s", "adapter": "fred", "every": "1h", **attrs})
        refused = [
            ((src(), src()), 'two <source> in <script> have id "s"'),
            ((source(id="s", adapter="fred"),), '<source id="s"> needs every'),
            ((src(every="10s"),), "every is from 30s to 7d"),
            ((src(via="ftp"),), 'via is "worker", "host", "vpn", "browser", "vm", "android-vm", "phone"'),
            ((src(mode="stream"),), 'mode="stream" holds a connection open, which runs on a host'),
            ((src(via="vm", snapshot="genesis"),), 'via="vm" costs money: it says maxCostPerDay'),
            ((src(via="phone"),), 'via="phone" names its phone: unit='),
            ((src(via="host", connection="gmail@jacobfv123@gmail.com"),), "connection names a connected account, which the api worker reads"),
        ]
        for children, words in refused:
            with self.subTest(words=words), self.assertRaisesRegex(ValueError, re.escape(words)):
                doc(*children)
        with self.assertRaisesRegex(ValueError, "sameAs is a list of subjects"):
            doc(same_as=["NVDA"])
        # The id is the file's path, and who reads the run is the file's Drive visibility: neither is a word of the file.
        with self.assertRaisesRegex(ValueError, "<script>: id is not read"):
            doc(id="economy/cpi")
        with self.assertRaisesRegex(ValueError, "<script>: visibility is not read"):
            doc(visibility="public")

    def test_a_derive_and_a_discover_name_files(self):
        m = doc(derive(id="spread", op="spread", inputs={"a": "fred:SOFR", "b": "fred:IORB"}),
                derive(id="own", op="last", inputs={"records": "./"}, since="2026-10-01", stream="derived"),
                discover(of="./kev/kev.script.tsx", into="./exploits", when={"class": "security.kev"}, slug="data.cve",
                         class_="./exploit.tsx#Exploit", props={"cve": "data.cve"}, max=20, visibility="public"),
                title="SOFR minus IORB")
        self.assertEqual(V.from_tree(V.to_tree(m)), m, "both ways")
        full = script_with_defaults(m)
        self.assertEqual(full["derives"], [
            {"id": "spread", "op": "spread", "inputs": {"a": "fred:SOFR", "b": "fred:IORB"}, "params": {}, "since": None, "stream": "records"},
            {"id": "own", "op": "last", "inputs": {"records": "./"}, "params": {}, "since": "2026-10-01", "stream": "derived"},
        ])
        self.assertEqual(full["discovers"][0], {"into": "./exploits", "of": ["./kev/kev.script.tsx"], "when": {"class": "security.kev"},
                                                "slug": "data.cve", "class": "./exploit.tsx#Exploit", "props": {"cve": "data.cve"},
                                                "name": None, "max": 20, "visibility": "public"})
        with self.assertRaisesRegex(ValueError, "inputs maps each port to a file it tails"):
            doc(derive(id="d", op="last", inputs={}))
        with self.assertRaisesRegex(ValueError, "inputs.a names a file"):
            doc(derive(id="d", op="last", inputs={"a": "../quotes"}))

        def disc(**attrs):
            return doc(discover(**{"slug": "cve", "class_": "../c.tsx#Exploit", **attrs}))
        disc()
        with self.assertRaisesRegex(ValueError, "of names a file"):
            disc(of="./kev")
        with self.assertRaisesRegex(ValueError, "of is a script file or a list of them"):
            disc(of=[])
        with self.assertRaisesRegex(ValueError, "max is a whole number from 1 to 50"):
            disc(max=500)

    def test_a_judge_names_what_it_judges_its_rubric_and_its_model(self):
        m = doc(judge(id="claims", of="task", rubric="./rubric.md", model="fireworks/glm-5p3"))
        self.assertEqual(script_with_defaults(m)["judges"], [{"id": "claims", "of": "task", "rubric": "./rubric.md", "model": "fireworks/glm-5p3"}])
        with self.assertRaisesRegex(ValueError, 'of is "turn", "task"'):
            doc(judge(id="j", of="thread", rubric="r.md", model="m"))

    def test_a_template_declares_its_params_both_ways(self):
        m = doc(param(id="cik", type="string", label="the company's CIK"),
                param(id="ticker", type="string", required=False, default="NVDA"),
                source(id="filings", adapter="sec-filings", params={"cik": "${cik}"}, every="30m"),
                title="${name} (${ticker})")
        self.assertEqual(V.from_tree(V.to_tree(m)), m, "both ways")
        self.assertEqual(script_with_defaults(m)["params"], [
            {"id": "cik", "type": "string", "label": "the company's CIK", "default": None, "required": True, "choices": None, "accept": None},
            {"id": "ticker", "type": "string", "label": None, "default": "NVDA", "required": False, "choices": None, "accept": None},
        ])

        def one(**attrs):
            return doc(param(**{"id": "p", "type": "string", **attrs}))
        with self.assertRaisesRegex(ValueError, 'type is "file"'):
            one(type="date")
        with self.assertRaisesRegex(ValueError, "id is letters, digits and _"):
            one(id="a-b")
        with self.assertRaisesRegex(ValueError, "a choice names its choices"):
            one(type="choice")
        self.assertEqual(one(type="choice", choices=["a", "b"])["params"][0]["choices"], ["a", "b"])
        with self.assertRaisesRegex(ValueError, 'two <param> in <script> have id "p"|declared twice'):
            doc(param(id="p", type="string"), param(id="p", type="number"))

    def test_a_placeholder_as_a_whole_value_passes_the_file_checks(self):
        # A template's ${name} is a file once its copy fills it.
        self.assertIsNone(tail_ref_problem("${of}"))
        m = doc(param(id="of", type="file"), param(id="cls", type="string"), tail(of="${of}"),
                derive(id="d", op="last", inputs={"a": "${of}"}),
                discover(of="${of}", slug="data.cve", class_="${cls}"))
        self.assertEqual(m["discovers"][0]["class"], "${cls}")
        with self.assertRaisesRegex(ValueError, "names a file"):
            doc(tail(of="../${of}"))
        with self.assertRaisesRegex(ValueError, "class is the class file"):
            doc(discover(slug="cve", class_="${a-b}"))

    def test_a_publish_folds_by_a_rule_one_a_rule(self):
        m = doc(publish(rule="capital", when={"class": "*.topic"}))
        self.assertEqual(m["publishes"], [{"rule": "capital", "when": {"class": "*.topic"}}])
        self.assertEqual(V.from_tree(V.to_tree(m)), m, "both ways")
        self.assertEqual(script_with_defaults(doc(publish(rule="capital")))["publishes"], [{"rule": "capital", "when": None}])
        with self.assertRaisesRegex(ValueError, 'rule is "capital", not "news"'):
            doc(publish(rule="news"))
        with self.assertRaisesRegex(ValueError, 'two <publish> in <script> have rule "capital"'):
            doc(publish(rule="capital"), publish(rule="capital"))
        with self.assertRaisesRegex(ValueError, "when"):
            doc(publish(rule="capital", when=3))

    def test_a_wake_on_its_own_records_or_on_a_clock(self):
        # script_wake.json is the golden of the three SDKs (the TypeScript SDK's script-wake.golden.json).
        golden = json.loads((pathlib.Path(__file__).parent / "script_wake.json").read_text(encoding="utf-8"))
        for row in golden["valid"]:
            with self.subTest(attrs=row["attrs"]):
                self.assertEqual(script_with_defaults(doc(wake(**snake(row["attrs"]))))["wakes"], [row["document"]])
        for row in golden["invalid"]:
            with self.subTest(attrs=row["attrs"]), self.assertRaisesRegex(ValueError, row["error"]):
                doc(wake(**snake(row["attrs"])))


if __name__ == "__main__":
    unittest.main()
