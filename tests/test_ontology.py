"""The ontology's files declared in Python give what the TypeScript SDK's JSX gives (ontology.test.ts there): a world,
a definition, a dashboard and a geo project leave a run as the document's JSON ({format, document, sources} beside an
empty graph, each element's call keyed by its tree path); a node graph is the editor's own op graph, each node with the
call that made it.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.element import declarer_of
from commandagi.design import firmware as fw
from commandagi.design.ontology import (body, camera, channel, dashboard, dateRange, device, geoproject, node, opgraph, pane, region,
                                        scene, split, unit, wire, world)


def declared(root):
    return declarer_of(root)(root, "Test")


class OntologyTests(unittest.TestCase):
    def test_a_world_is_its_world_json(self):
        d = declared(world(unit(uid="arm", name="arm", device="../../devices/so-101/definition.tsx", position=[100, 0, 0], rotation=90),
                           scene(body(id="cube", shape={"type": "box", "hx": 0.02}, at=[0, 0, 1]),
                                 camera(id="cam", at=[0, -0.7, 1], look_at=[0, 0, 0.76], fov_deg=50), hz=240),
                           name="Shop", kind="simulation"))["document"]
        self.assertEqual(d, {"format": "world", "sources": {}, "document": {
            "name": "Shop",
            "kind": "simulation",
            "units": [{"uid": "arm", "name": "arm", "device": "../../devices/so-101/definition.tsx", "position": [100, 0, 0], "rotation": 90}],
            "scene": {"hz": 240, "bodies": [{"id": "cube", "shape": {"type": "box", "hx": 0.02}, "at": [0, 0, 1]}],
                      "cameras": [{"id": "cam", "at": [0, -0.7, 1], "look_at": [0, 0, 0.76], "fov_deg": 50}]},
        }})
        # The world's model and the parts of it a run moves: attributes of world(), as the TypeScript SDK writes them.
        links = [{"node": "ram", "joint": {"unit": "press-1", "channel": "axes", "name": "z", "type": "prismatic", "axis": "z", "origin_mm": [0, 0, 0], "home": 0}}]
        posed = declared(world(name="Press", kind="physical", model="press.3d.tsx", links=links))["document"]["document"]
        self.assertEqual(posed, {"name": "Press", "kind": "physical", "model": "press.3d.tsx", "links": links, "units": []})
        with self.assertRaisesRegex(ValueError, "said explicitly"):
            declared(world(name="W", kind="real"))
        with self.assertRaisesRegex(ValueError, 'two <unit> in <world> have uid "a"'):
            declared(world(unit(uid="a", name="a", device="d"), unit(uid="a", name="b", device="d"), name="W", kind="physical"))
        with self.assertRaisesRegex(ValueError, "speed is not read"):
            declared(world(unit(uid="a", name="a", device="d", speed=3), name="W", kind="physical"))
        with self.assertRaisesRegex(ValueError, "focus is not read"):
            declared(world(scene(camera(id="cam", at=[0, 0, 1], look_at=[0, 1, 1], focus=2), hz=240), name="W", kind="simulation"))
        with self.assertRaisesRegex(ValueError, "stands in <scene>"):
            declared(world(camera(id="cam"), name="W", kind="simulation"))
        with self.assertRaisesRegex(TypeError, "<unit> holds nothing"):
            unit(world(name="W", kind="physical"))

    def test_a_definition_names_its_firmware_and_a_firmware_declares_its_channels(self):
        d = declared(device(channel(id="cam", dir="out", medium="video", format="video"), name="Cam", firmware="../../firmware/cam", revision="rev-a"))["document"]
        self.assertEqual({k: d["document"][k] for k in ("firmware", "revision")}, {"firmware": "../../firmware/cam", "revision": "rev-a"})
        f = declared(fw.firmware(fw.supports(revision="rev-a"), fw.channel(id="cam", dir="out", medium="video", format="video"), name="cam"))["document"]
        self.assertEqual(f["format"], "firmware")
        self.assertEqual(f["document"], {"name": "cam", "supports": [{"revision": "rev-a"}], "channels": [{"id": "cam", "dir": "out", "medium": "video", "format": "video"}]})

    def test_a_definition_a_dashboard_and_a_geo_project(self):
        d = declared(device(channel(id="joints", dir="duplex", medium="records", format="servo-bus", transport="serial", min_interval_ms=20),
                            name="Arm", model_number="A1", product_url="https://example.com/a1", price_usd=None))["document"]
        self.assertEqual(d["document"]["channels"][0]["minIntervalMs"], 20)
        # A definition's fields that are snake_case in its file keep their names.
        self.assertEqual([d["document"][k] for k in ("model_number", "product_url")], ["A1", "https://example.com/a1"])
        self.assertNotIn("modelNumber", d["document"])
        b = declared(dashboard(split(pane(id="a", kind="world"), pane(id="b", kind="devices"), axis="x", ratio=0.5),
                               region(side="left", tab="nav"), name="cockpit"))["document"]
        self.assertEqual(b["document"], {
            "format": "commandagi-dashboard",
            "name": "cockpit",
            "layout": {"kind": "split", "axis": "x", "ratio": 0.5, "children": [{"kind": "leaf", "paneId": "a"}, {"kind": "leaf", "paneId": "b"}]},
            "panes": {"a": {"kind": "world"}, "b": {"kind": "devices"}},
            "regions": {"left": {"tab": "nav"}},
        })
        with self.assertRaisesRegex(ValueError, "a <split> has two sides"):
            declared(dashboard(split(pane(id="a"), axis="x", ratio=0.5), name="d"))
        p = declared(geoproject(dateRange(start="2015-01", end="2030-01"), camera(center_lng=40, center_lat=25, scale=320),
                                id="p1", name="Chokepoints"))["document"]
        self.assertEqual(p["document"], {"type": "geoeconomics/project", "schemaVersion": "1.0", "id": "p1", "name": "Chokepoints",
                                         "data": {"defaultDateRange": {"start": "2015-01", "end": "2030-01"},
                                                  "defaultCamera": {"centerLng": 40, "centerLat": 25, "scale": 320}}})

    def test_a_node_graph_is_the_editors_op_graph(self):
        g = declared(opgraph(
            node(id="g", type="gradient", x=40, y=80, shade_a=40),
            node(id="b", type="blur", x=300, y=80, radius=6, output=True),
            node(id="m", type="mix", inputs={"layers.2": None}),
            wire(from_="g:out", to="b:in"),
            wire(from_="g:out", to="b:radius"),
            wire(from_="b:out", to="m:layers.1"),
            name="Mix"))["graph"]
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
            declared(opgraph(node(id="a", type="t"), wire(from_="a:out", to="z:in")))

    def test_a_document_names_each_elements_call_by_its_tree_path(self):
        out = run_module(
            "from commandagi.design.ontology import body, scene, unit, world\n"
            "result = world(\n"
            "    unit(uid='rover', name='rover', device='d.json', position=[0, 0, 0], rotation=0),\n"
            "    scene(body(id='cube'), hz=240),\n"
            "    name='Yard', kind='physical',\n"
            ")\n",
            "worlds/yard/world.py",
        )
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "world")
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in out["document"]["sources"].items()},
                         {"": ("world", 2), "unit#rover": ("unit", 3), "scene": ("scene", 4), "scene/body#cube": ("body", 4)})
        self.assertEqual(out["document"]["sources"]["unit#rover"]["props"]["uid"]["value"], "rover")
        # The map rides on the empty graph beside the document.
        self.assertEqual(out["graph"]["meta"]["sourceMap"]["language"], "py")

    def test_a_node_graph_names_each_nodes_call_and_each_wires_call(self):
        g = run_module(
            "from commandagi.design.ontology import node, opgraph, wire\n"
            "result = opgraph(\n"
            "    node(id='a', type='gradient', x=0, y=0),\n"
            "    node(id='b', type='blur', radius=6),\n"
            "    wire(from_='a:out', to='b:in'),\n"
            ")\n",
            "Mix.opgraph.py",
        )["graph"]
        b = g["nodes"]["b"]["meta"]
        self.assertEqual((b["source"]["tag"], b["source"]["line"]), ("node", 4))
        self.assertEqual(b["source"]["props"]["radius"]["value"], 6)
        self.assertEqual(list(b["sources"]), ["wire:in"])
        self.assertEqual((b["sources"]["wire:in"]["tag"], b["sources"]["wire:in"]["line"]), ("wire", 5))
        self.assertEqual(g["nodes"]["a"]["meta"]["x"], 0)


if __name__ == "__main__":
    unittest.main()
