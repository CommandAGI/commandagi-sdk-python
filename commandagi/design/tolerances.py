"""TOLERANCES — what a toleranced size allows, and the fit of a hole and a shaft. The same rules and messages as the
TypeScript SDK's ``tolerances.ts`` and the 3D engine's ``packages/domain/3d-core/tolerances.ts``::

    from commandagi.design.tolerances import tolerance_limits, fit_of

    tolerance_limits(25, {"class": "H7"})           # {"nominal": 25, "upper": 0.021, "lower": 0, "min": 25, "max": 25.021, ...}
    tolerance_limits(12, {"upper": 0.05, "lower": -0.05})
    fit_of(tolerance_limits(25, {"class": "H7"}), tolerance_limits(25, {"class": "g6"}))["kind"]   # "clearance"

A class is any ISO 286 class (``H7``, ``e8``, ``E10``, ``H13``, ``zc11``), computed from its fundamental deviation and
grade over 0 up to 3150 mm (``cloud://global/standards/iso-286-1-grades.csv``, ``iso-286-1-deviations.csv``), a general
tolerance of ISO 2768-1 (``ISO 2768-m``), or a bearing ring's ISO 492 Normal class (``ISO 492 bore``, ``ISO 492 outside``,
``ISO 492 width``); ``standards_data.py`` ``TOLERANCE_TABLES`` holds the tables. A class or a size the standard does not
give is refused, with the reason.
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


_GENERAL = re.compile(r"^ISO\s*2768(?:-1)?[-\s]*([fmcv])$", re.I)
# An ISO 286 class: the fundamental deviation's letters (capital: a hole, small: a shaft) and the grade.
_ISO286 = re.compile(r"^(A|B|CD|C|D|EF|E|FG|F|G|H|JS|J|K|M|N|P|R|S|T|U|V|X|Y|ZA|ZB|ZC|Z)(01|0|1[0-8]|[1-9])$")
_ISO286_SOURCE = "ISO 286-1: the fundamental deviation (Tables 2 and 3) and the standard tolerance grade (Table 1)"
# The shaft letters whose fundamental deviation is the upper one (es); a hole's A to H mirror them (EI = -es).
_UPPER_LETTERS = ["a", "b", "c", "cd", "d", "e", "ef", "f", "fg", "g", "h"]
_KNOWN = ("an ISO 286 class (a hole's letters A to ZC or a shaft's a to zc, then a grade 01, 0 or 1 to 18: H7, e8, JS9), "
          "ISO 2768-f, -m, -c or -v, or ISO 492 bore, outside or width")


def tolerance_classes() -> List[str]:
    """The classes an editor suggests: the usual ISO 286-2 classes, ISO 2768-1 and the ISO 492 rings. Every ISO 286 class
    is read, not only these."""
    holes = ["H6", "H7", "H8", "H9", "H10", "H11", "H12", "H13", "G6", "G7", "F7", "F8", "E8", "E9", "E10", "D9", "D10", "C11", "JS6", "JS7", "JS8", "K6", "K7", "M6", "M7", "N6", "N7", "P6", "P7", "R7", "S7", "U7"]
    shafts = ["h5", "h6", "h7", "h8", "h9", "h10", "h11", "h12", "h13", "g5", "g6", "f6", "f7", "e7", "e8", "e9", "d9", "d10", "c11", "js5", "js6", "js7", "j5", "j6", "k5", "k6", "m5", "m6", "n5", "n6", "p5", "p6", "r6", "s6", "u6"]
    out: List[str] = holes + shafts
    for r in TOLERANCE_TABLES.get("iso-2768-1", []):
        n = f"ISO 2768-{r['class']}"
        if n not in out:
            out.append(n)
    for r in TOLERANCE_TABLES.get("iso-492-normal", []):
        n = f"ISO 492 {r['ring']}"
        if n not in out:
            out.append(n)
    return out


def _row_at(table: str, size: float, where=lambda r: True) -> Optional[Dict[str, Any]]:
    return next((r for r in TOLERANCE_TABLES.get(table, []) if where(r) and r["overMm"] < size <= r["uptoMm"]), None)


def _iso286(letters: str, grade_text: str, size: float) -> Dict[str, float]:
    """An ISO 286 class at a size, in micrometres (the 3D engine's ``iso286``, line for line)."""
    name = f"{letters}{grade_text}"
    hole = letters != letters.lower()
    l = letters.lower()
    grade = -1 if grade_text == "01" else int(grade_text)
    if not (0 < size <= 3150):
        raise ValueError(f"{name}: ISO 286 gives sizes over 0 up to 3150 mm, not {_fmt(size)} mm")
    g = _row_at("iso-286-1-grades", size)
    it = g.get("it01" if grade_text == "01" else f"it{grade_text}") if g else None
    if it is None:
        raise ValueError(f"{name}: the grade IT{grade_text} is not defined at {_fmt(size)} mm (IT01 and IT0 go up to 500 mm)")
    if grade >= 14 and size <= 1:
        raise ValueError(f"{name}: the grades IT14 to IT18 are not used at 1 mm and below (ISO 286-1)")
    if l in ("a", "b") and size <= 1:
        raise ValueError(f"{name}: the deviations a and b are not used at 1 mm and below (ISO 286-1)")
    IT = it
    if l == "js":
        return {"upper": IT / 2, "lower": -IT / 2}
    d = _row_at("iso-286-1-deviations", size)
    none = ValueError(f"{name}: ISO 286-1 gives no fundamental deviation {letters} at {_fmt(size)} mm")
    if l in _UPPER_LETTERS:
        if d.get(l) is None:
            raise none
        return {"upper": -d[l] + IT, "lower": -d[l]} if hole else {"upper": d[l], "lower": d[l] - IT}
    if l == "j":
        k = f"holeJ{grade}" if hole else ("j5" if grade in (5, 6) else f"j{grade}")
        if d.get(k) is None:
            gives = "J6, J7 and J8" if hole else "j5, j6 and j7 (j8 to 3 mm)"
            raise ValueError(f"{name}: ISO 286-2 gives {gives} up to 500 mm, not {name} at {_fmt(size)} mm")
        return {"upper": d[k], "lower": d[k] - IT} if hole else {"upper": d[k] + IT, "lower": d[k]}
    if not hole:
        if l == "k":
            ei = d["k"] if 4 <= grade <= 7 else 0
        elif d.get(l) is None:
            raise none
        else:
            ei = d[l]
        return {"upper": ei + IT, "lower": ei}
    delta = d[f"delta{grade}"] if size <= 500 and 3 <= grade <= 8 else 0
    if l == "k":
        es = -d["k"] + delta if size <= 500 and grade <= 8 else 0
    elif l == "m":
        es = -9 if 250 < size <= 315 and grade == 6 else -d["m"] + (delta if grade <= 8 else 0)
    elif l == "n":
        es = 0 if 3 < size <= 500 and grade > 8 else -d["n"] + (delta if grade <= 8 else 0)
    else:
        if d.get(l) is None:
            raise none
        es = -d[l] + (delta if grade <= 7 else 0)
    return {"upper": es, "lower": es - IT}


def _class_deviations(name: str, size: float) -> Dict[str, Any]:
    """A class's deviations at a size, in millimetres, with the source they were read from. Raises when it has none."""
    text = name.strip()
    ring = _BEARING.match(text)
    if ring:
        rows = [r for r in TOLERANCE_TABLES.get("iso-492-normal", []) if str(r["ring"]) == ring.group(1).lower()]
        row = next((r for r in rows if r["overMm"] < size <= r["uptoMm"]), None)
        if row is None:
            raise ValueError(f"{text} is tabled over {_fmt(min(r['overMm'] for r in rows))} up to {_fmt(max(r['uptoMm'] for r in rows))} mm, not at {_fmt(size)} mm")
        return {"upper": row["upperUm"] / 1000, "lower": row["lowerUm"] / 1000, "source": row.get("source", "")}
    general = _GENERAL.match(text)
    if general:
        c = general.group(1).lower()
        row = _row_at("iso-2768-1", size, lambda r: str(r["class"]) == c)
        if row is None:
            raise ValueError(f"ISO 2768-{c} gives no deviation at {_fmt(size)} mm")
        return {"upper": row["deviationMm"], "lower": -row["deviationMm"], "source": row["source"]}
    # A shaft's class is all small letters; a hole's all capitals.
    m = _ISO286.match(text) or (_ISO286.match(text.upper()) if text == text.lower() else None)
    if not m:
        raise ValueError(f'there is no tolerance class "{name}": a class is {_KNOWN}')
    um = _iso286(m.group(1).lower() if text == text.lower() else m.group(1), m.group(2), size)
    return {"upper": _round(um["upper"] / 1000), "lower": _round(um["lower"] / 1000), "source": _ISO286_SOURCE}


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
        dev = _class_deviations(name, nominal)
        upper, lower = dev["upper"], dev["lower"]
        out = {"nominal": nominal, "upper": upper, "lower": lower, "min": _round(nominal + lower), "max": _round(nominal + upper), "class": name}
        if dev["source"]:
            out["source"] = dev["source"]
        return out
    return {"nominal": nominal, "upper": tol["upper"], "lower": tol["lower"], "min": _round(nominal + tol["lower"]), "max": _round(nominal + tol["upper"])}


def fit_of(hole: Dict[str, Any], shaft: Dict[str, Any]) -> Dict[str, Any]:
    """The fit of a hole and a shaft: clearance when the smallest hole takes the largest shaft (a minimum clearance of 0
    counts), interference when the largest hole is smaller than the smallest shaft, else transition."""
    min_c = hole["min"] - shaft["max"]
    max_c = hole["max"] - shaft["min"]
    kind = "clearance" if min_c >= -1e-9 else "interference" if max_c <= 1e-9 else "transition"
    return {"kind": kind, "minClearance": _round(min_c), "maxClearance": _round(max_c)}
