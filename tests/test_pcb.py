"""A board in code declares the same nodes as the TypeScript SDK's JSX board (sdk/typescript/src/design/pcb.test.ts).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.pcb import (arc, board, bus, component, declare_board_file, diffpair, dimension, graphic, group, keepout, kicad, masks, net, netclass,
                                   objective, pour, stack, text, thermal, trace, via)


def declared(*children, **attrs):
    attrs.setdefault("schematic", "Divider.sch.tsx")
    return declare_board_file(board(*children, **attrs)).ir


class BoardTests(unittest.TestCase):
    def test_a_boards_copper_is_the_copper_it_has(self):
        box = {"points": [[0, 0], [9, 0], [9, 9]]}
        run = {"width": 0.2, "points": [[0, 0], [9, 0]]}
        curve = {"width": 0.2, "points": [[0, 0], [4, 4], [9, 0]]}
        barrel = {"pcb_x": 5, "pcb_y": 5, "drill": 0.3, "diameter": 0.6}

        def refused(words, *children, **attrs):
            with self.assertRaises(ValueError) as caught:
                declared(*children, **attrs)
            self.assertEqual(str(caught.exception), words)

        two = "the board has no copper layer X.Cu (it has F.Cu, B.Cu)"
        refused(f"<trace>: {two}", trace(layer="X.Cu", **run))
        refused(f"<arc>: {two}", arc(layer="X.Cu", **curve))
        refused(f"<via>: {two}", via(layers=["X.Cu", "B.Cu"], **barrel))
        refused(f"<pour>: {two}", pour(layers=["X.Cu"], **box))
        # A keep-out on copper the board lacks declares: the DRC reports it, `constraint`, and the board still opens.
        declared(keepout(layers=["X.Cu"], **box))
        refused("<trace>: the board has no copper layer In1.Cu (it has F.Cu, B.Cu)", trace(layer="In1.Cu", **run), width=9, height=9)
        refused("<via>: the ends of a via are two layers, not F.Cu twice", via(layers=["F.Cu", "F.Cu"], **barrel))
        with self.assertRaisesRegex(ValueError, r"the board has no copper layer In1\.Cu"):
            declared(via(layers=["F.Cu", "In1.Cu", "F.Cu"], **barrel))
        refused("<via>: the board has no copper layer B.Cu (it has F.Cu)", via(**barrel), layers=[{"ordinal": 0, "name": "F.Cu", "type": "signal"}])

        four = stack(layers=[{"name": n, "role": "conductor", "thickness": 0.035} for n in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]])
        inner = [trace(layer="In1.Cu", **run), arc(layer="In2.Cu", **curve), via(layers=["F.Cu", "In1.Cu"], **barrel), pour(layers=["In2.Cu"], **box), keepout(layers=["In1.Cu"], **box)]
        declared(four, *inner)
        declared(*inner, layers=[{"ordinal": 0, "name": "F.Cu"}, {"ordinal": 1, "name": "In1.Cu"}, {"ordinal": 2, "name": "In2.Cu"}, {"ordinal": 31, "name": "B.Cu"}])
        refused("<trace>: the board has no copper layer In3.Cu (it has F.Cu, B.Cu, In1.Cu, In2.Cu)", four, trace(layer="In3.Cu", **run))
        # A mask or a dielectric named like copper is no copper.
        with self.assertRaisesRegex(ValueError, r"no copper layer In1\.Cu"):
            declared(stack(layers=[{"name": "F.Cu", "role": "conductor"}, {"name": "In1.Cu", "role": "dielectric"}]), trace(layer="In1.Cu", **run))
        with self.assertRaisesRegex(ValueError, "layer is a copper layer"):
            declared(trace(layer="Dwgs.User", **run), layers=[{"ordinal": 0, "name": "F.Cu"}, {"ordinal": 40, "name": "Dwgs.User"}])

    def test_a_board_declares_the_board_half(self):
        g = declared(
            component(name="R1", footprint="smd-0805", pcb_x=10, pcb_y=10),
            component(name="R2", footprint="axial-7.62", pcb_x=25, pcb_y=10, pcb_rotation=90, layer="bottom", locked=True, ref_at=[0, -2.5], ref_rot=90, value_at=[0, 2.5]),
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
        self.assertTrue(g["nodes"]["fp_R2"]["inputs"]["locked"])
        self.assertNotIn("locked", g["nodes"]["fp_R1"]["inputs"])
        self.assertEqual(g["nodes"]["fp_R2"]["inputs"]["refAt"], [0, -2.5])
        self.assertEqual(g["nodes"]["fp_R2"]["inputs"]["refRot"], 90, "the reference text is turned a quarter where it sits")
        self.assertEqual(g["nodes"]["fp_R2"]["inputs"]["valueAt"], [0, 2.5])
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

    def test_a_trace_names_its_routing_rule(self):
        g = declared(
            trace(layer="F.Cu", width=0.2, points=[[0, 0], [5, 5]], rule="45"),
            trace(layer="F.Cu", width=0.2, points=[[0, 0], [5, 0]], rule="90"),
            trace(layer="F.Cu", width=0.2, points=[[0, 0], [3, 1]]),
            arc(layer="F.Cu", width=0.2, points=[[0, 0], [1, 1], [2, 0]]),
        )
        self.assertEqual([g["nodes"][f"cu_{i}"]["inputs"].get("rule") for i in (1, 2, 3, 4)], ["45", "90", "any", None])
        with self.assertRaisesRegex(ValueError, 'rule is "45", "90" or "any", not 45'):
            declared(trace(layer="F.Cu", width=0.2, points=[[0, 0], [1, 0]], rule=45))
        with self.assertRaisesRegex(ValueError, "rule is not read on a board"):
            declared(arc(layer="F.Cu", width=0.2, points=[[0, 0], [1, 1], [2, 0]], rule="45"))

    def test_a_library_footprint_is_its_ref_and_its_library(self):
        g = declared(component(name="U1", footprint="Package_SO:SOIC-8", library="footprints.pretty", pcb_x=12, pcb_y=8, pcb_rotation=90))
        self.assertEqual(g["nodes"]["fp_U1"]["inputs"], {"ref": "U1", "footprint": "Package_SO:SOIC-8", "library": "footprints.pretty",
                                                         "placement": {"x": 12, "y": 8, "rot": 90, "side": "top"}})
        with self.assertRaisesRegex(ValueError, "its ref, \"Library:Footprint\""):
            declared(component(name="U1", footprint="SOIC-8", library="footprints.pretty"))
        with self.assertRaisesRegex(ValueError, "a footprint library folder"):
            declared(component(name="U1", footprint="Package_SO:SOIC-8", library="SOIC-8.kicad_mod"))

    def test_a_polygon_says_its_arcs(self):
        pts = [[0, 0], [1, 0], [2, 1], [3, 0], [3, 3]]
        g = declared(graphic(kind="poly", layer="F.Mask", points=pts, width=0, filled=True, arcs=[1]), width=10, height=10)
        fact = [n["inputs"] for n in g["nodes"].values() if n["type"] == "eda.boardfact"][0]
        self.assertEqual(fact["arcStarts"], [1])
        with self.assertRaisesRegex(ValueError, "arcs is, on a poly"):
            declared(graphic(kind="poly", layer="F.Mask", points=pts, width=0, arcs=[3]), width=10, height=10)

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

    def test_an_ic_mask_layout_is_declared_by_its_polygons_units_and_library(self):
        polygons = [{"layer": 1, "datatype": 0, "points": [[0, 0], [4, 0], [4, 2], [0, 2]]},
                    {"layer": 2, "datatype": 1, "points": [[1, 1], [3, 1], [2, 1.5]]}]
        g = declared(masks(polygons=polygons, unit_um_per_db=0.001, lib_name="Inverter"), width=10, height=10)
        self.assertEqual(g["nodes"]["masks"]["inputs"], {"polygons": polygons, "unitUmPerDb": 0.001, "libName": "Inverter"})
        self.assertEqual(g["nodes"]["masks"]["label"], "Inverter")
        # A die is its layout alone: with no board fact the file declares the layout and no board.
        die = declared(masks(polygons=polygons, unit_um_per_db=0.001))
        self.assertNotIn("board", die["nodes"])
        self.assertEqual(die["nodes"]["masks"]["label"], "Masks")
        with self.assertRaisesRegex(ValueError, "<masks> needs polygons"):
            declared(masks(unit_um_per_db=0.001))
        with self.assertRaisesRegex(ValueError, "polygons is the mask layout's polygons"):
            declared(masks(polygons=[{"layer": 1, "datatype": 0, "points": [[0, 0], [1, 1]]}], unit_um_per_db=0.001))
        with self.assertRaisesRegex(ValueError, "unitUmPerDb is more than 0"):
            declared(masks(polygons=polygons, unit_um_per_db=0))
        with self.assertRaisesRegex(ValueError, "<masks> needs unitUmPerDb"):
            declared(masks(polygons=polygons))

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "footprint is one of smd-0805"):
            declared(component(name="R1", footprint="0603"))
        with self.assertRaisesRegex(ValueError, "schX is the schematic's"):
            declared(component(name="R1", footprint="smd-0805", sch_x=3))
        with self.assertRaisesRegex(ValueError, "pcbX and pcbY together"):
            declared(component(name="R1", footprint="smd-0805", pcb_x=3))
        with self.assertRaisesRegex(ValueError, "locked is true or left out"):
            declared(component(name="R1", footprint="smd-0805", locked=False))
        with self.assertRaisesRegex(ValueError, "refRot needs pcbX and pcbY"):
            declared(component(name="R1", footprint="smd-0805", ref_rot=90))
        with self.assertRaisesRegex(ValueError, "valueAt needs pcbX and pcbY"):
            declared(component(name="R1", footprint="smd-0805", value_at=[0, 1]))
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

    def test_the_layouts_constraints_are_board_facts(self):
        g = declared(
            netclass(name="supply", nets=["P24", "FIN*"], kind="power", width=0.5, clearance=0.25, current=0.5, criticality=0.8, max_vias=2),
            diffpair(name="usb", positive="D+", negative="D-", gap=0.15, max_skew=0.5),
            group(name="in1", parts=["R1", "U1"], region=[10, 30, 30, 50], near=".J1 > .pin5", max_distance=4, conviction=0.5),
            group(name="io", parts=["J1"], side="any", edge="left", mating="top"),
            keepout(name="label", points=[[80, 20], [96, 20], [96, 28]], no=["track", "via"]),
            thermal(name="fets", parts=["Q1", "Q2"], watts=0.3, spacing=4, away_from=["U1"], distance=6),
            bus(name="data", nets=["D*"], pitch=0.6),
            objective(weights={"wirelength": 1, "vias": 3}),
            width=100, height=60,
        )
        facts = [n["inputs"] for n in g["nodes"].values() if n["type"] == "eda.boardfact"]
        self.assertEqual(facts, [
            {"fact": "netclass", "name": "supply", "nets": ["P24", "FIN*"], "kind": "power", "width": 0.5, "clearance": 0.25, "current": 0.5, "criticality": 0.8, "maxVias": 2},
            {"fact": "diffpair", "name": "usb", "positive": "D+", "negative": "D-", "gap": 0.15, "maxSkew": 0.5},
            {"fact": "group", "name": "in1", "parts": ["R1", "U1"], "region": [10, 30, 30, 50], "near": ".J1 > .pin5", "maxDistance": 4, "conviction": 0.5},
            {"fact": "group", "name": "io", "parts": ["J1"], "side": "any", "edge": "left", "mating": "top"},
            {"fact": "keepout", "name": "label", "points": [[80, 20], [96, 20], [96, 28]], "no": ["track", "via"]},
            {"fact": "thermal", "name": "fets", "parts": ["Q1", "Q2"], "watts": 0.3, "spacing": 4, "awayFrom": ["U1"], "distance": 6},
            {"fact": "bus", "name": "data", "nets": ["D*"], "pitch": 0.6},
            {"fact": "objective", "weights": {"wirelength": 1, "vias": 3}},
        ])
        with self.assertRaisesRegex(ValueError, "kind is signal, power"):
            declared(netclass(name="a", nets=["X"], kind="loud"))
        rules = declared(netclass(name="Default", nets=["*"], width=0.2, min_width=0.15, clearance=0.2, edge_clearance=0.3, hole_clearance=0.15,
                                  inner={"clearance": 0.15, "width": 0.15}, min_spokes=1), width=60, height=40)
        self.assertEqual([n["inputs"] for n in rules["nodes"].values() if n["type"] == "eda.boardfact"], [
            {"fact": "netclass", "name": "Default", "nets": ["*"], "width": 0.2, "minWidth": 0.15, "clearance": 0.2, "edgeClearance": 0.3,
             "holeClearance": 0.15, "inner": {"clearance": 0.15, "width": 0.15}, "minSpokes": 1},
        ])
        with self.assertRaisesRegex(ValueError, "minWidth is at most width"):
            declared(netclass(name="a", nets=["X"], width=0.2, min_width=0.3))
        with self.assertRaisesRegex(ValueError, "the rules on inner copper layers"):
            declared(netclass(name="a", nets=["X"], inner={"gap": 0.1}))
        with self.assertRaisesRegex(ValueError, "minSpokes is a whole number from 0 to 4"):
            declared(netclass(name="a", nets=["X"], min_spokes=1.5))
        with self.assertRaisesRegex(ValueError, "maxDistance needs near"):
            declared(group(name="g", parts=["R1"], max_distance=3))
        with self.assertRaisesRegex(ValueError, 'edge is "left", "right", "top", "bottom"'):
            declared(group(name="g", parts=["J1"], edge="front"))
        with self.assertRaisesRegex(ValueError, "mating needs edge"):
            declared(group(name="g", parts=["J1"], mating="top"))
        with self.assertRaisesRegex(ValueError, "give awayFrom and distance together"):
            declared(thermal(name="t", parts=["Q1"], watts=1, away_from=["U1"]))
        with self.assertRaisesRegex(ValueError, "pitch"):
            declared(bus(name="b", nets=["D0"], pitch=-1))
        with self.assertRaisesRegex(ValueError, "width"):
            declared(bus(name="b", nets=["D0"], width=0.2))
        with self.assertRaisesRegex(ValueError, "one <objective>"):
            declared(objective(weights={"vias": 1}), objective(weights={"vias": 2}))


if __name__ == "__main__":
    unittest.main()
