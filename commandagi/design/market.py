"""A market recording, declared in Python: a ``.market.py``. The same document and the same elements as the TypeScript
SDK's JSX (``commandagi/design`` ``market.ts``)::

    from commandagi.design.market import *

    result = market(
        quote(t="2026-10-01T13:30:00.000Z", sym="NRTH", last="185.09", bid="185.05", ask="185.13"),
        book(bid(price="185.05", qty="300"), ask(price="185.13", qty="200"), t="2026-10-01T13:30:01.000Z", sym="NRTH"),
        trade(t="2026-10-01T13:30:02.000Z", sym="NRTH", price="185.10", qty="25", side="buy"),
    )

A market file is a recording: one element per record, in time order, under one ``market()``. The host appends each
new record as an element just before the closing parenthesis. Records repeat, so no tag is keyed or single.

Every attribute is text. Prices and quantities are decimal text (``"185.09"``), never numbers: a float loses cents,
so a number is refused by name. A ``t`` is an ISO time text. What a record means (a venue's modes, the shape of an id,
time order) is the workbench's to check, not the SDK's.

The declared document is ``{"records": [...]}``, each record ``{"kind": <tag>, ...its attributes}``. A ``book`` adds
``bids`` and ``asks`` (``[price, qty]`` pairs, in order). An ``account`` adds ``positions`` (its ``holding``
children), ``open`` (its ``open_order`` children) and ``problems`` (its ``problem`` texts), each only when it has some.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "market": {"holds": "children"},
    "note": {},
    "quote": {},
    "trade": {},
    "book": {"holds": "children"},
    "bid": {},
    "ask": {},
    "news": {},
    "position": {},
    "fill": {},
    "order": {},
    "order-update": {},
    "cancel": {},
    "cancel-update": {},
    "amend": {},
    "amend-update": {},
    "account": {"holds": "children"},
    "holding": {},
    "open-order": {},
    "problem": {},
}

#: Each tag's parent, its required attributes, its other attributes and which of them are decimal text.
_RECORDS: Dict[str, Any] = {
    "note": ("market", ["t", "text"], [], []),
    "quote": ("market", ["t", "sym"], ["last", "bid", "ask", "vol"], ["last", "bid", "ask", "vol"]),
    "trade": ("market", ["t", "sym", "price", "qty"], ["side"], ["price", "qty"]),
    "book": ("market", ["t", "sym"], [], []),
    "bid": ("book", ["price", "qty"], [], ["price", "qty"]),
    "ask": ("book", ["price", "qty"], [], ["price", "qty"]),
    "news": ("market", ["t", "headline"], ["sym", "source", "tone"], []),
    "position": ("market", ["t", "sym", "qty", "avg"], [], ["qty", "avg"]),
    "fill": ("market", ["t", "sym", "side", "price", "qty"], ["by", "order", "leg", "mode", "ref", "at"], ["price", "qty"]),
    "order": ("market", ["t", "id", "sym", "side", "qty", "type", "tif", "venue", "mode", "by", "grant"],
              ["limit", "stop", "takeProfit", "stopLoss", "instrument", "account", "connection"],
              ["qty", "limit", "stop", "takeProfit", "stopLoss"]),
    "order-update": ("market", ["t", "order", "state", "mode"], ["leg", "ref", "filled", "avg", "error", "src"], ["filled", "avg"]),
    "cancel": ("market", ["t", "id", "venue", "mode", "ref", "by", "grant"], ["order", "leg", "connection", "account"], []),
    "cancel-update": ("market", ["t", "cancel", "state", "mode"], ["error"], []),
    "amend": ("market", ["t", "id", "order", "sym", "side", "qty", "type", "tif", "venue", "mode", "ref", "by", "grant"],
              ["limit", "stop", "connection", "account"], ["qty", "limit", "stop"]),
    "amend-update": ("market", ["t", "amend", "state", "mode"], ["ref", "error"], []),
    "account": ("market", ["t", "venue", "mode"],
                ["connection", "currency", "status", "value", "buyingPower", "cash", "equity", "dayChange", "dayChangePct"],
                ["value", "buyingPower", "cash", "equity", "dayChange", "dayChangePct"]),
    "holding": ("account", ["sym", "qty"], ["side", "avg", "price", "value", "pl", "plPct"], ["qty", "avg", "price", "value", "pl", "plPct"]),
    "open-order": ("account", ["sym", "status"],
                   ["ref", "client", "order", "side", "type", "tif", "state", "submitted", "qty", "filled", "avgPrice", "limit"],
                   ["qty", "filled", "avgPrice", "limit"]),
    "problem": ("account", ["text"], [], []),
}

_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")
# One shape check in all three SDKs, so a time one SDK takes is never refused by another.
_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d(\.\d+)?)?(Z|[+-]\d\d:\d\d)$")

__all__ = ["SIGNATURES", "MARKET_VOCABULARY", *define(globals(), "market", SIGNATURES)]


def _check(t: DocTree) -> None:
    """Every attribute is text; a decimal field is plain decimal text; a ``t`` is an ISO time."""
    tag = t["tag"]
    decimals = _RECORDS[tag][3] if tag in _RECORDS else []
    for k, v in t["attrs"].items():
        if k in decimals:
            if not isinstance(v, str):
                raise ValueError(f'<{tag}> {k} is decimal text ("185.09"), not {_what(v)}')
            if not _DECIMAL.match(v):
                raise ValueError(f'<{tag}> {k} is decimal text ("185.09"), not "{v}"')
        elif not isinstance(v, str):
            raise ValueError(f"<{tag}> {k} is text, not {_what(v)}")
        elif k == "t" and not _TIME.match(v):
            raise ValueError(f'<{tag}> t is an ISO time ("2026-10-01T13:30:00.000Z"), not "{v}"')


def _what(v: Any) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return "a number"
    return "None" if v is None else type(v).__name__


def _record(t: DocTree) -> Dict[str, Any]:
    _check(t)
    record: Dict[str, Any] = {"kind": t["tag"], **t["attrs"]}
    kids = t["children"]
    for c in kids:
        _check(c)
    if t["tag"] == "book":
        record["bids"] = [[c["attrs"]["price"], c["attrs"]["qty"]] for c in kids if c["tag"] == "bid"]
        record["asks"] = [[c["attrs"]["price"], c["attrs"]["qty"]] for c in kids if c["tag"] == "ask"]
    if t["tag"] == "account":
        for key, tag, read in (("positions", "holding", dict), ("open", "open-order", dict),
                               ("problems", "problem", lambda a: a["text"])):
            found = [read(c["attrs"]) for c in kids if c["tag"] == tag]
            if found:
                record[key] = found
    return record


def _market(t: DocTree) -> Dict[str, Any]:
    return {"records": [_record(c) for c in t["children"]]}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


def _tags() -> Dict[str, Dict[str, Any]]:
    tags: Dict[str, Dict[str, Any]] = {"market": {"parents": [], "attrs": []}}
    for tag, (parent, required, other, _) in _RECORDS.items():
        tags[tag] = {"parents": [parent], "required": required, "attrs": [*required, *other]}
    return tags


def _empty(_: str) -> Dict[str, List[Any]]:
    return {"records": []}


MARKET_VOCABULARY = Vocabulary("market", "a market recording", "market", _tags(), _market, _never, _empty)

register_vocabulary(MARKET_VOCABULARY, "market")
