"""A company's legal profile, declared in Python (docs/company-substrate.md § the legal profile): the facts a form asks
for, so an agent fills one from the company file alone. It adds the company's ``website``, its addresses by purpose
(``Address``), its classes of stock (``Stock``) and its beneficial owners (``Owner``); the same elements as the
TypeScript SDK's ``company-profile.ts``. A company names no mailbox and no phone line: a form's contact email and phone
are its responsible person's card::

    from commandagi.design.business import Address, Company, Entity, Owner, Stock

    result = Company(
        Entity(jurisdiction="US-DE", form="corporation", name="Acme Robotics, Inc.", formed="2026-01-05"),
        Address(kind="legal", line1="1 Main St", city="Austin", region="TX", postal="78701", country="US"),
        Stock(kind="common", authorized=10000000, issued=8000000, reserved=2000000, par="0.00001"),
        Owner(name="Ada Founder", holder="people/ada-founder/", percent="100"),
        name="Acme", website="https://acme.example",
    )

An address's ``kind`` is ``legal`` (the formation documents and the tax-id notice), ``mailing``, ``office`` or another
word. The document holds them as ``website``, ``addresses``, ``stock`` and ``owners``, each absent
when the file writes none. A company file with the profile's identifiers is private.
"""
from __future__ import annotations

from typing import Any, Dict

_TEXT, _AMOUNT = "text", "amount"

#: The attributes this part adds to ``Company``.
PROFILE_COMPANY_PROPS: Dict[str, str] = {"website": _TEXT}
PROFILE_TAGS: Dict[str, Dict[str, Any]] = {
    "Address": {"props": {k: _TEXT for k in ("kind", "line1", "line2", "city", "region", "postal", "country", "source")}, "required": ["kind", "line1", "country"]},
    "Stock": {"props": {"kind": _TEXT, "authorized": _AMOUNT, "issued": _AMOUNT, "reserved": _AMOUNT, "par": _TEXT, "source": _TEXT}, "required": ["kind", "authorized"]},
    "Owner": {"props": {"name": _TEXT, "holder": _TEXT, "percent": _AMOUNT, "since": _TEXT, "source": _TEXT}, "required": ["name", "percent"]},
}
PROFILE_LISTS: Dict[str, str] = {"addresses": "Address", "stock": "Stock", "owners": "Owner"}


def profile_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """The company document's profile fields, each only when the file writes it."""
    out: Dict[str, Any] = {k: node["props"][k] for k in PROFILE_COMPANY_PROPS if k in node["props"]}
    for field in PROFILE_LISTS:
        items = node["many"].get(field, [])
        if items:
            out[field] = [dict(n["props"]) for n in items]
    return out
