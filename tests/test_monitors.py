"""Monitor blueprints declared in Python give what the TypeScript SDK's JSX gives (monitors.test.ts there): a class is
a function, its instances data, and the run gives the MonitorsDoc; what the vocabulary has no words for is refused.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.monitors import follows, monitor, monitors, source, wake


def series(id, title, code, every="6h"):
    return monitor(source(id="fred", adapter="fred", params={"series": code}, every=every),
                   id=f"economy/{id}", title=title, class_="economic-series", about=f"fred:{code}")


class MonitorTests(unittest.TestCase):
    def test_a_blueprint_is_its_monitors(self):
        d = declare_document(monitors(
            [series(*row) for row in [("cpi", "CPI, all items", "CPIAUCSL"), ("unrate", "Unemployment rate", "UNRATE")]],
            monitor(source(id="dgs10", adapter="fred", params={"series": "DGS10"}, every="6h"),
                    follows(monitor="economy/cpi", match="fred.*"),
                    wake(match="fred.observation", prompt="Say what moved."),
                    id="economy/treasury-yields", title="Treasury yields", class_="interest-rate", visibility="unlisted"),
            id="economy", title="Economy"))
        cpi = {"id": "economy/cpi", "title": "CPI, all items", "class": "economic-series", "about": "fred:CPIAUCSL",
               "sources": [{"id": "fred", "adapter": "fred", "params": {"series": "CPIAUCSL"}, "every": "6h"}], "follows": [], "wakes": []}
        self.assertEqual(d["format"], "monitors")
        self.assertEqual(d["document"]["monitors"][0], cpi)
        self.assertEqual(d["document"]["monitors"][2], {
            "id": "economy/treasury-yields", "title": "Treasury yields", "class": "interest-rate", "visibility": "unlisted",
            "sources": [{"id": "dgs10", "adapter": "fred", "params": {"series": "DGS10"}, "every": "6h"}],
            "follows": [{"monitor": "economy/cpi", "match": "fred.*"}],
            "wakes": [{"match": "fred.observation", "prompt": "Say what moved."}]})

    def test_refusals(self):
        def one(*children):
            return declare_document(monitors(monitor(*children, id="m"), id="b"))
        with self.assertRaisesRegex(ValueError, 'two <source> in <monitor> have id "s"'):
            one(source(id="s", adapter="fred", every="1h"), source(id="s", adapter="fred", every="1h"))
        with self.assertRaisesRegex(ValueError, "every is from 30s to 7d"):
            one(source(id="s", adapter="fred", every="10s"))
        with self.assertRaisesRegex(ValueError, "every is a duration"):
            one(source(id="s", adapter="fred", every="hourly"))
        with self.assertRaisesRegex(ValueError, "follows itself"):
            one(follows(monitor="m"))
        with self.assertRaisesRegex(ValueError, 'visibility is "public", "unlisted", "private"'):
            declare_document(monitors(monitor(id="m", visibility="secret"), id="b"))


if __name__ == "__main__":
    unittest.main()
