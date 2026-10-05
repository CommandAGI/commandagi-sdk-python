"""The ontology's files declared in Python give what the TypeScript SDK's JSX gives (ontology.test.ts there): a world,
a definition, a dashboard and a geo project leave a run as the document's JSON ({format, document, sources} beside an
empty graph); a node graph is the editor's own op graph.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import (body, camera, channel, dashboard, date_range, declare_document, device, geoproject, graph_node,
                               opgraph, pane, region, run_module, scene, space, split, unit, wire, world)
from commandagi.design import graph_of


class OntologyTests(unittest.TestCase):
    def test_a_world_is_its_world_json(self):
        d = declare_document(world("Shop", "simulation",
                                   space(origin_mm=[0, 0, 0], size_mm=[4000, 3000, 2500]),
                                   unit(uid="arm", name="arm", device="../../devices/so-101/definition.tsx", position=[100, 0, 0], rotation=90),
                                   scene(body(id="cube", shape={"type": "box", "hx": 0.02}, at=[0, 0, 1]), hz=240)))
        self.assertEqual(d, {"format": "world", "sources": {}, "document": {
            "name": "Shop",
            "kind": "simulation",
            "space": {"origin_mm": [0, 0, 0], "size_mm": [4000, 3000, 2500]},
            "units": [{"uid": "arm", "name": "arm", "device": "../../devices/so-101/definition.tsx", "position": [100, 0, 0], "rotation": 90}],
            "scene": {"hz": 240, "bodies": [{"id": "cube", "shape": {"type": "box", "hx": 0.02}, "at": [0, 0, 1]}]},
        }})
        with self.assertRaisesRegex(ValueError, "said explicitly"):
            declare_document(world("W", "real"))
        with self.assertRaisesRegex(ValueError, 'two <unit> in <world> have uid "a"'):
            declare_document(world("W", "physical", unit(uid="a", name="a", device="d"), unit(uid="a", name="b", device="d")))
        with self.assertRaisesRegex(ValueError, 'speed is not read'):
            declare_document(world("W", "physical", unit(uid="a", name="a", device="d", speed=3)))

    def test_a_definition_a_dashboard_and_a_geo_project(self):
        d = declare_document(device("Arm", channel(id="joints", dir="duplex", medium="records", format="servo-bus", transport="serial", minIntervalMs=20)))
        self.assertEqual(d["document"]["channels"][0]["minIntervalMs"], 20)
        b = declare_document(dashboard("cockpit", split("x", 0.5, pane(id="a", kind="world"), pane(id="b", kind="devices")), region(side="left", tab="nav")))
        self.assertEqual(b["document"], {
            "format": "commandagi-dashboard",
            "name": "cockpit",
            "layout": {"kind": "split", "axis": "x", "ratio": 0.5, "children": [{"kind": "leaf", "paneId": "a"}, {"kind": "leaf", "paneId": "b"}]},
            "panes": {"a": {"kind": "world"}, "b": {"kind": "devices"}},
            "regions": {"left": {"tab": "nav"}},
        })
        p = declare_document(geoproject("p1", "Chokepoints", date_range("2015-01", "2030-01"), camera(centerLng=40, centerLat=25, scale=320)))
        self.assertEqual(p["document"], {"type": "geoeconomics/project", "schemaVersion": "1.0", "id": "p1", "name": "Chokepoints",
                                         "data": {"defaultDateRange": {"start": "2015-01", "end": "2030-01"}, "defaultCamera": {"centerLng": 40, "centerLat": 25, "scale": 320}}})

    def test_a_node_graph_is_the_editors_op_graph(self):
        g = graph_of(opgraph(
            graph_node("g", "gradient", x=40, y=80, shadeA=40),
            graph_node("b", "blur", x=300, y=80, radius=6, output=True),
            graph_node("m", "mix", inputs={"layers.2": None}),
            wire("g:out", "b:in"),
            wire("g:out", "b:radius"),
            wire("b:out", "m:layers.1"),
            name="Mix"))
        self.assertEqual(g, {
            "id": "nodegraph",
            "nodes": {
                "g": {"id": "g", "type": "gradient", "inputs": {"shadeA": 40}, "meta": {"x": 40, "y": 80}},
                "b": {"id": "b", "type": "blur", "inputs": {"radius": {"wire": {"node": "g", "port": "out"}, "value": 6}, "in": {"wire": {"node": "g", "port": "out"}}}, "meta": {"x": 300, "y": 80}},
                "m": {"id": "m", "type": "mix", "inputs": {"layers.2": None, "layers.1": {"wire": {"node": "b", "port": "out"}}}},
            },
            "outputs": ["b"],
            "meta": {"name": "Mix", "domain": "nodegraph"},
        })
        with self.assertRaisesRegex(ValueError, 'no <node id="z">'):
            graph_of(opgraph(graph_node("a", "t"), wire("a:out", "z:in")))

    def test_a_script_declares_a_world_in_the_runs_one_shape(self):
        source = ('from commandagi.design import world, unit\n'
                  'result = world("Yard", "physical", unit(uid="rover", name="rover", device="d.json", position=[0, 0, 0], rotation=0))\n')
        out = run_module(source, "worlds/yard/world.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "world")
        self.assertEqual(out["document"]["document"]["units"][0]["uid"], "rover")


if __name__ == "__main__":
    unittest.main()
