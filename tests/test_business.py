"""A company, an RFC and a case declared in Python read as the same documents as the TypeScript SDK's JSX
(business.test.ts), and each part names the call it was written in. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.business import (Books, CapTable, Case, Change, Company, Entity, Harm, Option, Registration, Relief, Rfc,
                                        document_of)


class BusinessTests(unittest.TestCase):
    def test_company_is_the_company_document(self):
        d = document_of(Company(
            Entity(jurisdiction="US-DE", form="llc", formed="2024-01-31", ids={"ein": "12-3"}),
            Books(journal="Northwind/books/main.journal"),
            CapTable(ocf="Northwind/captable/"),
            Registration(kind="tax-id", jurisdiction="US", id="12-3"),
            name="Northwind", files=["Northwind/"]))
        self.assertEqual(d["format"], "company")
        self.assertEqual(d["document"], {
            "format": "commandagi-company", "name": "Northwind", "about": "", "files": ["Northwind/"], "dashboard": None,
            "entity": {"jurisdiction": "US-DE", "form": "llc", "name": None, "formed": "2024-01-31", "fiscalYearEnd": None,
                       "ids": {"ein": "12-3"}, "operatesIn": []},
            "standard": {"enabled": True, "books": "Northwind/books/main.journal", "captable": "Northwind/captable/", "people": None,
                         "calendar": None, "registrations": [{"kind": "tax-id", "jurisdiction": "US", "id": "12-3"}], "matters": None},
        })
        self.assertEqual(document_of(Company(name="Bare"))["document"]["standard"], {"enabled": False})

    def test_rfc_and_case_are_their_drafts(self):
        rfc = document_of(Rfc(Option(Change(op="set_parameter", parameter="rfcDepositCents", value="500"), title="Ten hours"), id="rfc_1", title="Rest"))
        self.assertEqual(rfc["document"], {"id": "rfc_1", "draft": {"title": "Rest", "options": [
            {"title": "Ten hours", "changes": [{"op": "set_parameter", "value": "500", "key": "rfcDepositCents"}]}]}})
        case = document_of(Case(Harm(id="h1", interest="property", amount="4200"), Relief(kind="restitution", harm_ids=["h1"]), respondent="Acme"))
        self.assertEqual(case["document"], {"draft": {"respondent": "Acme", "harms": [{"id": "h1", "interest": "property", "amount": "4200"}],
                                                      "relief": [{"kind": "restitution", "harmIds": ["h1"]}]}})
        stored = document_of(Case(Harm(id="h1", amount=4200), Relief(kind="exclusion", amount=10.5, days=30)))
        self.assertEqual(stored["document"], {"draft": {"harms": [{"id": "h1", "amount": 4200}], "relief": [{"kind": "exclusion", "amount": 10.5, "days": 30}]}})
        with self.assertRaisesRegex(ValueError, "amount is text or a number"):
            document_of(Case(Harm(id="h1", amount=True)))

    def test_what_the_vocabulary_does_not_say_is_refused(self):
        with self.assertRaisesRegex(ValueError, "<Company> has no attribute mailbox"):
            document_of(Company(name="X", mailbox="a@b"))
        with self.assertRaisesRegex(ValueError, "<Company> does not take <Harm>"):
            document_of(Company(Harm(id="h"), name="X"))
        with self.assertRaisesRegex(ValueError, "<Company> needs name"):
            document_of(Company())
        with self.assertRaisesRegex(TypeError, "holds nothing"):
            Books(CapTable(ocf="x"), journal="j")
        with self.assertRaisesRegex(TypeError, "fiscalYearEnd is written fiscal_year_end"):
            Entity(jurisdiction="US", fiscalYearEnd="12-31")

    def test_run_module_names_each_part_by_its_call(self):
        out = run_module(
            "from commandagi.design.business import Change, Option, Rfc\n"
            "result = Rfc(\n"
            "    Option(Change(op=\"add_duty\", duty_id=\"rest\"), title=\"A\"),\n"
            "    Option(title=\"B\"),\n"
            "    title=\"Rest\",\n"
            ")\n", "Rest.rfc.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertIn("sourceMap", out["graph"]["meta"])
        self.assertEqual(out["document"]["document"]["draft"]["options"][0]["changes"], [{"op": "add_duty", "dutyId": "rest"}])
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "options/0", "options/0/changes/0", "options/1"])
        self.assertEqual((sources[""]["tag"], sources[""]["line"]), ("Rfc", 2))
        self.assertEqual((sources["options/0/changes/0"]["tag"], sources["options/0/changes/0"]["line"]), ("Change", 3))
        self.assertEqual(sources["options/0/changes/0"]["props"]["duty_id"]["value"], "rest")
        self.assertEqual((sources["options/1"]["tag"], sources["options/1"]["line"]), ("Option", 4))


if __name__ == "__main__":
    unittest.main()
