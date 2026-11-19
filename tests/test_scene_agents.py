"""The scene agents against scene_agents.json, the golden of the three SDKs (scene-agents.golden.json in the TypeScript
SDK): a scene the engine runs passes, and each refusal is the engine's own words.
Run: python -m unittest discover -s tests"""
import copy
import json
import pathlib
import unittest

from commandagi.design.scene_agents import check_scene_agents

GOLDEN = json.loads((pathlib.Path(__file__).parent / "scene_agents.json").read_text(encoding="utf-8"))


def changed(path):
    out = copy.deepcopy(GOLDEN["valid"])
    at = out
    for k in path[:-2]:
        at = at[k]
    at[path[-2]] = path[-1]
    return out


class SceneAgentTests(unittest.TestCase):
    def test_the_engines_refusals(self):
        self.assertIs(check_scene_agents(GOLDEN["valid"]), GOLDEN["valid"])
        for r in GOLDEN["refusals"]:
            with self.assertRaises(ValueError) as said:
                check_scene_agents(changed(r["change"]))
            self.assertIn(r["says"], str(said.exception))


if __name__ == "__main__":
    unittest.main()
