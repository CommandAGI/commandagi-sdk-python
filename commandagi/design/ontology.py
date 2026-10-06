"""THE ONTOLOGY'S OWN FILES IN PYTHON — worlds, device definitions, dashboards, geo projects and node graphs, written
as the elements their editors edit. The same elements as the TypeScript SDK's ``ontology.ts``, one call per tag::

    # worlds/shop/world.py
    from commandagi.design.ontology import unit, world

    result = world(
        unit(uid="arm", name="arm", device="../../devices/so-101/definition.tsx", position=[0, 0, 0], rotation=0),
        name="Shop", kind="physical",
    )

A record is an element and its fields are the element's attributes; a list of records is the parent's children
(``units`` -> ``unit(...)``, ``channels`` -> ``channel(...)``, a scene's ``bodies`` -> ``body(...)``). The tags:

    world(name, kind, description?, from_?, model?)   world.py             space, unit(uid …), view, scene (body children)
    device(name …)                                    definition.py        channel(id, dir, medium, format, transport …)
    dashboard(name …)                                 <name>.dashboard.py  param(id, type …), one layout: split(axis,
                                                                           ratio) of two split|pane(id, kind …), or one
                                                                           pane; region(side, tab …)
    geoproject(id, name …)                            <name>.geo.py        dateRange(start, end), camera, reference
    opgraph(name)                                     <name>.opgraph.py    node(id, type, x, y, …ports), wire(from_, to)

Every attribute is a keyword (``commandagi.design.element``: snake_case of the field's name). A field whose own name
has an underscore (a world's ``origin_mm``, ``size_mm``) has no keyword spelling: the keyword ``size_mm`` names the
field ``sizeMm``. A node graph is the editor's op graph itself: ``node(id="blur", type="blur", x=300, y=80, radius=6)``
is the node ``{id: "blur", type: "blur", inputs: {radius: 6}, meta: {x: 300, y: 80}}``, and
``wire(from_="gradient:out", to="blur:in")`` the wire into its ``in`` port. ``output=True`` marks a terminal. A port
whose name is not an attribute name (``layers.3``) is written in ``inputs={"layers.3": None}``.

A run gives back what the TypeScript SDK gives: for a world, a definition, a dashboard and a geo project, the document
in the run's one shape (``{"format", "document", "sources"}``, each element's call keyed by its tree path) beside an
empty graph; for a node graph, the editor's own op graph, each node with ``meta.source`` and each wire's call in its
target's ``meta.sources["wire:<port>"]``. A code form declares; it never enforces.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Sequence

from .documents import DocTree, Vocabulary, register_vocabulary, tree_of_element
from .element import declares, define

_HOLDS: Dict[str, Any] = {"holds": "children"}
#: Every tag of the ontology's files: what it holds (the TypeScript SDK's ``SIGNATURES``; absent: a leaf).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "world": _HOLDS, "space": {"snake": ["origin_mm", "size_mm"]}, "unit": {"snake": ["size_mm"]}, "view": {}, "scene": _HOLDS, "body": {},
    "device": _HOLDS, "channel": {},
    "dashboard": _HOLDS, "param": {}, "split": _HOLDS, "pane": {}, "region": {},
    "geoproject": _HOLDS, "dateRange": {}, "camera": {}, "reference": {},
    "opgraph": _HOLDS, "node": {}, "wire": {},
}

NODE_GRAPH_ID = "nodegraph"
#: The fields of a unit in a world's file (packages/domain/world/worlds.js).
UNIT_FIELDS = ["uid", "name", "device", "domain", "size_mm", "support", "channels", "manualUrl", "position", "rotation"]
WORLD_FIELDS = ["name", "kind", "description", "from", "model"]
GEO_FIELDS = ["id", "name", "createdAt", "updatedAt", "description", "defaultWorkspace", "metadata"]
#: A node's attributes that are not its ports.
_NODE_ATTRS = ["id", "type", "label", "x", "y", "disabled", "output", "meta", "inputs"]
_DASHBOARD_STRUCTURE = ["format", "layout", "panes", "params", "regions"]
_ATTRIBUTE_NAME = re.compile(r"^[A-Za-z_$][\w$-]*$")

__all__ = ["SIGNATURES", "NODE_GRAPH_ID", "UNIT_FIELDS", "ONTOLOGY", "port_is_attribute", *define(globals(), "ontology", SIGNATURES)]


def _own(o: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    return {k: copy.deepcopy(o[k]) for k in keys if o.get(k) is not None}


def _omit(o: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in o.items() if k not in keys and v is not None}


def _kids(t: DocTree, tag: str) -> List[DocTree]:
    return [c for c in t["children"] if c["tag"] == tag]


def _attrs(t: DocTree) -> Dict[str, Any]:
    return copy.deepcopy(t["attrs"])


# ── world.py ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _world(t: DocTree) -> Dict[str, Any]:
    kind = t["attrs"].get("kind")
    if kind not in ("physical", "simulation"):
        raise ValueError(f'<world> kind is "physical" or "simulation", said explicitly, not {kind!r}')
    space_, view_, scene_ = (next(iter(_kids(t, k)), None) for k in ("space", "view", "scene"))
    out: Dict[str, Any] = _own(t["attrs"], WORLD_FIELDS)
    if space_ is not None:
        out["space"] = _attrs(space_)
    out["units"] = [_attrs(u) for u in _kids(t, "unit")]
    if view_ is not None:
        out["view"] = _attrs(view_)
    if scene_ is not None:
        bodies = [_attrs(b) for b in _kids(scene_, "body")]
        out["scene"] = {**_attrs(scene_), **({"bodies": bodies} if bodies else {})}
    return out


_WORLD = Vocabulary("world", "a world", "world", {
    "world": {"parents": [], "required": ["name", "kind"], "attrs": WORLD_FIELDS},
    "space": {"parents": ["world"], "single": True, "required": ["origin_mm", "size_mm"], "attrs": ["origin_mm", "size_mm"]},
    "unit": {"parents": ["world"], "key": "uid", "required": ["uid", "name", "device"], "attrs": UNIT_FIELDS},
    "view": {"parents": ["world"], "single": True},
    "scene": {"parents": ["world"], "single": True},
    "body": {"parents": ["scene"], "key": "id", "required": ["id"]},
}, _world, lambda doc: _unsupported("world"))


# ── definition.py ──────────────────────────────────────────────────────────────────────────────────────────────────


def _device(t: DocTree) -> Dict[str, Any]:
    if "channels" in t["attrs"]:
        raise ValueError("<device>: write each channel as a <channel> element, not a channels attribute")
    channels = [_attrs(c) for c in _kids(t, "channel")]
    return {**_attrs(t), **({"channels": channels} if channels else {})}


_DEVICE = Vocabulary("device", "a device definition", "device", {
    "device": {"parents": [], "required": ["name"]},
    "channel": {"parents": ["device"], "key": "id", "required": ["id"]},
}, _device, lambda doc: _unsupported("device"))


# ── <name>.dashboard.py ────────────────────────────────────────────────────────────────────────────────────────────


def _dashboard(t: DocTree) -> Dict[str, Any]:
    for k in _DASHBOARD_STRUCTURE:
        if k in t["attrs"]:
            raise ValueError(f"<dashboard>: {k} is written as elements (<param>, <split>, <pane>, <region>), not an attribute")
    layouts = [c for c in t["children"] if c["tag"] in ("split", "pane")]
    if len(layouts) != 1:
        raise ValueError(f"<dashboard> has one layout: a <split> or one <pane> (it has {len(layouts)})")
    panes: Dict[str, Any] = {}

    def layout(n: DocTree) -> Dict[str, Any]:
        if n["tag"] == "pane":
            pid = str(n["attrs"]["id"])
            if pid in panes:
                raise ValueError(f'two <pane> have id "{pid}"')
            panes[pid] = _omit(n["attrs"], ["id"])
            return {"kind": "leaf", "paneId": pid}
        sides = [c for c in n["children"] if c["tag"] in ("split", "pane")]
        if len(sides) != 2:
            raise ValueError(f"a <split> has two sides (this one has {len(sides)})")
        return {"kind": "split", "axis": n["attrs"]["axis"], "ratio": n["attrs"]["ratio"], "children": [layout(c) for c in sides]}

    root = layout(layouts[0])
    params = [_attrs(p) for p in _kids(t, "param")]
    regions = {str(r["attrs"]["side"]): _omit(r["attrs"], ["side"]) for r in _kids(t, "region")}
    return {"format": "commandagi-dashboard", **_attrs(t), **({"params": params} if params else {}), "layout": root, "panes": panes,
            **({"regions": regions} if regions else {})}


_DASHBOARD = Vocabulary("dashboard", "a dashboard", "dashboard", {
    "dashboard": {"parents": [], "required": ["name"]},
    "param": {"parents": ["dashboard"], "key": "id", "required": ["id", "type"]},
    "split": {"parents": ["dashboard", "split"], "required": ["axis", "ratio"], "attrs": ["axis", "ratio"]},
    "pane": {"parents": ["dashboard", "split"], "key": "id", "required": ["id"]},
    "region": {"parents": ["dashboard"], "key": "side", "required": ["side"]},
}, _dashboard, lambda doc: _unsupported("dashboard"))


# ── <name>.geo.py (the geo project's manifest) ─────────────────────────────────────────────────────────────────────


def _geo(t: DocTree) -> Dict[str, Any]:
    range_, camera_ = (next(iter(_kids(t, k)), None) for k in ("dateRange", "camera"))
    refs = [_attrs(r) for r in _kids(t, "reference")]
    top = _own(t["attrs"], GEO_FIELDS)
    description, workspace = top.pop("description", None), top.pop("defaultWorkspace", None)
    data: Dict[str, Any] = {}
    if workspace is not None:
        data["defaultWorkspace"] = workspace
    if range_ is not None:
        data["defaultDateRange"] = _attrs(range_)
    if camera_ is not None:
        data["defaultCamera"] = _attrs(camera_)
    if description is not None:
        data["description"] = description
    # The geo project's manifest says which shape it is in; this is the one the studio reads.
    return {"type": "geoeconomics/project", "schemaVersion": "1.0", **top, **({"references": refs} if refs else {}), "data": data}


_GEO = Vocabulary("geo", "a geo project", "geoproject", {
    "geoproject": {"parents": [], "required": ["id", "name"], "attrs": GEO_FIELDS},
    "dateRange": {"parents": ["geoproject"], "single": True, "required": ["start", "end"]},
    "camera": {"parents": ["geoproject"], "single": True},
    "reference": {"parents": ["geoproject"], "key": "path", "required": ["role", "path"], "attrs": ["role", "path", "hash"]},
}, _geo, lambda doc: _unsupported("geo"))


# ── <name>.opgraph.py: the node graph ──────────────────────────────────────────────────────────────────────────────


def port_is_attribute(port: str) -> bool:
    """Whether a port is written as an attribute of its node (else in ``inputs={...}``)."""
    return bool(_ATTRIBUTE_NAME.match(port)) and port not in _NODE_ATTRS and port not in ("key", "children")


def _is_wire(v: Any) -> bool:
    return isinstance(v, dict) and isinstance(v.get("wire"), dict) and isinstance(v["wire"].get("node"), str) and isinstance(v["wire"].get("port"), str)


def _end(text: Any, what: str) -> Dict[str, str]:
    """``"gradient:out"`` -> {node, port} (a node id has no colon; a port may have dots: ``mix:layers.2``)."""
    m = re.match(r"^([^:]+):(.+)$", text, re.S) if isinstance(text, str) else None
    if not m:
        raise ValueError(f'<wire> {what} is "node:port", not {text!r}')
    return {"node": m.group(1), "port": m.group(2)}


def _opgraph(t: DocTree) -> Dict[str, Any]:
    nodes: Dict[str, Any] = {}
    outputs: List[str] = []
    for n in _kids(t, "node"):
        a = n["attrs"]
        nid = str(a.get("id"))
        if not isinstance(a.get("type"), str) or not a["type"]:
            raise ValueError(f'<node id="{nid}"> needs a type')
        if ":" in nid:
            raise ValueError(f'<node id="{nid}">: an id has no colon (a wire names "node:port")')
        inputs = {k: copy.deepcopy(v) for k, v in a.items() if k not in _NODE_ATTRS}
        if a.get("inputs") is not None:
            if not isinstance(a["inputs"], dict):
                raise ValueError(f'<node id="{nid}"> inputs is an object of ports')
            for k, v in a["inputs"].items():
                if port_is_attribute(k):
                    raise ValueError(f'<node id="{nid}">: write {k} as an attribute ({k}=…), not in inputs')
                inputs[k] = copy.deepcopy(v)
        if a.get("meta") is not None and not isinstance(a["meta"], dict):
            raise ValueError(f'<node id="{nid}"> meta is an object')
        meta = dict(a.get("meta") or {})
        for k in ("x", "y"):
            if a.get(k) is not None:
                meta[k] = a[k]
        if n.get("source") is not None:
            meta["source"] = n["source"]
        node: Dict[str, Any] = {"id": nid, "type": a["type"]}
        if isinstance(a.get("label"), str):
            node["label"] = a["label"]
        node["inputs"] = inputs
        if a.get("disabled") is True:
            node["disabled"] = True
        if meta:
            node["meta"] = meta
        nodes[nid] = node
        if a.get("output") is True:
            outputs.append(nid)
    for w in _kids(t, "wire"):
        src, dst = _end(w["attrs"].get("from"), "from"), _end(w["attrs"].get("to"), "to")
        target = nodes.get(dst["node"])
        if target is None:
            raise ValueError(f'<wire to="{w["attrs"].get("to")}">: no <node id="{dst["node"]}">')
        if src["node"] not in nodes:
            raise ValueError(f'<wire from="{w["attrs"].get("from")}">: no <node id="{src["node"]}">')
        literal = target["inputs"].get(dst["port"])
        if _is_wire(literal):
            raise ValueError(f"two <wire> go into {dst['node']}:{dst['port']} (a port takes one wire)")
        target["inputs"][dst["port"]] = {"wire": src, **({"value": literal} if literal is not None else {})}
        # Where the wire was written (`meta.sources`, by `wire:<port>`): the editor finds the element again to remove it.
        if w.get("source") is not None:
            meta = target.setdefault("meta", {})
            meta["sources"] = {**(meta.get("sources") or {}), f"wire:{dst['port']}": w["source"]}
    meta = dict(t["attrs"].get("meta") or {}) if isinstance(t["attrs"].get("meta"), dict) else {}
    if t["attrs"].get("name") is not None:
        meta["name"] = t["attrs"]["name"]
    meta["domain"] = t["attrs"].get("domain", NODE_GRAPH_ID)
    gid = t["attrs"].get("id")
    return {"id": gid if isinstance(gid, str) else NODE_GRAPH_ID, "nodes": nodes, "outputs": outputs, "meta": meta}


_OPGRAPH = Vocabulary("opgraph", "a node graph", "opgraph", {
    "opgraph": {"parents": [], "attrs": ["id", "name", "domain", "meta"]},
    "node": {"parents": ["opgraph"], "key": "id", "required": ["id", "type"]},
    "wire": {"parents": ["opgraph"], "key": "to", "required": ["from", "to"], "attrs": ["from", "to"]},
}, _opgraph, lambda doc: _unsupported("opgraph"),
    empty=lambda name: {"id": NODE_GRAPH_ID, "nodes": {}, "outputs": [], "meta": {"name": name, "domain": NODE_GRAPH_ID}})


def _unsupported(format: str) -> DocTree:
    # The tree a document is (its inverse) is the write-back engine's, in TypeScript; a run only declares.
    raise NotImplementedError(f"the Python SDK declares {format} documents; it does not write them back as elements")


#: The vocabularies of the ontology's files, by format.
ONTOLOGY = {"world": _WORLD, "device": _DEVICE, "dashboard": _DASHBOARD, "geo": _GEO, "opgraph": _OPGRAPH}

for _v in ONTOLOGY.values():
    register_vocabulary(_v, "ontology")
# A node graph is a graph, not a document beside one.
declares("ontology", "opgraph", lambda root, stem: {"graph": _opgraph(tree_of_element(root, _OPGRAPH))})
