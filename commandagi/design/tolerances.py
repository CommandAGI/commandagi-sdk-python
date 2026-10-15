"""TOLERANCES — what a toleranced size allows, and the fit of a hole and a shaft. The same rules and messages as the
TypeScript SDK's ``tolerances.ts`` and the 3D engine's ``packages/domain/3d-core/tolerances.ts``::

    from commandagi.design.tolerances import tolerance_limits, fit_of

    tolerance_limits(25, {"class": "H7"})           # {"nominal": 25, "upper": 0.021, "lower": 0, "min": 25, "max": 25.021, ...}
    tolerance_limits(12, {"upper": 0.05, "lower": -0.05})
    fit_of(tolerance_limits(25, {"class": "H7"}), tolerance_limits(25, {"class": "g6"}))["kind"]   # "clearance"

A class is read from the shipped tables (``cloud://global/standards/iso-286.csv``, ``iso-492-normal.csv``;
``standards_data.py`` ``TOLERANCE_TABLES``): an ISO 286 class (``H7``, ``g6``) or a bearing ring's ISO 492 Normal class
(``ISO 492 bore``, ``ISO 492 outside``, ``ISO 492 width``). A class or a size the tables do not have is refused.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .standards_data import TOLERANCE_TABLES

__all__ = ["fit_of", "tolerance_classes", "tolerance_limits", "tolerance_problem"]

_BEARING = re.compile(r"^ISO\s*492\s+(bore|outside|width)$", re.I)


def _fmt(n: float) -> str:
    v = round(n, 4)
    return str(int(v)) if v == int(v) else repr(v)


def _round(n: float) -> float:
    v = round(n, 6)
    return v + 0.0


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def tolerance_classes() -> List[str]:
    """The classes the shipped tables have."""
    out: List[str] = []
    for r in TOLERANCE_TABLES.get("iso-286", []):
        if str(r["class"]) not in out:
            out.append(str(r["class"]))
    for r in TOLERANCE_TABLES.get("iso-492-normal", []):
        n = f"ISO 492 {r['ring']}"
        if n not in out:
            out.append(n)
    return out


def tolerance_problem(tol: Any) -> Optional[str]:
    """What is wrong with a tolerance as written, or None."""
    if not isinstance(tol, dict):
        return "a tolerance is { upper, lower }, { class } or { basic: true }"
    for k in tol:
        if k not in ("upper", "lower", "class", "basic"):
            return f"a tolerance has no field {k} (it has upper, lower, class, basic)"
    up, lo, cls, basic = tol.get("upper"), tol.get("lower"), tol.get("class"), tol.get("basic")
    if up is not None and not _num(up):
        return "upper is a number of millimetres"
    if lo is not None and not _num(lo):
        return "lower is a number of millimetres"
    if cls is not None and (not isinstance(cls, str) or not cls.strip()):
        return "class is a name (H7, g6, ISO 492 bore)"
    if basic is not None and not isinstance(basic, bool):
        return "basic is true or false"
    devs = up is not None or lo is not None
    if basic and (devs or cls):
        return "a basic dimension has no tolerance of its own: clear basic, or clear the tolerance"
    if devs and cls:
        return f"give the class ({cls}) or the deviations, not both"
    if devs and (up is None or lo is None):
        return "give both deviations, upper and lower (0 for none)"
    if devs and not up >= lo:
        return f"the upper deviation ({_fmt(up)}) is below the lower ({_fmt(lo)})"
    if not devs and not cls and not basic:
        return "an empty tolerance: give upper and lower, or a class, or basic"
    return None


def tolerance_limits(nominal: float, tol: Dict[str, Any]) -> Dict[str, Any]:
    """The sizes a tolerance allows at a nominal size. Raises ValueError with the reason when it cannot say."""
    problem = tolerance_problem(tol)
    if problem:
        raise ValueError(problem)
    if tol.get("basic"):
        return {"nominal": nominal, "upper": 0, "lower": 0, "min": nominal, "max": nominal, "basic": True}
    cls = tol.get("class")
    if cls:
        name = cls.strip()
        ring = _BEARING.match(name)
        if ring:
            rows = [r for r in TOLERANCE_TABLES.get("iso-492-normal", []) if str(r["ring"]) == ring.group(1).lower()]
        else:
            rows = [r for r in TOLERANCE_TABLES.get("iso-286", []) if str(r["class"]) == name]
        if not rows:
            raise ValueError(f'the tables have no tolerance class "{cls}" (they have {", ".join(tolerance_classes())})')
        row = next((r for r in rows if r["overMm"] < nominal <= r["uptoMm"]), None)
        if row is None:
            lo = min(r["overMm"] for r in rows)
            hi = max(r["uptoMm"] for r in rows)
            raise ValueError(f"{name} is tabled over {_fmt(lo)} up to {_fmt(hi)} mm, not at {_fmt(nominal)} mm")
        upper, lower = row["upperUm"] / 1000, row["lowerUm"] / 1000
        out = {"nominal": nominal, "upper": upper, "lower": lower, "min": _round(nominal + lower), "max": _round(nominal + upper), "class": name}
        if row.get("source"):
            out["source"] = row["source"]
        return out
    return {"nominal": nominal, "upper": tol["upper"], "lower": tol["lower"], "min": _round(nominal + tol["lower"]), "max": _round(nominal + tol["upper"])}


def fit_of(hole: Dict[str, Any], shaft: Dict[str, Any]) -> Dict[str, Any]:
    """The fit of a hole and a shaft: clearance when the smallest hole takes the largest shaft (a minimum clearance of 0
    counts), interference when the largest hole is smaller than the smallest shaft, else transition."""
    min_c = hole["min"] - shaft["max"]
    max_c = hole["max"] - shaft["min"]
    kind = "clearance" if min_c >= -1e-9 else "interference" if max_c <= 1e-9 else "transition"
    return {"kind": kind, "minClearance": _round(min_c), "maxClearance": _round(max_c)}
