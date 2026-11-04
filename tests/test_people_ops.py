"""A company's Team(...) declared in Python reads as the same `team` as the TypeScript SDK's <Team> (people-ops.test.ts),
and each part names the call it was written in. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.business import Band, Benefit, Checklist, Company, People, Role, Team, document_of


class PeopleOpsTests(unittest.TestCase):
    def test_team_is_the_company_team(self):
        d = document_of(Company(
            People(folder="Northwind/people/"),
            Team(
                Role(id="ceo", title="Managing member"),
                Role(id="pilot", title="Drone pilot", reports_to="ceo", band="ic-2", headcount=2, kind="employee"),
                Band(id="ic-2", currency="USD", per="year", min="80000", max="110000"),
                Benefit(id="health", kind="health", eligible=["employee"], waiting_days=30),
                Checklist(id="onboarding", when="start", steps=["Sign the offer"]),
                hiring="Northwind/hiring/"),
            name="Northwind"))
        self.assertEqual(d["document"]["team"], {
            "hiring": "Northwind/hiring/",
            "roles": [{"id": "ceo", "title": "Managing member"}, {"id": "pilot", "title": "Drone pilot", "reportsTo": "ceo", "band": "ic-2", "headcount": 2, "kind": "employee"}],
            "bands": [{"id": "ic-2", "currency": "USD", "per": "year", "min": "80000", "max": "110000"}],
            "benefits": [{"id": "health", "kind": "health", "eligible": ["employee"], "waitingDays": 30}],
            "checklists": [{"id": "onboarding", "when": "start", "steps": ["Sign the offer"]}],
        })
        self.assertNotIn("team", document_of(Company(name="Bare"))["document"])

    def test_what_the_team_does_not_say_is_refused(self):
        with self.assertRaisesRegex(ValueError, "<Role> has no attribute ssn"):
            document_of(Company(Team(Role(id="x", title="X", ssn="123-45-6789")), name="N"))
        with self.assertRaisesRegex(ValueError, "<Company> has two <Team>"):
            document_of(Company(Team(), Team(), name="N"))
        with self.assertRaisesRegex(ValueError, "<Company> does not take <Role>"):
            document_of(Company(Role(id="x", title="X"), name="N"))

    def test_run_module_names_each_part_by_its_call(self):
        out = run_module(
            "from commandagi.design.business import Company, Role, Team\n"
            "result = Company(\n"
            "    Team(\n"
            "        Role(id=\"ceo\", title=\"Chief\"),\n"
            "    ),\n"
            "    name=\"N\",\n"
            ")\n", "N.company.py")
        self.assertIn("team/roles/0", out["document"]["sources"])


if __name__ == "__main__":
    unittest.main()
