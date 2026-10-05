"""Machine jobs, declared in Python: a machining setup (``.cam.py``) and a slicing setup (``.slice.py``), the same documents
as the TypeScript SDK's JSX (``commandagi/design`` ``fab.ts``), with calls in place of tags. Each call is one record;
its keyword arguments are the record's fields, verbatim (millimetres, the native names); its positional arguments are
its children::

    result = cam(
        stock(materialId="plywood", thicknessMm=6, xMm=90, yMm=70),
        cam_machine(post="grbl", maxSpindleRpm=10000),
        fixture(name="left clamp", xMm=-14, yMm=25, wMm=20, dMm=20, zMm=4),
        operation(id="op-1", op="mill_adaptive", profile="adaptive_wood", params={"toolDiameterMm": 3.175}),
        runs_on(unit="cloud://global/worlds/fab-cell/world.json#cnc-1", channel="gcode", name="cnc 3018 / 01"),
    )
    result = slicing(fab_source(fileId="carrier.stl", name="carrier.stl"), spool(materialId="pla", diameterMm=1.75),
                     profile="fdm_pla_0.20_draft")

A setup's single records are one call each, left out when the native field is null; operations run in the order they
are written. A run gives back the run's one shape (``{"format", "document", "sources"}`` beside an empty graph).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .ontology import Element, _fields

REF_FIELDS = ["fileId", "name"]
STOCK_FIELDS = ["materialId", "thicknessMm", "xMm", "yMm"]
PART_FIELDS = ["footprintXMm", "footprintYMm", "atXMm", "atYMm"]
MACHINE_FIELDS = ["post", "maxSpindleRpm", "maxFeedMmPerMin", "spindlePowerKw"]
FIXTURE_FIELDS = ["name", "xMm", "yMm", "wMm", "dMm", "zMm"]
OPERATION_FIELDS = ["id", "op", "profile", "enabled", "params", "tabs", "region"]
TARGET_FIELDS = ["unit", "channel", "name"]
SPOOL_FIELDS = ["materialId", "diameterMm"]

# tag → (fields, required, single); per root.
_CAM = {
    "source": (REF_FIELDS, REF_FIELDS, True),
    "design": (REF_FIELDS, REF_FIELDS, True),
    "stock": (STOCK_FIELDS, [], True),
    "part": (PART_FIELDS, ["footprintXMm", "footprintYMm"], True),
    "machine": (MACHINE_FIELDS, [], True),
    "fixture": (FIXTURE_FIELDS, FIXTURE_FIELDS, False),
    "operation": (OPERATION_FIELDS, ["id", "op", "profile"], False),
    "runsOn": (TARGET_FIELDS, TARGET_FIELDS, True),
}
_SLICE = {
    "source": (REF_FIELDS, REF_FIELDS, True),
    "design": (REF_FIELDS, REF_FIELDS, True),
    "spool": (SPOOL_FIELDS, [], True),
    "machine": (TARGET_FIELDS, TARGET_FIELDS, True),
}
_NOUN = {"cam": "a machining setup", "slice": "a slicing setup"}


def _record(el: Element, keys: List[str], required: List[str]) -> Dict[str, Any]:
    name = f'<{el.tag} id="{el.attrs["id"]}">' if isinstance(el.attrs.get("id"), str) else f"<{el.tag}>"
    for k in el.attrs:
        if k not in keys:
            raise ValueError(f"{name}: {k} is not read ({', '.join(keys)})")
    for k in required:
        if el.attrs.get(k) is None:
            raise ValueError(f"{name} needs {k}")
    if el.children:
        raise ValueError(f"{name} has no child records")
    return copy.deepcopy(el.attrs)


def _children(root: Element, tags: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    seen: Dict[str, int] = {}
    for c in root.children:
        if c.tag not in tags:
            raise ValueError(f"<{c.tag}> is not a tag of {_NOUN[root.tag]} ({', '.join('<' + t + '>' for t in tags)})")
        keys, required, single = tags[c.tag]
        rec = _record(c, keys, required)
        ident = c.tag if single else (f'{c.tag}#{rec["id"]}' if c.tag == "operation" else None)
        if ident is not None:
            if ident in seen:
                raise ValueError(f"<{root.tag}> has one <{c.tag}>" if single else f'two <{c.tag}> in <{root.tag}> have id "{rec["id"]}"')
            seen[ident] = 1
        if single:
            out[c.tag] = rec
        else:
            out.setdefault(c.tag, []).append(rec)
    return out


def _cam(root: Element) -> Dict[str, Any]:
    if root.attrs:
        raise ValueError(f"<cam>: {next(iter(root.attrs))} is not read")
    kids = _children(root, _CAM)
    doc: Dict[str, Any] = {k: kids[k] for k in ("source", "design", "stock", "part", "machine") if k in kids}
    if kids.get("fixture"):
        doc["fixtures"] = kids["fixture"]
    doc["operations"] = kids.get("operation", [])
    if "runsOn" in kids:
        doc["runsOn"] = kids["runsOn"]
    return doc


def _slice(root: Element) -> Dict[str, Any]:
    doc = _record(Element("slice", root.attrs), ["profile", "params"], ["profile"])
    kids = _children(root, _SLICE)
    for k in ("source", "design", "spool", "machine"):
        if k in kids:
            doc[k] = kids[k]
    return doc


def is_fab_document(value: Any) -> bool:
    """Whether a value is the root record of a machining or a slicing setup."""
    return isinstance(value, Element) and value.tag in ("cam", "slice")


def declare_fab_document(root: Element) -> Dict[str, Any]:
    """The setup a root record declares, in the run's one shape: ``{"format", "document", "sources"}``."""
    if root.tag == "cam":
        return {"format": "cam", "document": _cam(root), "sources": {}}
    if root.tag == "slice":
        return {"format": "slice", "document": _slice(root), "sources": {}}
    raise ValueError(f"<{root.tag}> is not a machining or a slicing setup")


def cam(*records: Element) -> Element:
    """A machining setup (``<name>.cam.py``): its records, operations in the order they run."""
    return Element("cam", {}, records)


def slicing(*records: Element, **fields: Any) -> Element:
    """A slicing setup (``<name>.slice.py``, ``<slice>`` in JSX): ``profile``, ``params`` and its records."""
    return Element("slice", _fields(fields), records)


def fab_source(**fields: Any) -> Element:
    """The file a job is made from (``<source fileId name>``): the STEP of a CAM job, the mesh of a slicing job."""
    return Element("source", _fields(fields))


def fab_design(**fields: Any) -> Element:
    """The 3D document (``.3d.tsx``) the source was exported from (``<design fileId name>``)."""
    return Element("design", _fields(fields))


def stock(**fields: Any) -> Element:
    return Element("stock", _fields(fields))


def cam_part(**fields: Any) -> Element:
    """The part's stated footprint (``<part>`` in a ``<cam>``)."""
    return Element("part", _fields(fields))


def cam_machine(**fields: Any) -> Element:
    """The CAM machine's post and limits (``<machine>`` in a ``<cam>``)."""
    return Element("machine", _fields(fields))


def fixture(**fields: Any) -> Element:
    return Element("fixture", _fields(fields))


def operation(**fields: Any) -> Element:
    return Element("operation", _fields(fields))


def runs_on(**fields: Any) -> Element:
    """The unit and channel a CAM job runs on (``<runsOn>``)."""
    return Element("runsOn", _fields(fields))


def spool(**fields: Any) -> Element:
    return Element("spool", _fields(fields))


def slice_machine(**fields: Any) -> Element:
    """The unit and channel a slicing job prints on (``<machine>`` in a ``<slice>``)."""
    return Element("machine", _fields(fields))
