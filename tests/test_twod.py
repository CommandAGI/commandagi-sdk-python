"""commandagi.design.twod declares the 2D editors' own nodes — the same graphs as the TypeScript SDK's twod.ts for the
same document (its JSX): a drawing's composite and layer groups, d as subpaths, placed pixels by file, the paint stack
with stroke chains carrying the layer's fields, photo adjustments by tag, masks, the nest's one-of nodes and parts, the
refusals by name, and where each node was written. Run: python -m unittest discover -s tests"""
import textwrap
import unittest

from commandagi.design import run_module
from commandagi.design.twod import (PHOTO_FILTERS, SCHEMA, artboard, bevelEmboss, blur, bucket, colorOverlay, drawing, dropShadow, ellipse, engrave, exposure, fill, from_twod, fx, gaussianBlur, gradient,
                                    gradientFill, gradientOverlay, group, image, innerGlow, innerShadow, layer, line, link, mask, move, erase, freeTransform,
                                    nest, noise, options, outerGlow, painting, part, path, patternOverlay, photo, raster, raster_layer, rect, satin, sheet, sharpen, sketch, stock, stroke,
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

    def test_a_drawing_is_its_first_artboard_and_each_artboard_after_its_layers_is_another(self):
        g = from_twod(drawing(
            layer(rect(x=1, y=2, w=3, h=4), name="Front"),
            artboard(layer(ellipse(cx=5, cy=6, rx=7, ry=7), name="Text"), name="Back", width=400, height=300, background="#eeeeee"),
            artboard(width=200, height=100),
            name="Card", width=400, height=300, background="#ffffff",
        ))
        self.assertEqual(g["outputs"], ["composite", "Back", "Artboard_3"])
        self.assertEqual(g["meta"]["pages"], [
            {"id": "composite", "name": "Card", "width": 400, "height": 300, "background": "#ffffff", "compositeId": "composite"},
            {"id": "Back", "name": "Back", "width": 400, "height": 300, "background": "#eeeeee", "compositeId": "Back"},
            {"id": "Artboard_3", "name": "Artboard 3", "width": 200, "height": 100, "compositeId": "Artboard_3"},
        ])
        self.assertEqual(g["nodes"]["Back"]["inputs"], {"background": "#eeeeee", "layers.1": wire("group_2")})
        self.assertEqual(g["nodes"]["Back"]["label"], "Back")
        self.assertNotIn("pages", from_twod(drawing(layer()))["meta"])
        with self.assertRaisesRegex(ValueError, "its layers come before its <artboard>s"):
            from_twod(drawing(artboard(), layer()))
        with self.assertRaisesRegex(ValueError, r"x is not read \(an artboard has name, width, height, background\)"):
            from_twod(drawing(artboard(x=4)))

    def test_an_image_and_a_raster_layer_name_their_files(self):
        g = from_twod(drawing(layer(image(src="photos/harbour.jpg", x=10, y=20, w=40, h=30), raster_layer(src="scan.png"), name="Pictures"),
                              width=100, height=80))
        nodes = {n["type"]: n for n in g["nodes"].values()}
        self.assertEqual(nodes["image"]["inputs"], {"x": 10, "y": 20, "w": 40, "h": 30,
                                                    "__asset": {"kind": "file", "$file": "photos/harbour.jpg", "mime": "image/jpeg"}})
        self.assertEqual(nodes["raster-layer"]["inputs"], {"__asset": {"kind": "file", "$file": "scan.png", "mime": "image/png"}})

    def test_a_constrained_sketch_is_a_leaf_whose_geometry_is_its_own_data(self):
        geometry = {"points": {"p1": {"id": "p1", "x": 0, "y": 0}, "p2": {"id": "p2", "x": 40, "y": 0}},
                    "segments": {"s1": {"id": "s1", "type": "line", "a": "p1", "b": "p2"}},
                    "constraints": {}, "pointOrder": ["p1", "p2"], "segmentOrder": ["s1"], "constraintOrder": []}
        g = from_twod(drawing(sketch(sketch=geometry, x=40, y=60, unit="mm", drawing_scale=2, annotations=False),
                              width=100, height=80))
        nodes = {n["type"]: n for n in g["nodes"].values()}
        self.assertEqual(nodes["sketch"]["inputs"],
                         {"sketch": geometry, "x": 40, "y": 60, "unit": "mm", "drawingScale": 2, "annotations": False})
        self.assertEqual(nodes["composite"]["inputs"]["layers.1"], wire("sketch"),
                         "written straight on the drawing, it is a layer of it")
        with self.assertRaisesRegex(ValueError, "<sketch>: sketch is its geometry"):
            from_twod(drawing(sketch()))
        with self.assertRaisesRegex(ValueError, "sketch is its geometry"):
            from_twod(drawing(sketch(sketch=[1, 2])))

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

    def test_a_paintings_bucket_gradient_and_move_chain_on_a_layer_a_shape_is_a_layer(self):
        selection = [{"rect": [10, 10, 40, 30], "feather": 4}, {"op": "subtract", "polygon": [[20, 20], [30, 20], [25, 30]]}]
        g = from_twod(painting(
            layer(
                stroke(points=[[1, 2, 0.5, 0]], color=[0, 0, 0, 1], selection=selection),
                bucket(x=5, y=6, tolerance=20, contiguous=True, color=[1, 0, 0, 1]),
                gradientFill(shape="linear", from_=[0, 0], to=[100, 0], stops=[{"at": 0, "color": [0, 0, 0, 1]}, {"at": 1, "color": [1, 1, 1, 1]}]),
                move(dx=12, dy=-3, selection=[{"wand": [5, 6], "tolerance": 32, "contiguous": False}]),
                erase(selection=[{"rect": [0, 0, 10, 10], "feather": 0}]),
                freeTransform(cx=50, cy=40, dx=2, dy=3, scale_x=1.5, scale_y=1.5, angle=0.25),
                name="Paint",
            ),
            rect(name="Rectangle 1", x=4, y=5, w=30, h=20, fill=[0, 0, 1, 1], stroke=[0, 0, 0, 1], stroke_width=2),
            line(name="Line 1", from_=[0, 0], to=[10, 10], stroke=[1, 0, 0, 1], stroke_width=3),
            width=100, height=80,
        ))
        n = g["nodes"]
        self.assertEqual(n["paint.stroke"]["inputs"]["selection"], selection)
        self.assertEqual(n["paint.bucket"]["inputs"], {"name": "Paint", "visible": True, "opacity": 1, "blend": "normal", "x": 5, "y": 6,
                                                       "tolerance": 20, "contiguous": True, "color": [1, 0, 0, 1], "src": wire("paint.stroke")})
        self.assertEqual(n["paint.gradientFill"]["inputs"]["from"], [0, 0])
        self.assertEqual(n["paint.erase"]["inputs"]["src"], wire("paint.move"))
        self.assertEqual(n["paint.freeTransform"]["inputs"]["scaleX"], 1.5)
        self.assertEqual(n["doc"]["inputs"]["layers.1"], wire("paint.freeTransform"))
        self.assertEqual(n["paint.shape"]["inputs"], {"name": "Rectangle 1", "x": 4, "y": 5, "w": 30, "h": 20, "fill": [0, 0, 1, 1],
                                                      "stroke": [0, 0, 0, 1], "strokeWidth": 2, "shape": "rect"})
        self.assertEqual(n["paint.shape_2"]["inputs"]["shape"], "line")

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

    def test_a_layers_fx_holds_the_ten_styles_in_order(self):
        g = from_twod(painting(layer(
            fx(
                dropShadow(distance=4), innerShadow(), outerGlow(), innerGlow(source="center"),
                bevelEmboss(depth=2), satin(invert=True), colorOverlay(), gradientOverlay(align="layer"),
                patternOverlay(pattern="dots"), stroke(position="inside"),
            ),
            name="Layer 1",
        ), name="Poster", width=100, height=80))
        node = g["nodes"]["paint.layer"]
        self.assertEqual(node["inputs"]["fx"], [
            {"type": "dropShadow", "distance": 4}, {"type": "innerShadow"}, {"type": "outerGlow"},
            {"type": "innerGlow", "source": "center"}, {"type": "bevelEmboss", "depth": 2},
            {"type": "satin", "invert": True}, {"type": "colorOverlay"}, {"type": "gradientOverlay", "align": "layer"},
            {"type": "patternOverlay", "pattern": "dots"}, {"type": "stroke", "position": "inside"},
        ])
        self.assertIn("fx", node["meta"]["sources"])
        with self.assertRaisesRegex(ValueError, "not a layer style"):
            from_twod(painting(layer(fx(blur(radius=2)))))

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

    def test_a_mask_that_names_a_layer_of_the_stack_is_wired_to_it(self):
        g = from_twod(photo(
            exposure(mask(of="Brush", enabled=False), name="Mood", ev=-0.5),
            fill(name="Brush"),
        ))
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"]["mask"], wire("photo.fill"))
        self.assertEqual(g["nodes"]["photo.adjust"]["inputs"]["maskEnabled"], False)
        self.assertNotIn("mask", g["nodes"]["photo.fill"]["inputs"])
        with self.assertRaisesRegex(ValueError, "no layer is named that"):
            from_twod(photo(exposure(mask(of="Gone"))))
        with self.assertRaisesRegex(ValueError, "2 layers are named that"):
            from_twod(photo(exposure(mask(of="B")), fill(name="B"), fill(name="B")))
        with self.assertRaisesRegex(ValueError, "holds no layer"):
            from_twod(photo(exposure(mask(fill(color=[1, 1, 1, 1]), of="B")), fill(name="B")))

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

    def test_an_engrave_is_a_nest_engrave_node_on_the_engraves_channel(self):
        g = from_twod(nest(
            sheet(width_mm=300, height_mm=200, margin_mm=5),
            stock(material_id="plywood", thickness_mm=3, machine={"powerW": 40}),
            options(resolution_mm=1),
            engrave(id="logo", src="logo.png", x_mm=20, y_mm=20, width_mm=60, height_mm=30, dpi=254, dither="ordered"),
            safe_z_mm=5,
        ))
        self.assertEqual(g["nodes"]["nest"]["inputs"]["engraves.1"], wire("logo"))
        self.assertEqual(g["nodes"]["logo"]["type"], "nest.engrave")
        self.assertEqual(g["nodes"]["logo"]["inputs"], {"src": "logo.png", "xMm": 20, "yMm": 20, "widthMm": 60, "heightMm": 30, "dpi": 254, "dither": "ordered"})
        with self.assertRaisesRegex(ValueError, "an engrave has an id"):
            from_twod(nest(sheet(), stock(), options(), engrave(src="a.png")))


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


class LinkAndFilterTests(unittest.TestCase):
    def test_a_link_is_a_draw_instance_node_that_names_another_drawing(self):
        g = from_twod(drawing(layer(
            link(label="Badge", src="parts/Badge.draw.py", x=40, y=60, inputs={"size": 48, "tone": "warm", "outlined": True}),
            link(src="cloud://global/examples/2d/Badge.draw.tsx"),
            name="Badge",
        ), width=400, height=300))
        first, second = (g["nodes"][g["nodes"]["group"]["inputs"][port]["wire"]["node"]] for port in ("children.1", "children.2"))
        self.assertEqual({"type": first["type"], "label": first["label"], "inputs": first["inputs"]},
                         {"type": "draw.instance", "label": "Badge", "inputs": {"__instance": {"path": "parts/Badge.draw.py"}, "x": 40, "y": 60, "inputs": {"size": 48, "tone": "warm", "outlined": True}}})
        self.assertEqual(second["inputs"], {"__instance": {"assetPath": "cloud://global/examples/2d/Badge.draw.tsx"}})

    def test_a_link_is_checked_against_its_schema(self):
        def refused(pattern, **props):
            with self.assertRaisesRegex(ValueError, pattern):
                from_twod(drawing(layer(link(**props))))
        refused(r"<link>: src: is required")
        refused(r'<link>: x: must be number \(got "string"\)', src="a.draw.py", x="40")
        refused(r"<link>: scale: is not one of its fields", src="a.draw.py", scale=2)
        refused(r"<link>: inputs/size: does not match an allowed shape", src="a.draw.py", inputs={"size": [1]})
        refused(r"src names a drawing by its path", src=" ")
        with self.assertRaisesRegex(TypeError, "<link> holds nothing"):
            link(rect(), src="a.draw.py")

    def test_a_paintings_filter_chains_among_its_strokes(self):
        g = from_twod(painting(
            layer(
                stroke(points=[[1, 2, 0.5, 0]], color=[0, 0, 0, 1]),
                gaussianBlur(radius=3),
                stroke(points=[[5, 6, 0.5, 0]], color=[1, 0, 0, 1]),
                noise(mask(fill(color=[1, 1, 1, 1])), amount=0.1, monochrome=True, seed=7),
                name="Paint", opacity=0.8,
            ),
            width=100, height=80,
        ))
        self.assertEqual(g["nodes"]["paint.filter"]["inputs"], {"name": "Paint", "visible": True, "opacity": 0.8, "blend": "normal", "filter": {"type": "gaussianBlur", "radius": 3}, "src": wire("paint.stroke")})
        self.assertEqual(g["nodes"]["paint.stroke_2"]["inputs"]["src"], wire("paint.filter"))
        self.assertEqual(g["nodes"]["paint.filter_2"]["inputs"]["filter"], {"type": "noise", "amount": 0.1, "monochrome": True, "seed": 7})
        self.assertEqual(g["nodes"]["paint.filter_2"]["inputs"]["mask"], wire("paint.fill"))
        self.assertEqual(g["nodes"]["doc"]["inputs"]["layers.1"], wire("paint.filter_2"))
        with self.assertRaisesRegex(ValueError, "is painted on a layer: write it inside one"):
            from_twod(painting(gaussianBlur(radius=3)))
        with self.assertRaisesRegex(ValueError, "opacity is the layer's"):
            from_twod(painting(layer(sharpen(amount=0.5, opacity=0.5))))

    def test_a_filter_is_checked_against_its_schema_in_a_photo_and_in_a_painting(self):
        in_photo = lambda f: photo(raster(f, src="a.png"))
        in_painting = lambda f: painting(layer(f))
        for holder in (in_photo, in_painting):
            for pattern, f in (
                (r"<gaussianBlur>: radius: must be at most 250 \(got 300\)", gaussianBlur(radius=300)),
                (r"<gaussianBlur>: strength: is not one of its fields", gaussianBlur(radius=3, strength=1)),
                (r'<noise>: monochrome: must be boolean \(got "string"\)', noise(amount=0.1, monochrome="yes")),
            ):
                with self.assertRaisesRegex(ValueError, pattern):
                    from_twod(holder(f))
            # A required field with a declared default may be left out: a blur with no radius is the editor's 4 px blur.
            nodes = from_twod(holder(gaussianBlur()))["nodes"].values()
            self.assertIn({"type": "gaussianBlur", "radius": 4}, [n["inputs"].get("filter") for n in nodes])

    def test_the_filter_tags_and_the_link_are_the_schemas_roots(self):
        self.assertEqual(sorted([*PHOTO_FILTERS, "link"]), sorted(SCHEMA["roots"]))


if __name__ == "__main__":
    unittest.main()
