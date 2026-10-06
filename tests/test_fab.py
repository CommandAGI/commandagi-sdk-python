"""Machine jobs declared in Python give what the TypeScript SDK's JSX gives (fab.test.ts there): the setup's JSON in the
run's one shape, single records once, operations in their order, a null record left out, each record's call in
``sources`` by its path.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.fab import cam, fixture, machine, operation, runsOn, slice, spool, stock


class FabTests(unittest.TestCase):
    def test_a_machining_setup_is_its_setup(self):
        d = declare_document(cam(
            stock(material_id="plywood", thickness_mm=6, x_mm=90, y_mm=70),
            machine(post="grbl", max_spindle_rpm=10000),
            fixture(name="clamp", x_mm=-14, y_mm=25, w_mm=20, d_mm=20, z_mm=4),
            operation(id="op-2", op="mill_contour", profile="contour_wood", tabs={"count": 4, "lengthMm": 5, "heightMm": 1.5}),
            operation(id="op-1", op="mill_pocket", profile="pocket_wood", enabled=False),
            runsOn(unit="cloud://global/worlds/fab-cell/world.tsx#cnc-1", channel="gcode", name="cnc"),
        ))
        self.assertEqual(d["format"], "cam")
        self.assertEqual(d["document"], {
            "stock": {"materialId": "plywood", "thicknessMm": 6, "xMm": 90, "yMm": 70},
            "machine": {"post": "grbl", "maxSpindleRpm": 10000},
            "fixtures": [{"name": "clamp", "xMm": -14, "yMm": 25, "wMm": 20, "dMm": 20, "zMm": 4}],
            "operations": [
                {"id": "op-2", "op": "mill_contour", "profile": "contour_wood", "tabs": {"count": 4, "lengthMm": 5, "heightMm": 1.5}},
                {"id": "op-1", "op": "mill_pocket", "profile": "pocket_wood", "enabled": False},
            ],
            "runsOn": {"unit": "cloud://global/worlds/fab-cell/world.tsx#cnc-1", "channel": "gcode", "name": "cnc"},
        })
        with self.assertRaisesRegex(ValueError, r'<operation id="a"> needs profile'):
            declare_document(cam(operation(id="a", op="face")))
        with self.assertRaisesRegex(ValueError, r'two <operation> in <cam> have id "a"'):
            declare_document(cam(operation(id="a", op="face", profile="p"), operation(id="a", op="face", profile="p")))
        with self.assertRaisesRegex(ValueError, r"<cam> has one <stock>"):
            declare_document(cam(stock(), stock()))
        with self.assertRaisesRegex(ValueError, r"<spool> is not a tag of a machining setup"):
            declare_document(cam(spool()))

    def test_a_slicing_setup_is_its_setup_and_each_record_its_call(self):
        out = run_module(
            'from commandagi.design.fab import machine, slice, source, spool\n'
            'result = slice(\n'
            '    source(file_id="carrier.stl", name="carrier.stl"),\n'
            '    spool(material_id="pla", diameter_mm=1.75),\n'
            '    machine(unit="cloud://g/w.json#printer-1", channel="gcode", name="ender"),\n'
            '    profile="fdm_pla_0.20_draft",\n'
            ')\n',
            "Carrier.slice.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["graph"]["meta"]["sourceMap"]["language"], "py")
        d = out["document"]
        self.assertEqual((d["format"], d["document"]), ("slice", {
            "profile": "fdm_pla_0.20_draft",
            "source": {"fileId": "carrier.stl", "name": "carrier.stl"},
            "spool": {"materialId": "pla", "diameterMm": 1.75},
            "machine": {"unit": "cloud://g/w.json#printer-1", "channel": "gcode", "name": "ender"},
        }))
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in d["sources"].items()},
                         {"": ("slice", 2), "source": ("source", 3), "spool": ("spool", 4), "machine": ("machine", 5)})
        self.assertEqual(d["sources"]["spool"]["props"]["diameter_mm"]["value"], 1.75)
        with self.assertRaisesRegex(ValueError, r"<slice> needs profile"):
            declare_document(slice())


if __name__ == "__main__":
    unittest.main()
