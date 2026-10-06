"""DOCUMENTS AS ELEMENTS — a JSON document of CommandAGI (a world, a device definition, a dashboard, a geo project, a
task, a machining setup …) written as a tree of elements. The Python port of the TypeScript SDK's ``documents.ts``.

Each element is one record of the document, and its attributes are that record's fields, verbatim
(``unit(uid="arm", position=[0, 0, 0])`` is the unit ``{"uid": "arm", "position": [0, 0, 0]}``). A vocabulary says which
tags a document has, where each may stand, which attribute names a record among its siblings, and how the tree maps
to the document's JSON, both ways.

What a run gives back is the run's one shape for a document that is not a graph: ``{format, document, sources}``,
the document's JSON and each element's call (``source``) keyed by its path (``tree_paths``: ``""`` the root,
``unit#arm``, ``scene/body#cube``). An editor makes the tree again from the document and finds each element's place by
the same path.

A tree (``DocTree``) is a dict: ``{"tag", "attrs", "children", "source"?}``. A tag rule is a dict: ``parents`` (the tags
it may be a child of; none: the root), ``key`` (the attribute that names it among its siblings), ``single`` (at most
one per parent), ``required``, ``attrs`` (the attributes it may have; absent: any).
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Dict, List, Optional

from .element import Element, child_elements, declares

__all__ = ["Vocabulary", "register_vocabulary", "vocabulary_of", "tree_of_element", "identities", "tree_paths", "declare_document"]

DocTree = Dict[str, Any]


class Vocabulary:
    """A document format written as elements: its tags, and its JSON both ways."""

    def __init__(self, format: str, noun: str, root: str, tags: Dict[str, Dict[str, Any]],
                 from_tree: Callable[[DocTree], Any], to_tree: Callable[[Any], DocTree],
                 empty: Optional[Callable[[str], Any]] = None):
        self.format = format
        self.noun = noun
        self.root = root
        self.tags = tags
        self.from_tree = from_tree
        self.to_tree = to_tree
        self.empty = empty


_vocabularies: Dict[str, Vocabulary] = {}


def register_vocabulary(v: Vocabulary, module: str) -> None:
    """Make a vocabulary's root tag (of ``module``'s elements) a document a code file may declare."""
    _vocabularies[v.root] = v
    _vocabularies[f"format:{v.format}"] = v
    declares(module, v.root, lambda root, stem: {"document": declare_document(root, v)})


def vocabulary_of(root_or_format: str) -> Optional[Vocabulary]:
    """The vocabulary of a root tag, or of a format (``format:world``), if one is registered."""
    return _vocabularies.get(root_or_format)


def _where(el: Element, key: Optional[str] = None) -> str:
    v = el.props.get(key) if key else None
    return f'<{el.tag} {key}="{v}">' if isinstance(v, str) else f"<{el.tag}>"


def _plain(v: Any, what: str) -> Any:
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"{what} is {v}, not a finite number")
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{what}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict) and all(isinstance(k, str) for k in v):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items()}
    raise ValueError(f"{what} is plain data (numbers, strings, booleans, lists and objects of them)")


def tree_of_element(root: Element, v: Vocabulary) -> DocTree:
    """The tree an element declares, checked against the vocabulary's tags (the root's rule has no parents)."""

    def visit(el: Element, parent: Optional[str]) -> DocTree:
        rule = v.tags.get(el.tag)
        if rule is None:
            raise ValueError(f"<{el.tag}> is not a tag of {v.noun} ({', '.join(f'<{t}>' for t in v.tags)})")
        parents = rule.get("parents") or []
        if (len(parents) > 0) if parent is None else parent not in parents:
            raise ValueError(f"{v.noun} in code is one <{v.root}> element, not <{el.tag}>" if parent is None
                             else f"<{el.tag}> stands in {' or '.join(f'<{p}>' for p in parents)}, not in <{parent}>")
        key = rule.get("key")
        attrs: Dict[str, Any] = {}
        for k, value in el.props.items():
            if k == "key" or value is None:
                continue
            allowed = rule.get("attrs")
            if allowed is not None and k not in allowed:
                raise ValueError(f"{_where(el, key)}: {k} is not read ({', '.join(allowed)})")
            attrs[k] = _plain(value, f"{_where(el, key)} {k}")
        for k in rule.get("required") or []:
            if attrs.get(k) is None:
                raise ValueError(f"{_where(el, key)} needs {k}")
        for c in el.children:
            if isinstance(c, str) and c.strip():
                raise ValueError(f'{_where(el, key)}: text is not read ("{c.strip()[:40]}")')
        children = [visit(c, el.tag) for c in child_elements(el)]
        seen = set()
        for c in children:
            r = v.tags[c["tag"]]
            ident = f"{c['tag']}#{_text(c['attrs'].get(r['key']))}" if r.get("key") else c["tag"] if r.get("single") else None
            if ident is None:
                continue
            if ident in seen:
                raise ValueError(f'two <{c["tag"]}> in <{el.tag}> have {r["key"]} "{_text(c["attrs"].get(r["key"]))}"' if r.get("key")
                                 else f"<{el.tag}> has one <{c['tag']}>")
            seen.add(ident)
        tree: DocTree = {"tag": el.tag, "attrs": attrs, "children": children}
        if el.source is not None:
            tree["source"] = el.source
        return tree

    return visit(root, None)


def _text(v: Any) -> str:
    """JavaScript's ``String(v)`` for a key's value."""
    if v is None:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (list, dict)):
        return ",".join(_text(x) for x in v) if isinstance(v, list) else "[object Object]"
    return str(v)


def _json(v: Any) -> str:
    """JavaScript's ``JSON.stringify(v)`` (no spaces)."""
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def identities(children: List[DocTree], v: Vocabulary) -> List[str]:
    """A record's identity among its siblings: ``unit#arm`` by its key, ``space`` when single, else ``split@1`` by position."""
    nth: Dict[str, int] = {}
    out = []
    for c in children:
        r = v.tags.get(c["tag"]) or {}
        key = r.get("key")
        if key and c["attrs"].get(key) is not None:
            k = c["attrs"][key]
            out.append(f"{c['tag']}#{k if isinstance(k, str) else _json(k)}")
            continue
        i = nth.get(c["tag"], 0)
        nth[c["tag"]] = i + 1
        out.append(c["tag"] if r.get("single") else f"{c['tag']}@{i}")
    return out


def tree_paths(tree: DocTree, v: Vocabulary, visit: Callable[[DocTree, str], None]) -> None:
    """Visit each element of a tree with its path: the identities from the root down, joined by ``/`` (``""`` is the
    root, ``scene/body#cube`` a scene's body). A declared document's ``sources`` name each element by it."""

    def walk(t: DocTree, path: str) -> None:
        visit(t, path)
        ids = identities(t["children"], v)
        for c, i in zip(t["children"], ids):
            walk(c, f"{path}/{i}" if path else i)

    walk(tree, "")


def declare_document(root: Element, v: Optional[Vocabulary] = None) -> Dict[str, Any]:
    """Declare a document from its root element: ``{format, document, sources}``."""
    v = v or vocabulary_of(root.tag)
    if v is None:
        raise ValueError(f"<{root.tag}> is not a document")
    tree = tree_of_element(root, v)
    # Its shape is checked when it is declared, not when an editor opens it.
    document = v.from_tree(tree)
    sources: Dict[str, Any] = {}

    def keep(t: DocTree, path: str) -> None:
        if t.get("source") is not None:
            sources[path] = t["source"]

    tree_paths(tree, v, keep)
    return {"format": v.format, "document": document, "sources": sources}
