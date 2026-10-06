"""The source map a ``.py`` run carries is the one shape every SDK's map has (the write-back contract, § the source map),
and a keyword is snake_case of the attribute's name. Run: python -m unittest tests.test_source"""
import unittest

from commandagi.design import run_module
from commandagi.design.element import attr_name
from commandagi.design.source import SourceMap

TEXT = '''from commandagi.design.schematic import group, resistor
from commandagi.design import schematic as sch

parts = [resistor("R%d" % i) for i in range(2)]
extra = {}
result = group(
    "S",
    resistor("R9", sch_x=1, sch_y=2),  # placed
    *parts,
    sch.trace(".R9 > .pin1", "net.GND"),
    **extra,
)
'''


class MapTests(unittest.TestCase):
    def setUp(self):
        self.graph = run_module(TEXT, "s.sch.py")["graph"]
        self.map = self.graph["meta"]["sourceMap"]
        self.els = {e["callee"]: e for e in self.map["elements"]}

    def at(self, start, end):
        return TEXT[start:end]

    def test_every_call_by_name_or_path_in_source_order(self):
        self.assertEqual([e["callee"] for e in self.map["elements"]], ["resistor", "range", "group", "resistor", "sch.trace"])
        self.assertEqual([e["index"] for e in self.map["elements"]], list(range(5)))
        self.assertEqual(self.els["sch.trace"]["tag"], "trace")
        self.assertEqual((self.map["language"], self.map["length"]), ("py", len(TEXT)))

    def test_a_child_has_a_slot_and_is_placed_and_a_looped_call_is_not(self):
        group, r9, trace = self.els["group"], self.map["elements"][3], self.els["sch.trace"]
        self.assertEqual((r9["parent"], trace["parent"]), (group["index"], group["index"]))
        self.assertEqual(self.at(r9["slot"]["before"], r9["slot"]["after"]), ',\n    resistor("R9", sch_x=1, sch_y=2),  # placed\n    ')
        self.assertTrue(r9["slot"]["comma"] and r9["placed"] and not r9["looped"])
        self.assertEqual(self.at(trace["slot"]["after"], trace["slot"]["after"] + 7), "**extra", "the next argument, keywords included")
        looped = self.map["elements"][0]
        self.assertEqual((looped["parent"], looped["slot"], looped["looped"], looped["placed"]), (None, None, True, False))
        self.assertFalse(self.map["elements"][1]["looped"], "a comprehension's first iterable runs once")

    def test_args_props_open_close_and_spread(self):
        group = self.els["group"]
        self.assertEqual(self.at(group["open"], group["close"] + 1), TEXT[TEXT.index("(\n    \"S\"") + 1:TEXT.rindex(")") + 1])
        self.assertEqual([a.get("value", a.get("expr")) for a in group["args"]][:1], ["S"])
        self.assertEqual([a.get("element") for a in group["args"]], [None, 3, None, 4])
        starred = group["args"][2]
        self.assertEqual((starred["expr"], starred["starred"], starred["literal"]), ("*parts", True, False))
        self.assertEqual(self.at(starred["start"], starred["end"]), "*parts")
        self.assertEqual(group["props"], [{"name": "**", "start": TEXT.index("**extra"), "end": TEXT.index("**extra") + 7,
                                           "valueStart": TEXT.index("**extra") + 2, "valueEnd": TEXT.index("**extra") + 7,
                                           "literal": False, "expr": "**extra", "line": 11}])
        self.assertEqual(group["spread"], {"line": 9, "expr": "*parts"})
        r9 = self.map["elements"][3]
        self.assertEqual([(p["name"], p["value"]) for p in r9["props"]], [("sch_x", 1), ("sch_y", 2)])
        self.assertEqual(self.at(r9["props"][0]["start"], r9["props"][0]["end"]), "sch_x=1")
        self.assertNotIn("**", self.graph["nodes"]["R9"]["meta"]["source"]["props"])

    def test_imports_with_the_span_of_each_name(self):
        imp = self.map["imports"]
        self.assertEqual([(i["module"], i["star"]) for i in imp], [("commandagi.design.schematic", False), ("commandagi.design", False)])
        self.assertEqual([(n["name"], n["asname"], self.at(n["start"], n["end"])) for n in imp[1]["names"]], [("schematic", "sch", "schematic as sch")])
        self.assertEqual(self.at(imp[0]["start"], imp[0]["end"]), TEXT.splitlines()[0])

    def test_no_with_block_fields(self):
        for e in self.map["elements"]:
            self.assertEqual(set(e), {"index", "tag", "callee", "start", "end", "line", "column", "parent", "props", "args", "open", "close",
                                      "spread", "slot", "looped", "placed"})

    def test_offsets_count_utf16_units_as_the_editor_does(self):
        text = '# Ω and 𝄞\nfrom commandagi.design.schematic import *\nresult = group("Ü", resistor("R1", resistance="1k", sch_x=1, sch_y=2))\n'
        src = run_module(text, "u.sch.py")["graph"]["nodes"]["R1"]["meta"]["source"]
        units = text.encode("utf-16-le")
        self.assertEqual(units[2 * src["start"]:2 * src["end"]].decode("utf-16-le"), 'resistor("R1", resistance="1k", sch_x=1, sch_y=2)')
        self.assertEqual(src["column"], len('result = group("Ü", ') + 1)

    def test_a_call_in_a_loop_counts_each_run(self):
        text = 'from commandagi.design.schematic import *\nresult = group("L", *[capacitor("C%d" % i, capacitance="1u", sch_x=10 * i, sch_y=0) for i in range(3)])\n'
        g = run_module(text, "l.sch.py")["graph"]
        src = g["nodes"]["C2"]["meta"]["source"]
        self.assertEqual(src["evaluations"], 3)
        el = g["meta"]["sourceMap"]["elements"][src["element"]]
        self.assertEqual((el["looped"], el["placed"], el["parent"]), (True, False, 0))

    def test_a_lambda_and_a_loop_body_are_looped(self):
        m = SourceMap("for i in range(2):\n    a(i)\nf = lambda: b()\nc(d())\n", "x.py")
        self.assertEqual([(e["tag"], e["looped"]) for e in m.elements], [("range", False), ("a", True), ("b", True), ("c", False), ("d", False)])
        self.assertTrue(m.elements[4]["placed"])


class KeywordTests(unittest.TestCase):
    def test_snake_case_is_the_attribute_name(self):
        self.assertEqual([attr_name(k) for k in ("frozen_rows", "sch_x", "from_", "foo_u_r_l", "x", "pin1")],
                         ["frozenRows", "schX", "from", "fooURL", "x", "pin1"])

    def test_a_camel_case_keyword_is_refused_by_name(self):
        with self.assertRaisesRegex(TypeError, "frozenRows is written frozen_rows"):
            attr_name("frozenRows")


if __name__ == "__main__":
    unittest.main()
