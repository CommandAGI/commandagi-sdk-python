"""A scout's comparison and a replacement-cost analysis declared in Python give what the TypeScript SDK's JSX gives
(scouts.test.ts in that SDK, the same examples): each is its record both ways, and what would make a run dishonest is
refused with why (a customer's case, a case with two scorers, two incumbents, a check with no kind). Run: python -m
unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.scouts import (capability, case, configuration, decision, differentiation, economics, evidence,
                                      judge, layer, replacement, scout, workload, SCOUTS)

SOURCES = "runs/thread-1/streams/chat@a/records.jsonl#12"
KNOWLEDGE = {
    "title": "GLM against Sonnet",
    "budget": 10,
    "repeats": 3,
    "configurations": [
        {"id": "sonnet", "model": "anthropic/claude-sonnet-5-5", "effort": "low", "incumbent": True},
        {"id": "glm", "model": "dashscope/glm-5.3"},
    ],
    "workloads": [{
        "id": "knowledge",
        "title": "Knowledge work",
        "needs": ["structured"],
        "sample": 20,
        "cases": [
            {"id": "rate", "from": "synthetic", "prompt": "What is 4.2% as a decimal?", "check": {"number": 0.042, "tolerance": 0.0005}},
            {"id": "page", "from": "own-run", "prompt": "Write the provider page.", "rubric": "Names the price and the terms.", "source": SOURCES},
        ],
    }],
    "judges": [{"model": "openai/gpt-5.6-terra"}],
}
BEEHIIV = {
    "product": "beehiiv",
    "vendor": "beehiiv, Inc.",
    "url": "https://www.beehiiv.com",
    "asOf": "2026-10-14",
    "by": "scout",
    "layers": [
        {"kind": "invisible", "title": "Deliverability", "capabilities": [
            {"id": "bulk-send", "title": "3M+ emails a minute", "need": "must", "have": "none", "effort": "XL", "run": 2000,
             "labour": 160, "note": "ESP or own MTAs", "evidence": [{"source": "beehiiv checklist", "claim": "reported"}]},
            {"id": "abuse", "title": "signup validation", "need": "must", "have": "partial", "effort": "L",
             "ref": "docs/moderation.md", "evidence": []},
        ]},
        {"kind": "visible", "title": "Editor", "capabilities": [
            {"id": "collab", "title": "real-time collaboration", "need": "should", "have": "partial", "effort": "M",
             "evidence": []}]},
        {"kind": "visible", "title": "Website", "capabilities": []},
    ],
    "decision": {"choice": "skip", "because": "The invisible layer is the product."},
    "differentiation": "Agents author the newsletter as code.",
    "economics": {"price": "$49 a month", "margin": "unknown"},
}

SOURCE = '''from commandagi.design.scouts import case, configuration, judge, scout, workload

result = scout(
    configuration(id="sonnet", model="anthropic/claude-sonnet-5-5", effort="low", incumbent=True),
    configuration(id="glm", model="dashscope/glm-5.3"),
    workload(
        case(id="rate", from_="synthetic", prompt="What is 4.2% as a decimal?",
             check={"number": 0.042, "tolerance": 0.0005}),
        case(id="page", from_="own-run", source="runs/thread-1/streams/chat@a/records.jsonl#12",
             prompt="Write the provider page.", rubric="Names the price and the terms."),
        id="knowledge", title="Knowledge work", needs=["structured"], sample=20),
    judge(model="openai/gpt-5.6-terra"),
    budget=10, repeats=3, title="GLM against Sonnet",
)
'''


def _comparison(**case_attrs):
    """The example comparison, its first case's attributes replaced (a None one is left out)."""
    attrs = {"id": "rate", "from_": "synthetic", "prompt": "What is 4.2% as a decimal?",
             "check": {"number": 0.042, "tolerance": 0.0005}, **case_attrs}
    return scout(
        configuration(id="sonnet", model="anthropic/claude-sonnet-5-5", effort="low", incumbent=True),
        configuration(id="glm", model="dashscope/glm-5.3"),
        workload(case(**{k: v for k, v in attrs.items() if v is not None}),
                 id="knowledge", title="Knowledge work", needs=["structured"], sample=20),
        judge(model="openai/gpt-5.6-terra"),
        budget=10, repeats=3, title="GLM against Sonnet")


class ScoutTests(unittest.TestCase):
    def test_a_comparison_declares_its_configurations_workloads_and_judges(self):
        out = run_module(SOURCE, "scouts/knowledge-work.scout.py")
        self.assertEqual(out["graph"]["nodes"], {}, "a comparison leaves beside an empty graph")
        self.assertEqual(out["document"]["format"], "scout")
        self.assertEqual(out["document"]["document"], KNOWLEDGE)
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "configuration#glm", "configuration#sonnet",
                                           "judge#openai/gpt-5.6-terra", "workload#knowledge",
                                           "workload#knowledge/case#page", "workload#knowledge/case#rate"])
        self.assertEqual(SCOUTS["scout"].from_tree(SCOUTS["scout"].to_tree(KNOWLEDGE)), KNOWLEDGE, "both ways")

    def test_a_comparison_refuses_what_would_make_its_verdict_dishonest(self):
        bad = {
            "from is one of public, synthetic, own-run": lambda: declare_document(_comparison(from_="customer")),
            "is scored by exactly one of check .* or rubric": lambda: declare_document(
                _comparison(rubric="and a judge")),
            "check is exactly one of": lambda: declare_document(
                _comparison(check={"tolerance": 1})),
            "it has exact and contains": lambda: declare_document(
                _comparison(check={"exact": "a", "contains": ["b"]})),
            "not a regular expression": lambda: declare_document(_comparison(check={"regex": "("})),
            "one incumbent": lambda: declare_document(scout(
                configuration(id="a", model="x/a", incumbent=True), configuration(id="b", model="x/b", incumbent=True),
                budget=5)),
            "budget is a number above 0": lambda: declare_document(scout(budget=0)),
            "<scout> needs budget": lambda: declare_document(scout(title="no budget")),
            r"<case> stands in <workload>": lambda: declare_document(scout(
                case(id="x", from_="public", prompt="p", check={"exact": "1"}), budget=5)),
        }
        for why, declare in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare()

    def test_a_tool_case_offers_its_tools_and_their_answers(self):
        tools = [
            {"name": "get_capital", "parameters": {"type": "object", "properties": {"country": {"type": "string"}}},
             "results": [{"when": {"country": "france"}, "result": "Paris"}]},
            {"name": "send_email", "description": "send an email", "parameters": {"type": "object"}},
        ]
        doc = declare_document(scout(
            configuration(id="a", model="x/a"),
            workload(case(id="chain", from_="synthetic", prompt="p", tools=tools, turns=4, check={"number": 4280000}),
                     case(id="first", from_="synthetic", prompt="p", tools=tools, check={"tool": "send_email"}),
                     case(id="mc", from_="public", source="TIGER-Lab/MMLU-Pro test 12", prompt="p", check={"letter": "I"}),
                     case(id="crux", from_="public", prompt="p", check={"literal": "[1, 'a']"}),
                     id="agentic"),
            budget=1))
        cases = doc["document"]["workloads"][0]["cases"]
        self.assertEqual(cases[0]["tools"], tools)
        self.assertEqual(cases[0]["turns"], 4)
        one = lambda **attrs: lambda: declare_document(scout(  # noqa: E731
            workload(case(id="c", from_="synthetic", prompt="p", **attrs), id="w"), budget=1))
        for why, attrs in {
            "tool needs the case's tools": {"check": {"tool": "send_email"}},
            "letter is one capital letter": {"check": {"letter": "ab"}},
            "turns goes with tools": {"check": {"exact": "x"}, "turns": 3},
            "a tool's name is a word": {"check": {"exact": "x"}, "tools": [{"name": "a b", "parameters": {}}]},
            "a result is": {"check": {"exact": "x"}, "tools": [
                {"name": "a", "parameters": {}, "results": [{"when": {"x": 1}, "result": "r"}]}]},
            r"program is \{ data: \[\[x, y\], …\] \}": {"check": {"program": {"data": []}}},
            "program tolerance is a number of 0 or more": {"check": {"program": {"data": [[1, 4]], "tolerance": -1}}},
        }.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                one(**attrs)()
        prog = declare_document(scout(
            workload(case(id="c", from_="synthetic", prompt="p", check={"program": {"data": [[1, 4], [2, 7], [5, 16]]}}),
                     id="w"), budget=1))
        self.assertEqual(prog["document"]["workloads"][0]["cases"][0]["check"],
                         {"program": {"data": [[1, 4], [2, 7], [5, 16]]}})

    def test_a_replacement_analysis_declares_its_layers_capabilities_and_decision(self):
        doc = declare_document(replacement(
            layer(
                capability(evidence(source="beehiiv checklist", claim="reported"), id="bulk-send",
                           title="3M+ emails a minute", need="must", have="none", effort="XL", run=2000, labour=160,
                           note="ESP or own MTAs"),
                capability(id="abuse", title="signup validation", need="must", have="partial", effort="L",
                           ref="docs/moderation.md"),
                kind="invisible", title="Deliverability"),
            layer(capability(id="collab", title="real-time collaboration", need="should", have="partial", effort="M"),
                  kind="visible", title="Editor"),
            layer(kind="visible", title="Website"),
            decision(choice="skip", because="The invisible layer is the product."),
            differentiation(text="Agents author the newsletter as code."),
            economics(price="$49 a month", margin="unknown"),
            product="beehiiv", vendor="beehiiv, Inc.", url="https://www.beehiiv.com", as_of="2026-10-14", by="scout"))
        self.assertEqual(doc["format"], "replacement")
        self.assertEqual(doc["document"], BEEHIIV)
        self.assertEqual(SCOUTS["replacement"].from_tree(SCOUTS["replacement"].to_tree(BEEHIIV)), BEEHIIV, "both ways")

    def test_a_replacement_analysis_refuses_a_value_its_sums_cannot_read(self):
        def one(**attrs):
            props = {"id": "c", "title": "t", "need": "must", "have": "none", **attrs}
            return lambda: declare_document(replacement(
                layer(capability(**props), kind="visible", title="V"), product="p", as_of="2026-10-14"))
        bad = {
            "need is one of must, should, later": one(need="nice"),
            "have is one of built, partial, none": one(have="some"),
            "effort is one of S, M, L, XL": one(effort="XXL"),
            "run is a number of 0 or more": one(run="ESP or own MTAs"),
            "asOf is a day": lambda: declare_document(replacement(product="p", as_of="October")),
            "kind is one of visible, invisible": lambda: declare_document(replacement(
                layer(kind="hidden", title="H"), product="p", as_of="2026-10-14")),
            "choice is one of build, buy, integrate, skip": lambda: declare_document(replacement(
                decision(choice="maybe", because="x"), product="p", as_of="2026-10-14")),
        }
        for why, declare in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare()


if __name__ == "__main__":
    unittest.main()
