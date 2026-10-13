"""ENGINEERING TABLES — material grades, standard holes by name and the dimension tables of standard parts. The same
data and the same calls as the TypeScript SDK's ``commandagi/design`` ``standards.ts``::

    from commandagi.design.standards import material, hole_size, standard_row, mass_grams

    material("6061-T6")["densityGCm3"]          # 2.7, with ["source"]: where the number was read
    hole_size("M4 close fit")["diameter"]       # 4.3 (ISO 273 fine)
    hole_size("M4 tap")["diameter"]             # 3.3 (ISO 2306)
    standard_row("iso-4762", "M4")              # {"thread": "M4", "dkMax": 7, "kMax": 4, "s": 3, "tMin": 2, "bRef": 20}
    mass_grams(1200, "6061-T6")                 # 3.24: 1200 mm³ × 2.7 g/cm³

The numbers are data (``standards_data.py``), generated from the shipped tables
(``cloud://global/standards/<table>.csv``, ``cloud://global/materials/engineering.csv``). Each row of a table names its
source, how it was read, by whom and when; ``STANDARD_SOURCES[table]`` and a material's ``source`` carry the source's
name here.

A name the tables do not have is refused with the names they do have. Nothing is computed in its place.

A 3D document uses them by name: ``hole(size="M4 close fit")`` has that diameter, and
``body(engineering={"material": "6061-T6"})`` has that density, so an observation of the document says the body's
mass. A materials table of your own (``materials/<name>.csv`` beside the document or in a folder above it) is read
before the shipped one: pass its rows as ``tables``.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence

from .standards_data import HOLE_SIZES, MATERIALS, STANDARD_SOURCES, STANDARD_TABLES

__all__ = ["HOLE_FITS", "HOLE_SIZES", "MATERIALS", "STANDARD_SOURCES", "STANDARD_TABLES", "hole_size", "mass_grams", "material",
           "sized_hole", "standard_row"]

#: What a hole's ``size`` says after its thread.
HOLE_FITS: List[str] = ["close fit", "normal fit", "loose fit", "tap"]


def _norm(i: str) -> str:
    return re.sub(r"[\s_]+", "-", i.strip().lower())


def _number(n: Any) -> str:
    """A number as JavaScript writes it in a message (4.5, 6)."""
    return str(int(n)) if isinstance(n, float) and n.is_integer() else str(n)


def material(id: str, tables: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """The row a material id names: the nearest of ``tables`` (your own tables, nearest first), then the shipped table."""
    want = _norm(id)
    for m in [*tables, *MATERIALS]:
        if _norm(m["id"]) == want:
            return m
    raise ValueError(f'no materials table has a row "{id}" (the shipped table has {", ".join(m["id"] for m in MATERIALS)})')


def mass_grams(volume_mm3: float, material_id: str, tables: Sequence[Dict[str, Any]] = ()) -> float:
    """The mass in grams of a solid of ``volume_mm3`` made of a material: volume × density (1 g/cm³ is 1 g per 1000 mm³)."""
    return (volume_mm3 / 1000) * material(material_id, tables)["densityGCm3"]


def hole_size(name: str) -> Dict[str, Any]:
    """The hole a name says: a thread and a fit, "M4 close fit", "M4 normal fit", "M4 loose fit" (the clearance holes of
    ISO 273 fine, medium and coarse; ASME B18.2.8 for an inch thread), or "M4 tap" (the drill before tapping):
    ``{"thread", "fit", "diameter", "row", "source"}``, millimetres."""
    text = re.sub(r"\s+", " ", name.strip())
    thread, _, rest = text.partition(" ")
    fit = rest.lower()
    key = next((k for k in HOLE_SIZES if k.lower() == thread.lower()), None)
    if key is None:
        raise ValueError(f'"{name}": no hole table has the thread {thread or "(none)"} (it has {", ".join(HOLE_SIZES)})')
    row = HOLE_SIZES[key]
    if fit not in HOLE_FITS:
        raise ValueError(f'"{name}": a hole size is a thread and one of {", ".join(HOLE_FITS)} ("{row["thread"]} close fit")')
    if fit == "tap":
        if "tap" not in row:
            raise ValueError(f'"{name}": the tap drill table has no {row["thread"]}')
        return {"thread": row["thread"], "fit": fit, "diameter": row["tap"], "row": row, "source": row["sources"].get("tap", "")}
    return {"thread": row["thread"], "fit": fit, "diameter": row[fit[:-4]], "row": row, "source": row["sources"]["clearance"]}


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sized_hole(hole: Dict[str, Any]) -> Dict[str, Any]:
    """A hole's fields with what its ``size`` says: the diameter, and for a counterbore or a countersink the head the
    tables give for that thread where the hole does not say its own. A countersink's depth follows from its diameter
    and angle. A ``diameter`` that differs from the size's is refused: leave it out, or clear ``size``."""
    if not isinstance(hole.get("size"), str):
        return hole
    named = hole_size(hole["size"])
    if _is_number(hole.get("diameter")) and abs(hole["diameter"] - named["diameter"]) > 1e-9:
        raise ValueError(f'diameter: "{hole["size"]}" is {_number(named["diameter"])} mm (got {_number(hole["diameter"])}); '
                         "leave diameter out, or clear size")
    out = {**hole, "diameter": named["diameter"]}
    if named["fit"] == "tap":
        return out
    bore: Optional[Dict[str, Any]] = named["row"].get("counterbore")
    sink: Optional[Dict[str, Any]] = named["row"].get("countersink")
    if hole.get("style") == "counterbore" and bore:
        out["headDiameter"] = hole["headDiameter"] if hole.get("headDiameter") is not None else bore["diameter"]
        out["headDepth"] = hole["headDepth"] if hole.get("headDepth") is not None else bore["depth"]
    elif hole.get("style") == "countersink" and sink:
        head = hole["headDiameter"] if _is_number(hole.get("headDiameter")) else sink["diameter"]
        out["headDiameter"] = head
        if hole.get("headDepth") is not None:
            out["headDepth"] = hole["headDepth"]
        else:
            depth = (head - named["diameter"]) / 2 / math.tan(sink["angleDeg"] * math.pi / 360)
            out["headDepth"] = math.floor(depth * 1e4 + 0.5) / 1e4
    return out


def standard_row(table: str, key: str) -> Dict[str, Any]:
    """A row of a dimension table by the value of its first column: ``standard_row("iso-4762", "M4")``,
    ``standard_row("bearings", "608")``. The tables are ``list(STANDARD_TABLES)``."""
    rows = STANDARD_TABLES.get(table)
    if rows is None:
        raise ValueError(f'no table "{table}" (the tables are {", ".join(STANDARD_TABLES)})')
    first = next(iter(rows[0]), "") if rows else ""
    for r in rows:
        if str(r.get(first)).lower() == key.lower():
            return r
    raise ValueError(f'table "{table}" has no row "{key}" (it has {", ".join(str(r.get(first)) for r in rows)})')
