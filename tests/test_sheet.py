"""A schematic in Python declares the circuit editor's own sheet nodes, and each node says which call of the file it came
from (the source map the editor writes edits back with). Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.sheet import sch_symbol_type_for

DIVIDER = '''from commandagi.design.sheet import ground, group, resistor, trace, voltagesource

with group("Divider"):
    voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3)  # the supply
    resistor(
        "R1",
        resistance="3k",
        sch_x=114.3 + 0,
        sch_y=88.9,
    )
    ground("#PWR1", sch_x=139.7, sch_y=114.3)
    trace(".V1 > .pos", ".R1 > .pin1")
    trace(".V1 > .neg", "net.GND")
'''


def wire(node, port):
    return {"wire": {"node": node, "port": port}}


def run(text, path="Divider.sch.py"):
    return run_module(text, path)["graph"]


class SheetTests(unittest.TestCase):
    def test_the_block_declares_placements_wires_bound_to_pins_and_labels(self):
        g = run(DIVIDER)
        self.assertEqual(g["meta"]["name"], "Divider")
        self.assertNotIn("outputs", g, "a schematic without a board has no outputs")
        self.assertEqual(g["nodes"]["sym_R1_1"]["inputs"], {"unit": 1, "style": 1, "at": {"x": 114.3, "y": 88.9}, "rot": 0, "mirror": "", "part": wire("R1", "@part")})
        self.assertEqual(g["nodes"]["sym_R1_1"]["type"], sch_symbol_type_for(["p1", "p2"]))
        self.assertEqual(g["nodes"]["R1"]["inputs"]["value"], "3k")
        self.assertEqual(g["nodes"]["PWR1"]["inputs"]["powerSymbol"], True)
        self.assertEqual(g["nodes"]["w_1"]["inputs"], {"ends.1": wire("sym_V1_1", "p1"), "ends.2": wire("sym_R1_1", "p1")})
        self.assertEqual(g["nodes"]["lbl_GND"]["inputs"], {"text": "GND", "on": wire("sym_V1_1", "p2")})

    def test_each_node_carries_its_call_with_the_span_of_each_keyword(self):
        g = run(DIVIDER)
        src = g["nodes"]["R1"]["meta"]["source"]
        self.assertEqual((src["tag"], src["line"], src["column"], src["evaluations"]), ("resistor", 5, 5, 1))
        self.assertEqual(DIVIDER[src["start"]:src["end"]], 'resistor(\n        "R1",\n        resistance="3k",\n        sch_x=114.3 + 0,\n        sch_y=88.9,\n    )')
        y = src["props"]["sch_y"]
        self.assertEqual((DIVIDER[y["start"]:y["end"]], y["literal"], y["value"], y["line"]), ("88.9", True, 88.9, 9))
        self.assertEqual(src["props"]["sch_x"], {"start": DIVIDER.index("114.3 + 0"), "end": DIVIDER.index("114.3 + 0") + 9, "literal": False, "expr": "114.3 + 0", "line": 8})
        self.assertEqual(g["nodes"]["sym_R1_1"]["meta"]["source"], src, "the part and its symbol are one call")
        m = g["meta"]["sourceMap"]
        self.assertEqual(m["length"], len(DIVIDER))
        self.assertEqual([e["tag"] for e in m["elements"]], ["group", "voltagesource", "resistor", "ground", "trace", "trace"])
        self.assertEqual(m["elements"][0]["block"], {"end": len(DIVIDER) - 1, "indent": "    ", "pass": None})
        self.assertEqual(m["imports"][0]["module"], "commandagi.design.sheet")
        self.assertTrue(all(e["parent"] == 0 and e["child"] and e["statement"] and e["body"]["size"] == 5 for e in m["elements"][1:]))

    def test_offsets_count_utf16_units_as_the_editor_does(self):
        text = '# Ω and 𝄞\nfrom commandagi.design.sheet import *\nwith group("Ü"):\n    resistor("R1", resistance="1k", sch_x=1, sch_y=2)\n'
        src = run(text, "u.sch.py")["nodes"]["R1"]["meta"]["source"]
        units = text.encode("utf-16-le")
        self.assertEqual(units[2 * src["start"]:2 * src["end"]].decode("utf-16-le"), 'resistor("R1", resistance="1k", sch_x=1, sch_y=2)')

    def test_a_call_in_a_loop_counts_each_run(self):
        text = 'from commandagi.design.sheet import *\nwith group("L"):\n    for i in range(3):\n        capacitor("C%d" % i, capacitance="1u", sch_x=10 * i, sch_y=0)\n'
        g = run(text, "l.sch.py")
        src = g["nodes"]["C2"]["meta"]["source"]
        self.assertEqual(src["evaluations"], 3)
        self.assertFalse(g["meta"]["sourceMap"]["elements"][src["element"]]["child"], "a call in a loop is not where a sibling goes")

    def test_refused_by_name(self):
        head = 'from commandagi.design.sheet import *\nwith group("S"):\n'
        cases = [
            ('    ground("GND1", sch_x=0, sch_y=0)\n', "starts with #"),
            ('    resistor("R1")\n    resistor("R2", sch_x=0, sch_y=0)\n    trace(".R1 > .pin1", ".R2 > .pin1")\n', "R1 is not on the sheet"),
            ('    resistor("R1", sch_x=0, sch_y=0, footprint="0603")\n', "footprint is not read on a schematic"),
            ('    with group("T"):\n        pass\n', "a schematic is one group"),
        ]
        for body, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                run(head + body, "s.sch.py")
        with self.assertRaisesRegex(RuntimeError, "belongs inside `with group"):
            run('from commandagi.design.sheet import *\nresistor("R1")\n', "s.sch.py")


if __name__ == "__main__":
    unittest.main()
