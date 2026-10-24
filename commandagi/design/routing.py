"""Routing knowledge documents: priors, hard rules, prices and measured observations."""
from __future__ import annotations
from typing import Any, Dict, List
from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

ROUTING_FIELDS = ["id", "region", "text", "config", "harness", "model", "quality", "importance", "cost", "currency", "channel", "billing", "weight", "count", "date", "source", "evidence", "reported", "checked", "task", "uncensored", "sensitive", "deny", "reason", "inputPerMillion", "outputPerMillion", "tokensPerTask", "budget", "tasksPerUsd", "linesPerUsd", "done", "blocked", "linesMerged", "spend"]
SIGNATURES: Dict[str, Dict[str, Any]] = {"routing": {"holds": "children"}, "prior": {}, "rule": {}, "price": {}, "observation": {}}
__all__ = ["ROUTING_FIELDS", "SIGNATURES", "ROUTING_VOCABULARY", *define(globals(), "routing", SIGNATURES)]
_GROUPS = {"prior": "priors", "rule": "rules", "price": "prices", "observation": "observations"}

def _from_tree(t: DocTree) -> Dict[str, Any]:
    out: Dict[str, Any] = {v: [] for v in _GROUPS.values()}
    seen = set()
    for child in t["children"]:
        tag, attrs = child["tag"], child["attrs"]
        if tag not in _GROUPS:
            raise ValueError(f"<{tag}> is not routing knowledge")
        if not isinstance(attrs.get("id"), str) or not attrs["id"].strip():
            raise ValueError(f"<{tag}> id is required")
        key = (tag, attrs["id"])
        if key in seen:
            raise ValueError(f"duplicate <{tag}> id {attrs['id']!r}")
        seen.add(key)
        out[_GROUPS[tag]].append(dict(attrs))
    return out

def _to_tree(d: Dict[str, Any]) -> DocTree:
    children = []
    for tag, group in _GROUPS.items():
        for row in d.get(group, []):
            children.append({"tag": tag, "attrs": dict(row), "children": []})
    return {"tag": "routing", "attrs": {}, "children": children}

ROUTING_VOCABULARY = Vocabulary("routing", "routing knowledge", "routing", {
    "routing": {"parents": [], "attrs": []},
    **{tag: {"parents": ["routing"], "key": "id", "required": ["id"], "attrs": ROUTING_FIELDS} for tag in _GROUPS},
}, _from_tree, _to_tree, lambda _stem: {v: [] for v in _GROUPS.values()})
register_vocabulary(ROUTING_VOCABULARY, "routing")
