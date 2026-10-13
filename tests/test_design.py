"""commandagi.design declares the op graph and nothing else — the same graphs as the TypeScript SDK.
Run: python -m unittest discover -s tests"""
import json
import unittest

from commandagi.design import (board, box, channels, circuit, component, connect, cylinder, extrude, fillet, footprints, graph,
                               hole, input_, linear_pattern, net, node, part, part_type_for, run_module, sketch, subtract, union)
from commandagi.design import cadquery as cq


def wire(node, port="out"):
    return {"wire": {"node": node, "port": port}}


class GraphTests(unittest.TestCase):
    def test_graph_declares_wires_inputs_and_channels(self):
        def body():
            gain = input_("gain", 0.8, min=0, max=1)
            a = node("oscillator", {"frequency": 440})
            b = node("oscillator", {"frequency": 660})
            return node("mixer", {"gain": gain, **channels("channels", [a, b])})

        g = graph("Mix", body).ir
        self.assertEqual(list(g["nodes"]), ["gain", "oscillator", "oscillator_2", "mixer"])
        self.assertEqual(g["nodes"]["gain"], {"id": "gain", "type": "input", "label": "gain", "inputs": {"value": 0.8, "min": 0, "max": 1}})
        self.assertEqual(g["nodes"]["mixer"]["inputs"], {"gain": wire("gain"), "channels.1": wire("oscillator"), "channels.2": wire("oscillator_2")})
        self.assertEqual(g["outputs"], ["mixer"])

    def test_a_wire_drives_a_whole_port(self):
        with self.assertRaisesRegex(ValueError, "a wire drives a whole port"):
            graph("G", lambda: node("x", {"at": [node("y"), 2]}))
        with self.assertRaisesRegex(RuntimeError, "must be called inside part"):
            node("x")


class CadTests(unittest.TestCase):
    def test_part_cut_pattern_and_offset_sketch(self):
        def body():
            plate = box(size=(60, 40, 5), center=(0, 0, 2.5), name="Plate")
            pin = cylinder(base=(-22, 0, 0), radius=1.6, height=5, name="Pin hole")
            cut = subtract(plate, pin)
            holes = linear_pattern(pin, direction=(1, 0, 0), spacing=44, count=2)
            boss = extrude(sketch(("XY", 5), lambda s: s.circle(radius=6)), distance=8)
            return [holes, boss, cut]

        g = part("Bracket", body).ir
        self.assertEqual(g["nodes"]["Plate"]["inputs"], {"center": [0, 0, 2.5], "size": [60, 40, 5], "operation": "new"})
        self.assertEqual(g["nodes"]["Pin_hole"]["inputs"]["operation"], "cut")
        self.assertEqual(g["nodes"]["Pin_hole"]["inputs"]["base.1"], wire("Plate"))
        self.assertEqual(g["nodes"]["LinearPattern_1"]["inputs"]["seed"], wire("Pin_hole"))
        datum = next(n for n in g["nodes"].values() if n["type"] == "datumPlane")
        sk = next(n for n in g["nodes"].values() if n["type"] == "sketch")
        self.assertEqual(sk["inputs"]["plane"], wire(datum["id"]))


    def test_a_feature_is_wired_to_the_heads_of_its_body_and_to_its_last_feature(self):
        """What a feature acts on, and what runs first, in two wires: a part of n features declares about 2n wires,
        not n². (A wire to every earlier feature made a plate of 129 holes 566 kB.)"""
        def body(n):
            plate = box(size=(n * 10 + 10, 30, 6), center=(0, 0, 3), name="Plate")
            for i in range(n):
                plate = hole(plate, at=(i * 10, 0, 6), diameter=4, depth=6)
            boss = box(size=(4, 4, 4), center=(0, 10, 8), name="Boss")
            plate = union(plate, boss)
            return fillet(plate, radius=1, edges=[(0, -15, 3)])

        g = part("Rail", lambda: body(3)).ir
        wires = lambda node: {k: v["wire"]["node"] for k, v in g["nodes"][node]["inputs"].items() if isinstance(v, dict) and "wire" in v}
        self.assertEqual(wires("Hole"), {"base.1": "Plate"})
        self.assertEqual(wires("Hole_2"), {"base.1": "Plate", "base.2": "Hole"})
        self.assertEqual(wires("Hole_3"), {"base.1": "Plate", "base.2": "Hole_2"})
        self.assertEqual(wires("Boss"), {"base.1": "Plate", "base.2": "Hole_3"})
        self.assertEqual(wires("Fillet_1"), {"on.1": "Plate", "on.2": "Boss"})

        size = lambda n: len(json.dumps(part("Rail", lambda: body(n)).ir))
        per_hole = [(size(b) - size(a)) / (b - a) for a, b in ((40, 80), (80, 160))]
        self.assertLess(abs(per_hole[1] - per_hole[0]), 16, per_hole)
        self.assertLess(size(129), 40_000)

    def test_a_solid_made_beside_a_tool_stays_a_body_of_the_result(self):
        def body():
            plate = box(size=(40, 40, 4), name="Plate")
            post = cylinder(radius=2, height=10, name="Post")
            cap = cylinder(radius=4, height=2, base=(0, 0, 10), name="Cap", operation="add", after=[post])
            return subtract(plate, cap)

        g = part("Capped", body).ir
        wires = lambda node: [v["wire"]["node"] for k, v in sorted(g["nodes"][node]["inputs"].items()) if isinstance(v, dict) and "wire" in v]
        # The cap is cut from the plate; the post it was made on is still a solid of what comes back.
        self.assertEqual(wires("Cap"), ["Plate"])
        self.assertEqual(g["nodes"]["Cap"]["inputs"]["operation"], "cut")


class EdaTests(unittest.TestCase):
    def test_part_type_is_the_engines_hash(self):
        self.assertEqual(part_type_for([{"id": "p1", "number": "1", "name": "1"}, {"id": "p2", "number": "2", "name": "2"}]), "eda.part.fe2410c4")

    def test_circuit_nets_by_name_and_connection(self):
        def body():
            board(width=30, height=20)
            j1 = component(ref="J1", footprint=footprints.pin_header(2), at=(4, 8))
            r1 = component(ref="R1", value="330", footprint=footprints.chip("0603", "R"), at=(12, 10))
            d1 = component(ref="D1", value="red", footprint=footprints.chip("0603", "LED"), at={"x": 20, "y": 10, "rot": 90})
            net("VIN", j1.pin(1), r1.pin(1))
            connect(r1.pin(2), d1.pin("A"))
            net("GND", d1.pin("K"))
            net("GND", j1.pin(2))

        g = circuit("Blinker", body).ir
        self.assertEqual(g["id"], "eda:Blinker")
        self.assertEqual(g["outputs"], ["board"])
        self.assertEqual(g["nodes"]["part_D1"]["inputs"]["placement"], {"x": 20, "y": 10, "rot": 90, "side": "top"})
        nets = [(n["label"], n["inputs"]) for n in g["nodes"].values() if n["type"] == "eda.net"]
        self.assertEqual(nets, [
            ("VIN", {"pins.1": wire("part_J1", "p1"), "pins.2": wire("part_R1", "p1")}),
            ("GND", {"pins.1": wire("part_D1", "p1"), "pins.2": wire("part_J1", "p2")}),
            ("Net-(R1-Pad2)", {"pins.1": wire("part_R1", "p2"), "pins.2": wire("part_D1", "p2")}),
        ])


class CadQueryTests(unittest.TestCase):
    def test_box_with_a_grid_of_through_holes_on_its_top_face(self):
        wp = cq.Workplane("XY").box(60, 40, 5, centered=(True, True, False)).faces(">Z").workplane().rarray(44, 24, 2, 2).hole(3.2)
        g = run_module(
            "import commandagi.design.cadquery as cq\n"
            "w = param('width', 60, unit='mm')\n"
            "result = cq.Workplane('XY').box(w, 40, 5, centered=(True, True, False)).faces('>Z').workplane().rarray(44, 24, 2, 2).hole(3.2)\n",
            "plate.py",
            {"width": 80},
        )
        self.assertEqual(g["params"], {"width": {"default": 60, "unit": "mm"}})
        nodes = list(g["graph"]["nodes"].values())
        self.assertEqual(nodes[0]["type"], "box")
        self.assertEqual(nodes[0]["inputs"]["center"], [0, 0, 2.5])
        self.assertEqual(nodes[0]["inputs"]["size"], [80, 40, 5])
        holes = [n for n in nodes if n["type"] == "cylinder"]
        self.assertEqual([h["inputs"]["center"] for h in holes], [[-22, -12, 0], [-22, 12, 0], [22, -12, 0], [22, 12, 0]])
        self.assertTrue(all(h["inputs"]["operation"] == "cut" and h["inputs"]["height"] == 5 for h in holes))
        self.assertIsNotNone(wp.solid())

    def test_refuses_what_needs_topology(self):
        with self.assertRaisesRegex(NotImplementedError, "fillet"):
            cq.Workplane("XY").box(1, 1, 1).fillet(0.2)
        with self.assertRaisesRegex(NotImplementedError, 'faces\\("\\|Z"\\)'):
            cq.Workplane("XY").box(1, 1, 1).faces("|Z")

    def test_main_with_params(self):
        g = run_module(
            "from commandagi.design import part, box\n"
            "params = {'n': 2}\n"
            "def main(n):\n"
            "    return part('P', lambda: box(size=(n, 1, 1)))\n",
            "p.py",
            {"n": 3},
        )
        self.assertEqual(g["params"], {"n": {"default": 2}})
        self.assertEqual(g["graph"]["nodes"]["Box_1"]["inputs"]["size"], [3, 1, 1])


if __name__ == "__main__":
    unittest.main()
