"""The two documents of CommandAGI's scouts, declared in Python: the same elements and the same documents as the
TypeScript SDK's JSX (``commandagi/design`` ``scouts.ts``) and the Rust SDK's ``scouts.rs`` (``docs/scouts.md``, in the
CommandAGI repository):

``<name>.scout.py``
    one comparison to run: the configurations (a harness, a model, an effort, instructions) measured on the same cases
    of each workload, and the rules of the verdict;
``<name>.replacement.py``
    what replacing a product would cost: its capabilities by layer, what we have of each, the effort, the running cost
    and the labour of the rest, and the decision.

A record is an element and its fields are its attributes (snake_case keywords: ``relative_margin`` is
``relativeMargin``; a Python keyword gets a trailing ``_``: a case's ``from`` is ``from_``)::

    from commandagi.design.scouts import case, configuration, judge, scout, workload

    result = scout(
        configuration(id="sonnet", model="anthropic/claude-sonnet-5-5", effort="low", incumbent=True),
        configuration(id="glm", model="dashscope/glm-5.3"),
        workload(id="knowledge", title="Knowledge work", sample=20,
                 cases=[case(id="rate", from_="synthetic", prompt="…", check={"number": 0.042, "tolerance": 0.001}),
                        case(id="page", from_="own-run", source="runs/…", prompt="…",
                             rubric="Names the price, the context and the terms.")]),
        judge(model="openai/gpt-5.6-terra"),
        judge(model="dashscope/qwen3.8-max"),
        title="GLM-5.3 against Sonnet 5.5 on knowledge work", budget=10, repeats=3,
    )

    from commandagi.design.scouts import capability, decision, evidence, layer, replacement

    result = replacement(
        layer(
            capability(
                evidence(source="beehiiv checklist", claim="reported"),
                id="auth", title="DKIM, SPF, DMARC-aligned custom domains", need="must", have="none", effort="M",
            ),
            kind="invisible", title="Deliverability",
        ),
        decision(choice="skip", because="…"),
        product="beehiiv", vendor="beehiiv, Inc.", url="https://www.beehiiv.com", as_of="2026-10-14", by="scout",
    )

References are refs: a path relative to the document's folder, or an absolute address. The rule of the ontology's
files: a record is an element and its fields are its attributes, verbatim. Nothing adds a default: what the file does
not say, the document does not have (the runner and the reader fill their own). Structure and enums are checked here;
the meaning (a model the catalog lists, a ref that resolves, the sums) is the reader's.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

SCOUT_FIELDS = ["title", "budget", "repeats", "margin", "relativeMargin", "errorFloor", "minCalls", "minCases", "resamples",
                "alpha", "seed", "maxCases", "readme"]
CONFIGURATION_FIELDS = ["id", "model", "harness", "effort", "instructions", "maxTokens", "incumbent"]
WORKLOAD_FIELDS = ["id", "title", "needs", "sample", "context"]
CASE_FIELDS = ["id", "from", "prompt", "system", "check", "rubric", "tools", "turns", "source", "terms"]
JUDGE_FIELDS = ["model", "effort"]

REPLACEMENT_FIELDS = ["product", "vendor", "url", "asOf", "by", "readme"]
LAYER_FIELDS = ["kind", "title"]
CAPABILITY_FIELDS = ["id", "title", "need", "have", "effort", "run", "labour", "ref", "note"]
EVIDENCE_FIELDS = ["source", "claim"]
DECISION_FIELDS = ["choice", "because"]
ECONOMICS_FIELDS = ["price", "customers", "margin", "note"]

#: Where a case's data came from (``docs/scouts.md`` § the corpus). A customer's runs and third-party records are
#: never cases.
CASE_ORIGINS = ["public", "synthetic", "own-run"]
#: What a workload needs of a model: a hard gate, never a score.
WORKLOAD_NEEDS = ["tools", "structured", "image"]
#: The checks a case may name, cheapest first (a judge's rubric only where no check exists).
CHECK_KINDS = ["exact", "oneOf", "number", "contains", "regex", "json", "letter", "literal", "tool", "program"]

LAYER_KINDS = ["visible", "invisible", "integrations", "operations", "economics"]
CAPABILITY_NEEDS = ["must", "should", "later"]
CAPABILITY_HAVES = ["built", "partial", "none"]
CAPABILITY_EFFORTS = ["S", "M", "L", "XL"]
EVIDENCE_CLAIMS = ["verified", "checked", "reported"]
DECISION_CHOICES = ["build", "buy", "integrate", "skip"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "scout": {"holds": "children"},
    "configuration": {},
    "workload": {"holds": "children"},
    "case": {},
    "judge": {},
    "replacement": {"holds": "children"},
    "layer": {"holds": "children"},
    "capability": {"holds": "children"},
    "evidence": {},
    "decision": {},
    "differentiation": {},
    "economics": {},
}

#: The form of a tool's name, and of a replacement analysis's day.
_TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LETTER = re.compile(r"^[A-Z]$")

__all__ = ["SCOUT_FIELDS", "CONFIGURATION_FIELDS", "WORKLOAD_FIELDS", "CASE_FIELDS", "JUDGE_FIELDS",
           "REPLACEMENT_FIELDS", "LAYER_FIELDS", "CAPABILITY_FIELDS", "EVIDENCE_FIELDS", "DECISION_FIELDS",
           "ECONOMICS_FIELDS", "CASE_ORIGINS", "WORKLOAD_NEEDS", "CHECK_KINDS", "LAYER_KINDS", "CAPABILITY_NEEDS",
           "CAPABILITY_HAVES", "CAPABILITY_EFFORTS", "EVIDENCE_CLAIMS", "DECISION_CHOICES", "SIGNATURES",
           "case_of", "SCOUT_VOCABULARY", "REPLACEMENT_VOCABULARY", "SCOUTS",
           *define(globals(), "scouts", SIGNATURES)]


def _said(attrs: Dict[str, Any], k: str) -> str:
    """JavaScript's ``JSON.stringify`` of a field as a message says it (an absent one is ``undefined``)."""
    return _json(attrs[k]) if k in attrs else "undefined"


def _said_value(v: Any) -> str:
    return _json(v) if v is not None else "undefined"


def _where(t: DocTree) -> str:
    ident = t["attrs"].get("id")
    return f'<{t["tag"]} id="{ident}">' if isinstance(ident, str) else f"<{t['tag']}>"


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _whole(v: Any) -> bool:
    return _number(v) and float(v).is_integer()


def _text(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not (isinstance(a[k], str) and a[k].strip()):
        raise ValueError(f"{_where(t)} {k} is text, not {_said(a, k)}")


def _positive(t: DocTree, k: str, integer: bool = False, zero: bool = False) -> None:
    """A number above 0 (of 0 or more with ``zero``), whole when ``integer``."""
    a = t["attrs"]
    if k not in a:
        return
    v = a[k]
    if not (_whole(v) if integer else _number(v)) or (v < 0 if zero else v <= 0):
        what = f"{'whole ' if integer else ''}number{' of 0 or more' if zero else ' above 0'}"
        raise ValueError(f"{_where(t)} {k} is a {what}, not {_said(a, k)}")


def _one_of(t: DocTree, k: str, allowed: List[str]) -> None:
    a = t["attrs"]
    if k in a and a[k] not in allowed:
        raise ValueError(f"{_where(t)} {k} is one of {', '.join(allowed)}, not {_said(a, k)}")


def _flag(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not isinstance(a[k], bool):
        raise ValueError(f"{_where(t)} {k} is true or false")


def _fields(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if k in attrs}


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent, None, "" or an empty list): code does not write it."""
    return v is None or v == "" or (isinstance(v, (list, tuple)) and not v)


def _attrs_of(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: d[k] for k in keys if not _nothing(d.get(k))}


def _node(tag: str, attrs: Dict[str, Any], children: List[DocTree] = None) -> DocTree:
    return {"tag": tag, "attrs": attrs, "children": children or []}


def _check_of(t: DocTree) -> None:
    c = t["attrs"].get("check")
    if c is None:
        return
    if not isinstance(c, dict):
        raise ValueError(f'{_where(t)} check is an object ({{ exact: "42" }}), not {_said_value(c)}')
    kinds = [k for k in c if k != "tolerance"]
    if len(kinds) != 1 or kinds[0] not in CHECK_KINDS:
        extra = f" (it has {' and '.join(kinds)})" if kinds else ""
        raise ValueError(f"{_where(t)} check is exactly one of {', '.join(CHECK_KINDS)}{extra}")
    kind = kinds[0]
    if "tolerance" in c and kind != "number":
        raise ValueError(f"{_where(t)} check: tolerance goes with number")
    if "number" in c and not (_number(c["number"]) and ("tolerance" not in c or (_number(c["tolerance"]) and c["tolerance"] >= 0))):
        raise ValueError(f"{_where(t)} check: number and tolerance are numbers")
    if "exact" in c and not isinstance(c["exact"], str):
        raise ValueError(f"{_where(t)} check: exact is text")
    for k in ("oneOf", "contains"):
        if k in c and not (isinstance(c[k], list) and c[k] and all(isinstance(s, str) and s for s in c[k])):
            raise ValueError(f"{_where(t)} check: {k} is a list of texts")
    if "regex" in c:
        if not (isinstance(c["regex"], str) and c["regex"]):
            raise ValueError(f"{_where(t)} check: regex is text")
        try:
            re.compile(c["regex"])
        except re.error:
            raise ValueError(f"{_where(t)} check: regex {_json(c['regex'])} is not a regular expression") from None
    if "json" in c and not isinstance(c["json"], dict):
        raise ValueError(f"{_where(t)} check: json is the object the answer must hold")
    if "letter" in c and not (isinstance(c["letter"], str) and _LETTER.match(c["letter"])):
        raise ValueError(f"{_where(t)} check: letter is one capital letter")
    for k in ("literal", "tool"):
        if k in c and not (isinstance(c[k], str) and c[k]):
            raise ValueError(f"{_where(t)} check: {k} is text")
    if "tool" in c and "tools" not in t["attrs"]:
        raise ValueError(f"{_where(t)} check: tool needs the case's tools")
    if "program" in c:
        p = c["program"]
        data = p.get("data") if isinstance(p, dict) else None
        if not (isinstance(data, list) and data
                and all(isinstance(d, list) and len(d) == 2 and all(_number(n) for n in d) for d in data)):
            raise ValueError(f"{_where(t)} check: program is {{ data: [[x, y], …] }}")
        if "tolerance" in p and not (_number(p["tolerance"]) and p["tolerance"] >= 0):
            raise ValueError(f"{_where(t)} check: program tolerance is a number of 0 or more")


def _tools_of(t: DocTree) -> None:
    tools = t["attrs"].get("tools")
    if tools is None:
        return
    if not isinstance(tools, list) or not tools:
        raise ValueError(f"{_where(t)} tools is a list of {{ name, parameters, results }}")
    names = set()
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if not (isinstance(name, str) and _TOOL_NAME.match(name)):
            raise ValueError(f"{_where(t)} a tool's name is a word of letters, digits, _ and -")
        if name in names:
            raise ValueError(f"{_where(t)} has two tools named {name}")
        names.add(name)
        if not isinstance(tool.get("parameters"), dict):
            raise ValueError(f"{_where(t)} tool {name}: parameters is a JSON Schema object")
        for r in tool.get("results") or []:
            when = r.get("when") if isinstance(r, dict) else None
            if not (isinstance(r, dict) and isinstance(r.get("result"), str)
                    and (when is None or (isinstance(when, dict) and all(isinstance(v, str) for v in when.values())))):
                raise ValueError(f"{_where(t)} tool {name}: a result is {{ when?: {{ <argument>: <text it contains> }}, result: <text> }}")
    _positive(t, "turns", integer=True)


def case_of(t: DocTree) -> Dict[str, Any]:
    """One case as its element declares it; raises with why it does not read (the TypeScript SDK's ``caseOf``)."""
    a = t["attrs"]
    for k in ("id", "prompt", "system", "rubric", "source"):
        _text(t, k)
    _one_of(t, "from", CASE_ORIGINS)
    _check_of(t)
    _tools_of(t)
    if "turns" in a and "tools" not in a:
        raise ValueError(f"{_where(t)} turns goes with tools")
    if ("check" in a) == ("rubric" in a):
        raise ValueError(f"{_where(t)} is scored by exactly one of check (a program) or rubric (a judge panel)")
    terms = a.get("terms")
    if terms is not None and not (isinstance(terms, list) and all(isinstance(s, str) and s for s in terms)):
        raise ValueError(f"{_where(t)} terms is a list of term ids")
    return _fields(a, CASE_FIELDS)


def _scout(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("title", "readme"):
        _text(t, k)
    _positive(t, "budget")
    for k in ("repeats", "minCalls", "minCases", "resamples", "maxCases"):
        _positive(t, k, integer=True)
    for k in ("margin", "relativeMargin", "errorFloor"):
        _positive(t, k, zero=True)
    _positive(t, "alpha")
    if isinstance(a.get("alpha"), (int, float)) and not isinstance(a.get("alpha"), bool) and a["alpha"] >= 1:
        raise ValueError("<scout> alpha is below 1")
    if "seed" in a and not (_whole(a["seed"]) and abs(a["seed"]) <= 2 ** 53 - 1):
        raise ValueError("<scout> seed is a whole number")
    parts = lambda tag: [c for c in t["children"] if c["tag"] == tag]  # noqa: E731
    configurations = []
    for c in parts("configuration"):
        for k in ("id", "model", "harness", "effort", "instructions"):
            _text(c, k)
        _positive(c, "maxTokens", integer=True)
        if "incumbent" in c["attrs"] and not isinstance(c["attrs"]["incumbent"], bool):
            raise ValueError(f"{_where(c)} incumbent is true or false")
        configurations.append(_fields(c["attrs"], CONFIGURATION_FIELDS))
    if len([c for c in configurations if c.get("incumbent")]) > 1:
        raise ValueError("<scout> has one incumbent configuration")
    workloads = []
    for w in parts("workload"):
        _text(w, "id")
        _text(w, "title")
        _positive(w, "sample", integer=True)
        _positive(w, "context", integer=True)
        needs = w["attrs"].get("needs")
        if needs is not None and not (isinstance(needs, list) and all(n in WORKLOAD_NEEDS for n in needs)):
            raise ValueError(f"{_where(w)} needs is a list of {', '.join(WORKLOAD_NEEDS)}")
        workloads.append({**_fields(w["attrs"], WORKLOAD_FIELDS), "cases": [case_of(c) for c in w["children"]]})
    judges = []
    for j in parts("judge"):
        _text(j, "model")
        _text(j, "effort")
        judges.append(_fields(j["attrs"], JUDGE_FIELDS))
    return {**_fields(a, SCOUT_FIELDS), "configurations": configurations, "workloads": workloads, "judges": judges}


def _replacement(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("product", "vendor", "url", "by", "readme"):
        _text(t, k)
    if not (isinstance(a.get("asOf"), str) and _DAY.match(a["asOf"])):
        raise ValueError(f'<replacement> asOf is a day (2026-10-14), not {_said(a, "asOf")}')
    parts = lambda tag: [c for c in t["children"] if c["tag"] == tag]  # noqa: E731
    layers = []
    for layer in parts("layer"):
        _one_of(layer, "kind", LAYER_KINDS)
        _text(layer, "title")
        capabilities = []
        for c in layer["children"]:
            for k in ("id", "title", "ref", "note"):
                _text(c, k)
            _one_of(c, "need", CAPABILITY_NEEDS)
            _one_of(c, "have", CAPABILITY_HAVES)
            _one_of(c, "effort", CAPABILITY_EFFORTS)
            _positive(c, "run", zero=True)
            _positive(c, "labour", zero=True)
            evidence = []
            for e in c["children"]:
                _text(e, "source")
                _one_of(e, "claim", EVIDENCE_CLAIMS)
                evidence.append(_fields(e["attrs"], EVIDENCE_FIELDS))
            capabilities.append({**_fields(c["attrs"], CAPABILITY_FIELDS), "evidence": evidence})
        layers.append({**_fields(layer["attrs"], LAYER_FIELDS), "capabilities": capabilities})
    decision = parts("decision")
    if decision:
        _one_of(decision[0], "choice", DECISION_CHOICES)
        _text(decision[0], "because")
    differentiation = parts("differentiation")
    if differentiation:
        _text(differentiation[0], "text")
    economics = parts("economics")
    if economics:
        for k in ECONOMICS_FIELDS:
            _text(economics[0], k)
    return {
        **_fields(a, REPLACEMENT_FIELDS),
        "layers": layers,
        **({"decision": _fields(decision[0]["attrs"], DECISION_FIELDS)} if decision else {}),
        **({"differentiation": differentiation[0]["attrs"]["text"]} if differentiation else {}),
        **({"economics": _fields(economics[0]["attrs"], ECONOMICS_FIELDS)} if economics else {}),
    }


def _scout_tree(d: Dict[str, Any]) -> DocTree:
    return _node("scout", _attrs_of(d, SCOUT_FIELDS), [
        _node("configuration", _attrs_of(c, CONFIGURATION_FIELDS)) for c in d.get("configurations") or []
    ] + [
        _node("workload", _attrs_of(w, WORKLOAD_FIELDS), [_node("case", _attrs_of(c, CASE_FIELDS)) for c in w.get("cases") or []])
        for w in d.get("workloads") or []
    ] + [
        _node("judge", _attrs_of(j, JUDGE_FIELDS)) for j in d.get("judges") or []
    ])


def _replacement_tree(r: Dict[str, Any]) -> DocTree:
    children = [
        _node("layer", _attrs_of(layer, LAYER_FIELDS), [
            _node("capability", _attrs_of(c, CAPABILITY_FIELDS),
                  [_node("evidence", _attrs_of(e, EVIDENCE_FIELDS)) for e in c.get("evidence") or []])
            for c in layer.get("capabilities") or []
        ]) for layer in r.get("layers") or []
    ]
    if r.get("decision"):
        children.append(_node("decision", _attrs_of(r["decision"], DECISION_FIELDS)))
    if r.get("differentiation"):
        children.append(_node("differentiation", {"text": r["differentiation"]}))
    if r.get("economics") and _attrs_of(r["economics"], ECONOMICS_FIELDS):
        children.append(_node("economics", _attrs_of(r["economics"], ECONOMICS_FIELDS)))
    return _node("replacement", _attrs_of(r, REPLACEMENT_FIELDS), children)


SCOUT_VOCABULARY = Vocabulary("scout", "a scout's comparison", "scout", {
    "scout": {"parents": [], "required": ["budget"], "attrs": SCOUT_FIELDS},
    "configuration": {"parents": ["scout"], "key": "id", "required": ["id", "model"], "attrs": CONFIGURATION_FIELDS},
    "workload": {"parents": ["scout"], "key": "id", "required": ["id"], "attrs": WORKLOAD_FIELDS},
    "case": {"parents": ["workload"], "key": "id", "required": ["id", "from", "prompt"], "attrs": CASE_FIELDS},
    "judge": {"parents": ["scout"], "key": "model", "required": ["model"], "attrs": JUDGE_FIELDS},
}, _scout, _scout_tree)

REPLACEMENT_VOCABULARY = Vocabulary("replacement", "a replacement-cost analysis", "replacement", {
    "replacement": {"parents": [], "required": ["product", "asOf"], "attrs": REPLACEMENT_FIELDS},
    # Two layers may be of one kind (the visible editor and the visible website): a layer is told apart by its title.
    "layer": {"parents": ["replacement"], "key": "title", "required": ["kind", "title"], "attrs": LAYER_FIELDS},
    "capability": {"parents": ["layer"], "key": "id", "required": ["id", "title", "need", "have"], "attrs": CAPABILITY_FIELDS},
    "evidence": {"parents": ["capability"], "key": "source", "required": ["source", "claim"], "attrs": EVIDENCE_FIELDS},
    "decision": {"parents": ["replacement"], "single": True, "required": ["choice", "because"], "attrs": DECISION_FIELDS},
    "differentiation": {"parents": ["replacement"], "single": True, "required": ["text"], "attrs": ["text"]},
    "economics": {"parents": ["replacement"], "single": True, "attrs": ECONOMICS_FIELDS},
}, _replacement, _replacement_tree)

for _v in (SCOUT_VOCABULARY, REPLACEMENT_VOCABULARY):
    register_vocabulary(_v, "scouts")

#: The vocabularies of a comparison and a replacement analysis, by format.
SCOUTS = {"scout": SCOUT_VOCABULARY, "replacement": REPLACEMENT_VOCABULARY}
