"""A 3D document, element by element, declares the .3dx body — the same nodes the TypeScript SDK's JSX declares
(sdk/typescript src/design/threed.test.ts holds the same expectations).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import graph_of, run_module
from commandagi.design.threed import document, h


def plate():
    return h(
        "part",
        h("parameter", name="depth", value=6, unit="mm", bindings=[{"target": "extrude1", "field": "distance"}]),
        h("sketch",
          h("point", id="p1", x=0, y=0), h("point", id="p2", x=40, y=0), h("point", id="p3", x=40, y=20),
          h("line", id="l1", a="p1", b="p2"), h("line", id="l2", a="p2", b="p3"), h("line", id="l3", a="p3", b="p1"),
          h("constraint", id="c1", kind="horizontal", entities=["l1"]),
          id="sketch1", name="Sketch1", plane={"type": "datum", "plane": "plane_xy"}),
        h("extrude", id="extrude1", name="Extrude1", profile={"sketch": "sketch1"}, distance=6, operation="new"),
        h("fillet", id="fillet1", name="Fillet1", radius=1, edges=[], consumes=["extrude1"], suppressed=True),
        h("body", id="extrude1", material="aluminium-6061"),
        h("slot", name="environment", value={"gravity": [0, 0, -9.81]}),
        name="Plate",
    )


class ThreeDTests(unittest.TestCase):
    def test_a_part_declares_the_3dx_body(self):
        g = document(plate()).ir
        self.assertEqual(g["id"], "3dx-plate")
        self.assertEqual(g["meta"], {"name": "Plate", "units": "mm", "presentation": {"order": ["sketch1", "extrude1", "fillet1"]}})
        n = g["nodes"]
        self.assertEqual(n["depth"], {"id": "depth", "type": "input", "label": "depth", "inputs": {"value": 6, "unit": "mm", "drives": [{"target": "extrude1", "field": "distance"}]}})
        self.assertEqual(n["extrude1"], {"id": "extrude1", "type": "extrude", "label": "Extrude1", "inputs": {"profile": {"sketch": "sketch1"}, "distance": 6, "operation": "new"}})
        self.assertEqual(n["fillet1"], {"id": "fillet1", "type": "fillet", "label": "Fillet1", "disabled": True, "inputs": {"radius": 1, "edges": [], "consumes": ["extrude1"]}})
        sketch = n["sketch1"]["inputs"]["sketch"]
        self.assertEqual(sketch["pointOrder"], ["p1", "p2", "p3"])
        self.assertEqual(sketch["segments"]["l1"], {"id": "l1", "type": "line", "a": "p1", "b": "p2"})
        self.assertEqual(sketch["constraints"]["c1"], {"id": "c1", "kind": "horizontal", "entities": ["l1"]})
        self.assertEqual(n["plane_xy"]["inputs"], {"origin": [0, 0, 0], "normal": [0, 0, 1], "xAxis": [1, 0, 0], "builtin": "XY"})
        self.assertEqual(n["bodyMeta"], {"id": "bodyMeta", "type": "3d.bodyMeta", "inputs": {"extrude1": {"material": "aluminium-6061"}}})
        self.assertEqual(n["environment"]["inputs"], {"gravity": [0, 0, -9.81]})

    def test_a_script_declares_it_too(self):
        src = "from commandagi.design.threed import h\nresult = h('assembly', name='A')\n"
        self.assertTrue(run_module(src, "a.3d.py")["graph"]["meta"]["isAssembly"])
        self.assertEqual(graph_of(h("part", name="P"))["meta"]["name"], "P")

    def test_what_a_3d_document_cannot_say_is_refused_by_name(self):
        def doc(*children):
            return lambda: document(h("part", *children, name="P"))
        cases = [
            (doc(h("widget", id="w")), "<widget> is not read in a 3D document"),
            (doc(h("box", name="B")), "needs an id"),
            (doc(h("box", id="a"), h("plane", id="a")), 'the id "a" is both plane "a" and feature "a"'),
            (doc(h("sketch", h("line", id="l", a="p1", b="p2"), id="s")), "segment l's a names no point"),
            (doc(h("sketch", h("box", id="b"), id="s")), "<box> is not read in a sketch"),
            (doc(h("slot", name="features", value={})), "features is not a slot"),
            (doc(h("extrude", id="e", distance=float("inf"))), "not a finite number"),
            (doc(h("parameter", name="w", value="6")), "value is a number"),
        ]
        cases += [
            (doc(h("feature", type="extrude", id="e")), "a extrude is written <extrude>"),
            (doc(h("box", id="a//b")), "an id is letters, digits, _ . - with / between them"),
            (lambda: document(h("part", name="P", builtinPlanes=["XY"])), "builtinPlanes lists built-in planes"),
        ]
        for fn, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                fn()

    def test_what_a_3dx_may_hold(self):
        def graph(*children, **props):
            return document(h("part", *children, name="P", **props)).ir

        def planes(g):
            return sorted(n["id"] for n in g["nodes"].values() if n["type"] == "plane")

        self.assertEqual(planes(graph()), ["plane_xy", "plane_xz", "plane_yz"])
        self.assertEqual(planes(graph(builtinPlanes=[])), [])
        xy = h("plane", id="XY", name="XY", origin=[0, 0, 0], normal=[0, 0, 1], xAxis=[1, 0, 0], builtin="XY")
        self.assertEqual(planes(graph(xy, builtinPlanes=["plane_xz"])), ["XY", "plane_xz"])
        g = graph(h("cylinder", id="fan/bore", radius=2), h("feature", type="rotate", id="r1", name="rotate_y_30", axis=[0, 1, 0], angle=30))
        self.assertEqual(g["nodes"]["fan/bore"]["inputs"], {"radius": 2})
        self.assertEqual(g["nodes"]["r1"], {"id": "r1", "type": "rotate", "label": "rotate_y_30", "inputs": {"axis": [0, 1, 0], "angle": 30}})
        self.assertEqual(g["meta"]["presentation"], {"order": ["fan/bore", "r1"]})


if __name__ == "__main__":
    unittest.main()
