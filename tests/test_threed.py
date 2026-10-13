"""A 3D document, element by element, declares its graph — the same nodes the TypeScript SDK's JSX declares
(sdk/typescript src/design/threed.test.ts holds the same expectations).
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.threed import (THREED_FEATURES, assembly, body, box, chamfer, circle, constraint, cylinder, declare_threed,
                                      externalPart, extrude, feature, fillet, hole, import_, line, meshBody, parameter, part, plane,
                                      point, pointCloud, sketch, slot)


def plate():
    return part(
        parameter(name="depth", value=6, unit="mm", bindings=[{"target": "extrude1", "field": "distance"}]),
        sketch(
            point(id="p1", x=0, y=0), point(id="p2", x=40, y=0), point(id="p3", x=40, y=20),
            line(id="l1", a="p1", b="p2"), line(id="l2", a="p2", b="p3"), line(id="l3", a="p3", b="p1"),
            constraint(id="c1", kind="horizontal", entities=["l1"]),
            id="sketch1", name="Sketch1", plane={"type": "datum", "plane": "plane_xy"}),
        extrude(id="extrude1", name="Extrude1", profile={"sketch": "sketch1"}, distance=6, operation="new"),
        fillet(id="fillet1", name="Fillet1", radius=1, edges=[{"kind": "edge", "signature": {"point": [20, 0, 6]}}], consumes=["extrude1"], suppressed=True),
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
        self.assertEqual(n["fillet1"], {"id": "fillet1", "type": "fillet", "label": "Fillet1", "disabled": True, "inputs": {"radius": 1, "edges": [{"kind": "edge", "signature": {"point": [20, 0, 6]}}], "consumes": ["extrude1"]}})
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
               "        id='s1', plane={'type': 'datum', 'plane': 'plane_xy'},\n"
               "    ),\n"
               "    extrude(id='e1', profile={'sketch': 's1'}, distance=6, operation='new'),\n"
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
        g = graph(cylinder(id="fan/bore", center=[0, 0, 0], axis=[0, 0, 1], radius=2, height=5, operation="cut"), feature(type_="rotate", id="r1", name="rotate_y_30", axis=[0, 1, 0], angle=30))
        self.assertEqual(g["nodes"]["fan/bore"]["inputs"], {"center": [0, 0, 0], "axis": [0, 0, 1], "radius": 2, "height": 5, "operation": "cut"})
        self.assertEqual(g["nodes"]["r1"], {"id": "r1", "type": "rotate", "label": "rotate_y_30", "inputs": {"axis": [0, 1, 0], "angle": 30}})
        self.assertEqual(g["meta"]["presentation"], {"order": ["fan/bore", "r1"]})
        self.assertTrue(declare_threed(assembly(name="A"))["meta"]["isAssembly"])

    def test_a_feature_whose_fields_do_not_fit_its_type_is_refused_with_the_op_panels_sentence(self):
        def read(*children):
            return lambda: declare_threed(part(*children, name="P"))

        profile = {"sketch": "s1"}
        cases = [
            (read(extrude(id="e1", profile=profile, distance=-1, operation="new")), '<extrude id="e1">: distance: must be greater than 0 (got -1)'),
            (read(extrude(id="e1", profile=profile, distance=5, operation="glue", colour="red")),
             '<extrude id="e1">: operation: must be one of new, add, cut, intersect (got "glue"); colour: is not one of its fields'),
            (read(extrude(id="e1", distance=5, operation="new")), '<extrude id="e1">: profile: is required'),
            (read(sketch(circle(id="c", center="p", radius="big"), point(id="p", x=0, y=0), id="s1", plane={"type": "datum", "plane": "plane_xy"})),
             '<sketch id="s1">: sketch/segments/c/radius: must be number (got "string")'),
        ]
        for fn, message in cases:
            with self.assertRaises(ValueError) as caught:
                fn()
            self.assertEqual(str(caught.exception), message)
        # A large array kept in a file beside the document stands for the array.
        positions = {"$file": "P.assets/m/positions.f64", "mime": "application/octet-stream", "encoding": "f64le", "len": 9}
        self.assertIn("makeHuman", THREED_FEATURES)
        self.assertNotIn("makehuman", THREED_FEATURES)
        read(pointCloud(id="pc", positions=positions))()

    def test_a_hole_is_placed_and_faces_and_edges_are_chosen_by_a_query(self):
        top = {"kind": "face", "select": {"normal": [0, 0, 1], "farthest": [0, 0, 1]}}
        g = declare_threed(part(
            box(id="plate", center=[0, 0, 4], size=[100, 60, 8], operation="new"),
            sketch(point(id="a", x=-30, y=0), point(id="b", x=30, y=0), id="places", plane={"type": "datum", "plane": "plane_xy"}),
            hole(id="cbore", face=top, positions=[[10, 20, 8], [-10, 20, 8]], diameter=5.5, through=True, style="counterbore", head_diameter=10, head_depth=5),
            hole(id="pins", face=top, sketch="places", diameter=3, through=True, style="simple"),
            chamfer(id="rims", distance=0.5, edges=[{"kind": "edge", "select": {"any": [{"createdBy": "cbore"}, {"createdBy": "pins"}], "geometry": "circle", "radius": {"max": 3}}}]),
            fillet(id="corners", radius=2, edges=[{"kind": "edge", "select": {"parallel": [0, 0, 1], "not": {"inBox": {"min": [0, -99, -99], "max": [99, 99, 99]}}}}]),
            name="Plate",
        ))
        n = g["nodes"]
        self.assertEqual(n["cbore"]["inputs"]["positions"], [[10, 20, 8], [-10, 20, 8]])
        self.assertEqual(n["cbore"]["inputs"]["face"], top)
        self.assertEqual(n["pins"]["inputs"]["sketch"], "places")
        self.assertEqual(n["rims"]["inputs"]["edges"][0]["select"]["any"][1], {"createdBy": "pins"})
        # No feature names what it follows: the order of the file says it (the reader fills `consumes`).
        self.assertNotIn("consumes", n["rims"]["inputs"])
        self.assertEqual(g["meta"]["presentation"]["order"], ["plate", "places", "cbore", "pins", "rims", "corners"])

        def refused(el):
            with self.assertRaises(ValueError) as e:
                declare_threed(part(box(id="plate", size=[1, 1, 1]), el))
            return str(e.exception)

        self.assertIn("positions/0: needs at least 3 items (got 2)", refused(hole(id="h", face=top, positions=[[1, 2]])))
        self.assertIn("is not one of its fields", refused(fillet(id="f", edges=[{"kind": "edge", "select": {"vertical": True}}])))
        self.assertIn("geometry", refused(fillet(id="f", edges=[{"kind": "edge", "select": {"geometry": "helix"}}])))

    def test_a_required_field_with_a_declared_default_may_be_left_out(self):
        # The TypeScript and Rust SDKs read the same assembly to the same inputs.
        def read(*children):
            return declare_threed(assembly(*children, name="A"))

        identity = {"position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": 1}
        g = read(externalPart(id="bare", path="bracket.3d.tsx"),
                 externalPart(id="moved", path="bracket.3d.tsx", placement={"position": [10, 0, 5]}, operation="add"))
        self.assertEqual(g["nodes"]["bare"]["inputs"], {"path": "bracket.3d.tsx", "placement": identity, "operation": "new"})
        # A placement that says only where: its orientation and scale are the identity's. The author's values stay.
        self.assertEqual(g["nodes"]["moved"]["inputs"],
                         {"path": "bracket.3d.tsx", "placement": {"position": [10, 0, 5], "quaternion": [0, 0, 0, 1], "scale": 1}, "operation": "add"})
        # An optional field stays absent: its absence is a value the kernel reads.
        self.assertNotIn("importer", g["nodes"]["bare"]["inputs"])
        # A defaulted field the author wrote wrong is still refused, and a field with no default is still required.
        for child, message in (
            (externalPart(id="p", path="b.3d.tsx", placement={"scale": "big"}), '<externalPart id="p">: placement/scale: must be number (got "string")'),
            (import_(id="i", format="step"), '<import id="i">: data: is required'),
        ):
            with self.assertRaises(ValueError) as caught:
                read(child)
            self.assertEqual(str(caught.exception), message)

    def test_a_world_body_written_by_tsx_reads_with_its_declared_fields(self):
        # The element an ingest writes in a .3d.tsx (sdk/typescript threed.test.ts reads the same one).
        def world_body(collider, restitution=0.1):
            return declare_threed(part(meshBody(
                id="world/t", name="t", positions=[0, 0, 0, 1000, 0, 0, 0, 1000, 0, 1000, 1000, 0], indices=[0, 1, 2, 1, 3, 2],
                world_collider=collider, world_center=[0, 0, 100], world_friction=0.8, world_restitution=restitution,
                world_meta={"tile": "12/1/2", "res": 30}), name="W"))

        g = world_body({"type": "heightfield", "nx": 2, "ny": 2, "sizeX": 1000, "sizeY": 1000})
        self.assertEqual(g["nodes"]["world/t"]["inputs"]["worldMeta"], {"tile": "12/1/2", "res": 30})
        world_body({"type": "trimesh"})
        with self.assertRaises(ValueError) as caught:
            world_body({"type": "heightfield", "nx": 1, "ny": 2, "sizeX": 1000, "sizeY": 1000}, 2)
        self.assertEqual(str(caught.exception),
                         '<meshBody id="world/t">: worldCollider/nx: must be at least 2 (got 1); worldRestitution: must be at most 1 (got 2)')


if __name__ == "__main__":
    unittest.main()
