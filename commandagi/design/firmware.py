"""FIRMWARE RELEASES AND ROLLOUTS IN PYTHON — the same elements, and the same documents, as the TypeScript SDK's JSX
(``commandagi/design`` ``firmware.ts``), one call each.

A firmware release (``<name>.firmware.py``) names one built image by ref and states what it is: its SHA-256 (the
digest a unit reports when it runs it), its SBOM, the device definition it is for and the hardware revisions it
supports. It holds no bytes: the image and the SBOM are files beside it::

    from commandagi.design.firmware import firmware, supports

    result = firmware(
        supports(revision="B"),
        supports(revision="C"),
        version="1.4.0", image="build/cam-002-1.4.0.bin", sha256="9f2c…", size=1203456,
        sbom="build/cam-002-1.4.0.cdx.json", device="../devices/commandagi-cam-002/definition.tsx", security_version=2,
    )

A rollout (``<name>.rollout.py``) pushes one release to the units of one world in stages: a canary share first, then
waves (cumulative percentages, the last one 100). A failure halts the rollout. Nothing retries an update: a retry is a
principal's own recorded command::

    from commandagi.design.firmware import health, rollout, target

    result = rollout(
        health(id="no-crash", channel="state", command={"verb": "read"}, read="crashes", max=0),
        target(unit="cam-1"),
        firmware="cam-002 1.4.0.firmware.tsx", world="worlds/fleet/world.tsx", channel="firmware",
        canary=10, waves=[50, 100], settle_ms=60000,
    )

A firmware's project folder holds ``firmware.py``, the same element without a built image: what the firmware gives,
its channels as a definition writes them, and the revisions it supports. A definition names that folder (or a release
by ``sha256:<hex>``) as its ``firmware``; ``commandagi check <definition>`` holds the two to each other::

    from commandagi.design.firmware import channel, firmware, supports

    result = firmware(supports(revision="A"), channel(id="cam", dir="out", medium="video", format="video"), name="ESP32 camera")

``target(unit=…)``: the units it updates, in that world; none: every unit of the world whose definition is the
release's device. A record is an element and its fields are its attributes (snake_case keywords of the native names:
``security_version`` is ``securityVersion``).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

FIRMWARE_FIELDS = ["name", "version", "image", "sha256", "size", "sbom", "device", "securityVersion", "title", "note"]
#: The fields a release states, all of them (a firmware's declaration in its project states none of them).
FIRMWARE_RELEASE_FIELDS = ["version", "image", "sha256", "sbom", "device"]
ROLLOUT_FIELDS = ["firmware", "world", "channel", "canary", "waves", "settleMs", "title", "note"]
HEALTH_FIELDS = ["id", "channel", "command", "read", "min", "max", "equals", "unit", "timeoutMs"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"firmware": {"holds": "children"}, "supports": {}, "channel": {}, "rollout": {"holds": "children"},
                                         "health": {}, "target": {}}

__all__ = ["FIRMWARE_FIELDS", "FIRMWARE_RELEASE_FIELDS", "ROLLOUT_FIELDS", "HEALTH_FIELDS", "SIGNATURES", "FIRMWARE_VOCABULARY", "ROLLOUT_VOCABULARY", "FIRMWARE",
           *define(globals(), "firmware", SIGNATURES)]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _nothing(v: Any) -> bool:
    """A field's value says nothing (absent, None, "" or []): code does not write it."""
    return v is None or v == "" or (isinstance(v, list) and not v)


def _attrs_of(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: o[k] for k in keys if not _nothing(o.get(k))}


def _list_of(t: DocTree, tag: str) -> List[Dict[str, Any]]:
    return [dict(c["attrs"]) for c in t["children"] if c["tag"] == tag]


def _leaf(tag: str, attrs: Dict[str, Any]) -> DocTree:
    return {"tag": tag, "attrs": attrs, "children": []}


def _firmware(t: DocTree) -> Dict[str, Any]:
    doc = dict(t["attrs"])
    if any(not _nothing(doc.get(k)) for k in FIRMWARE_RELEASE_FIELDS):
        missing = [k for k in FIRMWARE_RELEASE_FIELDS if _nothing(doc.get(k))]
        if missing:
            raise ValueError(f"<firmware> needs {', '.join(missing)}: a release states all of {', '.join(FIRMWARE_RELEASE_FIELDS)}")
        sha = doc.get("sha256")
        if not isinstance(sha, str) or not _SHA256.match(sha):
            raise ValueError(f"<firmware> sha256 is the image's SHA-256 in 64 lowercase hex digits, not {json.dumps(sha, ensure_ascii=False)}")
    elif _nothing(doc.get("name")):
        raise ValueError("<firmware>: a firmware's declaration states its name; a release states version, image, sha256, sbom and device")
    supports, channels = _list_of(t, "supports"), _list_of(t, "channel")
    if supports:
        doc["supports"] = supports
    if channels:
        doc["channels"] = channels
    return doc


def _firmware_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "firmware", "attrs": _attrs_of(d, FIRMWARE_FIELDS),
            "children": [_leaf("supports", {"revision": s["revision"]}) for s in d.get("supports") or []]
            + [_leaf("channel", dict(c)) for c in d.get("channels") or []]}


def _rollout(t: DocTree) -> Dict[str, Any]:
    doc = dict(t["attrs"])
    health, targets = _list_of(t, "health"), _list_of(t, "target")
    if health:
        doc["health"] = health
    if targets:
        doc["targets"] = targets
    return doc


def _rollout_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "rollout", "attrs": _attrs_of(d, ROLLOUT_FIELDS),
            "children": [_leaf("health", _attrs_of(h, HEALTH_FIELDS)) for h in d.get("health") or []]
            + [_leaf("target", {"unit": x["unit"]}) for x in d.get("targets") or []]}


FIRMWARE_VOCABULARY = Vocabulary("firmware", "a firmware", "firmware", {
    "firmware": {"parents": [], "attrs": FIRMWARE_FIELDS},
    "supports": {"parents": ["firmware"], "key": "revision", "required": ["revision"], "attrs": ["revision"]},
    "channel": {"parents": ["firmware"], "key": "id", "required": ["id"]},
}, _firmware, _firmware_tree)

ROLLOUT_VOCABULARY = Vocabulary("rollout", "a firmware rollout", "rollout", {
    "rollout": {"parents": [], "required": ["firmware", "world", "channel", "canary", "waves"], "attrs": ROLLOUT_FIELDS},
    "health": {"parents": ["rollout"], "key": "id", "required": ["id", "channel", "read"], "attrs": HEALTH_FIELDS},
    "target": {"parents": ["rollout"], "key": "unit", "required": ["unit"], "attrs": ["unit"]},
}, _rollout, _rollout_tree)

for _v in (FIRMWARE_VOCABULARY, ROLLOUT_VOCABULARY):
    register_vocabulary(_v, "firmware")

#: The vocabularies of firmware (a declaration or a release) and rollouts, by format.
FIRMWARE = {"firmware": FIRMWARE_VOCABULARY, "rollout": ROLLOUT_VOCABULARY}
