"""MACHINE JOBS IN PYTHON — a machining setup (``.cam.py``) and a slicing setup (``.slice.py``) written as the elements
the 3D app's CAM and slicing modes edit: the same elements as the TypeScript SDK's JSX (``commandagi/design``
``fab.ts``), one call each::

    from commandagi.design.fab import cam, fixture, machine, operation, runsOn, stock

    result = cam(
        stock(material_id="plywood", thickness_mm=6, x_mm=90, y_mm=70),
        machine(post="grbl", max_spindle_rpm=10000, max_feed_mm_per_min=1000, spindle_power_kw=0.3),
        fixture(name="left clamp", x_mm=-14, y_mm=25, w_mm=20, d_mm=20, z_mm=4),
        operation(id="op-1", op="mill_adaptive", profile="adaptive_wood", params={"toolDiameterMm": 3.175}),
        runsOn(unit="cloud://global/worlds/fab-cell/world.tsx#cnc-1", channel="gcode", name="cnc 3018 / 01"),
    )

    from commandagi.design.fab import machine, slice, source, spool

    result = slice(source(file_id="carrier.stl", name="carrier.stl"), spool(material_id="pla", diameter_mm=1.75),
                   profile="fdm_pla_0.20_draft")

The rule of the ontology's files: a record is an element and its fields are its attributes (keywords in snake_case
of the native names: ``thickness_mm`` is ``thicknessMm``; millimetres). A setup's single records (``source``,
``design``, ``stock``, ``part``, ``machine``, ``runsOn``, ``spool``) are one element each, absent when the native field
is null. A CAM operation is an ``operation(id=…)``; the order of the elements is the order the cuts run. An operation's
``params``, ``tabs`` and ``region`` and a slicing setup's ``params`` are attributes whose value is the native object,
written as it is stored (its keys are the native names). Nothing adds a default. A run gives back the run's one shape
(``{"format", "document", "sources"}`` beside an empty graph), each record's call in ``sources`` by its path
(``operation#op-1``, ``stock``).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .documents import Vocabulary, register_vocabulary
from .element import define

CAM_REF_FIELDS = ["fileId", "name"]
CAM_STOCK_FIELDS = ["materialId", "thicknessMm", "xMm", "yMm"]
CAM_PART_FIELDS = ["footprintXMm", "footprintYMm", "atXMm", "atYMm"]
CAM_MACHINE_FIELDS = ["post", "maxSpindleRpm", "maxFeedMmPerMin", "spindlePowerKw"]
CAM_FIXTURE_FIELDS = ["name", "xMm", "yMm", "wMm", "dMm", "zMm"]
CAM_OPERATION_FIELDS = ["id", "op", "profile", "enabled", "params", "tabs", "region"]
#: A unit's channel a job runs on (``runsOn`` of a machining setup, ``machine`` of a slicing setup).
TARGET_FIELDS = ["unit", "channel", "name"]
SPOOL_FIELDS = ["materialId", "diameterMm"]

_HOLDS: Dict[str, Any] = {"holds": "children"}
#: Every tag of the machine jobs: what it holds (the TypeScript SDK's ``SIGNATURES``). ``machine``, ``source`` and
#: ``design`` stand in either root; the root says what their fields are.
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "cam": _HOLDS, "slice": _HOLDS,
    "source": {}, "design": {}, "stock": {}, "part": {}, "machine": {}, "fixture": {}, "operation": {}, "runsOn": {}, "spool": {},
}

__all__ = ["CAM_REF_FIELDS", "CAM_STOCK_FIELDS", "CAM_PART_FIELDS", "CAM_MACHINE_FIELDS", "CAM_FIXTURE_FIELDS",
           "CAM_OPERATION_FIELDS", "TARGET_FIELDS", "SPOOL_FIELDS", "SIGNATURES", "cam_vocabulary", "slice_vocabulary", "FAB",
           *define(globals(), "fab", SIGNATURES)]


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent or null), or an object with no field: code does not write it."""
    return v is None or (isinstance(v, dict) and not v)


def _attrs_of(o: Dict[str, Any], keys: List[str], skip=lambda k, v: False) -> Dict[str, Any]:
    return {k: o[k] for k in keys if not _nothing(o.get(k)) and not skip(k, o.get(k))}


def _one(tag: str, v: Any, keys: List[str]) -> List[Dict[str, Any]]:
    return [{"tag": tag, "attrs": _attrs_of(v, keys), "children": []}] if isinstance(v, dict) else []


def _single(t: Dict[str, Any], tag: str):
    return next((c for c in t["children"] if c["tag"] == tag), None)


_REF = {"attrs": CAM_REF_FIELDS, "required": ["fileId", "name"]}


def _cam_from_tree(t: Dict[str, Any]) -> Dict[str, Any]:
    doc: Dict[str, Any] = {"operations": []}
    for tag in ("source", "design", "stock", "part", "machine"):
        c = _single(t, tag)
        if c:
            doc[tag] = dict(c["attrs"])
    fixtures = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "fixture"]
    if fixtures:
        doc["fixtures"] = fixtures
    doc["operations"] = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "operation"]
    target = _single(t, "runsOn")
    if target:
        doc["runsOn"] = dict(target["attrs"])
    return doc


def _cam_to_tree(d: Dict[str, Any]) -> Dict[str, Any]:
    return {"tag": "cam", "attrs": {}, "children": [
        *_one("source", d.get("source"), CAM_REF_FIELDS),
        *_one("design", d.get("design"), CAM_REF_FIELDS),
        *_one("stock", d.get("stock"), CAM_STOCK_FIELDS),
        *_one("part", d.get("part"), CAM_PART_FIELDS),
        *_one("machine", d.get("machine"), CAM_MACHINE_FIELDS),
        *({"tag": "fixture", "attrs": _attrs_of(f, CAM_FIXTURE_FIELDS), "children": []} for f in d.get("fixtures") or []),
        # An operation is enabled unless it says otherwise (the reader's rule): `enabled` is written only when false.
        *({"tag": "operation", "attrs": _attrs_of(o, CAM_OPERATION_FIELDS, lambda k, v: k == "enabled" and v is True), "children": []}
          for o in d.get("operations") or []),
        *_one("runsOn", d.get("runsOn"), TARGET_FIELDS),
    ]}


cam_vocabulary = Vocabulary(
    format="cam", noun="a machining setup", root="cam",
    tags={
        "cam": {"parents": [], "attrs": []},
        "source": {"parents": ["cam"], "single": True, **_REF},
        "design": {"parents": ["cam"], "single": True, **_REF},
        "stock": {"parents": ["cam"], "single": True, "attrs": CAM_STOCK_FIELDS},
        "part": {"parents": ["cam"], "single": True, "required": ["footprintXMm", "footprintYMm"], "attrs": CAM_PART_FIELDS},
        "machine": {"parents": ["cam"], "single": True, "attrs": CAM_MACHINE_FIELDS},
        "fixture": {"parents": ["cam"], "required": CAM_FIXTURE_FIELDS, "attrs": CAM_FIXTURE_FIELDS},
        "operation": {"parents": ["cam"], "key": "id", "required": ["id", "op", "profile"], "attrs": CAM_OPERATION_FIELDS},
        "runsOn": {"parents": ["cam"], "single": True, "required": TARGET_FIELDS, "attrs": TARGET_FIELDS},
    },
    from_tree=_cam_from_tree, to_tree=_cam_to_tree)


def _slice_from_tree(t: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(t["attrs"])
    for tag in ("source", "design", "spool", "machine"):
        c = _single(t, tag)
        if c:
            doc[tag] = dict(c["attrs"])
    return doc


def _slice_to_tree(d: Dict[str, Any]) -> Dict[str, Any]:
    return {"tag": "slice", "attrs": _attrs_of(d, ["profile", "params"]), "children": [
        *_one("source", d.get("source"), CAM_REF_FIELDS), *_one("design", d.get("design"), CAM_REF_FIELDS),
        *_one("spool", d.get("spool"), SPOOL_FIELDS), *_one("machine", d.get("machine"), TARGET_FIELDS)]}


slice_vocabulary = Vocabulary(
    format="slice", noun="a slicing setup", root="slice",
    tags={
        "slice": {"parents": [], "required": ["profile"], "attrs": ["profile", "params"]},
        "source": {"parents": ["slice"], "single": True, **_REF},
        "design": {"parents": ["slice"], "single": True, **_REF},
        "spool": {"parents": ["slice"], "single": True, "attrs": SPOOL_FIELDS},
        "machine": {"parents": ["slice"], "single": True, "required": TARGET_FIELDS, "attrs": TARGET_FIELDS},
    },
    from_tree=_slice_from_tree, to_tree=_slice_to_tree)

for _v in (cam_vocabulary, slice_vocabulary):
    register_vocabulary(_v, "fab")

#: The vocabularies of machine jobs, by format.
FAB = {"cam": cam_vocabulary, "slice": slice_vocabulary}
