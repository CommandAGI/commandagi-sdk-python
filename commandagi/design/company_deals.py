"""A company's deals declared in Python: its sales pipeline, one ``Deal`` child of the ``Company`` for each deal, and
the ``Pipeline`` that says what each stage is worth as a chance (CommandAGI's docs/formats.md § companies, "deals").
The same elements as the TypeScript SDK's ``company-deals.ts`` and the Rust SDK's ``company_deals.rs``;
``business.py`` defines their calls, so they are imported from ``commandagi.design.business``::

    Company(
        Pipeline(
            DealStage(id="lead", probability=0.1), DealStage(id="qualified", probability=0.25),
            DealStage(id="proposal", probability=0.5), DealStage(id="negotiation", probability=0.75),
            stale_days=30,
        ),
        Deal(
            DealMove(from_="lead", to="proposal", at="2026-11-01T17:02:00Z", by="person:ada"),
            id="acme-pilot", title="Pilot of ten units", counterparty="relationships/cards/acme.vcf", stage="proposal",
            value="120000", currency="USD", expected="2027-03-31", owner="ceo", since="2026-11-01",
            probability=0.3, probability_reason="their budget is not approved", source="the call of 2026-10-30",
        ),
        name="Northwind",
    )

``Pipeline`` lists the open stages in order, each with its default win probability (0 to 1); ``won`` (1) and ``lost``
(0) close every pipeline and are not listed. A company with no ``Pipeline`` has the stages ``lead``, ``qualified``,
``proposal`` and ``negotiation`` at 0.1, 0.25, 0.5 and 0.75 (the app's defaults). ``stale_days`` is how many days a
deal may go with no change before the app calls it stale.

``counterparty`` names who the deal is with: a ref to a card (a ``.vcf`` of the company's people or relationships
folder) or the id of a row of ``relationships/relationships.csv``. ``stage`` is one of the pipeline's stages, ``won``
or ``lost`` (the app refuses another word). ``value`` is the deal's worth as the file states it (text or a number) in
``currency``; a deal with no value is one whose worth is unknown, never one worth nothing. ``probability`` overrides
its stage's, and ``probability_reason`` says why (the app refuses one without the other). ``expected`` is the day it
is expected to close, ``closed`` the day it was won or lost, ``owner`` a role id of the team or a card ref, and
``source`` says where the facts came from. Each ``DealMove`` is one recorded stage change: from (``from_``, since
``from`` is a Python keyword), to, when (``at``, an ISO 8601 instant) and by whom (``by``, a principal). The company
document gains ``deals`` and ``pipeline`` only when the file writes them; every total, weight and rate is computed by
the app and never written.
"""
from __future__ import annotations

from typing import Any, Dict

_TEXT, _AMOUNT = "text", "amount"

#: The stages of a deal when the company declares no ``Pipeline``, in the order a pipeline shows them.
DEAL_STAGES = ("lead", "qualified", "proposal", "negotiation", "won", "lost")

DEALS_TAGS: Dict[str, Dict[str, Any]] = {
    "Deal": {"props": {"id": _TEXT, "title": _TEXT, "counterparty": _TEXT, "stage": _TEXT, "value": _AMOUNT, "currency": _TEXT, "expected": _TEXT,
                       "closed": _TEXT, "owner": _TEXT, "since": _TEXT, "probability": _AMOUNT, "probabilityReason": _TEXT, "source": _TEXT,
                       "note": _TEXT},
             "required": ["id", "title", "stage"], "many": {"moves": "DealMove"}},
    "DealMove": {"props": {"from": _TEXT, "to": _TEXT, "at": _TEXT, "by": _TEXT, "note": _TEXT}, "required": ["to", "at"]},
    "Pipeline": {"props": {"staleDays": _AMOUNT}, "many": {"stages": "DealStage"}},
    "DealStage": {"props": {"id": _TEXT, "label": _TEXT, "probability": _AMOUNT}, "required": ["id", "probability"]},
}

#: The children of a ``Company`` these add, by the field each fills.
COMPANY_DEALS_ONE = {"pipeline": "Pipeline"}
COMPANY_DEALS_MANY = {"deals": "Deal"}


def deals_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """What a Company's deals add to the company document: ``deals`` and ``pipeline``, only when the file writes them."""
    deals, pipe = node["many"].get("deals", []), node["one"].get("pipeline")

    def deal(n: Dict[str, Any]) -> Dict[str, Any]:
        moves = n["many"].get("moves", [])
        return {**n["props"], **({"moves": [dict(m["props"]) for m in moves]} if moves else {})}
    return {
        **({"pipeline": {**pipe["props"], "stages": [dict(s["props"]) for s in pipe["many"].get("stages", [])]}} if pipe else {}),
        **({"deals": [deal(d) for d in deals]} if deals else {}),
    }
