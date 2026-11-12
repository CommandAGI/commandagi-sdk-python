"""A company's legal profile (website, email, phone, Address, Listing, Stock, Owner), read as the same document as the TypeScript
SDK's JSX. company_profile.json is the golden of the three SDKs. Run: python -m unittest discover -s tests"""
import json
import pathlib
import unittest

from commandagi.design.business import Address, Company, Entity, Listing, Owner, Stock, document_of

_TAGS = {"Entity": Entity, "Address": Address, "Listing": Listing, "Stock": Stock, "Owner": Owner}


def _company(props, children):
    parts = [_TAGS[c["tag"]](**c["attrs"]) for c in children]
    return document_of(Company(*parts, **props))["document"]


class CompanyProfileTests(unittest.TestCase):
    def test_the_golden(self):
        golden = json.loads((pathlib.Path(__file__).parent / "company_profile.json").read_text(encoding="utf-8"))
        for row in golden["valid"]:
            d = _company(row["company"], row["children"])
            for field, want in row["document"].items():
                self.assertEqual(d.get(field), want, field)
        for row in golden["invalid"]:
            with self.assertRaisesRegex(ValueError, row["error"]):
                _company({"name": "Acme"}, [{"tag": "Entity", "attrs": {"jurisdiction": "US-DE"}}, row])


if __name__ == "__main__":
    unittest.main()
