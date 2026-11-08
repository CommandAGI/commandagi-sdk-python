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

An option contract is one ``sym`` in one spelling, ``<underlying> <expiry> <C|P> <strike>[ x<multiplier>]``
(``"AAPL 2026-12-18 C 200"``): an ISO date, C or P, the strike as decimal text with no trailing zeros, and the multiplier
only when it is not 100. ``option_symbol`` writes it and ``parse_option`` reads it, as the TypeScript SDK's
``optionSymbol`` and ``parseOption`` do; a ``sym`` with a space in any record must be a contract in that spelling. An
option ``order`` may say ``effect`` (``"open"`` or ``"close"``).
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List, Optional

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
              ["limit", "stop", "takeProfit", "stopLoss", "effect", "instrument", "account", "connection"],
              ["qty", "limit", "stop", "takeProfit", "stopLoss"]),
    "order-update": ("market", ["t", "order", "state", "mode"], ["leg", "ref", "filled", "avg", "error", "src"], ["filled", "avg"]),
    "cancel": ("market", ["t", "id", "venue", "mode", "ref", "by", "grant"], ["order", "leg", "connection", "account"], []),
    "cancel-update": ("market", ["t", "cancel", "state", "mode"], ["error"], []),
    "amend": ("market", ["t", "id", "order", "sym", "side", "qty", "type", "tif", "venue", "mode", "ref", "by", "grant"],
              ["limit", "stop", "effect", "connection", "account"], ["qty", "limit", "stop"]),
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

__all__ = ["SIGNATURES", "MARKET_VOCABULARY", "STANDARD_MULTIPLIER", "option_symbol", "parse_option", *define(globals(), "market", SIGNATURES)]

#: The multiplier a contract has when its symbol writes none: the standard US equity option.
STANDARD_MULTIPLIER = "100"
_UNDERLYING = re.compile(r"^[A-Za-z0-9._/-]{1,24}$")
_OPTION_FORM = '<underlying> <expiry YYYY-MM-DD> <C|P> <strike>[ x<multiplier>], for example "AAPL 2026-12-18 C 200"'


def _canonical(v: Any) -> Optional[str]:
    """Decimal text without leading or trailing zeros (``"0200.50"`` is ``"200.5"``), or None."""
    s = v.strip() if isinstance(v, str) else repr(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
    m = re.match(r"^(\d+)(?:\.(\d+))?$", s)
    if not m:
        return None
    whole = m.group(1).lstrip("0") or "0"
    frac = (m.group(2) or "").rstrip("0")
    return f"{whole}.{frac}" if frac else whole


def _is_date(s: str) -> bool:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _quote(s: str) -> str:
    """A text as JSON quotes it, so a message reads the same in all three SDKs."""
    return json.dumps(s)


def parse_option(sym: str) -> Optional[Dict[str, str]]:
    """The contract a symbol names (``underlying``, ``expiry``, ``right``, ``strike``, ``multiplier``, all text), or None
    for a plain symbol (one with no space). A symbol with a space must be a contract in its one spelling: anything else
    raises ValueError naming the part and the spelling to write."""
    if " " not in sym:
        return None
    parts = sym.split(" ")
    if not 4 <= len(parts) <= 5 or not all(parts):
        raise ValueError(f"an option contract is {_OPTION_FORM}, not {_quote(sym)}")
    underlying, expiry, right, strike = parts[:4]
    if not _UNDERLYING.match(underlying):
        raise ValueError(f"an option's underlying is letters, digits and . _ / - (at most 24), not {_quote(underlying)}")
    if not _is_date(expiry):
        raise ValueError(f"an option's expiry is a date, YYYY-MM-DD, not {_quote(expiry)}")
    if right not in ("C", "P"):
        raise ValueError(f"an option's right is C (a call) or P (a put), not {_quote(right)}")
    k = _canonical(strike)
    if k is None or re.match(r"^0(\.0*)?$", k):
        raise ValueError(f"an option's strike is decimal text above 0, not {_quote(strike)}")
    if k != strike:
        raise ValueError(f"an option's strike is written {k}, not {strike} (one spelling for each contract)")
    multiplier = STANDARD_MULTIPLIER
    if len(parts) == 5:
        mult = parts[4]
        if not re.match(r"^x[1-9]\d*$", mult):
            raise ValueError(f'an option\'s multiplier is x and a whole number above 0 ("x10"), not {_quote(mult)}')
        if mult[1:] == STANDARD_MULTIPLIER:
            raise ValueError(f"a multiplier of {STANDARD_MULTIPLIER} is not written: {' '.join(parts[:4])} is that contract")
        multiplier = mult[1:]
    return {"underlying": underlying, "expiry": expiry, "right": right, "strike": strike, "multiplier": multiplier}


def option_symbol(underlying: str, expiry: str, right: str, strike: Any, multiplier: Any = STANDARD_MULTIPLIER) -> str:
    """A contract's one spelling, from its parts: ``right`` is C, P, call or put; ``strike`` and ``multiplier`` are
    decimal text or numbers. Raises ValueError as ``parse_option`` does."""
    r = {"c": "C", "call": "C", "p": "P", "put": "P"}.get(str(right).lower(), str(right))
    k = _canonical(strike) or str(strike)
    m = _canonical(multiplier) or str(multiplier)
    sym = f"{underlying} {expiry} {r} {k}" + ("" if m == STANDARD_MULTIPLIER else f" x{m}")
    parse_option(sym)
    return sym


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
        elif k == "sym":
            try:
                parse_option(v)
            except ValueError as e:
                raise ValueError(f"<{tag}> sym: {e}") from None


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
