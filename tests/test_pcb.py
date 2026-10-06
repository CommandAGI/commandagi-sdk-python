"""A board in code declares the same nodes as the TypeScript SDK's JSX board (sdk/typescript/src/design/pcb.test.ts).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.pcb import arc, board, component, declare_board_file, dimension, graphic, kicad, net, pour, stack, text, trace, via


def declared(*children, **attrs):
    attrs.setdefault("schematic", "Divider.sch.tsx")
    return declare_board_file(board(*children, **attrs)).ir


class BoardTests(unittest.TestCase):
    def test_a_board_declares_the_board_half(self):
        g = declared(
            component(name="R1", footprint="smd-0805", pcb_x=10, pcb_y=10),
            component(name="R2", footprint="axial-7.62", pcb_x=25, pcb_y=10, pcb_rotation=90, layer="bottom"),
            component(name="V1", footprint="smd-0805"),
            trace(layer="F.Cu", width=0.2, points=[[11, 10], [18, 14], [24, 10]], from_=".R1 > .pin2", to=".R2 > .1"),
            trace(layer="B.Cu", width=0.25, points=[[18, 14], [18, 20]], from_=".VIA1"),
            via(name="VIA1", pcb_x=18, pcb_y=14, drill=0.4, diameter=0.8),
            width=40, height=30, core=1.5, copper=0.035,
        )
        self.assertEqual(g["meta"]["schematic"], "Divider.sch.tsx")
        self.assertEqual(g["outputs"], ["board"])
        self.assertEqual(g["nodes"]["board"]["inputs"]["thicknessMm"], 1.57)
        self.assertEqual(g["nodes"]["board"]["inputs"]["stack"], {"wire": {"node": "stack", "port": "stack"}})
        self.assertEqual(g["nodes"]["fp_R1"]["inputs"], {"ref": "R1", "footprint": "Authored:smd-0805", "placement": {"x": 10, "y": 10, "rot": 0, "side": "top"}})
        self.assertEqual(g["nodes"]["fp_R2"]["inputs"]["placement"], {"x": 25, "y": 10, "rot": 90, "side": "bottom"})
        self.assertNotIn("placement", g["nodes"]["fp_V1"]["inputs"])
        self.assertEqual(g["nodes"]["cu_1"]["inputs"], {
            "kind": "run", "points": [{"x": 11, "y": 10, "id": "start"}, {"x": 18, "y": 14, "id": "p1"}, {"x": 24, "y": 10, "id": "end"}],
            "widthMm": 0.2, "layer": "F.Cu", "rule": "any",
            "terminals": [{"point": 0, "ref": "R1", "number": "2"}, {"point": 2, "ref": "R2", "number": "1"}]})
        self.assertEqual(g["nodes"]["cu_2"]["inputs"]["terminals"], [{"point": 0, "via": "VIA1"}])
        self.assertEqual(g["nodes"]["VIA1"]["inputs"], {"kind": "via", "points": [{"x": 18, "y": 14}], "drillMm": 0.4, "padDiameterMm": 0.8, "layers": ["F.Cu", "B.Cu"]})

    def test_a_pcb_py_file_runs_and_each_node_names_its_call(self):
        out = run_module('from commandagi.design.pcb import board, component, trace\n'
                         'result = board(\n'
                         '    component(name="R1", footprint="smd-0805", pcb_x=1, pcb_y=2),\n'
                         '    trace(layer="F.Cu", width=0.2, points=[[0, 0], [1, 0]], from_=".R1 > .pin1"),\n'
                         '    schematic="Divider.sch.tsx",\n'
                         ')\n', "Divider.pcb.py")
        nodes = out["graph"]["nodes"]
        self.assertEqual(nodes["fp_R1"]["inputs"]["placement"], {"x": 1, "y": 2, "rot": 0, "side": "top"})
        self.assertNotIn("board", nodes)
        at = nodes["fp_R1"]["meta"]["source"]
        self.assertEqual((at["tag"], at["line"]), ("component", 3))
        self.assertEqual(at["props"]["pcb_x"]["value"], 1)
        self.assertEqual((nodes["cu_1"]["meta"]["source"]["tag"], nodes["cu_1"]["meta"]["source"]["line"]), ("trace", 4))
        self.assertIn("sourceMap", out["graph"]["meta"])

    def test_ends_name_a_via_or_another_traces_point_before_or_after_it(self):
        g = declared(
            trace(layer="F.Cu", width=0.2, points=[[0, 0], [5, 0]], to=".VIA1"),
            trace(name="T1", layer="F.Cu", width=0.2, points=[[5, 0], [5, 5], [9, 5]]),
            trace(layer="F.Cu", width=0.2, points=[[5, 5], [5, 9]], from_=".T1 > .1"),
            via(name="VIA1", pcb_x=5, pcb_y=0, drill=0.3, diameter=0.6),
        )
        self.assertNotIn("board", g["nodes"])
        self.assertEqual(g["nodes"]["cu_1"]["inputs"]["terminals"], [{"point": 1, "via": "VIA1"}])
        self.assertEqual(g["nodes"]["cu_2"]["inputs"]["terminals"], [{"point": 0, "run": "T1", "runPoint": "p1"}])

    def test_a_library_footprint_is_its_ref_and_its_library(self):
        g = declared(component(name="U1", footprint="Package_SO:SOIC-8", library="footprints.pretty", pcb_x=12, pcb_y=8, pcb_rotation=90))
        self.assertEqual(g["nodes"]["fp_U1"]["inputs"], {"ref": "U1", "footprint": "Package_SO:SOIC-8", "library": "footprints.pretty",
                                                         "placement": {"x": 12, "y": 8, "rot": 90, "side": "top"}})
        with self.assertRaisesRegex(ValueError, "its ref, \"Library:Footprint\""):
            declared(component(name="U1", footprint="SOIC-8", library="footprints.pretty"))
        with self.assertRaisesRegex(ValueError, "a footprint library folder"):
            declared(component(name="U1", footprint="Package_SO:SOIC-8", library="SOIC-8.kicad_mod"))

    def test_what_a_kicad_board_holds(self):
        layers = [{"ordinal": 0, "name": "F.Cu", "type": "signal"}, {"ordinal": 4, "name": "In1.Cu", "type": "signal"},
                  {"ordinal": 2, "name": "B.Cu", "type": "signal"}, {"ordinal": 25, "name": "Edge.Cuts", "type": "user"}]
        g = declared(
            stack(name="four-layer", label="JLC 4-layer", process={"name": "JLC"}, layers=[{"name": "F.Cu", "role": "conductor", "thickness": 0.035}]),
            kicad(version=20260206, generator="pcbnew", forms='(paper "A4")'),
            graphic(kind="line", layer="Edge.Cuts", points=[[0, 0], [40, 0]], width=0.1, id="e0", kicad="(stroke (type solid))"),
            text(text="REV A", at=[2, 3], layer="F.SilkS", size=1, thickness=0.15),
            dimension(points=[[0, 0], [10, 0]], height=2, layer="Dwgs.User", width=0.1, text_size=1),
            net(name="GND", code=1),
            component(name="C1", footprint="Lib:C_0805", library="Board.pretty", pcb_x=4, pcb_y=5, uuid="u-c1"),
            arc(name="A1", layer="F.Cu", width=0.2, points=[[0, 0], [1, 1], [2, 0]], to=".C1 > .pin1"),
            via(name="V1", pcb_x=5, pcb_y=0, drill=0.3, diameter=0.6, layers=["F.Cu", "In1.Cu", "B.Cu"], pads=[".C1 > .pin2"], net="GND"),
            pour(layers=["In1.Cu"], points=[[0, 0], [9, 0], [9, 9]], terminals=[[0, ".V1"]], net="GND", kicad="(min_thickness 0.25)"),
            layers=layers,
        )
        self.assertEqual(g["nodes"]["board"]["inputs"], {"layers": layers, "stack": {"wire": {"node": "stack", "port": "stack"}}})
        self.assertEqual(g["nodes"]["stack"]["label"], "JLC 4-layer")
        facts = [n["inputs"] for n in g["nodes"].values() if n["type"] == "eda.boardfact"]
        self.assertEqual(facts[2], {"fact": "text", "text": "REV A", "at": {"x": 2, "y": 3}, "rot": 0, "layer": "F.SilkS", "size": 1, "sizeX": 1,
                                    "thickness": 0.15, "kind": "text"})
        self.assertEqual(facts[3]["textSize"], 1)
        self.assertEqual(g["nodes"]["A1"]["inputs"]["terminals"], [{"point": 2, "ref": "C1", "number": "1"}])
        self.assertEqual(g["nodes"]["V1"]["inputs"]["pads"], [{"ref": "C1", "number": "2"}])
        self.assertEqual(g["nodes"]["cu_1"]["inputs"]["terminals"], [{"point": 0, "via": "V1"}])

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "footprint is one of smd-0805"):
            declared(component(name="R1", footprint="0603"))
        with self.assertRaisesRegex(ValueError, "schX is the schematic's"):
            declared(component(name="R1", footprint="smd-0805", sch_x=3))
        with self.assertRaisesRegex(ValueError, "pcbX and pcbY together"):
            declared(component(name="R1", footprint="smd-0805", pcb_x=3))
        with self.assertRaisesRegex(ValueError, "a list of 3 \\[x, y\\]"):
            declared(arc(layer="F.Cu", width=0.2, points=[[0, 0], [1, 0]]))
        with self.assertRaisesRegex(ValueError, "no component or trace R9"):
            declared(trace(layer="F.Cu", width=0.2, points=[[0, 0], [1, 0]], from_=".R9 > .pin1"))
        with self.assertRaisesRegex(ValueError, "two elements are called V1"):
            declared(component(name="V1", footprint="smd-0805"), via(name="V1", pcb_x=0, pcb_y=0, drill=0.3, diameter=0.6))
        with self.assertRaisesRegex(ValueError, "relative to this file"):
            declared(schematic="/abs.sch.tsx")
        with self.assertRaisesRegex(TypeError, "holds nothing"):
            component(trace(layer="F.Cu"))
        with self.assertRaisesRegex(TypeError, "pcb_x"):
            component(name="R1", pcbX=3)


if __name__ == "__main__":
    unittest.main()
