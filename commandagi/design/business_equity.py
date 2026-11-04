"""A company's priced round, pro forma, in Python — the same ``<Round>`` and ``<Investment>`` as the TypeScript SDK's
``business-equity.ts`` (docs/formats.md § companies, "a round, pro forma"; docs/company-substrate.md § equity
instruments)::

    from commandagi.design.business import CapTable, Company, Investment, Round

    result = Company(
        CapTable(ocf="Kite Works/captable/"),
        Round(Investment(stakeholder="Lead Fund", amount="5000000"),
              name="Series A", date="2027-03-01", pre_money="20000000", currency="USD", pool_target="0.10"),
        name="Kite Works",
    )

A round is a model, not a record: the cap table (Open Cap Table Format) holds what happened, and the company app
computes the price, each SAFE's and note's conversion and every holder's part after it. ``business.py`` takes these
tags into its vocabulary; the company document's ``rounds`` lists each round with its investments, in the order written.
"""
from __future__ import annotations

from typing import Any, Dict, List

EQUITY_TAGS: Dict[str, Dict[str, Any]] = {
    "Round": {"props": {"name": "text", "date": "text", "preMoney": "amount", "raise": "amount", "currency": "text", "poolTarget": "amount",
                        "poolTopUp": "amount", "pricePlaces": "amount", "stockClass": "text"},
              "required": ["name", "preMoney"], "many": {"investments": "Investment"}},
    "Investment": {"props": {"stakeholder": "text", "amount": "amount", "instrument": "text"}, "required": ["stakeholder", "amount"]},
}


def rounds_of(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The company document's ``rounds``: each round's attributes and its investments, in the order written."""
    return [dict(r["props"]) | {"investments": [dict(i["props"]) for i in r["many"]["investments"]]} for r in node["many"].get("rounds", [])]
