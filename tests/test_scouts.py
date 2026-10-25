"""A scout's comparison and a replacement-cost analysis in Python give what the TypeScript SDK's JSX gives
(scouts.test.ts in that SDK, the same examples): each is its record both ways, and what would make a run dishonest is
refused by name (a customer's case, a case with two scorers, two incumbents, a check with no kind, a letter that is not
one). Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.scouts import SCOUTS, capability, case, configuration, decision, evidence, judge, layer, replacement, scout, workload

COMPARISON = {
    "title": "GLM against Sonnet",
    "budget": 10,
    "repeats": 3,
    "configurations": [
        {"id": "sonnet", "model": "anthropic/claude-sonnet-5-5", "effort": "low", "incumbent": True},
        {"id": "glm", "model": "dashscope/glm-5.3"},
    ],
    "workloads": [{
        "id": "knowledge", "title": "Knowledge work", "sample": 20, "needs": ["structured"],
        "cases": [
            {"id": "rate", "from": "synthetic", "prompt": "What is 4.2% as a decimal?",
             "check": {"number": 0.042, "tolerance": 0.0005}},
            {"id": "page", "from": "own-run", "source": "runs/thread-1/streams/chat@a/records.jsonl#12",
             "prompt": "Write the provider page.", "rubric": "Names the price and the terms."},
        ],
    }],
    "judges": [{"model": "openai/gpt-5.6-terra"}],
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
        id="knowledge", title="Knowledge work", sample=20, needs=["structured"],
    ),
    judge(model="openai/gpt-5.6-terra"),
    title="GLM against Sonnet", budget=10, repeats=3,
)
'''


def comparison(case_props=None, more=()):
    """The example comparison, with a case's props replaced (`case_props`) and more children."""
    props = {"id": "rate", "from": "synthetic", "prompt": "What is 4.2% as a decimal?",
             "check": {"number": 0.042, "tolerance": 0.0005}, **(case_props or {})}
    if "from" in props:
        props["from_"] = props.pop("from")
    return declare_document(scout(
        configuration(id="sonnet", model="anthropic/claude-sonnet-5-5", effort="low", incumbent=True),
        configuration(id="glm", model="dashscope/glm-5.3"),
        workload(
            case(**props),
            case(id="page", from_="own-run", source="runs/thread-1/streams/chat@a/records.jsonl#12",
                 prompt="Write the provider page.", rubric="Names the price and the terms."),
            id="knowledge", title="Knowledge work", sample=20, needs=["structured"],
        ),
        judge(model="openai/gpt-5.6-terra"),
        *more,
        title="GLM against Sonnet", budget=10, repeats=3,
    ))


class ScoutTests(unittest.TestCase):
    def test_a_comparison_declares_its_configurations_workloads_with_their_cases_and_judges(self):
        out = run_module(SOURCE, "scouts/GLM against Sonnet.scout.py")
        self.assertEqual(out["graph"]["nodes"], {}, "a comparison leaves beside an empty graph")
        self.assertEqual(out["document"]["format"], "scout")
        self.assertEqual(out["document"]["document"], COMPARISON)
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "configuration#glm", "configuration#sonnet", "judge#openai/gpt-5.6-terra",
                                           "workload#knowledge", "workload#knowledge/case#page", "workload#knowledge/case#rate"])
        self.assertEqual((sources["workload#knowledge/case#rate"]["tag"], sources["workload#knowledge/case#rate"]["line"]), ("case", 7))
        self.assertEqual(SCOUTS["scout"].from_tree(SCOUTS["scout"].to_tree(COMPARISON)), COMPARISON, "both ways")

    def test_a_comparison_refuses_what_would_make_its_verdict_dishonest(self):
        bad = {
            r"from is one of public, synthetic, own-run": lambda: comparison({"from": "customer"}),
            r"exactly one of check .* or rubric": lambda: comparison({"rubric": "and a judge"}),
            r"check is exactly one of": lambda: comparison({"check": {"tolerance": 1}}),
            r"it has exact and contains": lambda: comparison({"check": {"exact": "a", "contains": ["b"]}}),
            r"not a regular expression": lambda: comparison({"check": {"regex": "("}}),
            r"one incumbent": lambda: comparison(more=[configuration(id="third", model="openai/gpt-6-luna", incumbent=True)]),
            r"budget is a number above 0": lambda: declare_document(scout(budget=0)),
            r"needs budget": lambda: declare_document(scout(title="no budget")),
            r"<case> stands in": lambda: declare_document(scout(case(id="x", from_="public", prompt="p", check={"exact": "1"}), budget=5)),
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
            workload(
                case(id="chain", from_="synthetic", prompt="p", tools=tools, turns=4, check={"number": 4280000}),
                case(id="first", from_="synthetic", prompt="p", tools=tools, check={"tool": "send_email"}),
                case(id="mc", from_="public", source="TIGER-Lab/MMLU-Pro test 12", prompt="p", check={"letter": "I"}),
                case(id="crux", from_="public", prompt="p", check={"literal": "[1, 'a']"}),
                id="agentic",
            ),
            budget=1,
        ))["document"]
        cases = doc["workloads"][0]["cases"]
        self.assertEqual(cases[0]["tools"], tools)
        self.assertEqual(cases[0]["turns"], 4)

        def one(**props):
            return lambda: declare_document(scout(workload(case(id="c", from_="synthetic", prompt="p", **props), id="w"), budget=1))

        prog = one(check={"program": {"data": [[1, 4], [2, 7], [5, 16]]}})()
        self.assertEqual(prog["document"]["workloads"][0]["cases"][0]["check"], {"program": {"data": [[1, 4], [2, 7], [5, 16]]}})
        bad = {
            r"tool needs the case's tools": one(check={"tool": "send_email"}),
            r"letter is one capital letter": one(check={"letter": "ab"}),
            r"turns goes with tools": one(check={"exact": "x"}, turns=3),
            r"a tool's name is a word": one(check={"exact": "x"}, tools=[{"name": "a b", "parameters": {}}]),
            r"a result is": one(check={"exact": "x"}, tools=[{"name": "a", "parameters": {}, "results": [{"when": {"x": 1}, "result": "r"}]}]),
            r"program is \{ data: \[\[x, y\], …\] \}": one(check={"program": {"data": []}}),
            r"program is \{ data: \[\[x, y\], …\] \}": one(check={"program": {"data": [[1, 4], [2]]}}),
            r"program tolerance is a number of 0 or more": one(check={"program": {"data": [[1, 4]], "tolerance": -1}}),
        }
        for why, declare in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare()

    def test_a_replacement_analysis_declares_its_layers_capabilities_with_evidence_and_its_decision(self):
        source = '''from commandagi.design.scouts import capability, decision, differentiation, economics, evidence, layer, replacement

result = replacement(
    layer(
        capability(
            evidence(source="beehiiv checklist", claim="reported"),
            id="bulk-send", title="3M+ emails a minute", need="must", have="none", effort="XL", run=2000, labour=160,
            note="ESP or own MTAs",
        ),
        capability(id="abuse", title="signup validation", need="must", have="partial", effort="L", ref="docs/moderation.md"),
        kind="invisible", title="Deliverability",
    ),
    layer(capability(id="collab", title="real-time collaboration", need="should", have="partial", effort="M"),
          kind="visible", title="Editor"),
    layer(kind="visible", title="Website"),
    decision(choice="skip", because="The invisible layer is the product."),
    differentiation(text="Agents author the newsletter as code."),
    economics(price="$49 a month", margin="unknown"),
    product="beehiiv", vendor="beehiiv, Inc.", url="https://www.beehiiv.com", as_of="2026-10-14", by="scout",
)
'''
        out = run_module(source, "scouts/beehiiv.replacement.py")
        self.assertEqual(out["document"]["format"], "replacement")
        doc = out["document"]["document"]
        self.assertEqual([layer_["title"] for layer_ in doc["layers"]], ["Deliverability", "Editor", "Website"])
        self.assertEqual(doc["layers"][0]["capabilities"][0], {
            "id": "bulk-send", "title": "3M+ emails a minute", "need": "must", "have": "none", "effort": "XL", "run": 2000,
            "labour": 160, "note": "ESP or own MTAs", "evidence": [{"source": "beehiiv checklist", "claim": "reported"}],
        })
        self.assertEqual(doc["decision"], {"choice": "skip", "because": "The invisible layer is the product."})
        self.assertEqual(doc["differentiation"], "Agents author the newsletter as code.")
        self.assertEqual(doc["economics"], {"price": "$49 a month", "margin": "unknown"})
        self.assertEqual(SCOUTS["replacement"].from_tree(SCOUTS["replacement"].to_tree(doc)), doc, "both ways")

    def test_a_replacement_analysis_refuses_a_value_its_sums_cannot_read(self):
        def one(**props):
            return lambda: declare_document(replacement(
                layer(capability(**{"id": "c", "title": "t", "need": "must", "have": "none", **props}),
                      kind="visible", title="V"),
                product="p", as_of="2026-10-14"))

        bad = {
            r"need is one of must, should, later": one(need="nice"),
            r"have is one of built, partial, none": one(have="some"),
            r"effort is one of S, M, L, XL": one(effort="XXL"),
            r"run is a number of 0 or more": one(run="ESP or own MTAs"),
            r"asOf is a day": lambda: declare_document(replacement(product="p", as_of="October")),
            r"kind is one of visible, invisible": lambda: declare_document(
                replacement(layer(kind="hidden", title="H"), product="p", as_of="2026-10-14")),
            r"choice is one of build, buy, integrate, skip": lambda: declare_document(
                replacement(decision(choice="maybe", because="x"), product="p", as_of="2026-10-14")),
        }
        for why, declare in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare()


if __name__ == "__main__":
    unittest.main()
