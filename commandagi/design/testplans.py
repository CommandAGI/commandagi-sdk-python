"""TEST PLANS IN PYTHON — a test plan (``<name>.testplan.py``) holds the steps that test one serial-numbered unit, never
the results: the same elements, and the same document, as the TypeScript SDK's JSX (``commandagi/design``
``testplans.ts``), one call each::

    from commandagi.design.testplans import condition, fixture, step, testplan

    result = testplan(
        condition(id="ambient", quantity="temperature", min=15, max=35, unit="C"),
        fixture(id="supply", kind="instrument", unit="psu-1", channel="output", note="5 V, current limit 1 A"),
        step(id="rail-3v3", channel="power", command={"verb": "read"}, read="v3v3", min=3.2, max=3.4, unit="V",
             verifies=["requirements/power.req.tsx#rail-3v3"]),
        step(id="supply-current", fixture="supply", command={"verb": "read"}, read="current", max=0.4, unit="A"),
        title="Cam-001 power rail", device="../devices/commandagi-cam-001/definition.tsx",
    )

A record is an element and its fields are its attributes (snake_case keywords of the native names: ``settle_ms`` is
``settleMs``). A step reads the unit's channel (``channel``) or an instrument's (``fixture``). ``command`` is one
record in the channel format's shape, sent first; ``read`` is a value of the state the channel reports after it.
Steps keep their order. Nothing adds a default: the runner says what it assumes.

The document a test plan declares: ``{title?, device?, note?, conditions?, fixtures?, steps?}``, each list in the
order its elements are written.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

TESTPLAN_FIELDS = ["title", "device", "note"]
CONDITION_FIELDS = ["id", "quantity", "value", "min", "max", "unit", "note"]
FIXTURE_FIELDS = ["id", "kind", "unit", "channel", "note"]
STEP_FIELDS = ["id", "channel", "fixture", "command", "read", "min", "max", "equals", "unit", "settleMs", "timeoutMs", "condition",
               "verifies", "note"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"testplan": {"holds": "children"}, "condition": {}, "fixture": {}, "step": {}}

_LISTS = [("condition", "conditions", CONDITION_FIELDS), ("fixture", "fixtures", FIXTURE_FIELDS), ("step", "steps", STEP_FIELDS)]

__all__ = ["TESTPLAN_FIELDS", "CONDITION_FIELDS", "FIXTURE_FIELDS", "STEP_FIELDS", "SIGNATURES", "TESTPLAN_VOCABULARY", "TESTPLANS",
           *define(globals(), "testplans", SIGNATURES)]


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent, None, "" or []): code does not write it."""
    return v is None or v == "" or (isinstance(v, list) and not v)


def _attrs_of(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: o[k] for k in keys if not _nothing(o.get(k))}


def _json(v: Any) -> str:
    """JavaScript's ``JSON.stringify(v)`` (no spaces)."""
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def _from_tree(t: DocTree) -> Dict[str, Any]:
    doc: Dict[str, Any] = dict(t["attrs"])
    for tag, field, _ in _LISTS:
        items = [dict(c["attrs"]) for c in t["children"] if c["tag"] == tag]
        if items:
            doc[field] = items
    for s in doc.get("steps", []):
        verifies = s.get("verifies")
        if "verifies" in s and not (isinstance(verifies, list) and all(isinstance(r, str) and r for r in verifies)):
            raise ValueError(f'<step id="{s.get("id")}"> verifies is a list of refs to requirements, not {_json(verifies)}')
        command = s.get("command")
        if "command" in s and not isinstance(command, dict):
            raise ValueError(f'<step id="{s.get("id")}"> command is one record in the channel format\'s shape ({{ verb: … }}), not {_json(command)}')
    return doc


def _to_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "testplan", "attrs": _attrs_of(d, TESTPLAN_FIELDS),
            "children": [{"tag": tag, "attrs": _attrs_of(x, keys), "children": []} for tag, field, keys in _LISTS for x in d.get(field) or []]}


TESTPLAN_VOCABULARY = Vocabulary("testplan", "a test plan", "testplan", {
    "testplan": {"parents": [], "attrs": TESTPLAN_FIELDS},
    "condition": {"parents": ["testplan"], "key": "id", "required": ["id", "quantity"], "attrs": CONDITION_FIELDS},
    "fixture": {"parents": ["testplan"], "key": "id", "required": ["id", "kind"], "attrs": FIXTURE_FIELDS},
    "step": {"parents": ["testplan"], "key": "id", "required": ["id"], "attrs": STEP_FIELDS},
}, _from_tree, _to_tree, empty=lambda name: {})

register_vocabulary(TESTPLAN_VOCABULARY, "testplans")

#: The vocabulary of test plans, by format.
TESTPLANS = {"testplan": TESTPLAN_VOCABULARY}
