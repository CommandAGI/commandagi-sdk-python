"""A symbolic agent's skill declared in Python gives what the TypeScript vocabulary's JSX gives (skills.ts in the
CommandAGI repository): its phrases, steps, reply, rules, facts and examples, and a literal script's result; a skill that
does not read is refused with why.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.skills import example, fact, phrase, reply, result, rule, skill, step


class SkillTests(unittest.TestCase):
    def test_the_example_is_its_document(self):
        d = declare_document(skill(
            phrase(match="count [the] errors in {file:path}"),
            step(tool="read_file", args={"path": "{file}"}, as_="read"),
            step(script="./count.py", args={"text": "{read.text}", "word": "error"}, as_="n"),
            reply(text="{file} has {n} lines that say error."),
            rule(if_=["unit(?u, ?d)"], then="known(?u)"),
            fact(is_="ready(cam)"),
            example(say="count the errors in a.txt", reply=""),
            about="How many lines of a file say error.",
            needs=["ready(cam)"],
        ))
        self.assertEqual(d["format"], "skill")
        self.assertEqual(d["document"], {
            "about": "How many lines of a file say error.",
            "needs": ["ready(cam)"],
            "phrases": [{"match": "count [the] errors in {file:path}"}],
            "steps": [
                {"tool": "read_file", "args": {"path": "{file}"}, "as": "read"},
                {"script": "./count.py", "args": {"text": "{read.text}", "word": "error"}, "as": "n"},
            ],
            "reply": "{file} has {n} lines that say error.",
            "rules": [{"if": ["unit(?u, ?d)"], "then": "known(?u)"}],
            "facts": ["ready(cam)"],
            "examples": [{"say": "count the errors in a.txt", "reply": ""}],
        })

    def test_a_skill_that_does_not_read_is_refused(self):
        bad = {
            "is exactly one of expr, tool, script, skill, see \\(it has expr and tool\\)": skill(step(expr="1", tool="read_file")),
            "is exactly one of": skill(step(as_="x")),
            "always is true or false": skill(step(expr="1", always="yes")),
            "args is an object": skill(step(tool="read_file", args=["a"])),
            "if is a fact or a list of facts": skill(rule(if_=[], then="x")),
            "needs is a list of facts": skill(needs="ready"),
        }
        for why, s in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(s)

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
