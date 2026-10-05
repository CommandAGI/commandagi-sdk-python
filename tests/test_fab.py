"""Machine jobs declared in Python give what the TypeScript SDK's JSX gives (fab.test.ts there): the setup's JSON in the
run's one shape, single records once, operations in their order, a null record left out.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import (cam, cam_machine, fab_source, fixture, operation, run_module, runs_on, slice_machine, slicing,
                               spool, stock)
from commandagi.design.fab import declare_fab_document


class FabTests(unittest.TestCase):
    def test_a_machining_setup_is_its_camx(self):
        d = declare_fab_document(cam(
            stock(materialId="plywood", thicknessMm=6, xMm=90, yMm=70),
            cam_machine(post="grbl", maxSpindleRpm=10000, spindlePowerKw=None),
            fixture(name="clamp", xMm=-14, yMm=25, wMm=20, dMm=20, zMm=4),
            operation(id="op-2", op="mill_contour", profile="contour_wood", tabs={"count": 4, "lengthMm": 5, "heightMm": 1.5}),
            operation(id="op-1", op="mill_pocket", profile="pocket_wood", enabled=False),
            runs_on(unit="cloud://global/worlds/fab-cell/world.tsx#cnc-1", channel="gcode", name="cnc"),
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
            declare_fab_document(cam(operation(id="a", op="face")))
        with self.assertRaisesRegex(ValueError, r'two <operation> in <cam> have id "a"'):
            declare_fab_document(cam(operation(id="a", op="face", profile="p"), operation(id="a", op="face", profile="p")))
        with self.assertRaisesRegex(ValueError, r"<cam> has one <stock>"):
            declare_fab_document(cam(stock(), stock()))
        with self.assertRaisesRegex(ValueError, r"<spool> is not a tag of a machining setup"):
            declare_fab_document(cam(spool()))

    def test_a_slicing_setup_is_its_slicex(self):
        out = run_module(
            'from commandagi.design import slicing, fab_source, spool, slice_machine\n'
            'result = slicing(fab_source(fileId="carrier.stl", name="carrier.stl"), spool(materialId="pla", diameterMm=1.75),\n'
            '                 slice_machine(unit="cloud://g/w.json#printer-1", channel="gcode", name="ender"), profile="fdm_pla_0.20_draft")',
            "Carrier.slice.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"], {"format": "slice", "document": {
            "profile": "fdm_pla_0.20_draft",
            "source": {"fileId": "carrier.stl", "name": "carrier.stl"},
            "spool": {"materialId": "pla", "diameterMm": 1.75},
            "machine": {"unit": "cloud://g/w.json#printer-1", "channel": "gcode", "name": "ender"},
        }, "sources": {}})
        with self.assertRaisesRegex(ValueError, r"<slice> needs profile"):
            declare_fab_document(slicing())


if __name__ == "__main__":
    unittest.main()
