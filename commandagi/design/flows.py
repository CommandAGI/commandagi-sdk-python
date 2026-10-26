"""A process flow, declared in Python (``<name>.flow.py``): the ordered steps that make one thing, each with the tool it
visits, its recipe parameters with their units, its time and who does it, and the measurements taken in the process,
the same document and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``flows.ts``)::

    from commandagi.design.flows import flow, tool, step, param, measure, visit

    result = flow(
        tool(id="coater", ref="stage1.bom.3d.py#coater", rate_per_hour=40, currency="USD"),
        step(id="why", kind="note", instruction="Marks first: every later layer aligns to them."),
        step(
            param(name="speed", value=3000, unit="rpm"),
            measure(id="resist", name="resist thickness", nominal=1.2, plus=0.1, minus=0.1, unit="um"),
            visit(tool="oven", minutes=2, instruction="soft bake"),
            id="coat", order=1, tool="coater", by="in-house", minutes=6,
        ),
        name="Alignment marks", of="stage1.bom.3d.py#wafer",
    )

A record is an element and its fields are the element's attributes (snake_case keywords: ``rate_per_hour`` is
``ratePerHour``). A step that goes to more tools than its own names each in a ``visit(tool=…, minutes=…)``. Nothing
adds a default. The check is the host's (``commandagi check <file>.flow.py``).
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

FLOW_STEP_KINDS = ["work", "note", "message", "command", "computer", "robot", "chain", "workflow", "decision", "agent"]
FLOW_ACTION_KINDS = ["message", "command", "computer", "robot", "chain", "workflow", "decision", "agent"]
FLOW_INPUT_TYPES = ["text", "number", "boolean"]
FLOW_SURPRISE = ["parent", "agent", "person"]
FLOW_FIELDS = ["name", "description", "of"]
FLOW_INPUT_FIELDS = ["name", "type", "private", "default", "required", "description"]
FLOW_TOOL_FIELDS = ["id", "ref", "name", "ratePerHour", "currency", "description"]
FLOW_STEP_FIELDS = ["id", "order", "kind", "tool", "fixture", "by", "minutes", "setupMinutes", "ratePerHour", "currency", "instruction",
                    "note", "channel", "ref", "command", "after", "surprise", "surpriseTo"]
FLOW_PARAM_FIELDS = ["name", "value", "unit", "description"]
FLOW_MEASURE_FIELDS = ["id", "name", "nominal", "min", "max", "plus", "minus", "unit", "method", "sampling", "acceptance"]
FLOW_VISIT_FIELDS = ["tool", "minutes", "setupMinutes", "ratePerHour", "currency", "instruction"]
FLOW_EXPECT_FIELDS = ["name", "equals", "tolerance", "within"]

_CHILDREN = {"holds": "children"}
#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"flow": _CHILDREN, "input": {}, "tool": {}, "step": _CHILDREN, "param": {}, "measure": {},
                                         "visit": {}, "expect": {}}

__all__ = ["FLOW_STEP_KINDS", "FLOW_ACTION_KINDS", "FLOW_INPUT_TYPES", "FLOW_SURPRISE", "SIGNATURES", "FLOW_VOCABULARY",
           *define(globals(), "flows", SIGNATURES)]

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


def _input(a: Dict[str, Any]) -> None:
    at = _where("input", "name", a)
    _check(isinstance(a.get("name"), str) and _ID.fullmatch(a["name"]), f'{at}: name is letters, digits, ".", "_" and "-"')
    _check("type" not in a or a["type"] in FLOW_INPUT_TYPES,
           f"{at}: type is one of {', '.join(FLOW_INPUT_TYPES)} (got {json.dumps(a.get('type'))})")
    for k in ("private", "required"):
        _check(k not in a or isinstance(a[k], bool), f"{at}: {k} is true or false")
    _check(not (a.get("private") is True and "default" in a),
           f"{at}: a private input states no default: its value is bound by the run and never written in the document")
    d = a.get("default")
    if "default" in a:
        ok = _num(d) if a.get("type") == "number" else isinstance(d, bool) if a.get("type") == "boolean" else isinstance(d, str)
        _check(ok, f"{at}: default is a {a.get('type') or 'text'} (the input's type)")


def _placeholders(s: str):
    for inner in re.findall(r"\$\{([^}]*)\}", s):
        head, sep, name = inner.partition(":")
        yield (head, name) if sep else ("", inner)


def _bound(value: Any, at: str, inputs: set) -> None:
    if not isinstance(value, str):
        return
    declared = ", ".join(sorted(inputs)) or "none declared"
    for kind, name in _placeholders(value):
        ok = (kind == "input" and name in inputs) or (kind == "env" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))
        shown = "${" + (kind + ":" if kind else "") + name + "}"
        _check(ok, f"{at}: {shown} is not a bound value: name a declared input ({declared}) as ${{input:name}}, "
                   f"or the secret store as ${{env:NAME}}")


#: What an action step must state, per kind.
_ACTION_NEEDS = {
    "message": ["channel", "instruction"], "command": ["channel", "command"], "computer": ["channel", "instruction"],
    "robot": ["channel", "command"], "chain": ["ref", "channel"], "workflow": ["ref"], "decision": ["instruction"],
    "agent": ["ref", "instruction"],
}


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
               f"{at}: a note step names no tool, takes no time (minutes 0 or absent) and holds no param, measure, visit or expect")
    action = a.get("kind") in FLOW_ACTION_KINDS

    def says(n: str) -> str:
        return {"instruction": "its instruction", "channel": "its channel", "command": "its command"}.get(n, "what it calls (ref)")

    if action:
        missing = [says(n) for n in _ACTION_NEEDS[a["kind"]] if n not in a]
        _check(not missing, f"{at}: a {a['kind']} step states {' and '.join(missing)}")
        _check("tool" not in a and "by" not in a and "fixture" not in a,
               f"{at}: an action step names no tool, no fixture and no by: it acts on its channel (or calls what its ref names)")
        _check(not any(c["tag"] in ("visit", "measure") for c in t["children"]),
               f"{at}: an action step takes no visit or measure: say what must be observed after it in an <expect>")
        _check(a["kind"] not in ("chain", "workflow") or (isinstance(a.get("ref"), str) and a["ref"].strip()),
               f"{at}: a {a['kind']} step names the {a['kind']} it calls (ref)")
        _check(any(c["tag"] == "expect" for c in t["children"]),
               f"{at}: an action step declares what must be observed after it (<expect name equals>)")
        _check("surprise" in a, f"{at}: an action step says where a surprise goes (surprise: parent, agent or person)")
    _check("surprise" not in a or a["surprise"] in FLOW_SURPRISE,
           f"{at}: surprise is one of {', '.join(FLOW_SURPRISE)} (got {json.dumps(a.get('surprise'))})")
    _check("surprise" not in a or a["surprise"] == "parent" or (isinstance(a.get("surpriseTo"), str) and a["surpriseTo"].strip()),
           f"{at}: surprise {json.dumps(a.get('surprise'))} names who handles it (surpriseTo: an agent or a person)")
    _check(a.get("surprise") != "parent" or "surpriseTo" not in a, f"{at}: a surprise that goes to the parent names no surpriseTo")
    if "after" in a:
        raw = a["after"]
        _check(isinstance(raw, str) and raw.strip(), f"{at}: after names the steps this one follows (their ids, space separated)")
        ids = raw.strip().split()
        for i in ids:
            _check(bool(_ID.fullmatch(i)), f"{at}: after names a step's id (got {json.dumps(i)})")
        _check(a["id"] not in ids, f"{at}: after does not name the step itself")
        _check(len(ids) == len(set(ids)), f"{at}: after names a step twice")
    names = [c["attrs"].get("name") for c in t["children"] if c["tag"] == "param"]
    twice = next((n for i, n in enumerate(names) if n in names[:i]), None)
    _check(twice is None, f"{at}: two params are named {json.dumps(twice, ensure_ascii=False)}")
    expect_names = [c["attrs"].get("name") for c in t["children"] if c["tag"] == "expect"]
    expect_twice = next((n for i, n in enumerate(expect_names) if n in expect_names[:i]), None)
    _check(expect_twice is None, f"{at}: two expects are named {json.dumps(expect_twice, ensure_ascii=False)}")
    for c in t["children"]:
        b = c["attrs"]
        if c["tag"] == "param":
            pat = _where("param", "name", b)
            _check(isinstance(b.get("name"), str) and b["name"].strip(), f"{pat}: name says what the parameter is")
            v = b.get("value")
            _check(_num(v) or isinstance(v, (str, bool)), f"{pat}: value is a number, a text or true/false")
            _check("unit" not in b or (isinstance(b["unit"], str) and b["unit"].strip()), f"{pat}: unit is a unit's symbol (rpm, sccm, mTorr, °C, s)")
        elif c["tag"] == "visit":
            vat = f'{at} {_where("visit", "tool", b)}'
            _check(isinstance(b.get("tool"), str) and _ID.fullmatch(b["tool"]), f"{vat}: tool is the id of one of the flow's tools")
            for k in ("minutes", "setupMinutes"):
                _check(k not in b or (_num(b[k]) and b[k] >= 0), f"{vat}: {k} is a number of at least 0")
            _money(b, vat)
        elif c["tag"] == "expect":
            eat = _where("expect", "name", b)
            _check(isinstance(b.get("name"), str) and b["name"].strip(), f"{eat}: name says what is observed (a screen, an exit code, a reply)")
            _check(_num(b.get("equals")) or isinstance(b.get("equals"), (str, bool)), f"{eat}: equals is the value the observation must have (a number, a text or true/false)")
            _check("tolerance" not in b or (_num(b["tolerance"]) and b["tolerance"] >= 0), f"{eat}: tolerance is a number of at least 0")
            _check("tolerance" not in b or _num(b.get("equals")), f"{eat}: a tolerance holds of a number: equals is not a number")
            _check("within" not in b or (_num(b["within"]) and b["within"] > 0), f"{eat}: within is a number of seconds, more than 0")
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
    visits = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "visit"]
    expects = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "expect"]
    return {**t["attrs"], **({"params": params} if params else {}), **({"measures": measures} if measures else {}), **({"visits": visits} if visits else {}), **({"expects": expects} if expects else {})}


def _flow(t: DocTree) -> Dict[str, Any]:
    _check("of" not in t["attrs"] or isinstance(t["attrs"]["of"], str),
           "<flow>: of is a ref to what the flow makes (a 3D document, or <file>#<item or body>)")
    for c in t["children"]:
        if c["tag"] == "input":
            _input(c["attrs"])
    inputs = {c["attrs"].get("name") for c in t["children"] if c["tag"] == "input"}
    for c in t["children"]:
        if c["tag"] == "tool":
            _tool(c["attrs"])
        elif c["tag"] == "step":
            _step(c)
            sat = _where("step", "id", c["attrs"])
            for b in c["children"]:
                if b["tag"] == "param":
                    _bound(b["attrs"].get("value"), _where("param", "name", b["attrs"]), inputs)
            _bound(c["attrs"].get("command"), sat, inputs)
            _bound(c["attrs"].get("instruction"), sat, inputs)
    step_ids = [c["attrs"].get("id") for c in t["children"] if c["tag"] == "step"]
    for c in t["children"]:
        if c["tag"] == "step" and isinstance(c["attrs"].get("after"), str):
            for i in c["attrs"]["after"].strip().split():
                _check(i in step_ids, f"{_where('step', 'id', c['attrs'])}: after names the step {json.dumps(i)}, which this flow does not declare")
    measures = [m["attrs"].get("id") for c in t["children"] for m in c["children"] if m["tag"] == "measure"]
    again = next((m for i, m in enumerate(measures) if m in measures[:i]), None)
    _check(again is None, f"<measure id={json.dumps(again, ensure_ascii=False)}>: two measures have this id (a ref names it as <file>#<id>)")
    declared = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "input"]
    tools = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "tool"]
    steps = [_step_record(c) for c in t["children"] if c["tag"] == "step"]
    own = {k: t["attrs"][k] for k in FLOW_FIELDS if k in t["attrs"]}
    return {**own, **({"inputs": declared} if declared else {}), **({"tools": tools} if tools else {}), **({"steps": steps} if steps else {})}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


FLOW_VOCABULARY = Vocabulary("flow", "a process flow", "flow", {
    "flow": {"parents": [], "attrs": FLOW_FIELDS},
    "input": {"parents": ["flow"], "key": "name", "required": ["name"], "attrs": FLOW_INPUT_FIELDS},
    "tool": {"parents": ["flow"], "key": "id", "required": ["id"], "attrs": FLOW_TOOL_FIELDS},
    "step": {"parents": ["flow"], "key": "id", "required": ["id"], "attrs": FLOW_STEP_FIELDS},
    "param": {"parents": ["step"], "required": ["name", "value"], "attrs": FLOW_PARAM_FIELDS},
    "measure": {"parents": ["step"], "key": "id", "required": ["id"], "attrs": FLOW_MEASURE_FIELDS},
    "visit": {"parents": ["step"], "required": ["tool"], "attrs": FLOW_VISIT_FIELDS},
    "expect": {"parents": ["step"], "required": ["name", "equals"], "attrs": FLOW_EXPECT_FIELDS},
}, _flow, _never, lambda name: {"name": name})

register_vocabulary(FLOW_VOCABULARY, "flows")

