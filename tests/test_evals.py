"""An eval and a metric declared in Python give what the TypeScript SDK's JSX gives (evals.test.ts in that SDK, the
same example): each is its record both ways; a case names its task file or says its instruction (one of the two);
`frozen` is a digest; what does not read is refused with why. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.evals import EVALS, case, eval, metric

DIGEST = "sha256:" + "ab" * 32
EVAL = {
    "slug": "yard-shakedown",
    "domain": "robot",
    "version": "3",
    "metrics": ["Fleet availability.metric.tsx"],
    "repeats": 3,
    "frozen": DIGEST,
    "cases": [
        {"slug": "undock-and-lap", "name": "Undock and lap", "task": "../Tasks/Undock and lap.task.tsx",
         "environment": {"kind": "synthetic", "seed": 41}},
        {"slug": "open-a-terminal", "name": "Open a terminal", "instruction": "Open a terminal window.",
         "acceptanceMetric": "Terminal open.metric.tsx", "hints": ["The dock has a terminal icon."], "timeLimitMs": 120000,
         "environment": {"kind": "none"}, "tags": ["smoke"]},
    ],
}
METRIC = {"slug": "fleet-availability", "probe": {"kind": "event", "eventKind": "telemetry"}, "aggregation": "rate", "target": 0.96}

SOURCE = '''from commandagi.design.evals import case, eval

result = eval(
    case(slug="undock-and-lap", name="Undock and lap", task="../Tasks/Undock and lap.task.tsx",
         environment={"kind": "synthetic", "seed": 41}),
    case(slug="open-a-terminal", name="Open a terminal", instruction="Open a terminal window.",
         acceptance_metric="Terminal open.metric.tsx", hints=["The dock has a terminal icon."], time_limit_ms=120000,
         environment={"kind": "none"}, tags=["smoke"]),
    slug="yard-shakedown", domain="robot", version="3", metrics=["Fleet availability.metric.tsx"], repeats=3,
    frozen="sha256:''' + "ab" * 32 + '''",
)
'''


class EvalTests(unittest.TestCase):
    def test_an_eval_holds_one_case_per_case_each_named_by_its_slug(self):
        out = run_module(SOURCE, "Evals/Yard shakedown.eval.py")
        self.assertEqual(out["graph"]["nodes"], {}, "an eval leaves beside an empty graph")
        self.assertEqual(out["document"]["format"], "eval")
        self.assertEqual(out["document"]["document"], EVAL)
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "case#open-a-terminal", "case#undock-and-lap"])
        self.assertEqual((sources["case#undock-and-lap"]["tag"], sources["case#undock-and-lap"]["line"]), ("case", 4))
        self.assertEqual(EVALS["eval"].from_tree(EVALS["eval"].to_tree(EVAL)), EVAL, "both ways")
        self.assertEqual(EVALS["eval"].empty("Yard shakedown"), {"slug": "yard-shakedown", "cases": []})

    def test_a_metric_is_one_element(self):
        d = declare_document(metric(slug="fleet-availability", probe={"kind": "event", "eventKind": "telemetry"},
                                    aggregation="rate", target=0.96))
        self.assertEqual(d, {"format": "metric", "sources": {}, "document": METRIC})
        self.assertEqual(EVALS["metric"].from_tree(EVALS["metric"].to_tree(METRIC)), METRIC, "both ways")
        self.assertEqual(declare_document(metric(slug="m", probe={"kind": "event"}, aggregation="rate", pass_={"min": 1}))["document"]["pass"], {"min": 1})

    def test_what_does_not_read_is_refused_with_why(self):
        def kase(**attrs):
            return lambda: declare_document(eval(case(slug="c", name="C", **{"environment": {"kind": "none"}, **attrs}), slug="e"))
        bad = {
            "says what the agent is handed once: .* not neither": kase(),
            "not both": kase(task="a.task.tsx", instruction="Do it."),
            "task is text": kase(task={"id": "t", "instruction": "Do it."}),
            "environment is a world": kase(instruction="Do it.", environment={"seed": 1}),
            "timeLimitMs is a whole number": kase(instruction="Do it.", time_limit_ms=1.5),
            "frozen is the digest the eval is frozen at": lambda: declare_document(eval(slug="e", frozen=True)),
            "metricIds is not read": lambda: declare_document(eval(slug="e", metric_ids=["m1"])),
            "metrics is a list of texts": lambda: declare_document(eval(slug="e", metrics="m.metric.tsx")),
            "probe is what to measure": lambda: declare_document(metric(slug="m", probe={}, aggregation="rate")),
            "<metric> needs probe": lambda: declare_document(metric(slug="m", aggregation="rate")),
        }
        for why, declare in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare()


if __name__ == "__main__":
    unittest.main()
