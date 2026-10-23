"""An eval and a metric, declared in Python: the same documents and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``evals.ts``), each element a call. ``<name>.eval.py`` declares one ``eval``, each of its cases
one ``case``; ``<name>.metric.py`` declares one ``metric``. A record is an element and its fields are its attributes
(snake_case keywords: ``time_limit_ms`` is ``timeLimitMs``)::

    from commandagi.design.evals import case, eval, metric

    result = eval(
        case(slug="undock-and-lap", name="Undock and lap", task="../Tasks/Undock and lap.task.tsx",
             environment={"kind": "synthetic", "seed": 41}),
        case(slug="open-a-terminal", name="Open a terminal", instruction="Open a terminal window.", time_limit_ms=120000,
             environment={"kind": "none"}),
        domain="robot", slug="yard-shakedown", version="3", metrics=["Fleet availability.metric.tsx"], repeats=3,
    )

    result = metric(slug="fleet-availability", probe={"kind": "event", "eventKind": "telemetry"}, aggregation="rate")

The element ``eval`` is named by its tag, as every element is: importing it hides Python's builtin ``eval`` in that
file. A metric's ``pass`` is written ``pass_`` (a Python keyword).

References are refs: a path relative to the eval file's folder, or an absolute address. ``metrics`` names the metric
files the eval reads; a case's ``task`` names the ``.task.tsx`` whose title and text the agent is handed. A case with no
task file says its ``instruction`` itself; a case says one of the two. ``objective`` and ``scoring``'s ``weights`` name
metric files by ref as well: ``{"kind": "metric", "metric": "<ref>"}``, ``{"kind": "linear", "terms": [{"metric": "<ref>",
"weight": 2}], "bias": 0}`` or a ``function``; the weights are keyed by ref. ``frozen`` is the digest an eval is frozen at
(``sha256:<hex>``). Nothing adds a default: what the file does not say, the document does not have. A run gives back
``{"format", "document", "sources"}`` beside an empty graph; ``sources`` names each case's call by its slug
(``case#undock-and-lap``).
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

EVAL_FIELDS = ["domain", "slug", "version", "description", "metrics", "scoring", "objective", "axes", "repeats", "published",
               "frozen", "official", "rung", "provenance"]
EVAL_CASE_FIELDS = ["slug", "name", "task", "instruction", "acceptance", "acceptanceMetric", "hints", "maxSteps", "timeLimitMs",
                    "environment", "config", "seed", "weight", "tags"]
METRIC_FIELDS = ["slug", "description", "probe", "aggregation", "role", "direction", "unit", "target", "pass", "threadId"]
#: The form of a frozen eval's digest.
EVAL_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "eval": {"holds": "children"},
    "case": {},
    "metric": {},
}

__all__ = ["EVAL_FIELDS", "EVAL_CASE_FIELDS", "METRIC_FIELDS", "EVAL_DIGEST", "SIGNATURES", "eval_case_of", "EVAL_VOCABULARY",
           "METRIC_VOCABULARY", "EVALS", *define(globals(), "evals", SIGNATURES)]


def _said(attrs: Dict[str, Any], k: str) -> str:
    """JavaScript's ``JSON.stringify`` of a field as a message says it (an absent one is ``undefined``)."""
    return _json(attrs[k]) if k in attrs else "undefined"


def _where(t: DocTree) -> str:
    slug = t["attrs"].get("slug")
    return f'<{t["tag"]} slug="{slug}">' if isinstance(slug, str) else f"<{t['tag']}>"


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _whole(v: Any) -> bool:
    return _number(v) and float(v).is_integer()


def _text(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not (isinstance(a[k], str) and a[k].strip()):
        raise ValueError(f"{_where(t)} {k} is text, not {_said(a, k)}")


def _object(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not isinstance(a[k], dict):
        raise ValueError(f"{_where(t)} {k} is an object, not {_said(a, k)}")


def _texts(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not (isinstance(a[k], list) and all(isinstance(s, str) and s.strip() for s in a[k])):
        raise ValueError(f"{_where(t)} {k} is a list of texts")


def _numeric(t: DocTree, k: str, integer: bool = False) -> None:
    a = t["attrs"]
    if k in a and not (_whole(a[k]) if integer else _number(a[k])):
        raise ValueError(f"{_where(t)} {k} is a {'whole ' if integer else ''}number, not {_said(a, k)}")


def _flag(t: DocTree, k: str) -> None:
    a = t["attrs"]
    if k in a and not isinstance(a[k], bool):
        raise ValueError(f"{_where(t)} {k} is true or false")


def _fields(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if k in attrs}


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent, None, "", [] or {}): code does not write it."""
    return v is None or v == "" or (isinstance(v, (list, dict)) and not v)


def _attrs_of(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: d[k] for k in keys if not _nothing(d.get(k))}


def eval_case_of(t: DocTree) -> Dict[str, Any]:
    """One case as its element declares it; raises with why it does not read (the TypeScript SDK's ``evalCaseOf``)."""
    a = t["attrs"]
    for k in ("slug", "name", "task", "instruction", "acceptanceMetric"):
        _text(t, k)
    for k in ("acceptance", "environment", "config"):
        _object(t, k)
    if not isinstance(a.get("environment"), dict) or not isinstance(a["environment"].get("kind"), str):
        raise ValueError(f'{_where(t)} environment is a world ({{ kind: "synthetic", seed: 41 }}), not {_said(a, "environment")}')
    if ("task" in a) == ("instruction" in a):
        raise ValueError(f"{_where(t)} says what the agent is handed once: a task file (task) or an instruction, not "
                         f"{'neither' if 'task' not in a else 'both'}")
    _texts(t, "hints")
    _texts(t, "tags")
    _numeric(t, "maxSteps", True)
    _numeric(t, "timeLimitMs", True)
    _numeric(t, "seed", True)
    _numeric(t, "weight")
    return _fields(a, EVAL_CASE_FIELDS)


def _metric_named(t: DocTree, at: str, v: Any) -> None:
    """A metric named in ``objective``: a ref (``metric``), never a node id (``metricId``)."""
    if not isinstance(v, dict):
        raise ValueError(f"{_where(t)} {at} is an object, not {_json(v)}")
    if "metricId" in v:
        raise ValueError(f"{_where(t)} {at} names its metric file by ref (metric), not by node id (metricId)")
    if not (isinstance(v.get("metric"), str) and v["metric"].strip()):
        raise ValueError(f"{_where(t)} {at}.metric is a metric file's ref, not {_said(v, 'metric')}")


def _objective(t: DocTree) -> None:
    o = t["attrs"].get("objective")
    if o is None:
        return
    if not isinstance(o, dict) or not isinstance(o.get("kind"), str):
        raise ValueError(f'{_where(t)} objective is {{ kind: "metric" | "linear" | "function", … }}, not {_json(o)}')
    if o["kind"] == "metric":
        _metric_named(t, "objective", o)
    if o["kind"] == "linear":
        terms = o.get("terms")
        if not isinstance(terms, list) or not terms:
            raise ValueError(f"{_where(t)} objective.terms is a list of {{ metric, weight }}")
        for i, term in enumerate(terms):
            _metric_named(t, f"objective.terms[{i}]", term)
            if "weight" in term and not _number(term["weight"]):
                raise ValueError(f"{_where(t)} objective.terms[{i}].weight is a number, not {_json(term['weight'])}")


def _weights(t: DocTree) -> None:
    s = t["attrs"].get("scoring")
    if not isinstance(s, dict) or "weights" not in s:
        return
    w = s["weights"]
    if not isinstance(w, dict) or not all(_number(v) for v in w.values()):
        raise ValueError(f'{_where(t)} scoring.weights is {{ "<metric file ref>": <number> }}, not {_json(w)}')


def _eval(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("slug", "domain", "version", "description", "rung"):
        _text(t, k)
    for k in ("scoring", "objective", "provenance"):
        _object(t, k)
    _objective(t)
    _weights(t)
    _texts(t, "metrics")
    _texts(t, "axes")
    _numeric(t, "repeats", True)
    for k in ("published", "official"):
        _flag(t, k)
    if "frozen" in a and not (isinstance(a["frozen"], str) and EVAL_DIGEST.match(a["frozen"])):
        raise ValueError(f"{_where(t)} frozen is the digest the eval is frozen at (sha256:<hex>), not {_said(a, 'frozen')}")
    cases = [eval_case_of(c) for c in t["children"] if c["tag"] == "case"]
    return {**_fields(a, EVAL_FIELDS), "cases": cases}


def _metric(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("slug", "description", "aggregation", "role", "direction", "unit", "threadId"):
        _text(t, k)
    for k in ("probe", "pass"):
        _object(t, k)
    if not isinstance(a.get("probe"), dict) or not isinstance(a["probe"].get("kind"), str):
        raise ValueError(f'{_where(t)} probe is what to measure ({{ kind: "event", eventKind: "telemetry" }}), not {_said(a, "probe")}')
    _numeric(t, "target")
    return _fields(a, METRIC_FIELDS)


def _slug_of(name: str) -> str:
    """A slug from a file's name ("Yard shakedown" -> "yard-shakedown")."""
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", name.lower())) or "eval"


EVAL_VOCABULARY = Vocabulary("eval", "an eval", "eval", {
    "eval": {"parents": [], "required": ["slug"], "attrs": EVAL_FIELDS},
    "case": {"parents": ["eval"], "key": "slug", "required": ["slug", "name", "environment"], "attrs": EVAL_CASE_FIELDS},
}, _eval, lambda d: {"tag": "eval", "attrs": _attrs_of(d, EVAL_FIELDS), "children": [
    {"tag": "case", "attrs": _attrs_of(c, EVAL_CASE_FIELDS), "children": []} for c in d.get("cases") or []]},
    lambda stem: {"slug": _slug_of(stem), "cases": []})

METRIC_VOCABULARY = Vocabulary("metric", "a metric", "metric", {
    "metric": {"parents": [], "required": ["slug", "probe", "aggregation"], "attrs": METRIC_FIELDS},
}, _metric, lambda d: {"tag": "metric", "attrs": _attrs_of(d, METRIC_FIELDS), "children": []})

for _v in (EVAL_VOCABULARY, METRIC_VOCABULARY):
    register_vocabulary(_v, "evals")

#: The vocabularies of an eval and a metric, by format.
EVALS = {"eval": EVAL_VOCABULARY, "metric": METRIC_VOCABULARY}
