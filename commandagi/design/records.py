"""Signed records, declared in Python: a market contract (``.contract``) and a product instance (``.instance``), the same
documents as the TypeScript SDK's JSX (``commandagi/design`` ``records.ts``), with calls in place of tags::

    result = contract("c-1", contract_party(principal="u-1", role="offeror", sig="ed25519:…", signedAt=1780765664000),
                      terms={"subject": {...}, "title": "Bench time", "schedule": None, ...}, createdAt=1780765664000)
    result = product_instance("ACME-FU-0031", instance_event(seq=0, kind="manufacture", at=1772409600000, prev=None,
                              by="org-acme", sig="ed25519:…"), productId="fleet-unit")

These records are signed, so nothing is rewritten: a contract's ``terms`` is one value (the object the parties sign;
a ``None`` inside it is JSON's null and is kept), times are epoch milliseconds, signatures as they are. A contract's
parties are ``contract_party`` records in order; an instance's chain is ``instance_event`` records, oldest first
(``seq`` 0, 1, 2 …). A genesis event's ``prev=None`` is kept: it is the chain's null, not a field left out. A run gives
back the run's one shape (``{"format", "document", "sources"}`` beside an empty graph).
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from .ontology import Element, _fields

CONTRACT_FIELDS = ["id", "terms", "createdAt"]
INSTANCE_FIELDS = ["serial", "productId", "model"]
INSTANCE_EVENT_FIELDS = ["seq", "kind", "at", "prev", "by", "to", "contractRef", "attestationRef", "data", "sig"]


def _check(el: Element, keys: list, required: list) -> None:
    for k in el.attrs:
        if k not in keys:
            raise ValueError(f"<{el.tag}>: {k} is not read ({', '.join(keys)})")
    for k in required:
        if k not in el.attrs:
            raise ValueError(f"<{el.tag}> needs {k}")


def _contract(root: Element) -> Dict[str, Any]:
    _check(root, CONTRACT_FIELDS, CONTRACT_FIELDS)
    terms, created = root.attrs["terms"], root.attrs["createdAt"]
    if not isinstance(terms, dict):
        raise ValueError(f'<contract id="{root.attrs["id"]}">: terms is the object the parties sign')
    if not isinstance(created, int) or isinstance(created, bool):
        raise ValueError(f'<contract id="{root.attrs["id"]}">: createdAt is epoch milliseconds, not {created!r}')
    parties = []
    for c in root.children:
        if c.tag != "party":
            raise ValueError(f"<{c.tag}> is not a tag of a contract record (<party>)")
        for k in ("principal", "role"):
            if k not in c.attrs:
                raise ValueError(f"<party> needs {k}")
        parties.append(copy.deepcopy(c.attrs))
    return {"id": root.attrs["id"], "terms": copy.deepcopy(terms), "parties": parties, "createdAt": created}


def _instance(root: Element) -> Dict[str, Any]:
    _check(root, INSTANCE_FIELDS, ["serial", "productId"])
    doc = {k: root.attrs[k] for k in INSTANCE_FIELDS if k in root.attrs}
    events = []
    for i, c in enumerate(root.children):
        if c.tag != "event":
            raise ValueError(f"<{c.tag}> is not a tag of a product instance (<event>)")
        _check(c, INSTANCE_EVENT_FIELDS, ["seq", "kind", "at", "by"])
        if c.attrs["seq"] != i:
            raise ValueError(f"<event seq={{{c.attrs['seq']!r}}}> is event {i} of the chain: events are written oldest first, seq 0, 1, 2 …")
        events.append(copy.deepcopy(c.attrs))
    doc["events"] = events
    return doc


def is_record_document(value: Any) -> bool:
    """Whether a value is the root record of a contract or a product instance."""
    return isinstance(value, Element) and value.tag in ("contract", "instance")


def declare_record_document(root: Element) -> Dict[str, Any]:
    """The record a root declares, in the run's one shape: ``{"format", "document", "sources"}``."""
    if root.tag == "contract":
        return {"format": "contract", "document": _contract(root), "sources": {}}
    if root.tag == "instance":
        return {"format": "instance", "document": _instance(root), "sources": {}}
    raise ValueError(f"<{root.tag}> is not a contract record or a product instance")


def contract(id: str, *parties: Element, **fields: Any) -> Element:
    """A contract record (``<name>.contract``): its id, terms and createdAt, and its parties in order."""
    return Element("contract", {"id": id, **_fields(fields)}, parties)


def contract_party(**fields: Any) -> Element:
    """A party of a contract (``<party>`` in JSX): principal, role, and its signature fields as stored."""
    return Element("party", _fields(fields))


def product_instance(serial: str, *events: Element, **fields: Any) -> Element:
    """A product instance (``<name>.instance``): its serial, productId and model, and its chain oldest first."""
    return Element("instance", {"serial": serial, **_fields(fields)}, events)


def instance_event(**fields: Any) -> Element:
    """One event of an instance's chain (``<event>`` in JSX). ``prev=None`` (genesis) is kept as null."""
    el = Element("event", _fields(fields))
    if "prev" in fields and fields["prev"] is None:
        el.attrs["prev"] = None
    return el
