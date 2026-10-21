"""A process flow, declared in Python (``<name>.flow.py``): the ordered steps that make one thing, each with the tool it
visits, its recipe parameters with their units, its time and who does it, and the measurements taken in the process,
the same document and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``flows.ts``)::

    from commandagi.design.flows import flow, tool, step, param, measure

    result = flow(
        tool(id="coater", ref="stage1.bom.3d.py#coater", rate_per_hour=40, currency="USD"),
        step(id="why", kind="note", instruction="Marks first: every later layer aligns to them."),
        step(
            param(name="speed", value=3000, unit="rpm"),
            measure(id="resist", name="resist thickness", nominal=1.2, plus=0.1, minus=0.1, unit="um"),
            id="coat", order=1, tool="coater", by="in-house", minutes=6,
        ),
        name="Alignment marks", of="stage1.bom.3d.py#wafer",
    )

A record is an element and its fields are the element's attributes (snake_case keywords: ``rate_per_hour`` is
``ratePerHour``). Nothing adds a default. The check is the host's (``commandagi check <file>.flow.py``).
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

FLOW_STEP_KINDS = ["work", "note"]
FLOW_FIELDS = ["name", "description", "of"]
FLOW_TOOL_FIELDS = ["id", "ref", "name", "ratePerHour", "currency", "description"]
FLOW_STEP_FIELDS = ["id", "order", "kind", "tool", "fixture", "by", "minutes", "setupMinutes", "ratePerHour", "currency", "instruction",
                    "note"]
FLOW_PARAM_FIELDS = ["name", "value", "unit", "description"]
FLOW_MEASURE_FIELDS = ["id", "name", "nominal", "min", "max", "plus", "minus", "unit", "method", "sampling", "acceptance"]

_CHILDREN = {"holds": "children"}
#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"flow": _CHILDREN, "tool": {}, "step": _CHILDREN, "param": {}, "measure": {}}

__all__ = ["FLOW_STEP_KINDS", "SIGNATURES", "FLOW_VOCABULARY", *define(globals(), "flows", SIGNATURES)]

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _where(tag: str, key: str, a: Dict[str, Any]) -> str:
    return f"<{tag} {key}={json.dumps(a[key], ensure_ascii=False)}>" if key in a else f"<{tag}>"


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check(cond: Any, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _money(a: Dict[str, Any], at: str) -> None:
    _check("ratePerHour" not in a or (_num(a["ratePerHour"]) and a["ratePerHour"] >= 0), f"{at}: ratePerHour is a number of at least 0 (money an hour)")
    _check("currency" not in a or (isinstance(a["currency"], str) and re.fullmatch(r"[A-Z]{3}", a["currency"])),
           f"{at}: currency is an ISO 4217 code (USD)")


def _tool(a: Dict[str, Any]) -> None:
    at = _where("tool", "id", a)
    _check(isinstance(a.get("id"), str) and _ID.fullmatch(a["id"]), f'{at}: id is letters, digits, ".", "_" and "-"')
    _check("ref" not in a or (isinstance(a["ref"], str) and a["ref"].strip()),
           f"{at}: ref is a device definition, or an item or body of a 3D document (<file>#<id>)")
    _money(a, at)


def _step(t: DocTree) -> None:
    a = t["attrs"]
    at = _where("step", "id", a)
    _check(isinstance(a.get("id"), str) and _ID.fullmatch(a["id"]), f'{at}: id is letters, digits, ".", "_" and "-"')
    o = a.get("order")
    _check("order" not in a or (isinstance(o, int) and not isinstance(o, bool) and o >= 1) or (isinstance(o, float) and o.is_integer() and o >= 1),
           f"{at}: order is a whole number from 1")
    _check("kind" not in a or a["kind"] in FLOW_STEP_KINDS, f"{at}: kind must be one of {', '.join(FLOW_STEP_KINDS)} (got {json.dumps(a.get('kind'))})")
    for k in ("minutes", "setupMinutes"):
        _check(k not in a or (_num(a[k]) and a[k] >= 0), f"{at}: {k} is a number of at least 0")
    _money(a, at)
    if a.get("kind") == "note":
        _check("tool" not in a and a.get("minutes", 0) == 0 and not t["children"],
               f"{at}: a note step names no tool, takes no time (minutes 0 or absent) and holds no param or measure")
    names = [c["attrs"].get("name") for c in t["children"] if c["tag"] == "param"]
    twice = next((n for i, n in enumerate(names) if n in names[:i]), None)
    _check(twice is None, f"{at}: two params are named {json.dumps(twice, ensure_ascii=False)}")
    for c in t["children"]:
        b = c["attrs"]
        if c["tag"] == "param":
            pat = _where("param", "name", b)
            _check(isinstance(b.get("name"), str) and b["name"].strip(), f"{pat}: name says what the parameter is")
            v = b.get("value")
            _check(_num(v) or isinstance(v, (str, bool)), f"{pat}: value is a number, a text or true/false")
            _check("unit" not in b or (isinstance(b["unit"], str) and b["unit"].strip()), f"{pat}: unit is a unit's symbol (rpm, sccm, mTorr, °C, s)")
        else:
            mat = _where("measure", "id", b)
            _check(isinstance(b.get("id"), str) and _ID.fullmatch(b["id"]), f'{mat}: id is letters, digits, ".", "_" and "-"')
            for k in ("nominal", "min", "max", "plus", "minus"):
                _check(k not in b or _num(b[k]), f"{mat}: {k} is a number")
            for k in ("plus", "minus"):
                _check(k not in b or b[k] >= 0, f"{mat}: {k} is a number of at least 0")
            _check(("plus" not in b and "minus" not in b) or "nominal" in b, f"{mat}: plus and minus are tolerances of the nominal: give nominal")
            _check("min" not in b or "max" not in b or b["min"] <= b["max"], f"{mat}: min is at most max")


def _step_record(t: DocTree) -> Dict[str, Any]:
    params = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "param"]
    measures = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "measure"]
    return {**t["attrs"], **({"params": params} if params else {}), **({"measures": measures} if measures else {})}


def _flow(t: DocTree) -> Dict[str, Any]:
    _check("of" not in t["attrs"] or isinstance(t["attrs"]["of"], str),
           "<flow>: of is a ref to what the flow makes (a 3D document, or <file>#<item or body>)")
    for c in t["children"]:
        _tool(c["attrs"]) if c["tag"] == "tool" else _step(c)
    measures = [m["attrs"].get("id") for c in t["children"] for m in c["children"] if m["tag"] == "measure"]
    again = next((m for i, m in enumerate(measures) if m in measures[:i]), None)
    _check(again is None, f"<measure id={json.dumps(again, ensure_ascii=False)}>: two measures have this id (a ref names it as <file>#<id>)")
    tools = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "tool"]
    steps = [_step_record(c) for c in t["children"] if c["tag"] == "step"]
    own = {k: t["attrs"][k] for k in FLOW_FIELDS if k in t["attrs"]}
    return {**own, **({"tools": tools} if tools else {}), **({"steps": steps} if steps else {})}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


FLOW_VOCABULARY = Vocabulary("flow", "a process flow", "flow", {
    "flow": {"parents": [], "attrs": FLOW_FIELDS},
    "tool": {"parents": ["flow"], "key": "id", "required": ["id"], "attrs": FLOW_TOOL_FIELDS},
    "step": {"parents": ["flow"], "key": "id", "required": ["id"], "attrs": FLOW_STEP_FIELDS},
    "param": {"parents": ["step"], "required": ["name", "value"], "attrs": FLOW_PARAM_FIELDS},
    "measure": {"parents": ["step"], "key": "id", "required": ["id"], "attrs": FLOW_MEASURE_FIELDS},
}, _flow, _never, lambda name: {"name": name})

register_vocabulary(FLOW_VOCABULARY, "flows")

