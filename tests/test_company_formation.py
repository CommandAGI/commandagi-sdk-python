"""A company's RegisteredAgent children, a Paper(kind="filing")'s filing attributes and Entity(dissolved=…), read as the same document as the TypeScript
SDK's JSX. company_formation.json is the golden of the three SDKs. Run: python -m unittest discover -s tests"""
import json
import pathlib
import unittest

from commandagi.design.business import Company, Entity, Paper, RegisteredAgent, document_of

_TAGS = {"Paper": Paper, "RegisteredAgent": RegisteredAgent}
_SNAKE = {"operatesIn": "operates_in", "fiscalYearEnd": "fiscal_year_end"}


def _company(entity, children):
    parts = [_TAGS[c["tag"]](**c["attrs"]) for c in children]
    return document_of(Company(Entity(**{_SNAKE.get(k, k): v for k, v in entity.items()}), *parts, name="Acme"))["document"]


class CompanyFormationTests(unittest.TestCase):
    def test_the_golden(self):
        golden = json.loads((pathlib.Path(__file__).parent / "company_formation.json").read_text(encoding="utf-8"))
        for row in golden["valid"]:
            d = _company(row["entity"], row["children"])
            self.assertEqual(d["entity"], row["document"]["entity"])
            self.assertEqual(d.get("papers"), row["document"]["papers"])
            self.assertEqual(d.get("registeredAgents"), row["document"]["registeredAgents"])
        for row in golden["invalid"]:
            with self.assertRaisesRegex(ValueError, row["error"]):
                _company({"jurisdiction": "US-DE"}, [row])


if __name__ == "__main__":
    unittest.main()
