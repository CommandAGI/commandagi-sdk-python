"""A company's deals, declared in Python, read as the TypeScript SDK's JSX reads them. company_deals.json is the golden of the
three SDKs (sdk/typescript/src/design/company-deals.golden.json). Run: python -m unittest discover -s tests"""
import json
import pathlib
import re
import unittest

from commandagi.design import business
from commandagi.design.business import document_of

GOLDEN = json.loads((pathlib.Path(__file__).parent / "company_deals.json").read_text(encoding="utf-8"))


def snake(attrs):
    """The golden writes TypeScript names; a keyword is the snake_case of one."""
    return {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): v for k, v in attrs.items()}


def element(tree):
    return getattr(business, tree["tag"])(*[element(c) for c in tree.get("children", [])], **snake(tree["attrs"]))


class CompanyDealsTests(unittest.TestCase):
    def test_each_part_is_the_company_document(self):
        for row in GOLDEN["valid"]:
            d = document_of(element(row["tree"]))
            self.assertEqual(d["format"], "company")
            self.assertEqual(d["document"], row["document"])

    def test_what_the_vocabulary_does_not_say_is_refused(self):
        for row in GOLDEN["invalid"]:
            with self.assertRaisesRegex(ValueError, row["error"]):
                document_of(element(row["tree"]))


if __name__ == "__main__":
    unittest.main()
