"""Solid expressions — what the CadQuery importer builds while a script runs: primitives, extrusions and
booleans, with no geometry computed. ``declare_solids`` declares the tree as a part's feature graph. A
boolean's tools must be primitives or extrusions (or unions of them); anything else is refused by name.
Bounding boxes are arithmetic on the declared primitives (for CadQuery's face selectors), not a kernel.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cad import Body, box, cylinder, extrude, intersect, part, sketch, sphere, subtract, union
from .ir import Declaration

Solid = Dict[str, Any]


def translate(s: Solid, d: Sequence[float]) -> Solid:
    k = s["k"]
    if k in ("box", "sphere"):
        return {**s, "center": [s["center"][i] + d[i] for i in range(3)]}
    if k == "cylinder":
        return {**s, "base": [s["base"][i] + d[i] for i in range(3)]}
    if k == "extrude":
        return {**s, "profile": translate2d(s["profile"], (d[0], d[1])), "z": s["z"] + d[2]}
    return {**s, "items": [translate(i, d) for i in s["items"]]}


def translate2d(p: Dict[str, Any], d: Tuple[float, float]) -> Dict[str, Any]:
    if p["k"] in ("rect", "circle"):
        return {**p, "center": [p["center"][0] + d[0], p["center"][1] + d[1]]}
    return {**p, "points": [[x + d[0], y + d[1]] for x, y in p["points"]]}


def _rot(v: Sequence[float], axis: str, a: float) -> List[float]:
    c, s = math.cos(a), math.sin(a)
    x, y, z = v

    def r(t: float) -> float:
        return 0.0 if abs(t) < 1e-12 else t

    if axis == "X":
        return [r(x), r(y * c - z * s), r(y * s + z * c)]
    if axis == "Y":
        return [r(x * c + z * s), r(y), r(-x * s + z * c)]
    return [r(x * c - y * s), r(x * s + y * c), r(z)]


def rotate(s: Solid, axis: str, a: float, what: str) -> Solid:
    k = s["k"]
    if abs(a) < 1e-12:
        return s
    if k == "sphere":
        return {**s, "center": _rot(s["center"], axis, a)}
    if k == "cylinder":
        return {**s, "base": _rot(s["base"], axis, a), "axis": _rot(s["axis"], axis, a)}
    if k == "box":
        q = a / (math.pi / 2)
        if abs(q - round(q)) > 1e-9:
            raise ValueError(f"{what}: a box turns only in quarter turns (the feature graph's box is axis-aligned)")
        sx, sy, sz = s["size"]
        odd = round(q) % 2 == 1
        size = s["size"] if not odd else ([sx, sz, sy] if axis == "X" else [sz, sy, sx] if axis == "Y" else [sy, sx, sz])
        return {"k": "box", "center": _rot(s["center"], axis, a), "size": size}
    if k == "extrude":
        if axis != "Z":
            raise ValueError(f"{what}: an extrusion turns only about Z")
        p = s["profile"]
        if p["k"] == "circle":
            q = _rot([p["center"][0], p["center"][1], 0], "Z", a)
            return {**s, "profile": {**p, "center": [q[0], q[1]]}}
        pts = p["points"] if p["k"] == "poly" else _rect_points(p)
        return {**s, "profile": {"k": "poly", "points": [_rot([x, y, 0], "Z", a)[:2] for x, y in pts]}}
    return {**s, "items": [rotate(i, axis, a, what) for i in s["items"]]}


def _rect_points(p: Dict[str, Any]) -> List[List[float]]:
    (cx, cy), (w, h) = p["center"], p["size"]
    return [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]]


def bounds(s: Solid) -> Tuple[List[float], List[float]]:
    """The axis-aligned bounds of the declared solids (a subtraction keeps its target's bounds)."""
    k = s["k"]
    if k == "box":
        return [s["center"][i] - s["size"][i] / 2 for i in range(3)], [s["center"][i] + s["size"][i] / 2 for i in range(3)]
    if k == "sphere":
        return [c - s["r"] for c in s["center"]], [c + s["r"] for c in s["center"]]
    if k == "cylinder":
        b, ax, r, h = s["base"], s["axis"], s["r"], s["h"]
        ln = math.sqrt(sum(a * a for a in ax)) or 1.0
        top = [b[i] + ax[i] / ln * h for i in range(3)]
        pad = [r * math.sqrt(max(0.0, 1 - (ax[i] / ln) ** 2)) for i in range(3)]
        return [min(b[i], top[i]) - pad[i] for i in range(3)], [max(b[i], top[i]) + pad[i] for i in range(3)]
    if k == "extrude":
        p = s["profile"]
        if p["k"] == "circle":
            lo2 = [p["center"][0] - p["r"], p["center"][1] - p["r"]]
            hi2 = [p["center"][0] + p["r"], p["center"][1] + p["r"]]
        else:
            pts = p["points"] if p["k"] == "poly" else _rect_points(p)
            lo2 = [min(x for x, _ in pts), min(y for _, y in pts)]
            hi2 = [max(x for x, _ in pts), max(y for _, y in pts)]
        return [lo2[0], lo2[1], s["z"]], [hi2[0], hi2[1], s["z"] + s["h"]]
    if k == "union":
        bs = [bounds(i) for i in s["items"]]
        return [min(b[0][i] for b in bs) for i in range(3)], [max(b[1][i] for b in bs) for i in range(3)]
    if k == "subtract":
        return bounds(s["items"][0])
    bs = [bounds(i) for i in s["items"]]
    return [max(b[0][i] for b in bs) for i in range(3)], [min(b[1][i] for b in bs) for i in range(3)]


def declare_solids(name: str, solids: List[Solid]) -> Declaration:
    if not solids:
        raise ValueError("the script produced no solids")
    return part(name, lambda: [_emit(s) for s in solids])


def _emit(s: Solid) -> Body:
    k = s["k"]
    if k == "box":
        return box(size=s["size"], center=s["center"])
    if k == "sphere":
        return sphere(radius=s["r"], center=s["center"])
    if k == "cylinder":
        return cylinder(radius=s["r"], height=s["h"], base=s["base"], axis=s["axis"])
    if k == "extrude":
        p = s["profile"]

        def draw(b: Any) -> None:
            if p["k"] == "rect":
                b.rect(size=p["size"], center=p["center"])
            elif p["k"] == "circle":
                b.circle(radius=p["r"], center=p["center"])
            else:
                b.polygon(p["points"])

        sk = sketch(("XY", s["z"]) if s["z"] else "XY", draw)
        return extrude(sk, distance=s["h"])
    first, rest = s["items"][0], s["items"][1:]
    if not rest:
        return _emit(first)
    target = _emit(first)
    tools = [t for r in rest for t in _tools(r)]
    return {"union": union, "subtract": subtract, "intersect": intersect}[k](target, *tools)


def _tools(s: Solid) -> List[Body]:
    if s["k"] == "union":
        return [t for i in s["items"] for t in _tools(i)]
    if s["k"] in ("subtract", "intersect"):
        raise ValueError("a difference or an intersection used as a boolean's tool cannot be declared as features; declare the tools separately")
    return [_emit(s)]
