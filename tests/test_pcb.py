"""A board in code declares the same nodes as the TypeScript SDK's JSX board (sdk/typescript/src/design/pcb.test.ts).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import pcb_board, pcb_component, pcb_trace, pcb_via, run_module


class BoardTests(unittest.TestCase):
    def test_a_board_declares_the_board_half(self):
        g = pcb_board("Divider.sch.tsx", width=40, height=30, core=1.5, copper=0.035, children=[
            pcb_component("R1", "smd-0805", x=10, y=10),
            pcb_component("R2", "axial-7.62", x=25, y=10, rotation=90, layer="bottom"),
            pcb_component("V1", "smd-0805"),
            pcb_trace("F.Cu", 0.2, [(11, 10), (18, 14), (24, 10)], from_=".R1 > .pin2", to=".R2 > .1"),
            pcb_trace("B.Cu", 0.25, [(18, 14), (18, 20)], from_=".VIA1"),
            pcb_via(18, 14, drill=0.4, diameter=0.8, name="VIA1"),
        ]).ir
        self.assertEqual(g["meta"]["schematic"], "Divider.sch.tsx")
        self.assertEqual(g["outputs"], ["board"])
        self.assertEqual(g["nodes"]["board"]["inputs"]["thicknessMm"], 1.57)
        self.assertEqual(g["nodes"]["board"]["inputs"]["stack"], {"wire": {"node": "stack", "port": "stack"}})
        self.assertEqual(g["nodes"]["fp_R1"], {"id": "fp_R1", "type": "eda.footprint", "label": "R1",
                                               "inputs": {"ref": "R1", "footprint": "Authored:smd-0805", "placement": {"x": 10, "y": 10, "rot": 0, "side": "top"}}})
        self.assertEqual(g["nodes"]["fp_R2"]["inputs"]["placement"], {"x": 25, "y": 10, "rot": 90, "side": "bottom"})
        self.assertNotIn("placement", g["nodes"]["fp_V1"]["inputs"])
        self.assertEqual(g["nodes"]["cu_1"]["inputs"], {
            "kind": "run", "points": [{"x": 11, "y": 10, "id": "start"}, {"x": 18, "y": 14, "id": "p1"}, {"x": 24, "y": 10, "id": "end"}],
            "widthMm": 0.2, "layer": "F.Cu", "rule": "any",
            "terminals": [{"point": 0, "ref": "R1", "number": "2"}, {"point": 2, "ref": "R2", "number": "1"}]})
        self.assertEqual(g["nodes"]["cu_2"]["inputs"]["terminals"], [{"point": 0, "via": "VIA1"}])
        self.assertEqual(g["nodes"]["VIA1"]["inputs"], {"kind": "via", "points": [{"x": 18, "y": 14}], "drillMm": 0.4, "padDiameterMm": 0.8, "layers": ["F.Cu", "B.Cu"]})

    def test_a_pcb_py_file_runs(self):
        out = run_module('from commandagi.design import pcb_board, pcb_component\n'
                         'result = pcb_board("Divider.sch.tsx", children=[pcb_component("R1", "smd-0805", x=1, y=2)])\n', "Divider.pcb.py")
        self.assertEqual(out["graph"]["nodes"]["fp_R1"]["inputs"]["placement"], {"x": 1, "y": 2, "rot": 0, "side": "top"})
        self.assertNotIn("board", out["graph"]["nodes"])

    def test_a_library_footprint_is_its_ref_and_its_library(self):
        g = pcb_board("D.sch.tsx", children=[pcb_component("U1", "Package_SO:SOIC-8", x=12, y=8, rotation=90, library="footprints.pretty")]).ir
        self.assertEqual(g["nodes"]["fp_U1"]["inputs"], {"ref": "U1", "footprint": "Package_SO:SOIC-8", "library": "footprints.pretty",
                                                         "placement": {"x": 12, "y": 8, "rot": 90, "side": "top"}})
        with self.assertRaisesRegex(ValueError, "its ref, \"Library:Footprint\""):
            pcb_board("D.sch.tsx", children=[pcb_component("U1", "SOIC-8", library="footprints.pretty")])
        with self.assertRaisesRegex(ValueError, "a footprint library folder"):
            pcb_board("D.sch.tsx", children=[pcb_component("U1", "Package_SO:SOIC-8", library="SOIC-8.kicad_mod")])

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "footprint is one of smd-0805"):
            pcb_board("D.sch.tsx", children=[pcb_component("R1", "0603")])
        with self.assertRaisesRegex(ValueError, "no component or trace R9"):
            pcb_board("D.sch.tsx", children=[pcb_trace("F.Cu", 0.2, [(0, 0), (1, 0)], from_=".R9 > .pin1")])
        with self.assertRaisesRegex(ValueError, "two elements are called V1"):
            pcb_board("D.sch.tsx", children=[pcb_component("V1", "smd-0805"), pcb_via(0, 0, 0.3, 0.6, name="V1")])
        with self.assertRaisesRegex(ValueError, "relative to this file"):
            pcb_board("/abs.sch.json")


if __name__ == "__main__":
    unittest.main()
