"""A 3D DOCUMENT IN PYTHON — the document's own graph, declared element by element, so the 3D editor opens a
``.3d.py`` with all its tools and writes each edit back into the file. The same elements, node for node, as the
TypeScript SDK's JSX (``commandagi/design`` ``threed.ts``)::

    from commandagi.design.threed import body, constraint, extrude, line, parameter, part, point, sketch

    result = part(
        parameter(name="depth", value=6, unit="mm", bindings=[{"target": "extrude1", "field": "distance"}]),
        sketch(
            point(id="p1", x=-30, y=-20),
            point(id="p2", x=30, y=-20),
            line(id="l1", a="p1", b="p2"),
            constraint(id="c1", kind="horizontal", entities=["l1"]),
            id="sketch1", name="Sketch1", plane={"type": "datum", "plane": "plane_xy"},
        ),
        extrude(id="extrude1", name="Extrude1", profile={"sketch": "sketch1"}, distance=6, operation="new"),
        body(id="extrude1", material="aluminium-6061"),
        name="Mounting plate",
    )

The calls (each keyword is the field of the same name, in snake_case: ``x_axis`` is ``xAxis``):
    part(*elements, name=) | assembly(*elements, name=)   the document; an assembly opens in the assembly mode
    parameter(name=, value=, unit=, comment=, min=, max=, step=, bindings=[{"target", "field"}])
    part(builtin_planes=[…])                  the built-in planes the document has (absent: all three; []: none)
    plane(id=, name=, origin=, normal=, x_axis=)                a datum plane
    FEATURE(id=, name=, …fields)              a feature: the function is its type (extrude, revolve, fillet, chamfer,
                                              hole, linearPattern, circularPattern, mirror, transform, box,
                                              import_, …); ``suppressed``, ``consumes`` as stored
    feature(type_=, id=, name=, …)            a feature of a type the kernel does not know
    sketch(*entities, id=, name=, plane=)     a sketch: point(id=, x=, y=), a segment by its type (line, circle, arc,
                                              spline, ellipse, ellipseArc), constraint(id=, kind=, entities=, …),
                                              projection(id=, ref=, feature=)
    body(id=, name=, material=, visible=)     a body's own data (``bodyMeta[id]``)
    slot(name=, value=)                       any other field of the document, whole

The reader declares the document's graph exactly: a feature is a node of its type with its fields as ports, a plane a
``plane`` node, a parameter an ``input`` node whose ``drives`` are its bindings, a slot a ``3d.<field>`` node, the bodies
one ``3d.bodyMeta`` node. The order of the feature elements is the order of the left-hand list (``presentation.order``).
Every node carries the call it came from in ``meta.source``; a sketch's entities and the bodies are listed by key in
``meta.sources``. Units are millimetres and radians, as stored. Anything else is refused by name, never guessed.

A feature element is checked against its type's schema (``SCHEMA``; its keywords are typed in ``threed_elements.py``,
``ExtrudeProps`` …): the feature ``{type: <tag>, name: <its id when absent>, …its fields}``, a sketch with the ``sketch``
its children make. A wrong field is refused with the sentence an op panel shows for it, the same as the TypeScript
SDK: ``<extrude id="e1">: distance: must be greater than 0 (got -1)``. A ``feature(type_=…)`` of an unknown type is not
checked.
"""
from __future__ import annotations

import copy as _copy
import math
import re
from typing import Any, Dict, List, Optional, Set

from .element import Element, child_elements, declares, define
from .ir import slug
from .schema import describe_issue, validate
from .threed_schema import SCHEMA

#: The feature types a 3D document holds, by tag: the roots of ``SCHEMA`` (``threed_schema.py``), generated from the
#: ``Feature`` union (``packages/domain/3d-core/types.ts``).
THREED_FEATURES: List[str] = list(SCHEMA["roots"])
_FEATURES = set(THREED_FEATURES)
#: Tags with a meaning of their own: never a ``feature(type_=…)``.
_NOT_FEATURES = {"feature", "part", "assembly", "parameter", "plane", "body", "slot", "point", "constraint", "projection", "line", "circle",
                 "arc", "spline", "ellipse", "ellipseArc", "input"}
#: A sketch's segment kinds, by tag.
SKETCH_SEGMENTS: List[str] = ["line", "circle", "arc", "spline", "ellipse", "ellipseArc"]
_SEGMENTS = set(SKETCH_SEGMENTS)
#: The datum planes every 3D document has (``3d-core/document.ts`` basePlanes).
BUILTIN_PLANES: Dict[str, Dict[str, Any]] = {
    "plane_xy": {"name": "Front (XY)", "origin": [0, 0, 0], "normal": [0, 0, 1], "xAxis": [1, 0, 0], "builtin": "XY"},
    "plane_xz": {"name": "Top (XZ)", "origin": [0, 0, 0], "normal": [0, 1, 0], "xAxis": [1, 0, 0], "builtin": "XZ"},
    "plane_yz": {"name": "Right (YZ)", "origin": [0, 0, 0], "normal": [1, 0, 0], "xAxis": [0, 1, 0], "builtin": "YZ"},
}
#: The document's view fields a root element may hold (the graph's ``meta``), beside ``name``.
_VIEW_ATTRS = ["semanticVisibility"]
_PARAM_FIELDS = ["value", "unit", "comment", "min", "max", "step"]
#: Document fields a slot may not hold: they have elements of their own, or are the graph itself.
_NOT_SLOTS = {"id", "name", "units", "planes", "features", "parameters", "presentation", "isAssembly", "bodyMeta", "semanticVisibility"}
#: Slots whose value is an object: each field is a port of the slot's node; any other slot holds its value whole.
_OBJECT_SLOTS = {"environment", "assembly", "sceneConstraints", "dynamics", "animation", "optimization", "standardParts"}

_HOLDS: Dict[str, Any] = {"holds": "children"}
#: Every tag of the 3D document: what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "part": _HOLDS, "assembly": _HOLDS, "parameter": {}, "plane": {}, "body": {}, "slot": {}, "feature": {},
    **{t: (_HOLDS if t == "sketch" else {}) for t in THREED_FEATURES},
    "point": {}, **{t: {} for t in SKETCH_SEGMENTS}, "constraint": {}, "projection": {},
}

__all__ = ["THREED_FEATURES", "SKETCH_SEGMENTS", "BUILTIN_PLANES", "SIGNATURES", "declare_threed", "is_threed",
           *define(globals(), "threed", SIGNATURES)]


def is_threed(root: Any) -> bool:
    """Whether a value is a 3D document: one part or assembly element of this module."""
    return isinstance(root, Element) and root.module == "threed" and root.tag in ("part", "assembly")


def _where(el: Element) -> str:
    for k in ("id", "name"):
        if isinstance(el.props.get(k), str):
            return f'<{el.tag} {k}="{el.props[k]}">'
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
    if isinstance(v, dict) and all(isinstance(k, str) for k in v):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items()}
    raise ValueError(f"{what} is plain data (numbers, strings, arrays, objects)")


def _fields(el: Element, skip: tuple = ()) -> Dict[str, Any]:
    """The element's attributes as fields: plain data, without ``key`` and the names in ``skip``."""
    return {k: _plain(v, f"{_where(el)} {k}") for k, v in el.props.items() if k != "key" and k not in skip and v is not None}


#: An id: letters, digits, ``_ . -``, with ``/`` between them (a merged code part's features are ``<code id>/<id>``).
_ID = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")


def _id_of(el: Element) -> str:
    i = el.props.get("id")
    if not isinstance(i, str) or not i:
        raise ValueError(f"{_where(el)} needs an id")
    if not _ID.match(i):
        raise ValueError(f"{_where(el)}: an id is letters, digits, _ . - with / between them ({i!r})")
    return i


def _no_children(el: Element) -> None:
    if child_elements(el):
        raise ValueError(f"{_where(el)} has no child elements")


def _meta(el: Element) -> Dict[str, Any]:
    return {} if el.source is None else {"meta": {"source": el.source}}


def _sketch_of(el: Element):
    """The sketch a sketch element's children declare, and where each entity was written."""
    points: Dict[str, Any] = {}
    segments: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    projections: Dict[str, Any] = {}
    sources: Dict[str, Any] = {}
    taken: Set[str] = set()

    def claim(child: Element, kind: str) -> str:
        i = _id_of(child)
        if i in taken:
            raise ValueError(f"{_where(el)}: two entities are called {i}")
        taken.add(i)
        if child.source is not None:
            sources[f"{kind}:{i}"] = child.source
        _no_children(child)
        return i

    for child in child_elements(el):
        if child.tag == "point":
            i = claim(child, "point")
            f = _fields(child)
            if not _is_number(f.get("x")) or not _is_number(f.get("y")):
                raise ValueError(f"{_where(el)} {_where(child)}: a point has x and y (mm)")
            points[i] = f
        elif child.tag in _SEGMENTS:
            i = claim(child, "segment")
            if "type" in child.props:
                raise ValueError(f"{_where(el)} {_where(child)}: the tag is the segment's type")
            segments[i] = {"id": i, "type": child.tag, **_fields(child, ("id",))}
        elif child.tag == "constraint":
            i = claim(child, "constraint")
            f = _fields(child)
            if not isinstance(f.get("kind"), str) or not isinstance(f.get("entities"), list):
                raise ValueError(f"{_where(el)} {_where(child)}: a constraint has a kind and its entities")
            constraints[i] = f
        elif child.tag == "projection":
            projections[claim(child, "projection")] = _fields(child)
        else:
            raise ValueError(f"{_where(el)}: <{child.tag}> is not read in a sketch (point, {', '.join(SKETCH_SEGMENTS)}, constraint, projection)")
    for i, s in segments.items():
        for k in ("a", "b", "center", "start", "end", "focus"):
            p = s.get(k)
            if p is not None and (not isinstance(p, str) or p not in points):
                raise ValueError(f"{_where(el)}: segment {i}'s {k} names no point of the sketch ({p!r})")
    sketch: Dict[str, Any] = {"points": points, "segments": segments, "constraints": constraints, "pointOrder": list(points),
                              "segmentOrder": list(segments), "constraintOrder": list(constraints)}
    if projections:
        sketch["projections"] = projections
        sketch["projectionOrder"] = list(projections)
    return sketch, sources


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_feature(el: Element, feature: Dict[str, Any]) -> None:
    """Refuses a feature whose fields do not fit its type's schema, with every issue."""
    d = SCHEMA["roots"].get(feature["type"])
    if d is None:
        return
    issues = validate({"$ref": f"#/$defs/{d}"}, feature, SCHEMA["$defs"])
    if issues:
        raise ValueError(f"{_where(el)}: {'; '.join(describe_issue(x) for x in issues)}")


def _builtin_planes_of(root: Element) -> List[str]:
    """The built-in planes a root says the document has (``builtinPlanes``); absent: all three."""
    v = root.props.get("builtinPlanes")
    if v is None:
        return list(BUILTIN_PLANES)
    if not isinstance(v, (list, tuple)) or any(not isinstance(x, str) or x not in BUILTIN_PLANES for x in v):
        raise ValueError(f"{_where(root)}: builtinPlanes lists built-in planes ({', '.join(BUILTIN_PLANES)})")
    if len(set(v)) != len(v):
        raise ValueError(f"{_where(root)}: builtinPlanes names a plane twice")
    return list(v)


def declare_threed(root: Element, fallback_name: str = "Part") -> Dict[str, Any]:
    """The graph a part or assembly element declares: an op graph whose nodes are its parameters, planes, features and
    slots."""
    if not is_threed(root):
        raise ValueError("a 3D document is one part() or assembly() element")
    for k in root.props:
        if k not in ("key", "name", "id", "builtinPlanes") and k not in _VIEW_ATTRS:
            raise ValueError(f"{_where(root)}: prop {k} is not read on a 3D document")
    builtins = _builtin_planes_of(root)
    name = root.props["name"] if isinstance(root.props.get("name"), str) and root.props["name"] else fallback_name
    nodes: Dict[str, Dict[str, Any]] = {}
    owner: Dict[str, str] = {}

    def claim(i: str, what: str) -> None:
        if i in owner:
            raise ValueError(f'the id "{i}" is both {owner[i]} and {what}; a node id is used once')
        owner[i] = what

    order: List[str] = []
    bodies: Dict[str, Any] = {}
    body_sources: Dict[str, Any] = {}
    declared: List[Element] = []
    for el in child_elements(root):
        if el.tag == "parameter":
            _no_children(el)
            pname = el.props.get("name")
            if not isinstance(pname, str) or not pname or slug(pname) != pname:
                raise ValueError(f"{_where(el)} needs a name (letters, digits, _ . -)")
            for k in el.props:
                if k not in ("key", "name", "bindings", *_PARAM_FIELDS):
                    raise ValueError(f"{_where(el)}: prop {k} is not read on a parameter")
            if not _is_number(el.props.get("value")):
                raise ValueError(f"{_where(el)}: value is a number")
            claim(pname, f'parameter "{pname}"')
            f = _fields(el, ("name", "bindings"))
            bindings = [] if el.props.get("bindings") is None else _plain(el.props["bindings"], f"{_where(el)} bindings")
            if not isinstance(bindings, list) or any(not isinstance(b, dict) or not isinstance(b.get("target"), str)
                                                     or not isinstance(b.get("field"), str) for b in bindings):
                raise ValueError(f"{_where(el)}: bindings are [{{ target, field }}]")
            nodes[pname] = {"id": pname, "type": "input", "label": pname, "inputs": {**f, **({"drives": bindings} if bindings else {})}, **_meta(el)}
        elif el.tag == "plane":
            _no_children(el)
            i = _id_of(el)
            claim(i, f'plane "{i}"')
            rest = _fields(el, ("id",))
            label = rest.pop("name", None)
            nodes[i] = {"id": i, "type": "plane", **({"label": label} if isinstance(label, str) else {}), "inputs": rest, **_meta(el)}
        elif el.tag == "body":
            _no_children(el)
            i = _id_of(el)
            if i in bodies:
                raise ValueError(f"two body elements are called {i}")
            bodies[i] = _fields(el, ("id",))
            if el.source is not None:
                body_sources[i] = el.source
        elif el.tag == "slot":
            _no_children(el)
            field = el.props.get("name")
            if not isinstance(field, str) or not re.match(r"^[A-Za-z_]\w*$", field):
                raise ValueError(f"{_where(el)} needs the name of a document field")
            if field in _NOT_SLOTS:
                raise ValueError(f"{_where(el)}: {field} is not a slot (it has its own element or attribute)")
            for k in el.props:
                if k not in ("key", "name", "value"):
                    raise ValueError(f'{_where(el)}: prop {k} is not read on a slot (its value is "value")')
            claim(field, f"the document's {field}")
            value = _plain(el.props.get("value"), f"{_where(el)} value")
            inputs: Dict[str, Any] = {"value": value}
            if field in _OBJECT_SLOTS:
                if not isinstance(value, dict):
                    raise ValueError(f"{_where(el)}: the document's {field} is an object")
                inputs = value
            nodes[field] = {"id": field, "type": f"3d.{field}", "inputs": inputs, **_meta(el)}
        elif el.tag in _FEATURES:
            declared.append(el)
        elif el.tag == "feature":
            t = el.props.get("type")
            if not isinstance(t, str) or not re.match(r"^[A-Za-z_][\w.-]*$", t):
                raise ValueError(f"{_where(el)} needs the feature's type")
            if t in _FEATURES or t in _NOT_FEATURES:
                raise ValueError(f"{_where(el)}: a {t} is written {t.replace('-', '_')}(…)")
            declared.append(el)
        else:
            raise ValueError(f"<{el.tag}> is not read in a 3D document (see commandagi.design.threed)")
    for el in declared:
        i = _id_of(el)
        claim(i, f'feature "{i}"')
        generic = el.tag == "feature"
        if not generic and "type" in el.props:
            raise ValueError(f"{_where(el)}: the tag is the feature's type")
        ftype = el.props["type"] if generic else el.tag
        rest = _fields(el, ("id", "type") if generic else ("id",))
        label = rest.pop("name", None)
        suppressed = rest.pop("suppressed", None)
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError(f"{_where(el)}: suppressed is true or false")
        inputs = rest
        sources: Optional[Dict[str, Any]] = None
        if el.tag == "sketch":
            if "sketch" in rest:
                raise ValueError(f"{_where(el)}: a sketch's points, segments and constraints are its child elements")
            sk, sources = _sketch_of(el)
            inputs = {**rest, "sketch": sk}
        if not generic:
            _check_feature(el, {"type": ftype, "id": i, "name": label if label is not None else i,
                                **({"suppressed": suppressed} if suppressed is not None else {}), **inputs})
        if el.tag != "sketch":
            _no_children(el)
            if el.tag == "code":
                # A code feature's `inputs` are ports of its node, beside `source` and `consumes` (the document graph's rule).
                code_inputs = rest.pop("inputs", None)
                if code_inputs is not None and not isinstance(code_inputs, dict):
                    raise ValueError(f"{_where(el)}: inputs is an object")
                for k in rest:
                    if k not in ("source", "consumes"):
                        raise ValueError(f"{_where(el)}: a code feature has source, inputs and consumes, not {k}")
                inputs = {**rest, **(code_inputs or {})}
        node: Dict[str, Any] = {"id": i, "type": ftype, "label": label if isinstance(label, str) else i}
        if suppressed is not None:
            node["disabled"] = suppressed
        node["inputs"] = inputs
        if el.source is not None or sources:
            m: Dict[str, Any] = {}
            if el.source is not None:
                m["source"] = el.source
            if sources:
                m["sources"] = sources
            node["meta"] = m
        nodes[i] = node
        order.append(i)
    for i, p in BUILTIN_PLANES.items():
        if i in owner or i not in builtins:
            continue
        inputs = _copy.deepcopy({k: v for k, v in p.items() if k != "name"})
        nodes[i] = {"id": i, "type": "plane", "label": p["name"], "inputs": inputs}
    if bodies:
        claim("bodyMeta", "the bodies (body)")
        nodes["bodyMeta"] = {"id": "bodyMeta", "type": "3d.bodyMeta", "inputs": bodies, **({"meta": {"sources": body_sources}} if body_sources else {})}
    view: Dict[str, Any] = {"name": name, "units": "mm"}
    for k in _VIEW_ATTRS:
        if root.props.get(k) is not None:
            view[k] = _plain(root.props[k], f"{_where(root)} {k}")
    if root.tag == "assembly":
        view["isAssembly"] = True
    if order:
        view["presentation"] = {"order": order}
    gid = root.props["id"] if isinstance(root.props.get("id"), str) and root.props["id"] else f"3d-{slug(name).lower()}"
    return {"id": gid, "nodes": nodes, "meta": view}


for _root in ("part", "assembly"):
    declares("threed", _root, lambda root, stem: {"graph": declare_threed(root, stem)})
