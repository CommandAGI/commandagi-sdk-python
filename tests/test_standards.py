"""The engineering tables as the SDK carries them, held to numbers typed here from the standards' own tables (the
shipped CSVs name the page each row was read from; ``cloud://global/standards/<table>.csv``). The TypeScript SDK's
src/design/standards.test.ts holds the same values: one set of tables makes every SDK's data.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.standards import (MATERIALS, STANDARD_SOURCES, STANDARD_TABLES, hole_size, mass_grams, material, sized_hole,
                                         standard_row)
from commandagi.design.threed import declare_threed, hole, part


class StandardsTests(unittest.TestCase):
    def test_a_sample_of_each_dimension_table_is_the_standards_number(self):
        def row(table, key, fields):
            r = standard_row(table, key)
            for k, v in fields.items():
                self.assertEqual(r[k], v, f"{table} {key} {k}")
        # ISO 4762 hexagon socket head cap screws: head diameter, head height, socket.
        row("iso-4762", "M3", {"dkMax": 5.5, "kMax": 3, "s": 2.5})
        row("iso-4762", "M8", {"dkMax": 13, "kMax": 8, "s": 6})
        # ISO 7380-1 button head, ISO 10642 countersunk head, ISO 4017 hexagon head, ISO 4026 set screw.
        row("iso-7380-1", "M5", {"dkMax": 9.5, "kMax": 2.75, "s": 3})
        row("iso-10642", "M6", {"dkTheoreticalMax": 13.44, "kMax": 3.72, "s": 4, "headAngleDeg": 90})
        row("iso-4014-4017", "M10", {"sMax": 16, "kNom": 6.4})
        row("iso-4026", "M6", {"s": 3})
        # ISO 4032 and ISO 4035 nuts; ISO 7089 and ISO 7093-1 washers.
        row("iso-4032", "M8", {"sMax": 13, "mMax": 6.8})
        row("iso-4035", "M8", {"mMax": 4})
        row("iso-7089", "M6", {"d1Nom": 6.4, "d2Nom": 12, "hNom": 1.6})
        row("iso-7093-1", "M6", {"d1Nom": 6.4, "d2Nom": 18, "hNom": 1.6})
        # ISO 261 coarse pitch; ASME B18.3 inch socket head cap screw.
        row("metric-threads", "M5", {"d": 5, "pitchCoarse": 0.8})
        row("asme-b18.3-shcs", "#4-40", {"headDiameterMaxIn": 0.183, "threadsPerInch": 40})
        # ISO 15 bearing boundary dimensions; a HIWIN MGN12H block; a MISUMI 2020 profile; ISO 2338 pins.
        row("bearings", "608", {"d": 8, "D": 22, "B": 7})
        row("bearings", "625", {"d": 5, "D": 16, "B": 5})
        row("mgn-linear-guide", "MGN12H", {"H": 13, "W": 27, "L": 45.4, "WR": 12, "HR": 8, "P": 25})
        row("t-slot-profiles", "HFS5-2020", {"width": 20, "height": 20, "slotWidth": 6})
        row("iso-2338", "6", {"chamferC": 1.2})
        row("heat-set-inserts", "M3x5.7", {"thread": "M3", "length": 5.7, "recommendedHoleDiameter": 4})

    def test_a_hole_by_name_is_the_clearance_hole_of_iso_273_or_the_tap_drill_of_iso_2306(self):
        fits = ["close fit", "normal fit", "loose fit"]
        self.assertEqual([hole_size(f"M5 {f}")["diameter"] for f in fits], [5.3, 5.5, 5.8])
        self.assertEqual([hole_size(f"M8 {f}")["diameter"] for f in fits], [8.4, 9, 10])
        self.assertEqual(hole_size("M6 tap")["diameter"], 5)
        self.assertEqual(hole_size("m10  Tap")["diameter"], 8.5)
        self.assertIn("ISO 273", hole_size("M4 close fit")["source"])
        # An inch thread: ASME B18.2.8 normal fit for 1/4 is 0.281 in.
        self.assertEqual(hole_size("1/4-20 normal fit")["diameter"], 7.1374)
        with self.assertRaises(ValueError) as caught:
            hole_size("M4 snug")
        self.assertEqual(str(caught.exception), '"M4 snug": a hole size is a thread and one of close fit, normal fit, loose fit, tap ("M4 close fit")')
        with self.assertRaisesRegex(ValueError, r"no hole table has the thread M7\.5 \(it has M1\.6, "):
            hole_size("M7.5 tap")
        # The head of a counterbore (DIN 974-1, for an ISO 4762 screw) and of a countersink (DIN 74 form F, 90°).
        self.assertEqual(sized_hole({"size": "M4 close fit", "style": "counterbore"}),
                         {"size": "M4 close fit", "style": "counterbore", "diameter": 4.3, "headDiameter": 8, "headDepth": 4.4})
        self.assertEqual(sized_hole({"size": "M4 normal fit", "style": "countersink"}),
                         {"size": "M4 normal fit", "style": "countersink", "diameter": 4.5, "headDiameter": 9.2, "headDepth": 2.35})
        self.assertEqual(sized_hole({"size": "M4 tap", "style": "simple"}), {"size": "M4 tap", "style": "simple", "diameter": 3.3})
        # The size gives the head too: a head that differs is refused (clear the size to give your own).
        with self.assertRaises(ValueError) as caught:
            sized_hole({"size": "M4 close fit", "style": "counterbore", "headDiameter": 9})
        self.assertEqual(str(caught.exception), 'headDiameter: "M4 close fit" is 8 mm (got 9); leave headDiameter out, or clear size')

    def test_a_material_is_a_row_with_its_density_and_its_source_and_a_mass_is_volume_times_density(self):
        self.assertEqual(material("6061-T6")["densityGCm3"], 2.7)
        self.assertEqual(material("304")["densityGCm3"], 8)
        self.assertEqual(material("petg")["densityGCm3"], 1.27)
        self.assertEqual(mass_grams(1000, "304"), 8)
        # A table of your own is read before the shipped one.
        mine = [{"id": "304", "densityGCm3": 7.93, "source": "mill certificate 4711"}]
        self.assertEqual(mass_grams(1000, "304", mine), 7.93)
        with self.assertRaisesRegex(ValueError, r'no materials table has a row "unobtainium" \(the shipped table has 6061-T6, '):
            material("unobtainium")
        for m in MATERIALS:
            self.assertTrue(m["source"] and m["sourceUrl"] and m["densityGCm3"] > 0, m["id"])
        for t in STANDARD_TABLES:
            self.assertTrue(all(s["source"] and s["sourceUrl"] and s["observedAt"] for s in STANDARD_SOURCES[t]), t)

    def test_a_hole_that_names_a_size_has_that_sizes_diameter_and_head(self):
        face = {"kind": "face", "signature": {"point": [0, 0, 6], "normal": [0, 0, 1]}}

        def read(**fields):
            return declare_threed(part(hole(id="h1", face=face, **fields), name="P"))["nodes"]["h1"]["inputs"]
        self.assertEqual(read(size="M4 close fit", style="counterbore"),
                         {"face": face, "size": "M4 close fit", "style": "counterbore", "diameter": 4.3, "headDiameter": 8, "headDepth": 4.4, "depth": 10})
        self.assertEqual(read(size="M3 tap", through=False, depth=8)["diameter"], 2.5)
        self.assertEqual(read(size="M4 close fit", diameter=4.3)["diameter"], 4.3)
        with self.assertRaises(ValueError) as caught:
            read(size="M4 close fit", diameter=6)
        self.assertEqual(str(caught.exception), '<hole id="h1">: diameter: "M4 close fit" is 4.3 mm (got 6); leave diameter out, or clear size')
        with self.assertRaisesRegex(ValueError, r'<hole id="h1">: "M4 snug": a hole size is a thread and one of'):
            read(size="M4 snug")


if __name__ == "__main__":
    unittest.main()
