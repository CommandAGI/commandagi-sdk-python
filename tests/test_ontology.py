"""The ontology's files declared in Python give the same op graphs as the TypeScript SDK's JSX (ontology.test.ts there):
a world's records ride out one node each, in document order; a node graph is the editor's own op graph.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import (camera, channel, dashboard, date_range, device, geoproject, graph_node, opgraph, pane, region,
                               run_module, scene, body, space, split, unit, wire, world)
from commandagi.design import graph_of


class OntologyTests(unittest.TestCase):
    def test_a_world_is_its_records_as_nodes(self):
        g = graph_of(world("Shop", "simulation",
                           space(origin_mm=[0, 0, 0], size_mm=[4000, 3000, 2500]),
                           unit(uid="arm", name="arm", device="../../devices/so-101/definition.json", position=[100, 0, 0], rotation=90),
                           scene(body(id="cube", shape={"type": "box", "hx": 0.02}, at=[0, 0, 1]), hz=240)))
        self.assertEqual(g["meta"], {"domain": "world", "document": "world", "name": "Shop"})
        self.assertEqual(g["nodes"]["e2"], {"id": "e2", "type": "world.unit", "inputs": {"uid": "arm", "name": "arm", "device": "../../devices/so-101/definition.json", "position": [100, 0, 0], "rotation": 90}, "meta": {"parent": "e0"}})
        self.assertEqual([n["type"] for n in g["nodes"].values()], ["world.world", "world.space", "world.unit", "world.scene", "world.body"])
        self.assertEqual(g["nodes"]["e4"]["meta"], {"parent": "e3"})
        with self.assertRaisesRegex(ValueError, "said explicitly"):
            graph_of(world("W", "real"))
        with self.assertRaisesRegex(ValueError, 'two <unit> in <world> have uid "a"'):
            graph_of(world("W", "physical", unit(uid="a", name="a", device="d"), unit(uid="a", name="b", device="d")))
        with self.assertRaisesRegex(ValueError, 'speed is not read'):
            graph_of(world("W", "physical", unit(uid="a", name="a", device="d", speed=3)))

    def test_a_definition_a_dashboard_and_a_geo_project(self):
        d = graph_of(device("Arm", channel(id="joints", dir="duplex", medium="records", format="servo-bus", transport="serial", minIntervalMs=20)))
        self.assertEqual(d["nodes"]["e1"]["inputs"]["minIntervalMs"], 20)
        b = graph_of(dashboard("cockpit", split("x", 0.5, pane(id="a", kind="world"), pane(id="b", kind="devices")), region(side="left", tab="nav")))
        self.assertEqual([n["type"] for n in b["nodes"].values()], ["dashboard.dashboard", "dashboard.split", "dashboard.pane", "dashboard.pane", "dashboard.region"])
        p = graph_of(geoproject("p1", "Chokepoints", date_range("2015-01", "2030-01"), camera(centerLng=40, centerLat=25, scale=320)))
        self.assertEqual(p["nodes"]["e1"]["inputs"], {"start": "2015-01", "end": "2030-01"})

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

    def test_a_script_declares_a_world(self):
        source = ('from commandagi.design import world, unit\n'
                  'result = world("Yard", "physical", unit(uid="rover", name="rover", device="d.json", position=[0, 0, 0], rotation=0))\n')
        out = run_module(source, "worlds/yard/world.py")
        self.assertEqual(out["graph"]["nodes"]["e1"]["inputs"]["uid"], "rover")


if __name__ == "__main__":
    unittest.main()
