"""The plant module against factory_operations.json, the golden of the three SDKs (factory-operations.golden.json in the
TypeScript SDK): a plant the engine runs passes, each refusal is the engine's own words, and the sizing gives the
machines the engine's sizing gives.
Run: python -m unittest discover -s tests"""
import copy
import json
import pathlib
import unittest

from commandagi.design.factory import check_operations_system, machines_for

GOLDEN = json.loads((pathlib.Path(__file__).parent / "factory_operations.json").read_text(encoding="utf-8"))


def changed(path):
    out = copy.deepcopy(GOLDEN["valid"])
    at = out
    for k in path[:-2]:
        at = at[k]
    at[path[-2]] = path[-1]
    return out


class FactoryTests(unittest.TestCase):
    def test_the_engines_refusals(self):
        self.assertIs(check_operations_system(GOLDEN["valid"]), GOLDEN["valid"])
        for r in GOLDEN["refusals"]:
            with self.assertRaises(ValueError) as said:
                check_operations_system(changed(r["change"]))
            self.assertIn(r["says"], str(said.exception))

    def test_machines_for(self):
        for c in GOLDEN["machines"]:
            args = {k: v for k, v in c.items() if k != "machines"}
            self.assertEqual(machines_for(**args), c["machines"], c)
        with self.assertRaises(ValueError):
            machines_for(1, 0)


if __name__ == "__main__":
    unittest.main()
