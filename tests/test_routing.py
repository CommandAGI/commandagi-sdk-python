"""The routing vocabulary has the same code document shape as the other SDKs."""
import unittest
from commandagi.design import run_module


class RoutingTests(unittest.TestCase):
    def test_routes_contain_each_knowledge_record_kind(self):
        result = run_module('''from commandagi.design.routing import routing, prior, rule, price, observation
result = routing(
    prior(id="abstract-codex", region="abstract", harness="codex", quality=0.75, evidence="reported"),
    rule(id="cli-only", deny=True, reason="CLI login only"),
    price(id="api-model", model="provider/model", input_per_million=1.2),
    observation(id="sample", count=4, cost=0.2, evidence="checked"))
''', "routing.py")
        document = result["document"]["document"]
        self.assertEqual(document["priors"][0]["id"], "abstract-codex")
        self.assertTrue(document["rules"][0]["deny"])
        self.assertEqual(document["prices"][0]["inputPerMillion"], 1.2)
        self.assertEqual(document["observations"][0]["count"], 4)

    def test_duplicate_keys_are_refused(self):
        with self.assertRaisesRegex(ValueError, "two <rule> in <routing>"):
            run_module('''from commandagi.design.routing import routing, rule
result = routing(rule(id="same"), rule(id="same"))
''', "routing.py")
