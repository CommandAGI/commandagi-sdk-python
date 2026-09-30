"""CadQuery → solids — a convenience importer, not CadQuery. A CadQuery-style script's ``Workplane`` chain is
recorded as solid expressions and declared as the 3D feature graph; nothing is computed (no OCCT here, and
none in the browser: the engine's kernel builds the part). Inside the CommandAGI sandbox ``import cadquery as
cq`` gives you this module.

    import cadquery as cq
    width = param("width", 60, unit="mm")
    result = (cq.Workplane("XY").box(width, 40, 5, centered=(True, True, False))
              .faces(">Z").workplane().rarray(44, 24, 2, 2).hole(3.2))
    show_object(result)

Read: ``Workplane("XY", origin=…)``; ``box cylinder sphere``; ``rect circle polygon polyline(...).close()``
then ``extrude`` / ``cutBlind`` / ``cutThruAll``; ``hole``; ``faces(">Z" | "<Z")`` then ``workplane(offset=…)``;
``center pushPoints rarray``; ``translate``, ``rotate`` about X, Y or Z through the origin; ``union cut
intersect``. ``faces`` picks by the declared solids' bounding box (arithmetic, not topology). Fillets,
chamfers, shells, edge selectors, sweeps, lofts, revolves and text need a kernel's topology and are refused
by name.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from . import solids as S


def _refuse(name: str) -> Any:
    raise NotImplementedError(f"cadquery {name} is not read by the CommandAGI importer (it declares structure only)")


def _centered(c: Union[bool, Sequence[bool]]) -> Tuple[bool, bool, bool]:
    if isinstance(c, bool):
        return (c, c, c)
    t = tuple(bool(x) for x in c)
    return (t + (True, True, True))[:3]  # type: ignore[return-value]


class Workplane:
    """A CadQuery-style workplane on XY (normal +Z), or on a top/bottom face found by bounds."""

    def __init__(self, plane: str = "XY", origin: Sequence[float] = (0, 0, 0), _state: Optional[Dict[str, Any]] = None):
        if _state is not None:
            self._s = _state
            return
        if plane != "XY":
            _refuse(f'Workplane("{plane}") (only "XY" is read)')
        self._s = {"origin": [float(origin[0]), float(origin[1]), float(origin[2])], "normal": 1, "points": [(0.0, 0.0)],
                   "pending": [], "solid": None, "face": None}

    # ── state ────────────────────────────────────────────────────────────────────────────────────
    def _with(self, **kw: Any) -> "Workplane":
        s = dict(self._s)
        s.update(kw)
        return Workplane(_state=s)

    def _at(self) -> List[Tuple[float, float]]:
        ox, oy = self._s["origin"][0], self._s["origin"][1]
        return [(ox + x, oy + y) for x, y in self._s["points"]]

    def _combine(self, new: S.Solid, op: str = "union") -> "Workplane":
        cur = self._s["solid"]
        if cur is None:
            if op != "union":
                _refuse(f"{op} with nothing to {op}")
            return self._with(solid=new, pending=[], points=[(0.0, 0.0)])
        return self._with(solid={"k": op, "items": [cur, new]}, pending=[], points=[(0.0, 0.0)])

    # ── 3D primitives (at each point) ────────────────────────────────────────────────────────────
    def box(self, length: float, width: float, height: float, centered: Union[bool, Sequence[bool]] = True, combine: bool = True) -> "Workplane":
        cx, cy, cz = _centered(centered)
        z0, n = self._s["origin"][2], self._s["normal"]
        items = []
        for x, y in self._at():
            center = [x if cx else x + length / 2, y if cy else y + width / 2, z0 if cz else z0 + n * height / 2]
            items.append({"k": "box", "center": center, "size": [length, width, height]})
        return self._combine(items[0] if len(items) == 1 else {"k": "union", "items": items})

    def cylinder(self, height: float, radius: float, direct: Sequence[float] = (0, 0, 1), angle: float = 360, centered: Union[bool, Sequence[bool]] = True) -> "Workplane":
        if angle != 360 or tuple(direct) != (0, 0, 1):
            _refuse("cylinder with an angle or a direction")
        cz = _centered(centered)[2]
        z0, n = self._s["origin"][2], self._s["normal"]
        items = [{"k": "cylinder", "base": [x, y, z0 - height / 2 if cz else (z0 if n > 0 else z0 - height)], "axis": [0, 0, 1], "r": radius, "h": height} for x, y in self._at()]
        return self._combine(items[0] if len(items) == 1 else {"k": "union", "items": items})

    def sphere(self, radius: float) -> "Workplane":
        z0 = self._s["origin"][2]
        items = [{"k": "sphere", "center": [x, y, z0], "r": radius} for x, y in self._at()]
        return self._combine(items[0] if len(items) == 1 else {"k": "union", "items": items})

    # ── 2D (pending until extruded or cut) ────────────────────────────────────────────────────────
    def rect(self, xLen: float, yLen: float, centered: Union[bool, Sequence[bool]] = True) -> "Workplane":
        cx, cy, _ = _centered(centered)
        shapes = [{"k": "rect", "center": [x if cx else x + xLen / 2, y if cy else y + yLen / 2], "size": [xLen, yLen]} for x, y in self._at()]
        return self._with(pending=self._s["pending"] + shapes)

    def circle(self, radius: float) -> "Workplane":
        return self._with(pending=self._s["pending"] + [{"k": "circle", "center": [x, y], "r": radius} for x, y in self._at()])

    def polygon(self, nSides: int, diameter: float) -> "Workplane":
        r = diameter / 2
        shapes = [{"k": "poly", "points": [[x + r * math.cos(2 * math.pi * i / nSides), y + r * math.sin(2 * math.pi * i / nSides)] for i in range(nSides)]} for x, y in self._at()]
        return self._with(pending=self._s["pending"] + shapes)

    def polyline(self, points: Sequence[Sequence[float]]) -> "_Polyline":
        return _Polyline(self, [(float(p[0]), float(p[1])) for p in points])

    def _extrusions(self, distance: float) -> S.Solid:
        pend = self._s["pending"]
        if not pend:
            _refuse("extrude with nothing drawn")
        z0, n = self._s["origin"][2], self._s["normal"]
        lo = z0 if (distance >= 0) == (n > 0) else z0 - abs(distance)
        items = [{"k": "extrude", "profile": p, "z": lo, "h": abs(distance)} for p in pend]
        return items[0] if len(items) == 1 else {"k": "union", "items": items}

    def extrude(self, distance: float, combine: bool = True, both: bool = False, taper: Optional[float] = None) -> "Workplane":
        if both or taper:
            _refuse("extrude(both=…, taper=…)")
        return self._combine(self._extrusions(distance))

    def cutBlind(self, depth: float) -> "Workplane":
        return self._combine(self._extrusions(depth), "subtract")

    def cutThruAll(self) -> "Workplane":
        cur = self._s["solid"]
        if cur is None:
            _refuse("cutThruAll with nothing to cut")
        lo, hi = S.bounds(cur)
        z0, n = self._s["origin"][2], self._s["normal"]
        depth = (z0 - lo[2] if n > 0 else hi[2] - z0) + 1.0
        return self._combine(self._extrusions(-depth), "subtract")

    def hole(self, diameter: float, depth: Optional[float] = None) -> "Workplane":
        cur = self._s["solid"]
        if cur is None:
            _refuse("hole with nothing to drill")
        lo, hi = S.bounds(cur)
        z0, n = self._s["origin"][2], self._s["normal"]
        d = depth if depth is not None else (z0 - lo[2] if n > 0 else hi[2] - z0)
        base_z = z0 - d if n > 0 else z0
        items = [{"k": "cylinder", "base": [x, y, base_z], "axis": [0, 0, 1], "r": diameter / 2, "h": d} for x, y in self._at()]
        tools = items[0] if len(items) == 1 else {"k": "union", "items": items}
        return self._combine(tools, "subtract")

    # ── where ────────────────────────────────────────────────────────────────────────────────────
    def faces(self, selector: str) -> "Workplane":
        cur = self._s["solid"]
        if cur is None:
            _refuse("faces() with no solid")
        if selector not in (">Z", "<Z"):
            _refuse(f'faces("{selector}") (only ">Z" and "<Z" are read)')
        lo, hi = S.bounds(cur)
        return self._with(face=(selector, hi[2] if selector == ">Z" else lo[2]))

    def workplane(self, offset: float = 0.0, invert: bool = False, centerOption: str = "ProjectedOrigin") -> "Workplane":
        if centerOption not in ("ProjectedOrigin",):
            _refuse(f'workplane(centerOption="{centerOption}")')
        face = self._s["face"]
        o = list(self._s["origin"])
        n = self._s["normal"]
        if face is not None:
            n = 1 if face[0] == ">Z" else -1
            o[2] = face[1]
        if invert:
            n = -n
        o[2] += n * offset
        return self._with(origin=o, normal=n, face=None, points=[(0.0, 0.0)], pending=[])

    def center(self, x: float, y: float) -> "Workplane":
        o = list(self._s["origin"])
        o[0] += x
        o[1] += y
        return self._with(origin=o, points=[(0.0, 0.0)])

    def pushPoints(self, pts: Sequence[Sequence[float]]) -> "Workplane":
        return self._with(points=[(float(p[0]), float(p[1])) for p in pts])

    def rarray(self, xSpacing: float, ySpacing: float, xCount: int, yCount: int, center: Union[bool, Sequence[bool]] = True) -> "Workplane":
        cx, cy, _ = _centered(center)
        x0 = -(xCount - 1) * xSpacing / 2 if cx else 0.0
        y0 = -(yCount - 1) * ySpacing / 2 if cy else 0.0
        return self._with(points=[(x0 + i * xSpacing, y0 + j * ySpacing) for i in range(xCount) for j in range(yCount)])

    # ── moves and booleans ───────────────────────────────────────────────────────────────────────
    def translate(self, vec: Sequence[float]) -> "Workplane":
        if self._s["solid"] is None:
            _refuse("translate with no solid")
        return self._with(solid=S.translate(self._s["solid"], vec))

    def rotate(self, axisStartPoint: Sequence[float], axisEndPoint: Sequence[float], angleDegrees: float) -> "Workplane":
        if any(axisStartPoint):
            _refuse("rotate about an axis not through the origin")
        e = list(axisEndPoint)
        axis = "X" if e[0] and not e[1] and not e[2] else "Y" if e[1] and not e[0] and not e[2] else "Z" if e[2] and not e[0] and not e[1] else None
        if axis is None:
            _refuse("rotate about an axis other than X, Y or Z")
        sign = -1 if sum(e) < 0 else 1
        return self._with(solid=S.rotate(self._s["solid"], axis, sign * math.radians(angleDegrees), "Workplane.rotate"))

    def _other(self, other: "Workplane", what: str) -> S.Solid:
        if not isinstance(other, Workplane) or other._s["solid"] is None:
            _refuse(f"{what} with something that is not a Workplane solid")
        return other._s["solid"]

    def union(self, other: "Workplane") -> "Workplane":
        return self._combine(self._other(other, "union"))

    def cut(self, other: "Workplane") -> "Workplane":
        return self._combine(self._other(other, "cut"), "subtract")

    def intersect(self, other: "Workplane") -> "Workplane":
        return self._combine(self._other(other, "intersect"), "intersect")

    def val(self) -> "Workplane":
        return self

    def vals(self) -> List["Workplane"]:
        return [self]

    def solid(self) -> Optional[S.Solid]:
        return self._s["solid"]

    # ── refused by name ──────────────────────────────────────────────────────────────────────────
    def fillet(self, *a: Any, **k: Any) -> Any:
        return _refuse("fillet (declare it with commandagi.design fillet(), naming edges by a point)")

    def chamfer(self, *a: Any, **k: Any) -> Any:
        return _refuse("chamfer (declare it with commandagi.design chamfer())")

    def edges(self, *a: Any, **k: Any) -> Any:
        return _refuse("edges() selectors")

    def shell(self, *a: Any, **k: Any) -> Any:
        return _refuse("shell")

    def cboreHole(self, *a: Any, **k: Any) -> Any:
        return _refuse("cboreHole")

    def cskHole(self, *a: Any, **k: Any) -> Any:
        return _refuse("cskHole")

    def revolve(self, *a: Any, **k: Any) -> Any:
        return _refuse("revolve")

    def sweep(self, *a: Any, **k: Any) -> Any:
        return _refuse("sweep")

    def loft(self, *a: Any, **k: Any) -> Any:
        return _refuse("loft")

    def text(self, *a: Any, **k: Any) -> Any:
        return _refuse("text")

    def mirror(self, *a: Any, **k: Any) -> Any:
        return _refuse("mirror")


class _Polyline:
    def __init__(self, wp: Workplane, pts: List[Tuple[float, float]]):
        self._wp = wp
        self._pts = pts

    def close(self) -> Workplane:
        if len(self._pts) < 3:
            raise ValueError("a closed polyline needs three points")
        ox, oy = self._wp._s["origin"][0], self._wp._s["origin"][1]
        return self._wp._with(pending=self._wp._s["pending"] + [{"k": "poly", "points": [[ox + x, oy + y] for x, y in self._pts]}])


def solids_of(value: Any) -> List[S.Solid]:
    """The solids a script's result holds (a Workplane, or a list of them)."""
    items = value if isinstance(value, (list, tuple)) else [value]
    out = []
    for v in items:
        if not isinstance(v, Workplane) or v.solid() is None:
            raise ValueError("the script's result is not a Workplane solid")
        out.append(v.solid())
    return out


# CadQuery's module-level names a script commonly touches.
class Vector(tuple):
    def __new__(cls, x: float = 0, y: float = 0, z: float = 0) -> "Vector":
        return super().__new__(cls, (x, y, z))


def exporters(*a: Any, **k: Any) -> Any:
    return _refuse("exporters")
