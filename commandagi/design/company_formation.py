"""A company's formation parts, declared in Python (docs/company-substrate.md § formation and filings): its registered
agent in each place (``RegisteredAgent``, a child of ``Company``), what a ``Paper(kind="filing")`` says about the
filing it is, and the day its dissolution was authorized (``Entity(dissolved=…)``); the same elements as the TypeScript
SDK's ``company-formation.ts``::

    from commandagi.design.business import Company, Entity, Paper, RegisteredAgent

    result = Company(
        Entity(jurisdiction="US-DE", form="corporation", formed="2026-01-05", operates_in=["US-CA"]),
        RegisteredAgent(jurisdiction="US-DE", name="Agent Co.", address="1 Main St, Dover, DE 19901"),
        Paper(kind="filing", title="Certificate of Incorporation", file="Acme/legal/filings/incorporation.md",
              jurisdiction="US-DE", rule="de-certificate-of-incorporation", status="accepted",
              submitted="2026-01-04", accepted="2026-01-05"),
        name="Acme",
    )

A filing's ``rule`` names the jurisdiction catalog's filing it follows, ``period`` the year an annual filing reports,
``due`` its day. Its status goes ``draft``, then ``submitted`` (a person submitted it), then ``accepted`` or
``rejected``. An agent drafts and never submits. The company document holds the agents as ``registeredAgents``,
absent when the file writes none.
"""
from __future__ import annotations

from typing import Any, Dict

_TEXT = "text"

FORMATION_TAGS: Dict[str, Dict[str, Any]] = {
    "RegisteredAgent": {"props": {"jurisdiction": _TEXT, "name": _TEXT, "address": _TEXT, "since": _TEXT}, "required": ["jurisdiction", "name"]},
}
FORMATION_LISTS: Dict[str, str] = {"registeredAgents": "RegisteredAgent"}
#: What a ``Paper(kind="filing")`` says beside every paper's attributes.
FILING_PAPER_PROPS: Dict[str, str] = {k: _TEXT for k in ("rule", "period", "due", "submitted", "accepted", "confirmation")}


def formation_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """The company document's ``registeredAgents``, only when the file writes one."""
    items = node["many"].get("registeredAgents", [])
    return {"registeredAgents": [dict(n["props"]) for n in items]} if items else {}
