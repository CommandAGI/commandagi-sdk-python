"""Signed records, declared in Python: a market contract (``.contract.py``) and a product instance (``.instance.py``), the
same documents and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``records.ts``)::

    from commandagi.design.records import contract, event, instance, party

    result = contract(
        party(principal="u-1", role="offeror", sig="ed25519:…", signed_at=1780765664000),
        id="c-1",
        terms={"subject": {...}, "title": "Bench time", "schedule": None, ...},
        created_at=1780765664000,
    )
    result = instance(
        event(seq=0, kind="manufacture", at=1772409600000, prev=None, by="org-acme", sig="ed25519:…"),
        serial="ACME-FU-0031",
        product_id="fleet-unit",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``created_at`` is ``createdAt``). These records are SIGNED, so nothing is rewritten: a contract's ``terms`` is
one value (the object the parties sign; a ``None`` inside it is JSON's null and is kept), times are epoch
milliseconds, signatures as they are. A contract's parties are ``party`` children in order; an instance's chain is
``event`` children, oldest first (``seq`` 0, 1, 2 …). A run gives back ``{"format", "document", "sources"}`` beside an
empty graph; ``sources`` names each element's call by its path (``""``, ``party@0``, ``event#0``).
"""
from __future__ import annotations

from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

CONTRACT_FIELDS = ["id", "terms", "createdAt"]
INSTANCE_FIELDS = ["serial", "productId", "model"]
INSTANCE_EVENT_FIELDS = ["seq", "kind", "at", "prev", "by", "to", "contractRef", "attestationRef", "data", "sig"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "contract": {"holds": "children"},
    "party": {},
    "instance": {"holds": "children"},
    "event": {},
}

__all__ = ["CONTRACT_FIELDS", "INSTANCE_FIELDS", "INSTANCE_EVENT_FIELDS", "SIGNATURES", "CONTRACT_VOCABULARY",
           "INSTANCE_VOCABULARY", *define(globals(), "records", SIGNATURES)]


def _own(o: Dict[str, Any], keys: Any = None) -> Dict[str, Any]:
    """The fields of a record that it has (None, "" and [] are fields, and are kept)."""
    return {k: o[k] for k in (keys if keys is not None else o) if k in o}


def _contract(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    terms, created = a.get("terms"), a.get("createdAt")
    if not isinstance(terms, dict):
        raise ValueError(f'<contract id="{a.get("id")}">: terms is the object the parties sign')
    if isinstance(created, bool) or not isinstance(created, int):
        raise ValueError(f'<contract id="{a.get("id")}">: createdAt is epoch milliseconds, not {created!r}')
    return {"id": a["id"], "terms": terms, "parties": [dict(c["attrs"]) for c in t["children"]], "createdAt": created}


def _instance(t: DocTree) -> Dict[str, Any]:
    events = [dict(c["attrs"]) for c in t["children"]]
    for i, e in enumerate(events):
        if e.get("seq") != i or isinstance(e.get("seq"), bool):
            raise ValueError(f"<event seq={{{e.get('seq')!r}}}> is event {i} of the chain: events are written oldest first, seq 0, 1, 2 …")
    return {**_own(t["attrs"], INSTANCE_FIELDS), "events": events}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


CONTRACT_VOCABULARY = Vocabulary("contract", "a contract record", "contract", {
    "contract": {"parents": [], "required": ["id", "terms", "createdAt"], "attrs": CONTRACT_FIELDS},
    # A party's fields are the record's as stored (principal, role, actedBy, agent, sig, signedAt, …): any.
    "party": {"parents": ["contract"], "required": ["principal", "role"]},
}, _contract, _never)

INSTANCE_VOCABULARY = Vocabulary("instance", "a product instance", "instance", {
    "instance": {"parents": [], "required": ["serial", "productId"], "attrs": INSTANCE_FIELDS},
    "event": {"parents": ["instance"], "key": "seq", "required": ["seq", "kind", "at", "by"], "attrs": INSTANCE_EVENT_FIELDS},
}, _instance, _never)

for _v in (CONTRACT_VOCABULARY, INSTANCE_VOCABULARY):
    register_vocabulary(_v, "records")
