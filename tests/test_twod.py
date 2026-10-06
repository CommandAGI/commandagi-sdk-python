"""commandagi.design.twod declares the 2D editors' own nodes — the same graphs as the TypeScript SDK's twod.ts for the
same document (its JSX): a drawing's composite and layer groups, d as subpaths, placed pixels by file, the paint stack
with stroke chains carrying the layer's fields, photo adjustments by tag, masks, the nest's one-of nodes and parts, the
refusals by name, and where each node was written. Run: python -m unittest discover -s tests"""
import textwrap
import unittest

from commandagi.design import run_module
from commandagi.design.twod import (blur, drawing, ellipse, exposure, fill, from_twod, gaussianBlur, gradient, group, image, layer, mask,
                                    nest, options, painting, part, path, photo, raster, raster_layer, rect, sheet, stock, stroke,
                                    subpaths_of)


def wire(node, port="out"):
    return {"wire": {"node": node, "port": port}}


class DrawingTests(unittest.TestCase):
    def test_a_drawing_declares_the_composite_layers_shapes_and_d(self):
        g = from_twod(drawing(
            layer(
                rect(x=1, y=2, w=3, h=4, fill="#000000"),
                group(
                    ellipse(cx=5, cy=6, rx=7, ry=7),
                    blur(path(d="M 0 0 L 10 0 C 1 2 3 4 5 6 Q 7 8 9 9 Z", label="Edge"), radius=2),
                    name="Badge",
                ),
                name="Layer 1",
            ),
            name="Poster", width=800, height=600, background="#ffffff",
        ))
        self.assertEqual(g["meta"], {"name": "Poster", "width": 800, "height": 600, "background": "#ffffff"})
        self.assertEqual(g["outputs"], ["composite"])
        self.assertEqual(g["nodes"]["composite"], {"id": "composite", "type": "composite", "label": "Output", "inputs": {"background": "#ffffff", "layers.1": wire("group_2")}})
        self.assertEqual(g["nodes"]["group_2"]["inputs"], {"name": "Layer 1", "children.1": wire("rect"), "children.2": wire("group")})
        self.assertEqual(g["nodes"]["group"]["inputs"], {"name": "Badge", "children.1": wire("ellipse"), "children.2": wire("blur")})
        self.assertEqual(g["nodes"]["blur"]["inputs"], {"radius": 2, "in": wire("Edge")})
        self.assertEqual(g["nodes"]["Edge"]["inputs"]["subpaths"], [
            {"start": {"x": 0, "y": 0}, "segs": [{"to": {"x": 10, "y": 0}}, {"c1": {"x": 1, "y": 2}, "c2": {"x": 3, "y": 4}, "to": {"x": 5, "y": 6}}, {"c1": {"x": 7, "y": 8}, "to": {"x": 9, "y": 9}}], "closed": True},
        ])

    def test_an_image_and_a_raster_layer_name_their_files(self):
        g = from_twod(drawing(layer(image(src="photos/harbour.jpg", x=10, y=20, w=40, h=30), raster_layer(src="scan.png"), name="Pictures"),
                              width=100, height=80))
        nodes = {n["type"]: n for n in g["nodes"].values()}
        self.assertEqual(nodes["image"]["inputs"], {"x": 10, "y": 20, "w": 40, "h": 30,
                                                    "__asset": {"kind": "file", "$file": "photos/harbour.jpg", "mime": "image/jpeg"}})
        self.assertEqual(nodes["raster-layer"]["inputs"], {"__asset": {"kind": "file", "$file": "scan.png", "mime": "image/png"}})

    def test_each_node_names_the_call_it_came_from(self):
        out = run_module(textwrap.dedent("""\
            from commandagi.design.twod import drawing, layer, rect
            result = drawing(
                layer(
                    *[rect(x=i * 10, y=0, w=5, h=5) for i in range(2)],
                    name="L",
                ),
                name="P",
            )
            """), "P.draw.py")
        nodes = out["graph"]["nodes"]
        self.assertEqual(sorted(n["type"] for n in nodes.values()), ["composite", "group", "rect", "rect"])
        self.assertEqual({k: (n["meta"]["source"]["tag"], n["meta"]["source"]["line"]) for k, n in nodes.items()},
                         {"rect": ("rect", 4), "rect_2": ("rect", 4), "group": ("layer", 3), "composite": ("drawing", 2)})
        # One call made both rects: it ran twice, and its x is an expression.
        self.assertEqual(nodes["rect"]["meta"]["source"]["evaluations"], 2)
        self.assertEqual(nodes["rect"]["meta"]["source"]["props"]["x"]["expr"], "i * 10")


class StackTests(unittest.TestCase):
    def test_strokes_chain_onto_their_layer_and_carry_its_fields(self):
        g = from_twod(painting(
            fill(name="Paper", color=[1, 1, 1, 1]),
            layer(
                stroke(points=[[1, 2, 0.5, 0], [3, 4, 0.5, 16, 10, 20]], brush={"kind": "round", "size": 4}, color=[0, 0, 0, 1]),
                stroke(points=[[5, 6, 1, 0]], color=[1, 0, 0, 1]),
                name="Ink", opacity=0.5, x=0, y=0, width=100, height=80, src="Sketch.assets/ink.png",
            ),
            name="Sketch", width=100, height=80, background=[1, 1, 1, 1],
        ))
        self.assertEqual(g["nodes"]["doc"]["inputs"], {"name": "Sketch", "width": 100, "height": 80, "background": [1, 1, 1, 1],
                                                       "layers.1": wire("paint.fill"), "layers.2": wire("paint.stroke_2")})
        self.assertEqual(g["nodes"]["paint.layer"]["inputs"]["__asset"], {"kind": "file", "$file": "Sketch.assets/ink.png", "mime": "image/png"})
        self.assertEqual(g["nodes"]["paint.stroke"]["inputs"], {
            "name": "Ink", "visible": True, "opacity": 0.5, "blend": "normal",
            "points": [{"x": 1, "y": 2, "pressure": 0.5, "t": 0}, {"x": 3, "y": 4, "pressure": 0.5, "t": 16, "tiltX": 10, "tiltY": 20}],
            "brush": {"kind": "round", "size": 4}, "color": [0, 0, 0, 1], "src": wire("paint.layer"),
        })
        self.assertEqual(g["meta"], {"domain": "paint", "name": "Sketch"})

    def test_a_photos_adjustments_are_tags_and_a_rasters_children_its_filters(self):
        g = from_twod(photo(
            raster(gaussianBlur(radius=3), name="Photo", src="Harbour.png"),
            exposure(name="Exposure", ev=0.35, offset=0, gamma=1),
            name="Harbour", width=1280, height=720,
        ))
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"], {"name": "Exposure", "adjustment": {"type": "exposure", "ev": 0.35, "offset": 0, "gamma": 1}})
        self.assertEqual(g["nodes"]["photo.filter"]["inputs"], {"name": "Photo", "visible": True, "opacity": 1, "blend": "normal",
                                                                "filter": {"type": "gaussianBlur", "radius": 3}, "src": wire("photo.raster")})
        self.assertEqual(g["nodes"]["doc"]["inputs"]["layers.1"], wire("photo.filter"))

    def test_a_gradients_from_is_written_from_(self):
        g = from_twod(photo(gradient(shape="linear", from_=[0, 0], to=[1, 1], stops=[])), "Photo")
        self.assertEqual(g["nodes"]["photo.gradient"]["inputs"], {"shape": "linear", "from": [0, 0], "to": [1, 1], "stops": []})

    def test_a_mask_is_the_one_layer_it_holds_wired_to_the_node_it_masks(self):
        g = from_twod(photo(
            exposure(mask(gradient()), name="Sky", ev=-0.5),
            raster(gaussianBlur(mask(fill(color=[1, 1, 1, 1])), radius=2), src="a.png"),
        ))
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"]["mask"], wire("photo.gradient"))
        self.assertEqual(g["nodes"]["photo.filter"]["inputs"]["mask"], wire("photo.fill"))
        self.assertNotIn("mask", g["nodes"]["photo.raster"]["inputs"])
        self.assertEqual(g["nodes"]["doc"]["inputs"]["layers.1"], wire("photo.adjust"))
        with self.assertRaisesRegex(ValueError, "holds one layer"):
            from_twod(photo(exposure(mask())))

    def test_a_masked_node_names_its_masks_call_in_meta_sources(self):
        out = run_module(textwrap.dedent("""\
            from commandagi.design.twod import exposure, gradient, mask, photo
            result = photo(
                exposure(
                    mask(gradient()),
                    ev=-0.5,
                ),
            )
            """), "Sky.img.py")
        adjust = out["graph"]["nodes"]["photo.adjust"]
        self.assertEqual((adjust["meta"]["source"]["tag"], adjust["meta"]["source"]["line"]), ("exposure", 3))
        self.assertEqual((adjust["meta"]["sources"]["mask"]["tag"], adjust["meta"]["sources"]["mask"]["line"]), ("mask", 4))
        self.assertEqual(out["graph"]["nodes"]["photo.gradient"]["meta"]["source"]["tag"], "gradient")


class NestTests(unittest.TestCase):
    def test_a_nest_declares_its_sheet_stock_options_and_parts(self):
        g = from_twod(nest(
            sheet(width_mm=600, height_mm=400, margin_mm=5),
            stock(material_id="plywood", thickness_mm=3, machine={"powerW": 40}),
            options(resolution_mm=1, spacing_mm=1, rotations=[0, 90], max_sheets=8),
            part(id="tab", label="Tab", quantity=2, outline=[[0, 0], [10, 0], [10, 5]]),
            safe_z_mm=5,
        ))
        self.assertEqual(g["nodes"]["nest"]["inputs"], {"safeZMm": 5, "sheet": wire("nest.sheet"), "stock": wire("nest.stock"),
                                                        "options": wire("nest.options"), "parts.1": wire("tab")})
        self.assertEqual(g["nodes"]["tab"], {"id": "tab", "type": "nest.part", "label": "Tab", "inputs": {"quantity": 2, "outline": [[0, 0], [10, 0], [10, 5]]}})
        self.assertEqual(g["nodes"]["nest.sheet"]["inputs"], {"widthMm": 600, "heightMm": 400, "marginMm": 5})


class RefusalTests(unittest.TestCase):
    def test_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "src names an image file by relative path"):
            from_twod(painting(layer(src="data:image/png;base64,AAAA")))
        with self.assertRaisesRegex(ValueError, "src names an image file by relative path"):
            from_twod(drawing(layer(image(src="data:image/png;base64,AAAA"))))
        with self.assertRaisesRegex(ValueError, "src names its image file"):
            from_twod(drawing(layer(raster_layer())))
        with self.assertRaisesRegex(ValueError, "is painted on a layer: write it inside one"):
            from_twod(painting(stroke(points=[])))
        with self.assertRaisesRegex(ValueError, "absolute commands"):
            subpaths_of("m 0 0 l 1 1", "<path>")
        with self.assertRaisesRegex(ValueError, "a nest needs its <sheet>"):
            from_twod(nest(part(id="a")))
        with self.assertRaisesRegex(TypeError, "<rect> holds nothing"):
            rect(ellipse())
        with self.assertRaisesRegex(TypeError, "strokeWidth is written stroke_width"):
            path(strokeWidth=2)


if __name__ == "__main__":
    unittest.main()
