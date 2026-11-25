"""A money account declared in Python gives what the TypeScript vocabulary's JSX gives (money.ts in the CommandAGI
repository): its connections, its counterparties and their payees, and its recurring payments.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.money import At, Connection, Counterparty, MoneyAccount, Recurring

OPERATING = {
    "name": "Operating", "kind": "checking", "institution": "Mercury", "last4": "0000", "currency": "USD",
    "ledger": "Assets:Cash:Operating", "books": "../books/main.journal",
    "connections": [
        {"id": "direct", "provider": "mercury", "account": "acc_test_operating"},
        {"id": "view", "provider": "plaid", "account": "acc_test_plaid", "mode": "sandbox"},
    ],
    "counterparties": [
        {"id": "landlord", "name": "Harbor Properties LLC", "at": [{"connection": "direct", "recipient": "rcp_test_landlord"}]},
        {"id": "reserve", "name": "Reserve", "file": "Reserve.money.tsx"},
    ],
    "recurring": [{"id": "rent", "to": "landlord", "amount": "4200.00", "rail": "ach", "every": "month", "day": 1, "by": "person:mock-founder", "starts": "2027-01-01", "memo": "Rent"}],
}

ACCOUNT = {"name": "Operating", "kind": "checking", "institution": "Mercury", "last4": "0000", "currency": "USD",
           "ledger": "Assets:Cash:Operating", "books": "../books/main.journal"}


def operating(**recurring):
    return MoneyAccount(
        Connection(id="direct", provider="mercury", account="acc_test_operating"),
        Connection(id="view", provider="plaid", account="acc_test_plaid", mode="sandbox"),
        Counterparty(At(connection="direct", recipient="rcp_test_landlord"), id="landlord", name="Harbor Properties LLC"),
        Counterparty(id="reserve", name="Reserve", file="Reserve.money.tsx"),
        Recurring(**{"id": "rent", "to": "landlord", "amount": "4200.00", "rail": "ach", "every": "month", "day": "1",
                     "by": "person:mock-founder", "starts": "2027-01-01", "memo": "Rent", **recurring}),
        **ACCOUNT)


class MoneyTests(unittest.TestCase):
    def test_a_money_account_is_its_document(self):
        d = declare_document(operating())
        self.assertEqual(d["format"], "money")
        self.assertEqual(d["document"], OPERATING)

    def test_a_money_file_runs(self):
        out = run_module(
            "from commandagi.design.money import At, Connection, Counterparty, MoneyAccount\n"
            "result = MoneyAccount(Connection(id=\"direct\", provider=\"mercury\", account=\"acc_test_operating\"),"
            " Counterparty(At(connection=\"direct\", recipient=\"rcp_test_landlord\"), id=\"landlord\", name=\"Harbor Properties LLC\"),"
            " name=\"Operating\", kind=\"checking\")\n",
            "money/Operating.money.py")
        self.assertEqual(out["document"]["format"], "money")
        self.assertEqual(out["document"]["document"]["counterparties"][0]["at"], [{"connection": "direct", "recipient": "rcp_test_landlord"}])

    def test_a_bad_money_account_is_refused(self):
        bad = {
            "kind is checking": lambda: MoneyAccount(name="Operating", kind="piggy-bank"),
            "last4 is the last four digits": lambda: MoneyAccount(name="Operating", kind="checking", last4="123456"),
            "routingNumber is not read": lambda: MoneyAccount(name="Operating", kind="checking", routing_number="000000000"),
            "provider is stripe-financial-connections": lambda: MoneyAccount(Connection(id="x", provider="acme", account="a"), name="O", kind="checking"),
            "accessToken is not read": lambda: MoneyAccount(Connection(id="x", provider="plaid", account="a", access_token="t"), name="O", kind="checking"),
            "needs an <At connection recipient>": lambda: MoneyAccount(Counterparty(id="a", name="A"), name="O", kind="checking"),
            "<At> connection is the id of a <Connection>": lambda: MoneyAccount(Counterparty(At(connection="nowhere", recipient="r"), id="a", name="A"), name="O", kind="checking"),
            "to is the id of a <Counterparty>": lambda: operating(to="nobody"),
            "amount is a decimal text": lambda: operating(amount=4200),
            "rail is ach": lambda: operating(rail="swift"),
            "day is a whole number from 1 to 7": lambda: operating(every="week", day=9),
            "by is the principal": lambda: operating(by="jacob"),
        }
        for why, make in bad.items():
            with self.assertRaises(ValueError, msg=why) as e:
                declare_document(make())
            self.assertIn(why, str(e.exception))


if __name__ == "__main__":
    unittest.main()
