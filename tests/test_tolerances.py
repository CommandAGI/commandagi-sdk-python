"""Tolerances as the SDK reads them: classes against numbers typed here from ISO 286-2 and ISO 492, a fit's kind, and a
parameter's tolerance through the 3D reader. The TypeScript SDK's src/design/tolerances.test.ts holds the same cases.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.threed import check, declare_threed, parameter, part
from commandagi.design.tolerances import fit_of, tolerance_limits


class TolerancesTests(unittest.TestCase):
    def test_a_class_is_read_from_the_tables_at_its_size(self):
        h7 = tolerance_limits(25, {"class": "H7"})
        self.assertEqual((h7["upper"], h7["lower"]), (0.021, 0))
        g6 = tolerance_limits(25, {"class": "g6"})
        self.assertEqual((g6["upper"], g6["lower"]), (-0.007, -0.02))
        self.assertEqual(tolerance_limits(10, {"class": "H7"})["max"], 10.015)
        self.assertEqual(tolerance_limits(15, {"class": "ISO 492 bore"})["min"], 14.992)
        self.assertTrue(h7["source"])
        with self.assertRaisesRegex(ValueError, 'no tolerance class "H77"'):
            tolerance_limits(25, {"class": "H77"})
        with self.assertRaisesRegex(ValueError, "H7 is tabled over 0 up to 120 mm, not at 900 mm"):
            tolerance_limits(900, {"class": "H7"})
        self.assertEqual(tolerance_limits(12, {"upper": 0.05, "lower": -0.05}), {"nominal": 12, "upper": 0.05, "lower": -0.05, "min": 11.95, "max": 12.05})

    def test_a_fit_is_clearance_transition_or_interference(self):
        def fit(h, s, d=25):
            return fit_of(tolerance_limits(d, {"class": h}), tolerance_limits(d, {"class": s}))
        self.assertEqual(fit("H7", "g6"), {"kind": "clearance", "minClearance": 0.007, "maxClearance": 0.041})
        self.assertEqual(fit("H7", "p6")["kind"], "interference")
        self.assertEqual(fit("H7", "k6")["kind"], "transition")
        self.assertEqual(fit("ISO 492 bore", "k5", 15)["kind"], "interference")

    def test_a_parameters_tolerance_is_read_into_the_graph(self):
        g = declare_threed(part(parameter(name="shaftD", value=15, tolerance={"class": "k5"}), name="P"))
        self.assertEqual(g["nodes"]["shaftD"]["inputs"], {"value": 15, "tolerance": {"class": "k5"}})
        for tol, said in [({"class": "k5", "upper": 0.1, "lower": 0}, r"tolerance: give the class \(k5\) or the deviations, not both"),
                          ({"upper": 0.1}, r"tolerance: give both deviations, upper and lower \(0 for none\)"),
                          ({"upper": -0.1, "lower": 0.1}, r"tolerance: the upper deviation \(-0.1\) is below the lower \(0.1\)")]:
            with self.assertRaisesRegex(ValueError, said):
                declare_threed(part(parameter(name="w", value=6, tolerance=tol), name="P"))
        with self.assertRaisesRegex(ValueError, "method: must be one of worst-case, rss, monte-carlo"):
            declare_threed(part(check(id="c", kind="stackup", method="average"), name="P"))


if __name__ == "__main__":
    unittest.main()
