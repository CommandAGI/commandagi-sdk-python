"""A company's team declared in Python — the people operations a ``Company(...)`` declares in one ``Team(...)``, the same
elements as the TypeScript SDK's ``people-ops.ts``::

    from commandagi.design.business import Band, Benefit, Checklist, Company, People, Role, Team

    result = Company(
        People(folder="Northwind/people/"),
        Team(
            Role(id="ceo", title="Managing member"),
            Role(id="pilot", title="Drone pilot", reports_to="ceo", band="ic-2", headcount=2, kind="employee"),
            Band(id="ic-2", currency="USD", per="year", min="80000", max="110000"),
            Benefit(id="health", kind="health", waiting_days=30),
            Checklist(id="onboarding", when="start", steps=["Sign the offer"]),
            hiring="Northwind/hiring/",
        ),
        name="Northwind",
    )

The team holds what the company decides (roles and reporting lines, bands, benefit plans, checklists, the hiring
folder). The payroll provider is the company's finance (``Payroll``, ``business_finance.py``). People, payroll runs and grants stay their own files; no element takes a tax id, a bank
number or a date of birth. ``business.py`` reads these tags with its own; this module only declares them.
"""
from __future__ import annotations

from typing import Any, Dict

PEOPLE_OPS_TAGS: Dict[str, Dict[str, Any]] = {
    "Team": {"props": {"hiring": "text", "offerLetter": "text"},
             "many": {"roles": "Role", "bands": "Band", "benefits": "Benefit", "checklists": "Checklist"}},
    "Role": {"props": {"id": "text", "title": "text", "department": "text", "reportsTo": "text", "band": "text", "headcount": "amount", "kind": "text"},
             "required": ["id", "title"]},
    "Band": {"props": {"id": "text", "title": "text", "level": "text", "currency": "text", "per": "text", "min": "amount", "mid": "amount", "max": "amount"},
             "required": ["id", "currency", "per", "min", "max"]},
    "Benefit": {"props": {"id": "text", "kind": "text", "name": "text", "provider": "text", "policy": "text", "starts": "text", "renews": "text", "file": "text",
                          "eligible": "texts", "waitingDays": "amount", "employerShare": "amount"}, "required": ["kind"]},
    "Checklist": {"props": {"id": "text", "title": "text", "when": "text", "kinds": "texts", "steps": "texts"}, "required": ["id", "when", "steps"]},
}


def team_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """A company's ``team`` from its <Team>: each list in the file's order."""
    p = node["props"]

    def items(f: str):
        return [dict(n["props"]) for n in node["many"][f]]
    out: Dict[str, Any] = {"hiring": p.get("hiring")}
    if "offerLetter" in p:
        out["offerLetter"] = p["offerLetter"]
    out.update({"roles": items("roles"), "bands": items("bands"), "benefits": items("benefits"), "checklists": items("checklists")})
    return out
