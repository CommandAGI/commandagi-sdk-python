"""A 3D document, element by element, declares its graph — the same nodes the TypeScript SDK's JSX declares
(sdk/typescript src/design/threed.test.ts holds the same expectations).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.threed import (assembly, body, box, constraint, cylinder, declare_threed, extrude, feature, fillet, line,
                                      parameter, part, plane, point, sketch, slot)


def plate():
    return part(
        parameter(name="depth", value=6, unit="mm", bindings=[{"target": "extrude1", "field": "distance"}]),
        sketch(
            point(id="p1", x=0, y=0), point(id="p2", x=40, y=0), point(id="p3", x=40, y=20),
            line(id="l1", a="p1", b="p2"), line(id="l2", a="p2", b="p3"), line(id="l3", a="p3", b="p1"),
            constraint(id="c1", kind="horizontal", entities=["l1"]),
            id="sketch1", name="Sketch1", plane={"type": "datum", "plane": "plane_xy"}),
        extrude(id="extrude1", name="Extrude1", profile={"sketch": "sketch1"}, distance=6, operation="new"),
        fillet(id="fillet1", name="Fillet1", radius=1, edges=[], consumes=["extrude1"], suppressed=True),
        body(id="extrude1", material="aluminium-6061"),
        slot(name="environment", value={"gravity": [0, 0, -9.81]}),
        name="Plate",
    )


class ThreeDTests(unittest.TestCase):
    def test_a_part_declares_the_document_graph(self):
        g = declare_threed(plate())
        self.assertEqual(g["id"], "3d-plate")
        self.assertEqual(g["meta"], {"name": "Plate", "units": "mm", "presentation": {"order": ["sketch1", "extrude1", "fillet1"]}})
        n = g["nodes"]
        self.assertEqual(n["depth"], {"id": "depth", "type": "input", "label": "depth", "inputs": {"value": 6, "unit": "mm", "drives": [{"target": "extrude1", "field": "distance"}]}})
        self.assertEqual(n["extrude1"], {"id": "extrude1", "type": "extrude", "label": "Extrude1", "inputs": {"profile": {"sketch": "sketch1"}, "distance": 6, "operation": "new"}})
        self.assertEqual(n["fillet1"], {"id": "fillet1", "type": "fillet", "label": "Fillet1", "disabled": True, "inputs": {"radius": 1, "edges": [], "consumes": ["extrude1"]}})
        sk = n["sketch1"]["inputs"]["sketch"]
        self.assertEqual(sk["pointOrder"], ["p1", "p2", "p3"])
        self.assertEqual(sk["segments"]["l1"], {"id": "l1", "type": "line", "a": "p1", "b": "p2"})
        self.assertEqual(sk["constraints"]["c1"], {"id": "c1", "kind": "horizontal", "entities": ["l1"]})
        self.assertEqual(n["plane_xy"]["inputs"], {"origin": [0, 0, 0], "normal": [0, 0, 1], "xAxis": [1, 0, 0], "builtin": "XY"})
        self.assertEqual(n["bodyMeta"], {"id": "bodyMeta", "type": "3d.bodyMeta", "inputs": {"extrude1": {"material": "aluminium-6061"}}})
        self.assertEqual(n["environment"]["inputs"], {"gravity": [0, 0, -9.81]})

    def test_a_script_declares_it_too(self):
        src = "from commandagi.design.threed import assembly\nresult = assembly(name='A')\n"
        self.assertTrue(run_module(src, "a.3d.py")["graph"]["meta"]["isAssembly"])

    def test_each_node_carries_the_call_it_came_from(self):
        src = ("from commandagi.design.threed import body, extrude, line, part, point, sketch\n"
               "result = part(\n"
               "    sketch(\n"
               "        point(id='p1', x=0, y=0),\n"
               "        point(id='p2', x=40, y=0),\n"
               "        line(id='l1', a='p1', b='p2'),\n"
               "        id='s1',\n"
               "    ),\n"
               "    extrude(id='e1', profile={'sketch': 's1'}, distance=6),\n"
               "    body(id='e1', material='steel'),\n"
               "    name='P',\n"
               ")\n")
        g = run_module(src, "P.3d.py")["graph"]
        n = g["nodes"]
        self.assertEqual((n["e1"]["meta"]["source"]["tag"], n["e1"]["meta"]["source"]["line"]), ("extrude", 9))
        self.assertEqual(n["e1"]["meta"]["source"]["props"]["distance"]["value"], 6)
        self.assertEqual(n["s1"]["meta"]["source"]["line"], 3)
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in n["s1"]["meta"]["sources"].items()},
                         {"point:p1": ("point", 4), "point:p2": ("point", 5), "segment:l1": ("line", 6)})
        self.assertEqual(n["bodyMeta"]["meta"]["sources"]["e1"]["tag"], "body")
        self.assertNotIn("meta", n["plane_xy"])
        self.assertEqual(g["meta"]["sourceMap"]["language"], "py")

    def test_what_a_3d_document_cannot_say_is_refused_by_name(self):
        def doc(*children):
            return lambda: declare_threed(part(*children, name="P"))
        cases = [
            (doc(box(name="B")), "needs an id"),
            (doc(box(id="a"), plane(id="a")), 'the id "a" is both plane "a" and feature "a"'),
            (doc(sketch(line(id="l", a="p1", b="p2"), id="s")), "segment l's a names no point"),
            (doc(sketch(box(id="b"), id="s")), "<box> is not read in a sketch"),
            (doc(slot(name="features", value={})), "features is not a slot"),
            (doc(extrude(id="e", distance=float("inf"))), "not a finite number"),
            (doc(parameter(name="w", value="6")), "value is a number"),
            (doc(feature(type_="extrude", id="e")), r"a extrude is written extrude\(…\)"),
            (doc(box(id="a//b")), "an id is letters, digits, _ . - with / between them"),
            (lambda: declare_threed(part(name="P", builtin_planes=["XY"])), "builtinPlanes lists built-in planes"),
        ]
        for fn, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                fn()
        with self.assertRaisesRegex(TypeError, "<box> holds nothing"):
            box(point(id="p", x=0, y=0), id="b")
        with self.assertRaisesRegex(TypeError, "builtinPlanes is written builtin_planes"):
            part(builtinPlanes=[])

    def test_what_a_document_may_hold(self):
        def graph(*children, **props):
            return declare_threed(part(*children, name="P", **props))

        def planes(g):
            return sorted(n["id"] for n in g["nodes"].values() if n["type"] == "plane")

        self.assertEqual(planes(graph()), ["plane_xy", "plane_xz", "plane_yz"])
        self.assertEqual(planes(graph(builtin_planes=[])), [])
        xy = plane(id="XY", name="XY", origin=[0, 0, 0], normal=[0, 0, 1], x_axis=[1, 0, 0], builtin="XY")
        self.assertEqual(graph(xy)["nodes"]["XY"]["inputs"]["xAxis"], [1, 0, 0])
        self.assertEqual(planes(graph(xy, builtin_planes=["plane_xz"])), ["XY", "plane_xz"])
        g = graph(cylinder(id="fan/bore", radius=2), feature(type_="rotate", id="r1", name="rotate_y_30", axis=[0, 1, 0], angle=30))
        self.assertEqual(g["nodes"]["fan/bore"]["inputs"], {"radius": 2})
        self.assertEqual(g["nodes"]["r1"], {"id": "r1", "type": "rotate", "label": "rotate_y_30", "inputs": {"axis": [0, 1, 0], "angle": 30}})
        self.assertEqual(g["meta"]["presentation"], {"order": ["fan/bore", "r1"]})
        self.assertTrue(declare_threed(assembly(name="A"))["meta"]["isAssembly"])


if __name__ == "__main__":
    unittest.main()
