"""A 3D document, declared element by element — the same graph the TypeScript SDK's JSX declares (``threed.ts``).

Python has no JSX, so an element is a call: ``h(tag, *children, **fields)``, and ``document`` reads a ``part`` (or
``assembly``) element::

    from commandagi.design.threed import h, document

    result = document(h("part",
        h("parameter", name="thickness", value=6, unit="mm", bindings=[{"target": "extrude1", "field": "distance"}]),
        h("sketch", h("point", id="p1", x=-30, y=-20), …, h("line", id="l1", a="p1", b="p2"),
          h("constraint", id="c1", kind="horizontal", entities=["l1"]),
          id="sketch1", name="Outline", plane={"type": "datum", "plane": "plane_xy"}),
        h("extrude", id="extrude1", name="Plate", profile={"sketch": "sketch1"}, distance=6, operation="new"),
        h("body", id="extrude1", material={"preset": "aluminum", …}),
        name="Mounting plate"))

The tags, the fields and the nodes are the TypeScript SDK's (``commandagi/design`` ``threed.ts``): a feature is a node
of its type with its fields as ports, a sketch's entities are its children, a parameter is an ``input`` node whose
``drives`` are its bindings, a ``<slot name value>`` any other document field, the bodies one ``3d.bodyMeta`` node, and
the three built-in planes are there unless the root's ``builtinPlanes`` lists the ones the document has (``[]``: none).
A ``feature`` element with a ``type`` declares a feature of a type the kernel does not know (a document may hold any).
An id is letters, digits, ``_ . -`` with ``/`` between them. Millimetres and radians, as stored. Anything else is
refused by name.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from .ir import Declaration, slug

THREED_FEATURES = [
    "sketch", "extrude", "revolve", "sweep", "loft", "fillet", "chamfer", "shell", "box", "import", "externalPart",
    "cylinder", "sphere", "cone", "makehuman", "linearPattern", "circularPattern", "pathPattern", "mirror",
    "datumPlane", "draft", "hole", "thread", "rib", "coil", "combine", "offsetFaces", "thicken", "split", "scale",
    "dome", "wrapText", "deleteFace", "fullRound", "sheetFlange", "unfold", "copyBody", "transform", "subdivBody",
    "meshBody", "meshModifier", "pointCloud", "gaussianSplat", "skeleton", "volume", "molecule", "graph", "generate",
    "pcbTrace", "copperPour", "generateVia", "platedHole", "code",
]
SKETCH_SEGMENTS = ["line", "circle", "arc", "spline", "ellipse", "ellipseArc"]
BUILTIN_PLANES = {
    "plane_xy": {"name": "Front (XY)", "origin": [0, 0, 0], "normal": [0, 0, 1], "xAxis": [1, 0, 0], "builtin": "XY"},
    "plane_xz": {"name": "Top (XZ)", "origin": [0, 0, 0], "normal": [0, 1, 0], "xAxis": [1, 0, 0], "builtin": "XZ"},
    "plane_yz": {"name": "Right (YZ)", "origin": [0, 0, 0], "normal": [1, 0, 0], "xAxis": [0, 1, 0], "builtin": "YZ"},
}
PARAM_FIELDS = ["value", "unit", "comment", "min", "max", "step"]
OBJECT_SLOTS = {"environment", "assembly", "sceneConstraints", "dynamics", "animation", "optimization", "standardParts"}
NOT_SLOTS = {"id", "name", "units", "planes", "features", "parameters", "presentation", "isAssembly", "bodyMeta", "semanticVisibility"}
VIEW_ATTRS = {"semanticVisibility"}


class Element:
    """One element: its tag, its fields and its children (what JSX would write)."""

    def __init__(self, tag: str, props: Dict[str, Any], children: List["Element"]):
        self.tag = tag
        self.props = props
        self.children = children


def h(tag: str, *children: Any, **props: Any) -> Element:
    """An element: ``h("extrude", id="extrude1", distance=6)``; children as positional arguments (lists are flattened)."""
    flat: List[Element] = []

    def walk(c: Any) -> None:
        if c is None or isinstance(c, bool):
            return
        if isinstance(c, (list, tuple)):
            for x in c:
                walk(x)
        elif isinstance(c, Element):
            flat.append(c)
        else:
            raise ValueError(f"<{tag}>'s children are elements")

    walk(list(children))
    return Element(tag, props, flat)


def _where(el: Element) -> str:
    if isinstance(el.props.get("id"), str):
        return f'<{el.tag} id="{el.props["id"]}">'
    if isinstance(el.props.get("name"), str):
        return f'<{el.tag} name="{el.props["name"]}">'
    return f"<{el.tag}>"


def _plain(v: Any, what: str) -> Any:
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"{what} is {v}, not a finite number")
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{what}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items() if x is not None}
    raise ValueError(f"{what} is plain data (numbers, strings, lists, dicts)")


def _fields(el: Element, skip: tuple = ()) -> Dict[str, Any]:
    return {k: _plain(v, f"{_where(el)} {k}") for k, v in el.props.items() if k not in skip and v is not None}


_ID = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
NOT_FEATURES = {"feature", "part", "assembly", "parameter", "plane", "body", "slot", "point", "constraint", "projection",
                "line", "circle", "arc", "spline", "ellipse", "ellipseArc", "input"}


def _builtin_planes(root: Element) -> set:
    v = root.props.get("builtinPlanes")
    if v is None:
        return set(BUILTIN_PLANES)
    if not isinstance(v, list) or any(not isinstance(x, str) or x not in BUILTIN_PLANES for x in v):
        raise ValueError(f"{_where(root)}: builtinPlanes lists built-in planes ({', '.join(BUILTIN_PLANES)})")
    if len(set(v)) != len(v):
        raise ValueError(f"{_where(root)}: builtinPlanes names a plane twice")
    return set(v)


def _id_of(el: Element) -> str:
    i = el.props.get("id")
    if not isinstance(i, str) or not i:
        raise ValueError(f"{_where(el)} needs an id")
    if not _ID.match(i):
        raise ValueError(f"{_where(el)}: an id is letters, digits, _ . - with / between them ({i!r})")
    return i


def _no_children(el: Element) -> None:
    if el.children:
        raise ValueError(f"{_where(el)} has no child elements")


def _sketch_of(el: Element) -> Dict[str, Any]:
    points: Dict[str, Any] = {}
    segments: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    projections: Dict[str, Any] = {}
    taken = set()
    for child in el.children:
        cid = _id_of(child)
        if cid in taken:
            raise ValueError(f"{_where(el)}: two entities are called {cid}")
        taken.add(cid)
        _no_children(child)
        if child.tag == "point":
            f = _fields(child)
            if not isinstance(f.get("x"), (int, float)) or not isinstance(f.get("y"), (int, float)):
                raise ValueError(f"{_where(el)} {_where(child)}: a point has x and y (mm)")
            points[cid] = f
        elif child.tag in SKETCH_SEGMENTS:
            if "type" in child.props:
                raise ValueError(f"{_where(el)} {_where(child)}: the tag is the segment's type")
            segments[cid] = {"id": cid, "type": child.tag, **_fields(child, ("id",))}
        elif child.tag == "constraint":
            f = _fields(child)
            if not isinstance(f.get("kind"), str) or not isinstance(f.get("entities"), list):
                raise ValueError(f"{_where(el)} {_where(child)}: a constraint has a kind and its entities")
            constraints[cid] = f
        elif child.tag == "projection":
            projections[cid] = _fields(child)
        else:
            raise ValueError(f"{_where(el)}: <{child.tag}> is not read in a sketch (point, {', '.join(SKETCH_SEGMENTS)}, constraint, projection)")
    for sid, s in segments.items():
        for k in ("a", "b", "center", "start", "end", "focus"):
            p = s.get(k)
            if p is not None and (not isinstance(p, str) or p not in points):
                raise ValueError(f"{_where(el)}: segment {sid}'s {k} names no point of the sketch ({p!r})")
    sketch: Dict[str, Any] = {
        "points": points, "segments": segments, "constraints": constraints,
        "pointOrder": list(points), "segmentOrder": list(segments), "constraintOrder": list(constraints),
    }
    if projections:
        sketch["projections"] = projections
        sketch["projectionOrder"] = list(projections)
    return sketch


def declare_threed(root: Element, fallback_name: str = "Part") -> Dict[str, Any]:
    """The graph a ``part`` or ``assembly`` element declares (the TypeScript SDK's ``declareThreeD``)."""
    if not isinstance(root, Element) or root.tag not in ("part", "assembly"):
        raise ValueError("a 3D document is one part or assembly element")
    for k in root.props:
        if k not in ("name", "id", "builtinPlanes") and k not in VIEW_ATTRS:
            raise ValueError(f"{_where(root)}: prop {k} is not read on a 3D document")
    builtins = _builtin_planes(root)
    name = root.props.get("name") if isinstance(root.props.get("name"), str) and root.props.get("name") else fallback_name
    nodes: Dict[str, Any] = {}
    owner: Dict[str, str] = {}

    def claim(i: str, what: str) -> None:
        if i in owner:
            raise ValueError(f'the id "{i}" is both {owner[i]} and {what}; a node id is used once')
        owner[i] = what

    order: List[str] = []
    bodies: Dict[str, Any] = {}
    features: List[Element] = []
    for el in root.children:
        if el.tag == "parameter":
            _no_children(el)
            pname = el.props.get("name")
            if not isinstance(pname, str) or not pname or slug(pname) != pname:
                raise ValueError(f"{_where(el)} needs a name (letters, digits, _ . -)")
            for k in el.props:
                if k not in ("name", "bindings", *PARAM_FIELDS):
                    raise ValueError(f"{_where(el)}: prop {k} is not read on a parameter")
            if not isinstance(el.props.get("value"), (int, float)) or isinstance(el.props.get("value"), bool):
                raise ValueError(f"{_where(el)}: value is a number")
            claim(pname, f'parameter "{pname}"')
            inputs = _fields(el, ("name", "bindings"))
            bindings = _plain(el.props.get("bindings") or [], f"{_where(el)} bindings")
            if any(not isinstance(b, dict) or not isinstance(b.get("target"), str) or not isinstance(b.get("field"), str) for b in bindings):
                raise ValueError(f"{_where(el)}: bindings are [{{ target, field }}]")
            if bindings:
                inputs["drives"] = bindings
            nodes[pname] = {"id": pname, "type": "input", "label": pname, "inputs": inputs}
        elif el.tag == "plane":
            _no_children(el)
            pid = _id_of(el)
            claim(pid, f'plane "{pid}"')
            f = _fields(el, ("id",))
            label = f.pop("name", None)
            nodes[pid] = {"id": pid, "type": "plane", **({"label": label} if isinstance(label, str) else {}), "inputs": f}
        elif el.tag == "body":
            _no_children(el)
            bid = _id_of(el)
            if bid in bodies:
                raise ValueError(f"two body elements are called {bid}")
            bodies[bid] = _fields(el, ("id",))
        elif el.tag == "slot":
            _no_children(el)
            field = el.props.get("name")
            if not isinstance(field, str) or not field.replace("_", "a").isalnum():
                raise ValueError(f"{_where(el)} needs the name of a document field")
            if field in NOT_SLOTS:
                raise ValueError(f"{_where(el)}: {field} is not a slot (it has its own element or attribute)")
            for k in el.props:
                if k not in ("name", "value"):
                    raise ValueError(f'{_where(el)}: prop {k} is not read on a slot (its value is "value")')
            claim(field, f"the document's {field}")
            value = _plain(el.props.get("value"), f"{_where(el)} value")
            if field in OBJECT_SLOTS:
                if not isinstance(value, dict):
                    raise ValueError(f"{_where(el)}: the document's {field} is an object")
                inputs = value
            else:
                inputs = {"value": value}
            nodes[field] = {"id": field, "type": f"3d.{field}", "inputs": inputs}
        elif el.tag in THREED_FEATURES:
            features.append(el)
        elif el.tag == "feature":
            t = el.props.get("type")
            if not isinstance(t, str) or not re.match(r"^[A-Za-z_][\w.-]*$", t):
                raise ValueError(f"{_where(el)} needs the feature's type")
            if t in THREED_FEATURES or t in NOT_FEATURES:
                raise ValueError(f"{_where(el)}: a {t} is written <{t}>")
            features.append(el)
        else:
            raise ValueError(f"<{el.tag}> is not read in a 3D document (see commandagi.design.threed)")
    for el in features:
        fid = _id_of(el)
        claim(fid, f'feature "{fid}"')
        generic = el.tag == "feature"
        if not generic and "type" in el.props:
            raise ValueError(f"{_where(el)}: the tag is the feature's type")
        ftype = el.props["type"] if generic else el.tag
        f = _fields(el, ("id", "type") if generic else ("id",))
        label = f.pop("name", None)
        suppressed = f.pop("suppressed", None)
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError(f"{_where(el)}: suppressed is True or False")
        if el.tag == "sketch":
            if "sketch" in f:
                raise ValueError(f"{_where(el)}: a sketch's points, segments and constraints are its child elements")
            f["sketch"] = _sketch_of(el)
        else:
            _no_children(el)
            if el.tag == "code":
                code_inputs = f.pop("inputs", None) or {}
                if not isinstance(code_inputs, dict):
                    raise ValueError(f"{_where(el)}: inputs is a dict")
                for k in f:
                    if k not in ("source", "consumes"):
                        raise ValueError(f"{_where(el)}: a code feature has source, inputs and consumes, not {k}")
                f = {**f, **code_inputs}
        node: Dict[str, Any] = {"id": fid, "type": ftype, "label": label if isinstance(label, str) else fid}
        if suppressed is not None:
            node["disabled"] = suppressed
        node["inputs"] = f
        nodes[fid] = node
        order.append(fid)
    for pid, p in BUILTIN_PLANES.items():
        if pid in owner or pid not in builtins:
            continue
        nodes[pid] = {"id": pid, "type": "plane", "label": p["name"], "inputs": {k: (list(v) if isinstance(v, list) else v) for k, v in p.items() if k != "name"}}
    if bodies:
        claim("bodyMeta", "the bodies (body)")
        nodes["bodyMeta"] = {"id": "bodyMeta", "type": "3d.bodyMeta", "inputs": bodies}
    meta: Dict[str, Any] = {"name": name, "units": "mm"}
    for k in VIEW_ATTRS:
        if root.props.get(k) is not None:
            meta[k] = _plain(root.props[k], f"{_where(root)} {k}")
    if root.tag == "assembly":
        meta["isAssembly"] = True
    if order:
        meta["presentation"] = {"order": order}
    did = root.props.get("id") if isinstance(root.props.get("id"), str) and root.props.get("id") else f"3d-{slug(name).lower()}"
    return {"id": did, "nodes": nodes, "meta": meta}


def document(root: Element, name: Optional[str] = None) -> Declaration:
    """A 3D document: the graph a ``part`` or ``assembly`` element declares, as a declaration."""
    return Declaration("assembly" if getattr(root, "tag", None) == "assembly" else "part", declare_threed(root, name or "Part"))
