"""A company's deals declared in Python: its sales pipeline, one ``Deal`` child of the ``Company`` for each deal
(CommandAGI's docs/formats.md § companies, "deals"). The same element as the TypeScript SDK's ``company-deals.ts``;
``business.py`` defines its call, so it is imported from ``commandagi.design.business``::

    Company(
        Deal(id="acme-pilot", title="Pilot of ten units", counterparty="relationships/cards/acme.vcf", stage="proposal",
             value="120000", currency="USD", expected="2027-03-31", owner="ceo", since="2026-11-01"),
        name="Northwind",
    )

``counterparty`` names who the deal is with: a ref to a card (a ``.vcf``) or the id of a row of
``relationships/relationships.csv``. ``stage`` is ``lead``, ``qualified``, ``proposal``, ``negotiation``, ``won`` or
``lost``. ``value`` is the deal's worth as the file states it, in ``currency``; a deal with no value is one whose
worth is unknown. The company document gains ``deals`` only when the file writes one; every total is computed by
the app and never written.
"""
from __future__ import annotations

from typing import Any, Dict

_TEXT, _AMOUNT = "text", "amount"

#: The stages of a deal, in the order a pipeline shows them.
DEAL_STAGES = ("lead", "qualified", "proposal", "negotiation", "won", "lost")

DEALS_TAGS: Dict[str, Dict[str, Any]] = {
    "Deal": {"props": {"id": _TEXT, "title": _TEXT, "counterparty": _TEXT, "stage": _TEXT, "value": _AMOUNT, "currency": _TEXT, "expected": _TEXT,
                       "closed": _TEXT, "owner": _TEXT, "since": _TEXT, "source": _TEXT, "note": _TEXT}, "required": ["id", "title", "stage"]},
}

#: The children of a ``Company`` this adds, by the field it fills.
COMPANY_DEALS_MANY = {"deals": "Deal"}


def deals_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """What a Company's deals add to the company document: ``deals``, only when the file writes one."""
    deals = node["many"].get("deals", [])
    return {"deals": [dict(d["props"]) for d in deals]} if deals else {}
