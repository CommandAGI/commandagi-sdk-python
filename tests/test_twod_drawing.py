"""commandagi.design.twod declares a drawing's placed image and raster layer by the image file they name, as the
TypeScript SDK's twod.ts does. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.twod import drawing, image, layer, raster_layer


class DrawingPixelTests(unittest.TestCase):
    def test_an_image_and_a_raster_layer_name_their_files(self):
        g = drawing(layer(image(src="photos/harbour.jpg", x=10, y=20, w=40, h=30), raster_layer(src="scan.png"), name="Pictures"),
                    width=100, height=80).ir
        nodes = {n["type"]: n for n in g["nodes"].values()}
        self.assertEqual(nodes["image"]["inputs"], {"x": 10, "y": 20, "w": 40, "h": 30,
                                                    "__asset": {"kind": "file", "$file": "photos/harbour.jpg", "mime": "image/jpeg"}})
        self.assertEqual(nodes["raster-layer"]["inputs"], {"__asset": {"kind": "file", "$file": "scan.png", "mime": "image/png"}})

    def test_pixels_in_code_are_refused(self):
        with self.assertRaisesRegex(ValueError, "src names an image file by relative path"):
            drawing(layer(image(src="data:image/png;base64,AAAA")))
        with self.assertRaisesRegex(ValueError, "src names its image file"):
            drawing(layer(raster_layer()))


if __name__ == "__main__":
    unittest.main()
