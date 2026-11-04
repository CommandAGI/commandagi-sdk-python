"""A company's governance, compliance, IP and insurance declared in Python: the children of a ``Company`` that hold
them, and the ``Vote`` children of a ``Paper`` (CommandAGI's docs/company-substrate.md § governance, compliance, IP and
insurance). The same elements as the TypeScript SDK's ``company-governance.ts``; ``business.py`` defines their calls
(``Seat``, ``Policy`` …), so they are imported from ``commandagi.design.business``::

    Company(
        Seat(body="board", title="director", holder="Northwind/people/Lin Chen.vcf", start="2024-01-31"),
        Compliance(industries=["naics:541370"]),
        Evidence(obligation="US-DE:de-llc-lp-annual-tax", due="2026-06-01", done="2026-05-20", file="Northwind/filings/2026.pdf"),
        IpAsset(kind="trademark", stage="registered", title="NORTHWIND", jurisdiction="US", registered="2025-02-11"),
        Policy(kind="aviation", carrier="Skyward Mutual", start="2025-07-01", end="2026-07-01"),
        Paper(Vote(holder="Northwind/people/Lin Chen.vcf", choice="for"), kind="board-consent", file="…pdf", body="board"),
        name="Northwind",
    )

The company document gains ``governance``, ``compliance``, ``ip`` and ``insurance`` only when the file writes one of
their elements. Every document stays its own file, named by a ref; tallies and statuses are computed by the app.
"""
from __future__ import annotations

from typing import Any, Dict

_TEXT, _TEXTS, _AMOUNT = "text", "texts", "amount"

GOVERNANCE_TAGS: Dict[str, Dict[str, Any]] = {
    "Seat": {"props": {"body": _TEXT, "title": _TEXT, "holder": _TEXT, "start": _TEXT, "end": _TEXT, "appointedBy": _TEXT}, "required": ["body", "title", "holder"]},
    "Compliance": {"props": {"industries": _TEXTS}},
    "Obligation": {"props": {"id": _TEXT, "name": _TEXT, "authority": _TEXT, "url": _TEXT, "due": _TEXT, "every": _TEXT, "note": _TEXT}, "required": ["id", "name", "due"]},
    "Evidence": {"props": {"obligation": _TEXT, "due": _TEXT, "done": _TEXT, "file": _TEXT, "note": _TEXT}, "required": ["obligation", "due"]},
    "IpAsset": {"props": {"kind": _TEXT, "stage": _TEXT, "title": _TEXT, "jurisdiction": _TEXT, "number": _TEXT, "filed": _TEXT, "registered": _TEXT,
                          "expires": _TEXT, "owner": _TEXT, "classes": _TEXTS, "file": _TEXT}, "required": ["kind", "title"]},
    "Assignment": {"props": {"person": _TEXT, "signed": _TEXT, "file": _TEXT}, "required": ["person"]},
    "Policy": {"props": {"kind": _TEXT, "carrier": _TEXT, "number": _TEXT, "start": _TEXT, "end": _TEXT, "limit": _AMOUNT, "currency": _TEXT, "broker": _TEXT,
                         "file": _TEXT}, "required": ["kind", "carrier", "start", "end"]},
    "Vote": {"props": {"holder": _TEXT, "choice": _TEXT, "signed": _TEXT, "evidence": _TEXT}, "required": ["holder", "choice"]},
}

#: The children of a ``Company`` these add, by the field each fills.
COMPANY_GOVERNANCE_ONE = {"compliance": "Compliance"}
COMPANY_GOVERNANCE_MANY = {"seats": "Seat", "obligations": "Obligation", "evidence": "Evidence", "ipAssets": "IpAsset", "assignments": "Assignment", "policies": "Policy"}
#: What a ``Paper`` takes for a vote on it: its body and its rule.
PAPER_VOTE_PROPS = {"body": _TEXT, "threshold": _TEXT, "quorum": _TEXT}


def governance_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """What a Company's governance children add to the company document: only the parts the file writes."""
    one, many = node["one"], node["many"]
    props = lambda f: [dict(n["props"]) for n in many.get(f, [])]  # noqa: E731
    out: Dict[str, Any] = {}
    if many.get("seats"):
        out["governance"] = {"seats": props("seats")}
    if one.get("compliance") or many.get("obligations") or many.get("evidence"):
        c = one["compliance"]["props"] if one.get("compliance") else {}
        out["compliance"] = {"industries": c.get("industries", []), "obligations": props("obligations"), "evidence": props("evidence")}
    if many.get("ipAssets") or many.get("assignments"):
        out["ip"] = {"assets": props("ipAssets"), "assignments": props("assignments")}
    if many.get("policies"):
        out["insurance"] = {"policies": props("policies")}
    return out


def votes_of(paper: Dict[str, Any]) -> Dict[str, Any]:
    """A paper's votes, when it records any."""
    votes = paper["many"].get("votes", [])
    return {"votes": [dict(v["props"]) for v in votes]} if votes else {}
