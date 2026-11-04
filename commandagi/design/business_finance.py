"""A company's finance in Python — the elements ``business.py`` reads inside a ``Company`` (the TypeScript SDK's
``business-finance.ts``; CommandAGI docs/company-substrate.md § finance operations)::

    Company(
        Books(journal="Northwind/books/main.journal"),
        Budget(journal="Northwind/books/budget.journal"),
        BankAccount(name="Operating", provider="First Bank", last4="4321", currency="USD", ledger="Assets:Cash:Operating",
                    kind="checking", statements="Northwind/bank/operating/"),
        Payroll(provider="Gusto", ledger="Expenses:Payroll", register="Northwind/payroll/", schedule="semimonthly"),
        DataRoom(Include(document="Northwind/Documents/Charter.pdf", section="corporate"), name="Seed round", expires="2026-12-31"),
        name="Northwind",
    )

Each element only refs files. A bank account names its journal account (``ledger``) and the folder of its
statements; at most the last four digits of its number, never the number. ``finance_of`` gives the company's ``finance``
(None when it names none of these).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_TEXT = "text"

FINANCE_TAGS: Dict[str, Dict[str, Any]] = {
    "Budget": {"props": {"journal": _TEXT}, "required": ["journal"]},
    "BankAccount": {"props": {"name": _TEXT, "provider": _TEXT, "last4": _TEXT, "currency": _TEXT, "ledger": _TEXT, "kind": _TEXT,
                              "statements": _TEXT, "opened": _TEXT, "closed": _TEXT}, "required": ["name"]},
    "Payroll": {"props": {"provider": _TEXT, "ledger": _TEXT, "register": _TEXT, "schedule": _TEXT, "jurisdiction": _TEXT}, "required": ["provider"]},
    "DataRoom": {"props": {"name": _TEXT, "about": _TEXT, "expires": _TEXT}, "required": ["name"], "many": {"include": "Include"}},
    "Include": {"props": {"document": _TEXT, "section": _TEXT}, "required": ["document"]},
}

#: The children a ``Company`` takes for its finance, by the field each fills.
COMPANY_FINANCE_ONE = {"budget": "Budget"}
COMPANY_FINANCE_MANY = {"bankAccounts": "BankAccount", "payroll": "Payroll", "dataRooms": "DataRoom"}


def finance_of(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A company's ``finance`` from its ``Company`` node, or None when it names none of it."""
    one, many = node["one"], node["many"]
    rows = {f: [dict(n["props"]) for n in many.get(f, [])] for f in ("bankAccounts", "payroll")}
    rooms = [dict(n["props"]) | {"include": [dict(i["props"]) for i in n["many"]["include"]]} for n in many.get("dataRooms", [])]
    budget = one["budget"]["props"]["journal"] if one.get("budget") else None
    if not (budget or rows["bankAccounts"] or rows["payroll"] or rooms):
        return None
    return {"budget": budget, "bankAccounts": rows["bankAccounts"], "payroll": rows["payroll"], "dataRooms": rooms}
