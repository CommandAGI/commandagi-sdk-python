"""A company's finance in Python: the same ``finance`` the TypeScript SDK's business-finance.test.ts pins for the same
elements; absent when the company names none of it; an unknown attribute refused by name."""
import unittest

from commandagi.design.business import BankAccount, Budget, Company, DataRoom, Include, Payroll, document_of


class FinanceTest(unittest.TestCase):
    def test_finance_is_the_company_finance(self):
        d = document_of(Company(
            Budget(journal="Harbor/books/budget.journal"),
            BankAccount(name="Operating", provider="First Bank", last4="4321", currency="USD", ledger="Assets:Cash:Operating", kind="checking", statements="Harbor/bank/"),
            Payroll(provider="Gusto", ledger="Expenses:Payroll", register="Harbor/payroll/", schedule="semimonthly"),
            DataRoom(Include(document="Harbor/Documents/Charter.pdf", section="corporate"), name="Seed", expires="2026-12-31"),
            name="Harbor"))
        self.assertEqual(d["document"]["finance"], {
            "budget": "Harbor/books/budget.journal",
            "bankAccounts": [{"name": "Operating", "provider": "First Bank", "last4": "4321", "currency": "USD", "ledger": "Assets:Cash:Operating", "kind": "checking", "statements": "Harbor/bank/"}],
            "payroll": [{"provider": "Gusto", "ledger": "Expenses:Payroll", "register": "Harbor/payroll/", "schedule": "semimonthly"}],
            "dataRooms": [{"name": "Seed", "expires": "2026-12-31", "include": [{"document": "Harbor/Documents/Charter.pdf", "section": "corporate"}]}],
        })
        self.assertNotIn("finance", document_of(Company(name="Bare"))["document"])

    def test_a_finance_element_says_only_its_own_words(self):
        with self.assertRaisesRegex(ValueError, "<BankAccount> has no attribute accountNumber"):
            document_of(Company(BankAccount(name="Op", account_number="000123"), name="X"))
        with self.assertRaisesRegex(ValueError, "<Include> needs document"):
            document_of(Company(DataRoom(Include(), name="Seed"), name="X"))


if __name__ == "__main__":
    unittest.main()
