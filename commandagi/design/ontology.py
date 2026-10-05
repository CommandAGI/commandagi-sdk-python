"""The ontology's own files, declared in Python: worlds, device definitions, dashboards, geo projects and node graphs.

The same documents as the TypeScript SDK's JSX (``commandagi/design`` ``ontology.ts``), with calls in place of tags.
Each call is one record; its keyword arguments are the record's fields, verbatim; its positional arguments are its
children::

    result = world("Bench", "simulation",
        space(origin_mm=[-1000, -600, 0], size_mm=[2000, 1200, 2000]),
        unit(uid="arm", name="arm", device="../../devices/so-101/definition.json", position=[0, 0, 750], rotation=0))

A field whose name is a Python keyword takes a trailing underscore (``from_=...``). A run gives back what the
TypeScript SDK gives: for a world, a definition, a dashboard and a geo project, the document's JSON in the run's one
shape (``{"format", "document", "sources"}`` beside an empty graph); for a node graph, the editor's own op graph. Structure only: a code form declares, and the application that reads it checks and enforces it.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Sequence

from .ir import Declaration

NODE_GRAPH_ID = "nodegraph"
UNIT_FIELDS = ["uid", "name", "device", "domain", "size_mm", "support", "channels", "manualUrl", "position", "rotation"]
WORLD_FIELDS = ["name", "kind", "description", "from", "model"]
GEO_FIELDS = ["id", "name", "createdAt", "updatedAt", "description", "defaultWorkspace", "metadata"]
_NODE_ATTRS = ["id", "type", "label", "x", "y", "disabled", "output", "meta", "inputs"]


class Element:
    """One record of a document: its tag, its fields and its children."""

    def __init__(self, tag: str, attrs: Dict[str, Any], children: Sequence["Element"] = ()):
        self.tag = tag
        # None is a field left out (Python has one word for JSON's null and for "not given").
        self.attrs = {k: _plain(v, f"<{tag}> {k}") for k, v in attrs.items() if v is not None}
        for c in children:
            if not isinstance(c, Element):
                raise ValueError(f"<{tag}>: a child is a record (an element), not {type(c).__name__}")
        self.children = list(children)


def _plain(v: Any, where: str) -> Any:
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"{where} is {v}, not a finite number")
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{where}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {str(k): _plain(x, f"{where}.{k}") for k, x in v.items()}
    raise ValueError(f"{where} is plain data (numbers, strings, booleans, lists and dicts of them)")


def _fields(kw: Dict[str, Any]) -> Dict[str, Any]:
    return {(k[:-1] if k.endswith("_") and not k.startswith("_") else k): v for k, v in kw.items()}


def element(tag: str, *children: Element, **attrs: Any) -> Element:
    """Any record: ``element("unit", uid="arm", ...)`` (the named calls below are this with their tag)."""
    return Element(tag, _fields(attrs), children)


# ── the vocabularies: where each tag stands, how its records are told apart ─────────────────────────────────────

_RULES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "world": {
        "world": {"parents": [], "required": ["name", "kind"], "attrs": WORLD_FIELDS},
        "space": {"parents": ["world"], "single": True, "required": ["origin_mm", "size_mm"], "attrs": ["origin_mm", "size_mm"]},
        "unit": {"parents": ["world"], "key": "uid", "required": ["uid", "name", "device"], "attrs": UNIT_FIELDS},
        "view": {"parents": ["world"], "single": True},
        "scene": {"parents": ["world"], "single": True},
        "body": {"parents": ["scene"], "key": "id", "required": ["id"]},
    },
    "device": {
        "device": {"parents": [], "required": ["name"]},
        "channel": {"parents": ["device"], "key": "id", "required": ["id"]},
    },
    "dashboard": {
        "dashboard": {"parents": [], "required": ["name"]},
        "param": {"parents": ["dashboard"], "key": "id", "required": ["id", "type"]},
        "split": {"parents": ["dashboard", "split"], "required": ["axis", "ratio"], "attrs": ["axis", "ratio"]},
        "pane": {"parents": ["dashboard", "split"], "key": "id", "required": ["id"]},
        "region": {"parents": ["dashboard"], "key": "side", "required": ["side"]},
    },
    "geo": {
        "geoproject": {"parents": [], "required": ["id", "name"], "attrs": GEO_FIELDS},
        "dateRange": {"parents": ["geoproject"], "single": True, "required": ["start", "end"]},
        "camera": {"parents": ["geoproject"], "single": True},
        "reference": {"parents": ["geoproject"], "key": "path", "required": ["role", "path"], "attrs": ["role", "path", "hash"]},
    },
    "opgraph": {
        "opgraph": {"parents": [], "attrs": ["id", "name", "domain", "meta"]},
        "node": {"parents": ["opgraph"], "key": "id", "required": ["id", "type"]},
        "wire": {"parents": ["opgraph"], "key": "to", "required": ["from", "to"], "attrs": ["from", "to"]},
    },
}
_ROOTS = {"world": "world", "device": "device", "dashboard": "dashboard", "geoproject": "geo", "opgraph": "opgraph"}
_NOUNS = {"world": "a world", "device": "a device definition", "dashboard": "a dashboard", "geo": "a geo project", "opgraph": "a node graph"}


def _check(root: Element, fmt: str) -> None:
    rules = _RULES[fmt]

    def visit(el: Element, parent: Optional[str]) -> None:
        rule = rules.get(el.tag)
        if rule is None:
            raise ValueError(f"<{el.tag}> is not a tag of {_NOUNS[fmt]} ({', '.join('<' + t + '>' for t in rules)})")
        if (parent is None and rule["parents"]) or (parent is not None and parent not in rule["parents"]):
            raise ValueError(f"<{el.tag}> stands in {' or '.join('<' + p + '>' for p in rule['parents'])}, not in <{parent}>" if parent else f"{_NOUNS[fmt]} in code is one <{fmt if fmt != 'geo' else 'geoproject'}> element")
        key = rule.get("key")
        name = f'<{el.tag} {key}="{el.attrs[key]}">' if key and isinstance(el.attrs.get(key), str) else f"<{el.tag}>"
        allowed = rule.get("attrs")
        for k in el.attrs:
            if allowed is not None and k not in allowed:
                raise ValueError(f"{name}: {k} is not read ({', '.join(allowed)})")
        for k in rule.get("required", []):
            if el.attrs.get(k) is None:
                raise ValueError(f"{name} needs {k}")
        seen = set()
        for c in el.children:
            r = rules.get(c.tag, {})
            ident = f"{c.tag}#{c.attrs.get(r['key'])}" if r.get("key") else (c.tag if r.get("single") else None)
            if ident is None:
                continue
            if ident in seen:
                raise ValueError(f'two <{c.tag}> in <{el.tag}> have {r["key"]} "{c.attrs.get(r["key"])}"' if r.get("key") else f"<{el.tag}> has one <{c.tag}>")
            seen.add(ident)
        for c in el.children:
            visit(c, el.tag)

    visit(root, None)


def _own(o: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    return {k: copy.deepcopy(o[k]) for k in keys if o.get(k) is not None}


def _omit(o: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in o.items() if k not in keys and v is not None}


def _kids(el: Element, tag: str) -> List[Element]:
    return [c for c in el.children if c.tag == tag]


def _first(el: Element, tag: str) -> Optional[Element]:
    kids = _kids(el, tag)
    return kids[0] if kids else None


def _world(t: Element) -> Dict[str, Any]:
    out: Dict[str, Any] = _own(t.attrs, WORLD_FIELDS)
    space_, view_, scene_ = _first(t, "space"), _first(t, "view"), _first(t, "scene")
    if space_ is not None:
        out["space"] = copy.deepcopy(space_.attrs)
    out["units"] = [copy.deepcopy(u.attrs) for u in _kids(t, "unit")]
    if view_ is not None:
        out["view"] = copy.deepcopy(view_.attrs)
    if scene_ is not None:
        bodies = [copy.deepcopy(b.attrs) for b in _kids(scene_, "body")]
        out["scene"] = {**copy.deepcopy(scene_.attrs), **({"bodies": bodies} if bodies else {})}
    return out


def _device(t: Element) -> Dict[str, Any]:
    if "channels" in t.attrs:
        raise ValueError("<device>: write each channel as a <channel> element, not a channels attribute")
    channels = [copy.deepcopy(c.attrs) for c in _kids(t, "channel")]
    return {**copy.deepcopy(t.attrs), **({"channels": channels} if channels else {})}


def _dashboard(t: Element) -> Dict[str, Any]:
    for k in ("format", "layout", "panes", "params", "regions"):
        if k in t.attrs:
            raise ValueError(f"<dashboard>: {k} is written as elements (<param>, <split>, <pane>, <region>), not an attribute")
    panes: Dict[str, Any] = {}

    def layout(n: Element) -> Dict[str, Any]:
        if n.tag == "pane":
            pid = str(n.attrs["id"])
            if pid in panes:
                raise ValueError(f'two <pane> have id "{pid}"')
            panes[pid] = _omit(n.attrs, ["id"])
            return {"kind": "leaf", "paneId": pid}
        sides = [c for c in n.children if c.tag in ("split", "pane")]
        return {"kind": "split", "axis": n.attrs["axis"], "ratio": n.attrs["ratio"], "children": [layout(c) for c in sides]}

    root = layout([c for c in t.children if c.tag in ("split", "pane")][0])
    params = [copy.deepcopy(p.attrs) for p in _kids(t, "param")]
    regions = {str(r.attrs["side"]): _omit(r.attrs, ["side"]) for r in _kids(t, "region")}
    return {"format": "commandagi-dashboard", **copy.deepcopy(t.attrs), **({"params": params} if params else {}), "layout": root,
            "panes": panes, **({"regions": regions} if regions else {})}


def _geo(t: Element) -> Dict[str, Any]:
    top = _own(t.attrs, GEO_FIELDS)
    description, workspace = top.pop("description", None), top.pop("defaultWorkspace", None)
    range_, camera_ = _first(t, "dateRange"), _first(t, "camera")
    refs = [copy.deepcopy(r.attrs) for r in _kids(t, "reference")]
    data: Dict[str, Any] = {}
    if workspace is not None:
        data["defaultWorkspace"] = workspace
    if range_ is not None:
        data["defaultDateRange"] = copy.deepcopy(range_.attrs)
    if camera_ is not None:
        data["defaultCamera"] = copy.deepcopy(camera_.attrs)
    if description is not None:
        data["description"] = description
    # The geo project's manifest says which shape it is in; this is the one the studio reads.
    return {"type": "geoeconomics/project", "schemaVersion": "1.0", **top, **({"references": refs} if refs else {}), "data": data}


_FROM_TREE = {"world": _world, "device": _device, "dashboard": _dashboard, "geo": _geo}


def _end(text: Any, what: str) -> Dict[str, str]:
    if not isinstance(text, str) or ":" not in text or text.startswith(":") or text.endswith(":"):
        raise ValueError(f'<wire> {what} is "node:port", not {text!r}')
    node, port = text.split(":", 1)
    return {"node": node, "port": port}


def _opgraph(root: Element) -> Dict[str, Any]:
    """A node graph: the editor's own op graph (as the TypeScript SDK's ``opgraphVocabulary.fromTree``)."""
    nodes: Dict[str, Any] = {}
    outputs: List[str] = []
    for el in (c for c in root.children if c.tag == "node"):
        a = el.attrs
        nid = str(a["id"])
        if ":" in nid:
            raise ValueError(f'<node id="{nid}">: an id has no colon (a wire names "node:port")')
        inputs = {k: v for k, v in a.items() if k not in _NODE_ATTRS}
        for k, v in (a.get("inputs") or {}).items():
            inputs[k] = v
        meta = dict(a.get("meta") or {})
        for k in ("x", "y"):
            if a.get(k) is not None:
                meta[k] = a[k]
        node: Dict[str, Any] = {"id": nid, "type": a["type"], "inputs": inputs}
        if isinstance(a.get("label"), str):
            node["label"] = a["label"]
        if a.get("disabled") is True:
            node["disabled"] = True
        if meta:
            node["meta"] = meta
        nodes[nid] = node
        if a.get("output") is True:
            outputs.append(nid)
    for el in (c for c in root.children if c.tag == "wire"):
        src, dst = _end(el.attrs.get("from"), "from"), _end(el.attrs.get("to"), "to")
        if dst["node"] not in nodes:
            raise ValueError(f'<wire to="{el.attrs["to"]}">: no <node id="{dst["node"]}">')
        if src["node"] not in nodes:
            raise ValueError(f'<wire from="{el.attrs["from"]}">: no <node id="{src["node"]}">')
        target = nodes[dst["node"]]["inputs"]
        literal = target.get(dst["port"])
        if isinstance(literal, dict) and "wire" in literal:
            raise ValueError(f"two <wire> go into {dst['node']}:{dst['port']} (a port takes one wire)")
        target[dst["port"]] = {"wire": src, **({"value": literal} if literal is not None else {})}
    meta = dict(root.attrs.get("meta") or {})
    if root.attrs.get("name") is not None:
        meta["name"] = root.attrs["name"]
    meta["domain"] = root.attrs.get("domain", NODE_GRAPH_ID)
    return {"id": root.attrs.get("id", NODE_GRAPH_ID), "nodes": nodes, "outputs": outputs, "meta": meta}


def is_document(value: Any) -> bool:
    """Whether a value is the root record of a world, a definition, a dashboard or a geo project (a node graph is a graph)."""
    return isinstance(value, Element) and value.tag in _ROOTS and value.tag != "opgraph"


def is_opgraph(value: Any) -> bool:
    return isinstance(value, Element) and value.tag == "opgraph"


def _checked(root: Element) -> str:
    fmt = _ROOTS.get(root.tag)
    if fmt is None:
        raise ValueError(f"<{root.tag}> is not a document (<world>, <device>, <dashboard>, <geoproject>, <opgraph>)")
    _check(root, fmt)
    if fmt == "world" and root.attrs.get("kind") not in ("physical", "simulation"):
        raise ValueError(f'<world> kind is "physical" or "simulation", said explicitly, not {root.attrs.get("kind")!r}')
    if fmt == "dashboard":
        layouts = [c for c in root.children if c.tag in ("split", "pane")]
        if len(layouts) != 1:
            raise ValueError(f"<dashboard> has one layout: a <split> or one <pane> (it has {len(layouts)})")
        for s in _walk(root):
            if s.tag == "split" and len([c for c in s.children if c.tag in ("split", "pane")]) != 2:
                raise ValueError("a <split> has two sides")
    return fmt


def declare_document(root: Element) -> Dict[str, Any]:
    """The document a root record declares, in the run's one shape: ``{"format", "document", "sources"}``. A Python
    file names no element sources yet (no editor writes into a ``world.py``), so ``sources`` is empty."""
    fmt = _checked(root)
    if fmt == "opgraph":
        raise ValueError("a node graph is a graph: declare it with declare_opgraph")
    return {"format": fmt, "document": _FROM_TREE[fmt](root), "sources": {}}


def declare_opgraph(root: Element) -> Declaration:
    """A node graph: the editor's own op graph."""
    _checked(root)
    return Declaration("graph", _opgraph(root))


def _walk(el: Element):
    yield el
    for c in el.children:
        yield from _walk(c)


# ── the named records ──────────────────────────────────────────────────────────────────────────────────────────


def world(name: str, kind: str, *children: Element, **fields: Any) -> Element:
    """A world (``worlds/<name>/world.json``): ``kind`` is "physical" or "simulation", said explicitly."""
    return Element("world", {"name": name, "kind": kind, **_fields(fields)}, children)


def space(**fields: Any) -> Element:
    return Element("space", _fields(fields))


def unit(**fields: Any) -> Element:
    """A unit placed in a world: uid, name, device (a ref to its definition), position (mm), rotation (rad)."""
    return Element("unit", _fields(fields))


def view(**fields: Any) -> Element:
    return Element("view", _fields(fields))


def scene(*bodies: Element, **fields: Any) -> Element:
    return Element("scene", _fields(fields), bodies)


def body(**fields: Any) -> Element:
    return Element("body", _fields(fields))


def device(name: str, *channels: Element, **fields: Any) -> Element:
    """A device definition (``devices/<name>/definition.json``): its channels, with the bounds its driver enforces."""
    return Element("device", {"name": name, **_fields(fields)}, channels)


def channel(**fields: Any) -> Element:
    return Element("channel", _fields(fields))


def dashboard(name: str, *children: Element, **fields: Any) -> Element:
    """A dashboard (``<name>.dashboard.json``): its params, one layout (a split or a pane), its regions."""
    return Element("dashboard", {"name": name, **_fields(fields)}, children)


def dashboard_param(**fields: Any) -> Element:
    """A dashboard's parameter (``<param>`` in JSX; ``param`` in a script reads the script's own input)."""
    return Element("param", _fields(fields))


def split(axis: str, ratio: float, first: Element, second: Element) -> Element:
    return Element("split", {"axis": axis, "ratio": ratio}, [first, second])


def pane(**fields: Any) -> Element:
    return Element("pane", _fields(fields))


def region(**fields: Any) -> Element:
    return Element("region", _fields(fields))


def geoproject(id: str, name: str, *children: Element, **fields: Any) -> Element:
    """A geo project's manifest (``<name>.geox``): its date range, camera and references."""
    return Element("geoproject", {"id": id, "name": name, **_fields(fields)}, children)


def date_range(start: str, end: str) -> Element:
    return Element("dateRange", {"start": start, "end": end})


def camera(**fields: Any) -> Element:
    return Element("camera", _fields(fields))


def reference(**fields: Any) -> Element:
    return Element("reference", _fields(fields))


def opgraph(*children: Element, **fields: Any) -> Element:
    """A node graph (``<name>.opgraph``): ``graph_node`` records and ``wire`` records between their ports."""
    return Element("opgraph", _fields(fields), children)


def graph_node(id: str, type: str, **fields: Any) -> Element:
    """A node of a node graph: id, type, x, y, output, and its ports' values (``<node>`` in JSX)."""
    return Element("node", {"id": id, "type": type, **_fields(fields)})


def wire(from_: str, to: str) -> Element:
    """A wire from ``"node:port"`` to ``"node:port"``."""
    return Element("wire", {"from": from_, "to": to})
