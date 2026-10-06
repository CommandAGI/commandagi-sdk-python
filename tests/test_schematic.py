"""A schematic in Python declares the circuit editor's own sheet nodes, and each node says which call of the file it came
from (the source map the editor writes edits back with). Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.schematic import sch_symbol_type_for

DIVIDER = '''from commandagi.design.schematic import ground, group, resistor, trace, voltagesource

result = group(
    "Divider",
    voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3),  # the supply
    resistor(
        "R1",
        resistance="3k",
        sch_x=114.3 + 0,
        sch_y=88.9,
    ),
    ground("#PWR1", sch_x=139.7, sch_y=114.3),
    trace(".V1 > .pos", ".R1 > .pin1"),
    trace(".V1 > .neg", "net.GND"),
)
'''


def wire(node, port):
    return {"wire": {"node": node, "port": port}}


def run(text, path="Divider.sch.py"):
    return run_module(text, path)["graph"]


def sheet(body, name="S"):
    """A file whose result is ``group(name, <body>)``; ``body`` is the group's arguments after the name."""
    return f'from commandagi.design.schematic import *\nresult = group("{name}",\n{body})\n'


class SheetTests(unittest.TestCase):
    def test_the_group_declares_placements_wires_bound_to_pins_and_labels(self):
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
        self.assertEqual((src["tag"], src["line"], src["column"], src["evaluations"]), ("resistor", 6, 5, 1))
        self.assertEqual(DIVIDER[src["start"]:src["end"]], 'resistor(\n        "R1",\n        resistance="3k",\n        sch_x=114.3 + 0,\n        sch_y=88.9,\n    )')
        y = src["props"]["sch_y"]
        self.assertEqual((DIVIDER[y["start"]:y["end"]], y["literal"], y["value"], y["line"]), ("88.9", True, 88.9, 10))
        self.assertEqual(src["props"]["sch_x"], {"start": DIVIDER.index("114.3 + 0"), "end": DIVIDER.index("114.3 + 0") + 9, "literal": False, "expr": "114.3 + 0", "line": 9})
        self.assertEqual(g["nodes"]["sym_R1_1"]["meta"]["source"], src, "the part and its symbol are one call")
        m = g["meta"]["sourceMap"]
        self.assertEqual(m["length"], len(DIVIDER))
        self.assertEqual([e["tag"] for e in m["elements"]], ["group", "voltagesource", "resistor", "ground", "trace", "trace"])
        self.assertTrue(all(e["parent"] == 0 and e["placed"] for e in m["elements"][1:]))

    def test_refused_by_name(self):
        cases = [
            ('    ground("GND1", sch_x=0, sch_y=0),\n', "starts with #"),
            ('    resistor("R1"),\n    resistor("R2", sch_x=0, sch_y=0),\n    trace(".R1 > .pin1", ".R2 > .pin1"),\n', "R1 is not on the sheet"),
            ('    resistor("R1", sch_x=0, sch_y=0, footprint="0603"),\n', "footprint is not read on a schematic"),
            ('    resistor("R1", sch_x=0, sch_y=0, pcb_x=3),\n', "pcbX is not read on a schematic"),
        ]
        for body, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                run(sheet(body), "s.sch.py")
        with self.assertRaisesRegex(TypeError, "holds nothing"):
            run('from commandagi.design.schematic import *\nresult = group("S", resistor("R1", resistor("R2")))\n', "s.sch.py")
        with self.assertRaisesRegex(TypeError, "write sch_x|is written sch_x"):
            run('from commandagi.design.schematic import *\nresult = group("S", resistor("R1", schX=1))\n', "s.sch.py")

    def test_a_library_part_names_its_symbol_by_ref_places_each_unit_mirrors_and_a_code_part_is_a_code_node(self):
        text = '''from commandagi.design.schematic import code, group, netlabel, part, resistor, trace, unit

result = group(
    "Rail",
    part("U1", symbol="Amplifier_Operational:LM358", library="opamps.kicad_sym", value="LM358", sch_x=50.8, sch_y=25.4, sch_mirror="x"),
    unit("U1", 2, sch_x=101.6, sch_y=25.4, sch_rotation=180),
    resistor("R1", resistance="10k", sch_x=76.2, sch_y=50.8, sch_mirror="y"),
    code("blinker", source="blinker.circuit.ts", inputs={"resistor": "330"}),
    trace(".U1 > .pin7", ".R1 > .pin1"),
    netlabel("OUT", ".U1 > .1"),
)
'''
        g = run(text, "rail.sch.py")
        n = g["nodes"]
        self.assertEqual(n["U1"]["inputs"], {"ref": "U1", "value": "LM358", "symbol": "Amplifier_Operational:LM358", "library": "opamps.kicad_sym", "pins": []}, "the pins are the library's")
        self.assertEqual(n["sym_U1_1"]["inputs"], {"unit": 1, "style": 1, "at": {"x": 50.8, "y": 25.4}, "rot": 0, "mirror": "x", "part": wire("U1", "@part")})
        self.assertEqual(n["sym_U1_1"]["type"], sch_symbol_type_for([]))
        self.assertEqual(n["sym_U1_2"]["inputs"], {"unit": 2, "style": 1, "at": {"x": 101.6, "y": 25.4}, "rot": 180, "mirror": "", "part": wire("U1", "@part")})
        self.assertEqual(n["sym_U1_2"]["meta"]["source"]["tag"], "unit", "a unit's placement maps to its unit(…) call")
        self.assertEqual(n["sym_R1_1"]["inputs"]["mirror"], "y")
        self.assertEqual(n["w_1"]["inputs"], {"ends.1": wire("U1", "pin:7"), "ends.2": wire("sym_R1_1", "p1")}, "a library pin by number, bound by the editor")
        self.assertEqual(n["lbl_OUT"]["inputs"]["on"], wire("U1", "pin:1"))
        b = n["blinker"]
        self.assertEqual((b["type"], b["label"], b["inputs"]), ("code", "blinker.circuit.ts", {"source": "blinker.circuit.ts", "resistor": "330"}))
        self.assertEqual(b["meta"]["source"]["tag"], "code")
        cases = [
            ('    part("U1", symbol="LM358", library="a.kicad_sym"),\n', "library ref"),
            ('    part("U1", symbol="A:B"),\n', "library is the path"),
            ('    resistor("R1", sch_x=0, sch_y=0),\n    unit("R1", 2, sch_x=1, sch_y=1),\n', "one unit"),
            ('    part("U1", symbol="A:B", library="a.kicad_sym"),\n    unit("U1", 1, sch_x=1, sch_y=1),\n', "unit is 2 or more"),
            ('    part("U1", symbol="A:B", library="a.kicad_sym"),\n    unit("U1", 2),\n', "give it schX and schY"),
            ('    part("U1", symbol="A:B", library="a.kicad_sym"),\n    unit("U1", 2, sch_x=1, sch_y=1),\n    unit("U1", 2, sch_x=2, sch_y=1),\n', "placed twice"),
            ('    resistor("R1", sch_x=0, sch_y=0, sch_mirror="z"),\n', 'schMirror is "x" or "y"'),
            ('    code("c", source="c.ts", inputs={"source": "d.ts"}),\n', "source is the file"),
        ]
        for body, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                run(sheet(body), "s.sch.py")

    def test_a_netlist_circuit_lists_pins_and_nets_and_carries_its_kicad_files(self):
        text = sheet('''    part("U1", value="LM358", pins=["1", {"number": "2", "name": "IN-"}]),
    part("C1", pins=["1", "2"], spice=[{"id": "c", "model": "C1u", "terminals": {"a": "1", "b": "2"}}]),
    net("N1", pins=[".U1 > .pin1", ".C1 > .1"]),
    attachment("schematic.kicad_sch", role="schematic", file="Rail.kicad_sch"),
''', "Rail")
        n = run(text, "rail.sch.py")["nodes"]
        self.assertEqual(n["U1"]["inputs"]["pins"], [{"id": "p1", "number": "1"}, {"id": "p2", "number": "2", "name": "IN-"}])
        self.assertEqual(n["C1"]["inputs"]["spice"], [{"id": "c", "model": "C1u", "terminals": {"a": "1", "b": "2"}}])
        self.assertEqual(n["net_N1"]["inputs"], {"pins.1": wire("U1", "p1"), "pins.2": wire("C1", "p1")})
        self.assertEqual(n["source_schematic.kicad_sch"]["inputs"], {"name": "schematic.kicad_sch", "role": "schematic", "file": "Rail.kicad_sch"})
        self.assertEqual(n["net_N1"]["meta"]["source"]["tag"], "net")


if __name__ == "__main__":
    unittest.main()
