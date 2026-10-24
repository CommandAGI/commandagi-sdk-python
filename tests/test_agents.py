"""A harness and an agent declared in Python give what the TypeScript SDK's JSX gives (agents.test.ts there): a base names
its harness, a fork names its parent, never both; a program harness needs no model; a realtime harness says what its
model takes and gives live; what the vocabulary has no words for is refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.agents import agent, harness
from commandagi.design.documents import declare_document

REALTIME = {"in": ["audio", "video", "text"], "out": ["audio", "text", "tools"],
            "audio": {"in": ["g711-ulaw@8000", "pcm16@24000"], "out": ["g711-ulaw@8000"]}, "fps": 1, "hz": 2, "minutes": 60}


def api(realtime, **more):
    return declare_document(harness(kind="api", label="X", provider="p", realtime=realtime, **more))


class AgentTests(unittest.TestCase):
    def test_a_harness_of_each_kind(self):
        cli = declare_document(harness(kind="cli", label="Claude Code", provider="anthropic", cli="claude", runs=["host", "vm"]))
        self.assertEqual(cli, {"format": "harness", "sources": {}, "document": {
            "kind": "cli", "label": "Claude Code", "provider": "anthropic", "cli": "claude", "runs": ["host", "vm"]}})
        program = declare_document(harness(kind="program", label="Symbolic Planner 001", family="symbolic", experimental=True, runs=["host"]))
        self.assertEqual(program["document"], {"kind": "program", "label": "Symbolic Planner 001", "runs": ["host"], "family": "symbolic",
                                               "experimental": True})
        single = declare_document(harness(kind="api", label="ScaleDown Classify-1", provider="scaledown", tasks=["classify", "decide"],
                                          family="system-one", experimental=True, runs=["host"]))
        self.assertEqual(single["document"]["tasks"], ["classify", "decide"])

    def test_a_base_names_its_harness_and_a_fork_its_parent(self):
        base = declare_document(agent(harness="anthropic", model="anthropic/claude-opus-5-5", effort="medium", name="Claude Opus 5.5"))
        self.assertEqual(base, {"format": "agent", "sources": {}, "document": {
            "harness": "anthropic", "name": "Claude Opus 5.5", "model": "anthropic/claude-opus-5-5", "effort": "medium"}})
        self.assertEqual(declare_document(agent(parent="cloud://global/agents/claude-code", supervisor="person:me"))["document"]["supervisor"], "person:me")
        with self.assertRaisesRegex(ValueError, "supervisor is an agent or a person"):
            declare_document(agent(parent="cloud://global/agents/claude-code", supervisor="lead"))
        fork = declare_document(agent(parent="cloud://global/agents/claude-code", name="Joe's secretary",
                                      instructions="Keep Joe's calendar.", tools=["calendar_save_event"], voice_mode="push-to-talk"))
        self.assertEqual(fork["document"], {"parent": "cloud://global/agents/claude-code", "name": "Joe's secretary",
                                            "instructions": "Keep Joe's calendar.", "voiceMode": "push-to-talk",
                                            "tools": ["calendar_save_event"]})

    def test_a_realtime_harness(self):
        h = declare_document(harness(kind="api", label="OpenAI Realtime API", provider="openai", runs=["worker", "host"], realtime=REALTIME))
        self.assertEqual(h["document"]["realtime"], REALTIME)
        self.assertEqual(api({"in": ["audio"], "out": ["audio", "tools"], "audio": {"in": ["pcm16@16000"], "out": ["pcm16@24000"]}, "hz": 1,
                              "minutes": 15, "videoMinutes": 2})["document"]["realtime"]["videoMinutes"], 2)
        with self.assertRaisesRegex(ValueError, "fps is the most video frames"):
            api({**REALTIME, "fps": None})
        with self.assertRaisesRegex(ValueError, "hz is the most tool calls"):
            api({**REALTIME, "hz": 0})
        with self.assertRaisesRegex(ValueError, "audio names the formats"):
            api({"in": ["audio"], "out": ["text"]})
        with self.assertRaisesRegex(ValueError, "in is a list of"):
            api({"in": ["smell"], "out": ["text"]})
        with self.assertRaisesRegex(ValueError, "has no field latency"):
            api({**REALTIME, "latency": 1})
        with self.assertRaisesRegex(ValueError, "audio is for a harness that takes or gives audio"):
            api({"in": ["text"], "out": ["text"], "audio": {"in": ["pcm16@24000"]}})
        with self.assertRaisesRegex(ValueError, 'realtime is for kind="api" with no tasks'):
            api(REALTIME, tasks=["act"])

    def test_refusals_by_name(self):
        for made, why in [
            (lambda: agent(name="x"), "names its harness .* or its parent"),
            (lambda: agent(harness="codex", parent="../a"), "not both: a fork keeps its parent's harness"),
            (lambda: agent(harness="Codex CLI"), "harness is a harness's id"),
            (lambda: agent(parent="../a", voice_mode="loud"), "voiceMode is"),
            (lambda: agent(parent="../a", tools="all"), "tools is a list"),
            (lambda: harness(kind="cli", label="X"), "names the program it starts"),
            (lambda: harness(kind="api", label="X"), "names its provider"),
            (lambda: harness(kind="program", label="X", cli="x"), 'cli is for kind="cli" only'),
            (lambda: harness(kind="api", label="X", provider="p", runs=["cloud"]), "runs is a list of"),
            (lambda: harness(kind="robot", label="X"), "kind is"),
            (lambda: harness(kind="program", label="X", experimental="yes"), "experimental is True or False"),
            (lambda: harness(kind="api", label="X", provider="p", tasks=["chat"]), "tasks is a list of"),
            (lambda: harness(kind="program", label="X", tasks=["classify"]), 'tasks is for kind="api" only'),
            (lambda: harness(label="X"), "needs kind"),
            (lambda: agent(parent="../a", colour="red"), "colour is not read"),
        ]:
            with self.assertRaisesRegex(ValueError, why):
                declare_document(made())
        with self.assertRaisesRegex(TypeError, "voiceMode is written voice_mode"):
            agent(parent="../a", voiceMode="off")

    def test_a_file_declares_its_harness_with_the_call_that_made_it(self):
        out = run_module(
            "from commandagi.design.agents import harness\n"
            "result = harness(\n"
            "    kind=\"api\",\n"
            "    label=\"xAI Voice Agent API\",\n"
            "    provider=\"xai\",\n"
            "    realtime={\"in\": [\"audio\", \"text\"], \"out\": [\"audio\", \"text\", \"tools\"],\n"
            "              \"audio\": {\"in\": [\"g711-ulaw@8000\"], \"out\": [\"g711-ulaw@8000\"]}, \"hz\": 2},\n"
            ")\n", "agents/harnesses/xai-realtime/harness.py")
        self.assertEqual(out["document"]["format"], "harness")
        self.assertEqual(out["document"]["document"]["realtime"]["hz"], 2)
        self.assertEqual((out["document"]["sources"][""]["tag"], out["document"]["sources"][""]["line"]), ("harness", 2))


if __name__ == "__main__":
    unittest.main()
