"""An agent's skill declared in Python gives what the TypeScript vocabulary's JSX gives (skills.ts in the CommandAGI
repository): its steps and reply, and a literal script's result; a skill that does not read is refused with why, and what
the vocabulary has no words for (a phrase, an example, a rule, a fact) is refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.element import Element
from commandagi.design.skills import reply, result, skill, step


class SkillTests(unittest.TestCase):
    def test_the_example_is_its_document(self):
        d = declare_document(skill(
            step(tool="read_file", args={"path": "{file}"}, as_="read"),
            step(script="./count.py", args={"text": "{read.text}", "word": "error"}, as_="n"),
            reply(text="{file} has {n} lines that say error."),
            step(tool="close_channel", args={"session": "{s}"}, always=True),
            about="How many lines of a file say error.",
            origin="frozen:cua",
        ))
        self.assertEqual(d["format"], "skill")
        self.assertEqual(d["document"], {
            "about": "How many lines of a file say error.",
            "origin": "frozen:cua",
            "steps": [
                {"tool": "read_file", "args": {"path": "{file}"}, "as": "read"},
                {"script": "./count.py", "args": {"text": "{read.text}", "word": "error"}, "as": "n"},
                {"tool": "close_channel", "args": {"session": "{s}"}, "always": True},
            ],
            "reply": "{file} has {n} lines that say error.",
        })

    def test_a_skill_that_does_not_read_is_refused(self):
        bad = {
            "is exactly one of expr, tool, script, skill, see \\(it has expr and tool\\)": skill(step(expr="1", tool="read_file")),
            "is exactly one of": skill(step(as_="x")),
            "always is true or false": skill(step(expr="1", always="yes")),
            "args is an object": skill(step(tool="read_file", args=["a"])),
            "gives is not read": skill(gives=["at(arm, home)"]),
        }
        for why, s in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(s)
        # Free text is read only by a model agent: a skill has no phrase to match or example utterance to check.
        for tag, props in [("phrase", {"match": "count errors in {file:path}"}), ("example", {"say": "count errors", "reply": "2"}),
                           ("rule", {"if": "a", "then": "b"}), ("fact", {"is": "a"})]:
            with self.assertRaisesRegex(ValueError, "is not a tag of a skill", msg=tag):
                declare_document(skill(Element(tag, props, [], None, "skills")))

    def test_a_script_reads_its_inputs_and_declares_its_result(self):
        out = run_module(
            "from commandagi.design.skills import result\n"
            "result = result(value=len([l for l in inputs[\"text\"].split(\"\\n\") if inputs[\"word\"] in l]))\n",
            "skills/count-errors/count.py", {"text": "error a\nok\nerror b", "word": "error"})
        self.assertEqual(out["document"]["format"], "result")
        self.assertEqual(out["document"]["document"], {"value": 2})
        self.assertEqual(declare_document(result(value=None))["document"], {"value": None})


if __name__ == "__main__":
    unittest.main()
