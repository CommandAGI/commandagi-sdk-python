"""Records, declared in Python: a market contract (``.contract.py``) and a product instance (``.instance.py``), which are
signed, a hardware release (``.release.py``: ``release(file(…), check(…), output(…), id=…, rev=…, of=…, frozen=…)``) and a
unit's calibration (``.calibration.py``: ``calibration(joint(…), rezero(…), device=…, serial=…)``), the
same documents and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``records.ts``)::

    from commandagi.design.records import contract, event, instance, party

    result = contract(
        party(principal="u-1", role="offeror", sig="ed25519:…", signed_at=1780765664000),
        id="c-1",
        terms={"subject": {...}, "title": "Bench time", "schedule": None, ...},
        created_at=1780765664000,
    )
    result = instance(
        event(seq=0, kind="manufacture", at=1772409600000, prev=None, by="org-acme", sig="ed25519:…"),
        serial="ACME-FU-0031",
        product_id="fleet-unit",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``created_at`` is ``createdAt``). These records are SIGNED, so nothing is rewritten: a contract's ``terms`` is
one value (the object the parties sign; a ``None`` inside it is JSON's null and is kept), times are epoch
milliseconds, signatures as they are. A contract's parties are ``party`` children in order; an instance's chain is
``event`` children, oldest first (``seq`` 0, 1, 2 …). A run gives back ``{"format", "document", "sources"}`` beside an
empty graph; ``sources`` names each element's call by its path (``""``, ``party@0``, ``event#0``).
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

CONTRACT_FIELDS = ["id", "terms", "createdAt"]
INSTANCE_FIELDS = ["serial", "productId", "model", "release"]
INSTANCE_EVENT_FIELDS = ["seq", "kind", "at", "prev", "by", "to", "contractRef", "attestationRef", "data", "sig"]
RELEASE_FIELDS = ["id", "rev", "of", "frozen", "product", "createdAt", "by", "note", "previous"]
RELEASE_FILE_FIELDS = ["path", "digest"]
RELEASE_CHECK_FIELDS = ["file", "id", "kind", "status", "accepted", "reason"]
RELEASE_OUTPUT_FIELDS = ["path", "digest", "from", "kind"]
RELEASE_CHECK_STATUSES = ["passed", "failed", "skipped", "accepted"]
#: A unit's calibration: the definition it calibrates (a ref), the unit's serial, a note.
CALIBRATION_FIELDS = ["device", "serial", "note"]
#: One calibrated joint: its zero (rad, what its encoder reads at the chain's zero), its servo's gains, the run that
#: measured them.
CALIBRATION_JOINT_FIELDS = ["name", "zero", "kp", "kv", "run"]
#: One re-zero: the joint, its new zero (rad), when (epoch ms), who (person:<id> | agent:<id>), why.
REZERO_FIELDS = ["joint", "zero", "at", "by", "reason"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "contract": {"holds": "children"},
    "party": {},
    "instance": {"holds": "children"},
    "event": {},
    "release": {"holds": "children"},
    "file": {},
    "check": {},
    "output": {},
    "calibration": {"holds": "children"},
    "joint": {},
    "rezero": {},
}

__all__ = ["CONTRACT_FIELDS", "INSTANCE_FIELDS", "INSTANCE_EVENT_FIELDS", "RELEASE_FIELDS", "RELEASE_FILE_FIELDS",
           "RELEASE_CHECK_FIELDS", "RELEASE_OUTPUT_FIELDS", "RELEASE_CHECK_STATUSES", "CALIBRATION_FIELDS",
           "CALIBRATION_JOINT_FIELDS", "REZERO_FIELDS", "SIGNATURES", "CONTRACT_VOCABULARY", "INSTANCE_VOCABULARY",
           "RELEASE_VOCABULARY", "CALIBRATION_VOCABULARY", "RECORDS", *define(globals(), "records", SIGNATURES)]


def _own(o: Dict[str, Any], keys: Any = None) -> Dict[str, Any]:
    """The fields of a record that it has (None, "" and [] are fields, and are kept)."""
    return {k: o[k] for k in (keys if keys is not None else o) if k in o}


def _contract(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    terms, created = a.get("terms"), a.get("createdAt")
    if not isinstance(terms, dict):
        raise ValueError(f'<contract id="{a.get("id")}">: terms is the object the parties sign')
    if isinstance(created, bool) or not isinstance(created, int):
        raise ValueError(f'<contract id="{a.get("id")}">: createdAt is epoch milliseconds, not {created!r}')
    return {"id": a["id"], "terms": terms, "parties": [dict(c["attrs"]) for c in t["children"]], "createdAt": created}


def _instance(t: DocTree) -> Dict[str, Any]:
    events = [dict(c["attrs"]) for c in t["children"]]
    for i, e in enumerate(events):
        if e.get("seq") != i or isinstance(e.get("seq"), bool):
            raise ValueError(f"<event seq={{{e.get('seq')!r}}}> is event {i} of the chain: events are written oldest first, seq 0, 1, 2 …")
    return {**_own(t["attrs"], INSTANCE_FIELDS), "events": events}


def _release(t: DocTree) -> Dict[str, Any]:
    at = f'<release rev="{t["attrs"].get("rev")}">'
    listed = {tag: [dict(c["attrs"]) for c in t["children"] if c["tag"] == tag] for tag in ("file", "check", "output")}
    for f in listed["file"] + listed["output"]:
        digest = f.get("digest")
        if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError(f"{at}: {f.get('path')}'s digest is its content's SHA-256 in hex (64 characters), not {digest!r}")
    for c in listed["check"]:
        if c.get("status") not in RELEASE_CHECK_STATUSES:
            raise ValueError(f"{at}: check {c.get('id')} of {c.get('file')}: status is {', '.join(RELEASE_CHECK_STATUSES)}, not {c.get('status')!r}")
    frozen = t["attrs"].get("frozen")
    if not isinstance(frozen, str) or not frozen or frozen.startswith("/") or any(p in ("", ".", "..") for p in frozen.split("/")):
        raise ValueError(f"{at}: frozen is a folder beside the record (files, files/<the folder's names>), not {frozen!r}")
    created = t["attrs"].get("createdAt")
    if created is not None and (isinstance(created, bool) or not isinstance(created, int)):
        raise ValueError(f"{at}: createdAt is epoch milliseconds, not {created!r}")
    return {**_own(t["attrs"], RELEASE_FIELDS), "files": listed["file"], "checks": listed["check"], "outputs": listed["output"]}


def _finite(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _json(v: Any) -> str:
    """A value as the TypeScript SDK's message writes it (JSON; undefined for a missing one)."""
    return "undefined" if v is None else json.dumps(v)


def _calibration(t: DocTree) -> Dict[str, Any]:
    listed = {tag: [dict(c["attrs"]) for c in t["children"] if c["tag"] == tag] for tag in ("joint", "rezero")}
    for j in listed["joint"]:
        at = f'<joint name="{j.get("name")}">'
        if "zero" in j and not _finite(j["zero"]):
            raise ValueError(f"{at}: zero is radians, not {_json(j['zero'])}")
        if "kp" in j and not (_finite(j["kp"]) and j["kp"] > 0):
            raise ValueError(f"{at}: kp is a positive number (N·m/rad), not {_json(j['kp'])}")
        if "kv" in j and not (_finite(j["kv"]) and j["kv"] >= 0):
            raise ValueError(f"{at}: kv is a number of at least 0 (N·m·s/rad), not {_json(j['kv'])}")
    last = -math.inf
    for r in listed["rezero"]:
        at = f'<rezero joint="{r.get("joint")}">'
        if not _finite(r.get("zero")):
            raise ValueError(f"{at}: zero is radians, not {_json(r.get('zero'))}")
        when = r.get("at")
        if not (_finite(when) and float(when).is_integer()):
            raise ValueError(f"{at}: at is epoch milliseconds, not {_json(when)}")
        if not isinstance(r.get("by"), str) or not re.match(r"^(person|agent):.+", r["by"]):
            raise ValueError(f"{at}: by is person:<id> or agent:<id>, not {_json(r.get('by'))}")
        if when < last:
            raise ValueError(f"{at}: the re-zeros are oldest first, and this one is older than the one before it")
        last = when
    return {**_own(t["attrs"], CALIBRATION_FIELDS), "joints": listed["joint"], "rezeros": listed["rezero"]}


def _calibration_tree(d: Dict[str, Any]) -> DocTree:
    def leaf(tag: str, o: Dict[str, Any], keys: Any) -> DocTree:
        return {"tag": tag, "attrs": _own(o, keys), "children": []}
    return {"tag": "calibration", "attrs": _own(d, CALIBRATION_FIELDS),
            "children": [leaf("joint", j, CALIBRATION_JOINT_FIELDS) for j in d.get("joints") or []]
            + [leaf("rezero", r, REZERO_FIELDS) for r in d.get("rezeros") or []]}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


CONTRACT_VOCABULARY = Vocabulary("contract", "a contract record", "contract", {
    "contract": {"parents": [], "required": ["id", "terms", "createdAt"], "attrs": CONTRACT_FIELDS},
    # A party's fields are the record's as stored (principal, role, actedBy, agent, sig, signedAt, …): any.
    "party": {"parents": ["contract"], "required": ["principal", "role"]},
}, _contract, _never)

INSTANCE_VOCABULARY = Vocabulary("instance", "a product instance", "instance", {
    "instance": {"parents": [], "required": ["serial", "productId"], "attrs": INSTANCE_FIELDS},
    "event": {"parents": ["instance"], "key": "seq", "required": ["seq", "kind", "at", "by"], "attrs": INSTANCE_EVENT_FIELDS},
}, _instance, _never)

RELEASE_VOCABULARY = Vocabulary("release", "a hardware release", "release", {
    "release": {"parents": [], "required": ["id", "rev", "of", "frozen"], "attrs": RELEASE_FIELDS},
    "file": {"parents": ["release"], "key": "path", "required": ["path", "digest"], "attrs": RELEASE_FILE_FIELDS},
    "check": {"parents": ["release"], "required": ["file", "id", "kind", "status"], "attrs": RELEASE_CHECK_FIELDS},
    "output": {"parents": ["release"], "key": "path", "required": ["path", "digest"], "attrs": RELEASE_OUTPUT_FIELDS},
}, _release, _never)

#: A unit's calibration (``<name>.calibration.py``): what one physical unit measures off its definition. A unit of a world
#: names it (``unit(calibration="arm.calibration.py", …)``). Each ``joint`` holds the joint's zero and its servo's gains
#: as this unit has them; each ``rezero`` is an event of the unit, oldest first. A joint's zero is its newest re-zero's,
#: else its ``joint``'s. A re-zero is appended, never edited::
#:
#:     calibration(
#:         joint(name="shoulder_lift", zero=0.012, kp=12, kv=0.6, run="runs/2026-10-30-lift/run.json"),
#:         rezero(joint="shoulder_lift", zero=0.015, at=1793318400000, by="person:owner", reason="motor replaced"),
#:         device="../../devices/so101-follower-arm/definition.tsx", serial="SO101-0007",
#:     )
CALIBRATION_VOCABULARY = Vocabulary("calibration", "a unit's calibration", "calibration", {
    "calibration": {"parents": [], "required": ["device"], "attrs": CALIBRATION_FIELDS},
    "joint": {"parents": ["calibration"], "key": "name", "required": ["name"], "attrs": CALIBRATION_JOINT_FIELDS},
    "rezero": {"parents": ["calibration"], "required": ["joint", "zero", "at", "by"], "attrs": REZERO_FIELDS},
}, _calibration, _calibration_tree, empty=lambda name: {"device": "", "joints": [], "rezeros": []})

for _v in (CONTRACT_VOCABULARY, INSTANCE_VOCABULARY, RELEASE_VOCABULARY, CALIBRATION_VOCABULARY):
    register_vocabulary(_v, "records")

#: The vocabularies of the records, by format.
RECORDS = {"contract": CONTRACT_VOCABULARY, "instance": INSTANCE_VOCABULARY, "release": RELEASE_VOCABULARY,
           "calibration": CALIBRATION_VOCABULARY}
