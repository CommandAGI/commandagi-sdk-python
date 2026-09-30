"""CAD — parts, sketches and features, declared as the 3D feature graph a ``.3dx`` holds (the same nodes the
TypeScript SDK declares). Lengths in millimetres; angles are taken in degrees and written in radians.
Structure only: the engine's geometry kernel builds the solid when it evaluates the part.

    from commandagi.design import part, box, cylinder, subtract

    def main(width=60):
        def body():
            plate = box(size=(width, 40, 5), center=(0, 0, 2.5))
            return subtract(plate, cylinder(base=(0, 0, 0), radius=1.6, height=5))
        return part("Bracket", body)
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .graph import CODE_OP
from .ir import Declaration, NodeRef, Scope, channels, current_scope, using

PLANES = {"XY": "plane_xy", "XZ": "plane_xz", "YZ": "plane_yz"}
Vec3 = Sequence[float]
Vec2 = Sequence[float]


def _rad(deg: float) -> float:
    return deg * math.pi / 180


def _axis_ref(axis: str) -> Dict[str, Any]:
    return {"type": "datumAxis", "axis": axis}


def _plane_ref(plane: str) -> Dict[str, Any]:
    if plane not in PLANES:
        raise ValueError(f"plane {plane!r} is not XY, XZ or YZ")
    return {"type": "datum", "plane": PLANES[plane]}


class Body(NodeRef):
    """A body: the feature that last shaped it, and every feature it is made of."""

    def __init__(self, scope: Scope, id: str, state: List[str]):
        super().__init__(scope, id)
        self.state = list(state)


class SketchRef(NodeRef):
    pass


def _scope(what: str) -> Scope:
    s = current_scope(what)
    if s.meta.get("domain") != "cad":
        raise RuntimeError(f"{what} declares a 3D feature and belongs inside part() or assembly()")
    return s


def _default_name(s: Scope, type: str) -> str:
    n = sum(1 for x in s.nodes.values() if x["type"] == type) + 1
    return type[0].upper() + type[1:] + " " + str(n)


def _feature(what: str, type: str, fields: Dict[str, Any], name: Optional[str], after: Sequence[str] = (), port: str = "base") -> Body:
    s = _scope(what)
    for i in after:
        if i not in s.nodes:
            raise ValueError(f"{what}: {i} is not a feature of this part")
    ref = s.add(type, {**fields, **channels(port, [NodeRef(s, i) for i in after])}, label=name or _default_name(s, type))
    return Body(s, ref.id, [*after, ref.id])


def part(name: str, fn: Callable[[], Union[Body, List[Body], None]], id: Optional[str] = None,
         meta: Optional[Dict[str, Any]] = None) -> Declaration:
    s = Scope(id or name, {"domain": "cad", "name": name, "units": "mm", **(meta or {})})
    with using(s):
        result = fn()
    if result is not None:
        s.output(*(result if isinstance(result, list) else [result]))
    return Declaration("part", s.build())


def assembly(name: str, fn: Callable[[], Union[Body, List[Body], None]], id: Optional[str] = None) -> Declaration:
    return Declaration("assembly", part(name, fn, id=id, meta={"assembly": True}).ir)


def instance(source: str, inputs: Optional[Dict[str, Any]] = None, name: Optional[str] = None) -> Body:
    s = _scope("instance()")
    ref = s.add(CODE_OP, {"source": source, **(inputs or {})}, label=name or source.split("/")[-1])
    return Body(s, ref.id, [ref.id])


def _after(after: Optional[Sequence[Body]]) -> List[str]:
    out: List[str] = []
    for b in after or []:
        out.extend(b.state)
    return out


def _v(v: Sequence[float]) -> List[float]:
    return [float(x) if isinstance(x, float) else x for x in v]


def box(size: Vec3, center: Vec3 = (0, 0, 0), name: Optional[str] = None, operation: str = "new", after: Optional[Sequence[Body]] = None) -> Body:
    return _feature("box()", "box", {"center": _v(center), "size": _v(size), "operation": operation}, name, _after(after))


def cylinder(radius: float, height: float, base: Vec3 = (0, 0, 0), axis: Vec3 = (0, 0, 1), name: Optional[str] = None,
             operation: str = "new", after: Optional[Sequence[Body]] = None) -> Body:
    """A cylinder standing on ``base`` (the centre of one end), ``height`` along ``axis``."""
    return _feature("cylinder()", "cylinder", {"center": _v(base), "axis": _v(axis), "radius": radius, "height": height, "operation": operation}, name, _after(after))


def sphere(radius: float, center: Vec3 = (0, 0, 0), name: Optional[str] = None, operation: str = "new", after: Optional[Sequence[Body]] = None) -> Body:
    return _feature("sphere()", "sphere", {"center": _v(center), "radius": radius, "operation": operation}, name, _after(after))


def cone(radius1: float, radius2: float, height: float, base: Vec3 = (0, 0, 0), axis: Vec3 = (0, 0, 1), name: Optional[str] = None,
         operation: str = "new", after: Optional[Sequence[Body]] = None) -> Body:
    return _feature("cone()", "cone", {"center": _v(base), "axis": _v(axis), "radius1": radius1, "radius2": radius2, "height": height, "operation": operation}, name, _after(after))


class SketchBuilder:
    """Points and segments in the plane's own millimetres. No constraints are solved."""

    def __init__(self) -> None:
        self.points: Dict[str, Dict[str, Any]] = {}
        self.segments: Dict[str, Dict[str, Any]] = {}
        self._n = 0

    def _point(self, x: float, y: float) -> str:
        self._n += 1
        i = f"p{self._n}"
        self.points[i] = {"id": i, "x": x, "y": y}
        return i

    def _seg(self, seg: Dict[str, Any]) -> None:
        self._n += 1
        i = f"s{self._n}"
        self.segments[i] = {**seg, "id": i}

    def polygon(self, points: Sequence[Vec2]) -> "SketchBuilder":
        if len(points) < 3:
            raise ValueError("a polygon needs at least three points")
        ids = [self._point(p[0], p[1]) for p in points]
        for i, a in enumerate(ids):
            self._seg({"type": "line", "a": a, "b": ids[(i + 1) % len(ids)]})
        return self

    def rect(self, size: Vec2, center: Optional[Vec2] = None, corner: Optional[Vec2] = None) -> "SketchBuilder":
        w, h = size[0], size[1]
        if corner is not None:
            cx, cy = corner[0] + w / 2, corner[1] + h / 2
        else:
            cx, cy = (center or (0, 0))[0], (center or (0, 0))[1]
        return self.polygon([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)])

    def circle(self, radius: float, center: Vec2 = (0, 0)) -> "SketchBuilder":
        self._seg({"type": "circle", "center": self._point(center[0], center[1]), "radius": radius})
        return self

    def to_sketch(self) -> Dict[str, Any]:
        return {"points": self.points, "segments": self.segments, "constraints": {}, "pointOrder": list(self.points),
                "segmentOrder": list(self.segments), "constraintOrder": []}


def sketch(plane: Union[str, Tuple[str, float]], draw: Callable[[SketchBuilder], Any], name: Optional[str] = None) -> SketchRef:
    """A sketch on a datum plane (``"XY"``), or offset along its normal (``("XY", 5)``)."""
    s = _scope("sketch()")
    b = SketchBuilder()
    draw(b)
    if not b.segments:
        raise ValueError("this sketch draws nothing")
    if isinstance(plane, str) or not plane[1]:
        on: Any = _plane_ref(plane if isinstance(plane, str) else plane[0])
    else:
        on = s.add("datumPlane", {"base": PLANES[plane[0]], "offset": plane[1]}, label=f"{plane[0]} + {plane[1]}")
    ref = s.add("sketch", {"plane": on, "sketch": b.to_sketch()}, label=name or _default_name(s, "sketch"))
    return SketchRef(s, ref.id)


def extrude(profile: SketchRef, distance: float, symmetric: bool = False, reverse: bool = False, name: Optional[str] = None,
            operation: str = "new", after: Optional[Sequence[Body]] = None) -> Body:
    fields: Dict[str, Any] = {"profile": profile, "distance": distance}
    if symmetric:
        fields["symmetric"] = True
    if reverse:
        fields["reverse"] = True
    fields["operation"] = operation
    return _feature("extrude()", "extrude", fields, name, _after(after))


def revolve(profile: SketchRef, axis: str, angle: float = 360, name: Optional[str] = None, operation: str = "new",
            after: Optional[Sequence[Body]] = None) -> Body:
    return _feature("revolve()", "revolve", {"profile": profile, "axis": _axis_ref(axis), "angle": _rad(angle), "operation": operation}, name, _after(after))


def _boolean(what: str, op: str, target: Body, tools: Sequence[Body]) -> Body:
    if not tools:
        raise ValueError(f"{what} needs at least one tool body")
    s = _scope(what)
    state = list(target.state)
    for tool in tools:
        n = s.nodes.get(tool.id)
        if not n or "operation" not in n["inputs"]:
            raise ValueError(f"{what}: {tool.id} is not a solid primitive or extrude")
        n["inputs"]["operation"] = op
        for k in [k for k in n["inputs"] if k.startswith("base.")]:
            del n["inputs"][k]
        before = [i for i in state if i not in tool.state]
        n["inputs"].update(channels("base", [{"wire": {"node": i, "port": "out"}} for i in before]))
        state = state + [i for i in tool.state if i not in state]
    return Body(s, tools[-1].id, state)


def union(target: Body, *tools: Body) -> Body:
    return _boolean("union()", "add", target, tools)


def subtract(target: Body, *tools: Body) -> Body:
    return _boolean("subtract()", "cut", target, tools)


def intersect(target: Body, *tools: Body) -> Body:
    return _boolean("intersect()", "intersect", target, tools)


def hole(target: Body, at: Vec3, diameter: float, depth: float, axis: Vec3 = (0, 0, 1), name: Optional[str] = None) -> Body:
    ln = math.sqrt(sum(a * a for a in axis)) or 1.0
    d = [a / ln for a in axis]
    base = [at[i] - d[i] * depth for i in range(3)]
    return subtract(target, cylinder(radius=diameter / 2, height=depth, base=base, axis=d, name=name or "Hole"))


def fillet(target: Body, radius: float, edges: Sequence[Vec3], name: Optional[str] = None) -> Body:
    """Round the edges of ``target`` that pass through these points (the kernel matches the nearest edge)."""
    return _feature("fillet()", "fillet", {"edges": [{"kind": "edge", "signature": {"point": list(e)}} for e in edges], "radius": radius}, name, target.state, port="on")


def chamfer(target: Body, distance: float, edges: Sequence[Vec3], name: Optional[str] = None) -> Body:
    return _feature("chamfer()", "chamfer", {"edges": [{"kind": "edge", "signature": {"point": list(e)}} for e in edges], "distance": distance}, name, target.state, port="on")


def _seeded(what: str, type: str, seed: Body, fields: Dict[str, Any], name: Optional[str]) -> Body:
    s = _scope(what)
    ref = s.add(type, {"seed": seed, **fields}, label=name or _default_name(s, type))
    return Body(s, ref.id, [*seed.state, ref.id])


def copy(seed: Body, translate: Optional[Vec3] = None, rotate: Optional[Tuple[str, float]] = None, name: Optional[str] = None) -> Body:
    fields: Dict[str, Any] = {}
    if translate is not None:
        fields["translate"] = list(translate)
    if rotate is not None:
        fields["rotateAxis"] = _axis_ref(rotate[0])
        fields["rotateAngle"] = _rad(rotate[1])
    return _seeded("copy()", "transform", seed, fields, name)


def linear_pattern(seed: Body, direction: Vec3, spacing: float, count: int, name: Optional[str] = None) -> Body:
    return _seeded("linear_pattern()", "linearPattern", seed, {"direction": list(direction), "spacing": spacing, "count": count}, name)


def circular_pattern(seed: Body, axis: str, count: int, angle: float = 360, name: Optional[str] = None) -> Body:
    return _seeded("circular_pattern()", "circularPattern", seed, {"axis": _axis_ref(axis), "count": count, "angle": _rad(angle)}, name)


def mirror(seed: Body, plane: str, name: Optional[str] = None) -> Body:
    return _seeded("mirror()", "mirror", seed, {"plane": _plane_ref(plane), "keepOriginal": True}, name)
