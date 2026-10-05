"""commandagi.design.twod declares the 2D editors' own nodes — the same graphs as the TypeScript SDK's twod.ts for the
same document (its JSX): a drawing's composite and layer groups, d as subpaths, the paint stack with stroke chains
carrying the layer's fields, photo adjustments by tag, the nest's one-of nodes and parts, and the refusals by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module, twod


def wire(node, port="out"):
    return {"wire": {"node": node, "port": port}}


class DrawingTests(unittest.TestCase):
    def test_a_drawing_declares_the_composite_layers_shapes_and_d(self):
        g = twod.drawing(
            twod.layer(
                twod.rect(x=1, y=2, w=3, h=4, fill="#000000"),
                twod.group(
                    twod.ellipse(cx=5, cy=6, rx=7, ry=7),
                    twod.blur(twod.path(d="M 0 0 L 10 0 C 1 2 3 4 5 6 Q 7 8 9 9 Z", label="Edge"), radius=2),
                    name="Badge",
                ),
                name="Layer 1",
            ),
            name="Poster", width=800, height=600, background="#ffffff",
        ).ir
        self.assertEqual(g["meta"], {"name": "Poster", "width": 800, "height": 600, "background": "#ffffff"})
        self.assertEqual(g["outputs"], ["composite"])
        self.assertEqual(g["nodes"]["composite"], {"id": "composite", "type": "composite", "label": "Output", "inputs": {"background": "#ffffff", "layers.1": wire("group_2")}})
        self.assertEqual(g["nodes"]["group_2"]["inputs"], {"name": "Layer 1", "children.1": wire("rect"), "children.2": wire("group")})
        self.assertEqual(g["nodes"]["group"]["inputs"], {"name": "Badge", "children.1": wire("ellipse"), "children.2": wire("blur")})
        self.assertEqual(g["nodes"]["blur"]["inputs"], {"radius": 2, "in": wire("Edge")})
        self.assertEqual(g["nodes"]["Edge"]["inputs"]["subpaths"], [
            {"start": {"x": 0, "y": 0}, "segs": [{"to": {"x": 10, "y": 0}}, {"c1": {"x": 1, "y": 2}, "c2": {"x": 3, "y": 4}, "to": {"x": 5, "y": 6}}, {"c1": {"x": 7, "y": 8}, "to": {"x": 9, "y": 9}}], "closed": True},
        ])

    def test_a_script_returns_a_drawing(self):
        out = run_module("from commandagi.design import twod\nresult = twod.drawing(twod.layer(twod.rect(x=1, y=1, w=2, h=2)), name='P')\n", "P.draw.py")
        self.assertEqual(sorted(n["type"] for n in out["graph"]["nodes"].values()), ["composite", "group", "rect"])


class StackTests(unittest.TestCase):
    def test_strokes_chain_onto_their_layer_and_carry_its_fields(self):
        g = twod.painting(
            twod.fill(name="Paper", color=[1, 1, 1, 1]),
            twod.layer(
                twod.stroke(points=[[1, 2, 0.5, 0], [3, 4, 0.5, 16, 10, 20]], brush={"kind": "round", "size": 4}, color=[0, 0, 0, 1]),
                twod.stroke(points=[[5, 6, 1, 0]], color=[1, 0, 0, 1]),
                name="Ink", opacity=0.5, x=0, y=0, width=100, height=80, src="Sketch.assets/ink.png",
            ),
            name="Sketch", width=100, height=80, background=[1, 1, 1, 1],
        ).ir
        self.assertEqual(g["nodes"]["doc"]["inputs"], {"name": "Sketch", "width": 100, "height": 80, "background": [1, 1, 1, 1], "layers.1": wire("paint.fill"), "layers.2": wire("paint.stroke_2")})
        self.assertEqual(g["nodes"]["paint.layer"]["inputs"]["__asset"], {"kind": "file", "$file": "Sketch.assets/ink.png", "mime": "image/png"})
        self.assertEqual(g["nodes"]["paint.stroke"]["inputs"], {
            "name": "Ink", "visible": True, "opacity": 0.5, "blend": "normal",
            "points": [{"x": 1, "y": 2, "pressure": 0.5, "t": 0}, {"x": 3, "y": 4, "pressure": 0.5, "t": 16, "tiltX": 10, "tiltY": 20}],
            "brush": {"kind": "round", "size": 4}, "color": [0, 0, 0, 1], "src": wire("paint.layer"),
        })
        self.assertEqual(g["meta"], {"domain": "paint", "name": "Sketch"})

    def test_a_photos_adjustments_are_tags_and_a_rasters_children_its_filters(self):
        g = twod.photo(
            twod.raster(twod.element("gaussianBlur", radius=3), name="Photo", src="Harbour.png"),
            twod.element("exposure", name="Exposure", ev=0.35, offset=0, gamma=1),
            name="Harbour", width=1280, height=720,
        ).ir
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"], {"name": "Exposure", "adjustment": {"type": "exposure", "ev": 0.35, "offset": 0, "gamma": 1}})
        self.assertEqual(g["nodes"]["photo.filter"]["inputs"], {"name": "Photo", "visible": True, "opacity": 1, "blend": "normal", "filter": {"type": "gaussianBlur", "radius": 3}, "src": wire("photo.raster")})
        self.assertEqual(g["nodes"]["doc"]["inputs"]["layers.1"], wire("photo.filter"))

    def test_a_gradients_from_is_written_from_(self):
        g = twod.photo(twod.gradient(shape="linear", from_=[0, 0], to=[1, 1], stops=[])).ir
        self.assertEqual(g["nodes"]["photo.gradient"]["inputs"], {"shape": "linear", "from": [0, 0], "to": [1, 1], "stops": []})


    def test_a_mask_is_the_one_layer_it_holds_wired_to_the_node_it_masks(self):
        g = twod.photo(
            twod.element("exposure", twod.mask(twod.gradient()), name="Sky", ev=-0.5),
            twod.raster(twod.element("gaussianBlur", twod.mask(twod.fill(color=[1, 1, 1, 1])), radius=2), src="a.png"),
        ).ir
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"]["mask"], wire("photo.gradient"))
        self.assertEqual(g["nodes"]["photo.filter"]["inputs"]["mask"], wire("photo.fill"))
        self.assertNotIn("mask", g["nodes"]["photo.raster"]["inputs"])
        self.assertEqual(g["nodes"]["doc"]["inputs"]["layers.1"], wire("photo.adjust"))
        with self.assertRaisesRegex(ValueError, "holds one layer"):
            twod.photo(twod.element("exposure", twod.mask()))


class NestTests(unittest.TestCase):
    def test_a_nest_declares_its_sheet_stock_options_and_parts(self):
        g = twod.nest(
            twod.sheet(widthMm=600, heightMm=400, marginMm=5),
            twod.stock(materialId="plywood", thicknessMm=3, machine={"powerW": 40}),
            twod.options(resolutionMm=1, spacingMm=1, rotations=[0, 90], maxSheets=8),
            twod.part(id="tab", label="Tab", quantity=2, outline=[[0, 0], [10, 0], [10, 5]]),
            safeZMm=5,
        ).ir
        self.assertEqual(g["nodes"]["nest"]["inputs"], {"safeZMm": 5, "sheet": wire("nest.sheet"), "stock": wire("nest.stock"), "options": wire("nest.options"), "parts.1": wire("tab")})
        self.assertEqual(g["nodes"]["tab"], {"id": "tab", "type": "nest.part", "label": "Tab", "inputs": {"quantity": 2, "outline": [[0, 0], [10, 0], [10, 5]]}})


class RefusalTests(unittest.TestCase):
    def test_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "src names an image file by relative path"):
            twod.painting(twod.layer(src="data:image/png;base64,AAAA"))
        with self.assertRaisesRegex(ValueError, "is painted on a layer: write it inside one"):
            twod.painting(twod.stroke(points=[]))
        with self.assertRaisesRegex(ValueError, "<sketch> is not declared in code yet"):
            twod.drawing(twod.layer(twod.element("sketch")))
        with self.assertRaisesRegex(ValueError, "absolute commands"):
            twod.subpaths_of("m 0 0 l 1 1", "<path>")
        with self.assertRaisesRegex(ValueError, "a nest needs its <sheet>"):
            twod.nest(twod.part(id="a"))


if __name__ == "__main__":
    unittest.main()
