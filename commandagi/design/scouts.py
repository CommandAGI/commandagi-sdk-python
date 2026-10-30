"""SCOUTS IN PYTHON — the two documents of CommandAGI's scouts (``docs/scouts.md`` in the CommandAGI repository), the
same elements as the TypeScript SDK's JSX (``commandagi/design`` ``scouts.ts``), one call each: a comparison
(``<name>.scout.py``) and a replacement-cost analysis (``<name>.replacement.py``)::

    from commandagi.design.scouts import case, configuration, judge, scout, workload

    result = scout(
        configuration(id="sonnet", model="anthropic/claude-sonnet-5-5", effort="low", incumbent=True),
        configuration(id="glm", model="dashscope/glm-5.3"),
        workload(case(id="rate", from_="synthetic", prompt="What is 4.2% as a decimal?",
                      check={"number": 0.042, "tolerance": 0.0005}),
                 id="knowledge", title="Knowledge work", sample=20),
        judge(model="openai/gpt-5.6-terra"),
        budget=10, repeats=3, title="GLM against Sonnet",
    )

    result = replacement(
        layer(capability(evidence(source="beehiiv checklist", claim="reported"), id="bulk-send", need="must", have="none",
                          effort="XL", title="3M+ emails a minute"),
              kind="invisible", title="Deliverability"),
        decision(because="The invisible layer is the product.", choice="skip"),
        as_of="2026-10-14", product="beehiiv", vendor="beehiiv, Inc.",
    )

A record is an element and its fields are its attributes (snake_case keywords: ``max_tokens`` is ``maxTokens``,
``from_`` is ``from``). Nothing adds a default: what the file does not say, the document does not have (the runner and
the reader fill their own). Structure and enums are checked here; the meaning (a model the catalog lists, a ref that
resolves, the sums) is the reader's.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

SCOUT_FIELDS = ["title", "budget", "repeats", "margin", "relativeMargin", "errorFloor", "minCalls", "minCases",
                "resamples", "alpha", "seed", "maxCases", "readme"]
CONFIGURATION_FIELDS = ["id", "model", "harness", "effort", "instructions", "maxTokens", "incumbent"]
WORKLOAD_FIELDS = ["id", "title", "needs", "sample", "context"]
CASE_FIELDS = ["id", "from", "prompt", "system", "check", "rubric", "tools", "turns", "source", "terms"]
JUDGE_FIELDS = ["model", "effort"]

#: Where a case's data came from (docs/scouts.md § the corpus). A customer's runs and third-party records are never cases.
CASE_ORIGINS = ["public", "synthetic", "own-run"]
#: What a workload needs of a model: a hard gate, never a score.
WORKLOAD_NEEDS = ["tools", "structured", "image"]
#: The checks a case may name, cheapest first (a judge's rubric only where no check exists).
CHECK_KINDS = ["exact", "oneOf", "number", "contains", "regex", "json", "letter", "literal", "tool", "program"]

REPLACEMENT_FIELDS = ["product", "vendor", "url", "asOf", "by", "readme"]
LAYER_FIELDS = ["kind", "title"]
CAPABILITY_FIELDS = ["id", "title", "need", "have", "effort", "run", "labour", "ref", "note"]
EVIDENCE_FIELDS = ["source", "claim"]
DECISION_FIELDS = ["choice", "because"]
ECONOMICS_FIELDS = ["price", "customers", "margin", "note"]

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

__all__ = ["SCOUT_FIELDS", "CONFIGURATION_FIELDS", "WORKLOAD_FIELDS", "CASE_FIELDS", "JUDGE_FIELDS", "CASE_ORIGINS",
           "WORKLOAD_NEEDS", "CHECK_KINDS", "REPLACEMENT_FIELDS", "LAYER_FIELDS", "CAPABILITY_FIELDS", "EVIDENCE_FIELDS",
           "DECISION_FIELDS", "ECONOMICS_FIELDS", "LAYER_KINDS", "CAPABILITY_NEEDS", "CAPABILITY_HAVES",
           "CAPABILITY_EFFORTS", "EVIDENCE_CLAIMS", "DECISION_CHOICES", "SIGNATURES", "SCOUT_VOCABULARY",
           "REPLACEMENT_VOCABULARY", "SCOUTS", *define(globals(), "scouts", SIGNATURES)]


def _said(attrs: Dict[str, Any], k: str) -> str:
    """JavaScript's ``JSON.stringify`` of a field as a message says it (an absent one is ``undefined``)."""
    return _json(attrs[k]) if k in attrs else "undefined"


def _where(t: DocTree) -> str:
    ident = t["attrs"].get("id")
    return f'<{t["tag"]} id="{ident}">' if isinstance(ident, str) else f"<{t['tag']}>"


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _whole(v: Any) -> bool:
    return _number(v) and float(v).is_integer()


def _text(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not (isinstance(a[k], str) and a[k]):
        raise ValueError(f"{_where(t)} {k} is text, not {_said(a, k)}")


def _positive(t: DocTree, k: str, integer: bool = False, zero: bool = False) -> None:
    a = t["attrs"]
    if k not in a:
        return
    v = a[k]
    if not _number(v) or (v < 0 if zero else v <= 0) or (integer and not _whole(v)):
        raise ValueError(f"{_where(t)} {k} is a {'whole ' if integer else ''}number"
                         f"{' of 0 or more' if zero else ' above 0'}, not {_said(a, k)}")


def _one_of(t: DocTree, k: str, allowed: List[str]) -> None:
    a = t["attrs"]
    if k in a and a[k] not in allowed:
        raise ValueError(f"{_where(t)} {k} is one of {', '.join(allowed)}, not {_said(a, k)}")


def _check(t: DocTree) -> None:
    c = t["attrs"].get("check")
    if c is None:
        return
    if not isinstance(c, dict):
        raise ValueError(f'{_where(t)} check is an object ({{ exact: "42" }}), not {_json(c)}')
    kinds = [k for k in c if k != "tolerance"]
    if len(kinds) != 1 or kinds[0] not in CHECK_KINDS:
        said = f" (it has {' and '.join(kinds)})" if kinds else ""
        raise ValueError(f"{_where(t)} check is exactly one of {', '.join(CHECK_KINDS)}{said}")
    x = c
    if "tolerance" in x and kinds[0] != "number":
        raise ValueError(f"{_where(t)} check: tolerance goes with number")
    if "number" in x and (not _number(x["number"]) or ("tolerance" in x and not (_number(x["tolerance"]) and x["tolerance"] >= 0))):
        raise ValueError(f"{_where(t)} check: number and tolerance are numbers")
    if "exact" in x and not isinstance(x["exact"], str):
        raise ValueError(f"{_where(t)} check: exact is text")
    for k in ("oneOf", "contains"):
        if k in x:
            v = x[k]
            if not (isinstance(v, list) and v and all(isinstance(s, str) and s for s in v)):
                raise ValueError(f"{_where(t)} check: {k} is a list of texts")
    if "regex" in x:
        if not (isinstance(x["regex"], str) and x["regex"]):
            raise ValueError(f"{_where(t)} check: regex is text")
        try:
            re.compile(x["regex"])
        except re.error:
            raise ValueError(f"{_where(t)} check: regex {_json(x['regex'])} is not a regular expression") from None
    if "json" in x and not isinstance(x["json"], dict):
        raise ValueError(f"{_where(t)} check: json is the object the answer must hold")
    if "letter" in x and not (isinstance(x["letter"], str) and re.fullmatch(r"[A-Z]", x["letter"])):
        raise ValueError(f"{_where(t)} check: letter is one capital letter")
    for k in ("literal", "tool"):
        if k in x and not (isinstance(x[k], str) and x[k]):
            raise ValueError(f"{_where(t)} check: {k} is text")
    if "tool" in x and "tools" not in t["attrs"]:
        raise ValueError(f"{_where(t)} check: tool needs the case's tools")
    if "program" in x:
        p = x["program"]
        if not (isinstance(p, dict) and isinstance(p.get("data"), list) and p["data"]
                and all(isinstance(d, list) and len(d) == 2 and all(_number(n) for n in d) for d in p["data"])):
            raise ValueError(f"{_where(t)} check: program is {{ data: [[x, y], …] }}")
        if "tolerance" in p and not (_number(p["tolerance"]) and p["tolerance"] >= 0):
            raise ValueError(f"{_where(t)} check: program tolerance is a number of 0 or more")


def _tools_of(t: DocTree) -> None:
    tools = t["attrs"].get("tools")
    if tools is None:
        return
    if not (isinstance(tools, list) and tools):
        raise ValueError(f"{_where(t)} tools is a list of {{ name, parameters, results }}")
    names = set()
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if not (isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name)):
            raise ValueError(f"{_where(t)} a tool's name is a word of letters, digits, _ and -")
        if name in names:
            raise ValueError(f"{_where(t)} has two tools named {name}")
        names.add(name)
        if not isinstance(tool.get("parameters"), dict):
            raise ValueError(f"{_where(t)} tool {name}: parameters is a JSON Schema object")
        for r in tool.get("results") or []:
            if not (isinstance(r, dict) and isinstance(r.get("result"), str)
                    and ("when" not in r or (isinstance(r["when"], dict) and all(isinstance(v, str) for v in r["when"].values())))):
                raise ValueError(f"{_where(t)} tool {name}: a result is {{ when?: {{ <argument>: <text it contains> }}, "
                                 f"result: <text> }}")
    _positive(t, "turns", integer=True)


def _case_of(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("id", "prompt", "system", "rubric", "source"):
        _text(t, k)
    _one_of(t, "from", CASE_ORIGINS)
    _check(t)
    _tools_of(t)
    if "turns" in a and "tools" not in a:
        raise ValueError(f"{_where(t)} turns goes with tools")
    if ("check" in a) == ("rubric" in a):
        raise ValueError(f"{_where(t)} is scored by exactly one of check (a program) or rubric (a judge panel)")
    if "terms" in a:
        v = a["terms"]
        if not (isinstance(v, list) and all(isinstance(s, str) and s for s in v)):
            raise ValueError(f"{_where(t)} terms is a list of term ids")
    return _fields(a, CASE_FIELDS)


def _configuration_of(c: DocTree) -> Dict[str, Any]:
    for k in ("id", "model", "harness", "effort", "instructions"):
        _text(c, k)
    _positive(c, "maxTokens", integer=True)
    if "incumbent" in c["attrs"] and not isinstance(c["attrs"]["incumbent"], bool):
        raise ValueError(f"{_where(c)} incumbent is true or false")
    return _fields(c["attrs"], CONFIGURATION_FIELDS)


def _workload_of(w: DocTree) -> Dict[str, Any]:
    _text(w, "id")
    _text(w, "title")
    _positive(w, "sample", integer=True)
    _positive(w, "context", integer=True)
    if "needs" in w["attrs"]:
        v = w["attrs"]["needs"]
        if not (isinstance(v, list) and all(n in WORKLOAD_NEEDS for n in v)):
            raise ValueError(f"{_where(w)} needs is a list of {', '.join(WORKLOAD_NEEDS)}")
    return {**_fields(w["attrs"], WORKLOAD_FIELDS), "cases": [_case_of(c) for c in w["children"]]}


def _judge_of(j: DocTree) -> Dict[str, Any]:
    _text(j, "model")
    _text(j, "effort")
    return _fields(j["attrs"], JUDGE_FIELDS)


def _scout(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text(t, "title")
    _text(t, "readme")
    _positive(t, "budget")
    for k in ("repeats", "minCalls", "minCases", "resamples", "maxCases"):
        _positive(t, k, integer=True)
    for k in ("margin", "relativeMargin", "errorFloor"):
        _positive(t, k, zero=True)
    _positive(t, "alpha")
    if _number(a.get("alpha")) and a["alpha"] >= 1:
        raise ValueError("<scout> alpha is below 1")
    if "seed" in a and not (_whole(a["seed"]) and abs(a["seed"]) <= 2 ** 53 - 1):
        raise ValueError("<scout> seed is a whole number")
    configurations = [_configuration_of(c) for c in t["children"] if c["tag"] == "configuration"]
    if sum(1 for c in configurations if c.get("incumbent")) > 1:
        raise ValueError("<scout> has one incumbent configuration")
    workloads = [_workload_of(w) for w in t["children"] if w["tag"] == "workload"]
    judges = [_judge_of(j) for j in t["children"] if j["tag"] == "judge"]
    return {**_fields(a, SCOUT_FIELDS), "configurations": configurations, "workloads": workloads, "judges": judges}


def _replacement_capability(c: DocTree) -> Dict[str, Any]:
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
    return {**_fields(c["attrs"], CAPABILITY_FIELDS), "evidence": evidence}


def _replacement(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("product", "vendor", "url", "by", "readme"):
        _text(t, k)
    if not (isinstance(a.get("asOf"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["asOf"])):
        raise ValueError(f"<replacement> asOf is a day (2026-10-14), not {_said(a, 'asOf')}")
    layers = []
    for l in (c for c in t["children"] if c["tag"] == "layer"):
        _one_of(l, "kind", LAYER_KINDS)
        _text(l, "title")
        layers.append({**_fields(l["attrs"], LAYER_FIELDS), "capabilities": [_replacement_capability(c) for c in l["children"]]})
    doc: Dict[str, Any] = {**_fields(a, REPLACEMENT_FIELDS), "layers": layers}
    decision = next((c for c in t["children"] if c["tag"] == "decision"), None)
    if decision is not None:
        _one_of(decision, "choice", DECISION_CHOICES)
        _text(decision, "because")
        doc["decision"] = _fields(decision["attrs"], DECISION_FIELDS)
    differentiation = next((c for c in t["children"] if c["tag"] == "differentiation"), None)
    if differentiation is not None:
        _text(differentiation, "text")
        doc["differentiation"] = differentiation["attrs"].get("text")
    economics = next((c for c in t["children"] if c["tag"] == "economics"), None)
    if economics is not None:
        for k in ECONOMICS_FIELDS:
            _text(economics, k)
        doc["economics"] = _fields(economics["attrs"], ECONOMICS_FIELDS)
    return doc


def _fields(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if k in attrs}


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent, None, "", [] or {}): code does not write it."""
    return v is None or v == "" or (isinstance(v, (list, dict)) and not v)


def _attrs_of(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: d[k] for k in keys if not _nothing(d.get(k))}


def _leaf(tag: str, attrs: Dict[str, Any], children: Optional[List[DocTree]] = None) -> DocTree:
    return {"tag": tag, "attrs": attrs, "children": list(children or [])}


SCOUT_VOCABULARY = Vocabulary("scout", "a scout's comparison", "scout", {
    "scout": {"parents": [], "required": ["budget"], "attrs": SCOUT_FIELDS},
    "configuration": {"parents": ["scout"], "key": "id", "required": ["id", "model"], "attrs": CONFIGURATION_FIELDS},
    "workload": {"parents": ["scout"], "key": "id", "required": ["id"], "attrs": WORKLOAD_FIELDS},
    "case": {"parents": ["workload"], "key": "id", "required": ["id", "from", "prompt"], "attrs": CASE_FIELDS},
    "judge": {"parents": ["scout"], "key": "model", "required": ["model"], "attrs": JUDGE_FIELDS},
}, _scout, lambda d: _leaf("scout", _attrs_of(d, SCOUT_FIELDS), [
    *[_leaf("configuration", _attrs_of(c, CONFIGURATION_FIELDS)) for c in d.get("configurations") or []],
    *[_leaf("workload", _attrs_of(w, WORKLOAD_FIELDS),
            [_leaf("case", _attrs_of(c, CASE_FIELDS)) for c in w.get("cases") or []]) for w in d.get("workloads") or []],
    *[_leaf("judge", _attrs_of(j, JUDGE_FIELDS)) for j in d.get("judges") or []],
]))

REPLACEMENT_VOCABULARY = Vocabulary("replacement", "a replacement-cost analysis", "replacement", {
    "replacement": {"parents": [], "required": ["product", "asOf"], "attrs": REPLACEMENT_FIELDS},
    # Two layers may be of one kind (the visible editor and the visible website): a layer is told apart by its title.
    "layer": {"parents": ["replacement"], "key": "title", "required": ["kind", "title"], "attrs": LAYER_FIELDS},
    "capability": {"parents": ["layer"], "key": "id", "required": ["id", "title", "need", "have"], "attrs": CAPABILITY_FIELDS},
    "evidence": {"parents": ["capability"], "key": "source", "required": ["source", "claim"], "attrs": EVIDENCE_FIELDS},
    "decision": {"parents": ["replacement"], "single": True, "required": ["choice", "because"], "attrs": DECISION_FIELDS},
    "differentiation": {"parents": ["replacement"], "single": True, "required": ["text"], "attrs": ["text"]},
    "economics": {"parents": ["replacement"], "single": True, "attrs": ECONOMICS_FIELDS},
}, _replacement, lambda r: _leaf("replacement", _attrs_of(r, REPLACEMENT_FIELDS), [
    *[_leaf("layer", _attrs_of(l, LAYER_FIELDS), [
        _leaf("capability", _attrs_of(c, CAPABILITY_FIELDS), [
            _leaf("evidence", _attrs_of(e, EVIDENCE_FIELDS)) for e in c.get("evidence") or []])
        for c in l.get("capabilities") or []]) for l in r.get("layers") or []],
    *([_leaf("decision", _attrs_of(r["decision"], DECISION_FIELDS))] if r.get("decision") else []),
    *([_leaf("differentiation", {"text": r["differentiation"]})] if r.get("differentiation") else []),
    *([_leaf("economics", _attrs_of(r["economics"], ECONOMICS_FIELDS))]
      if r.get("economics") and _attrs_of(r["economics"], ECONOMICS_FIELDS) else []),
]))

for _v in (SCOUT_VOCABULARY, REPLACEMENT_VOCABULARY):
    register_vocabulary(_v, "scouts")

#: The vocabularies of the scouts, by format.
SCOUTS = {"scout": SCOUT_VOCABULARY, "replacement": REPLACEMENT_VOCABULARY}
