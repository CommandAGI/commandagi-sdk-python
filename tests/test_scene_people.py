"""A person in a scene against scene_people.json, the golden of the three SDKs (scene-people.golden.json in the
TypeScript SDK): each case the engine accepts passes, and each refusal is the engine's own words.
Run: python -m unittest discover -s tests"""
import json
import pathlib
import unittest

from commandagi.design.scene_people import (HUMANOID_JOINTS, check_assist, check_goal, check_humanoid_policy, check_look,
                                            check_motors, humanoid_constraint)

GOLDEN = json.loads((pathlib.Path(__file__).parent / "scene_people.json").read_text(encoding="utf-8"))
CHECKS = {"look": check_look, "goal": check_goal, "humanoid": check_humanoid_policy, "motors": check_motors, "assist": check_assist}


class ScenePeopleTests(unittest.TestCase):
    def test_the_engines_refusals(self):
        for c in GOLDEN["cases"]:
            check = CHECKS[c["check"]]
            if "says" not in c:
                self.assertIs(check(c["value"]), c["value"])
                continue
            with self.assertRaises(ValueError, msg=c["says"]) as said:
                check(c["value"])
            self.assertIn(c["says"], str(said.exception))

    def test_the_joints(self):
        self.assertEqual(len(set(HUMANOID_JOINTS)), 33)
        self.assertEqual(humanoid_constraint("ana", "shoulder_l_abduct"), "ana-shoulder-l-abduct")


if __name__ == "__main__":
    unittest.main()
