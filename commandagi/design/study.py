"""STUDIES IN PYTHON — a study (``<name>.study.py``) holds the question of an analysis of a part, never the answer: the
same elements as the TypeScript SDK's JSX (``commandagi/design`` ``study.ts``), one call each::

    from commandagi.design.study import criterion, fixture, force, loadCase, material, mesh, study

    result = study(
        material(grade="PETG", poisson=0.38),
        fixture(id="mount", type="fixed", faces={"kind": "face", "select": {"normal": [0, 0, -1]}}),
        loadCase(force(id="grip", faces={"kind": "face", "select": {"farthest": [1, 0, 0]}}, total=[-40, 0, 0]), id="clamp"),
        mesh(order=2, size=2, refine=[1, 0.7, 0.5]),
        criterion(id="safety", quantity="vonMises.max", limit="yield / 2"),
        kind="structural", part="Jaw.3d.tsx", units="mm-N-MPa-t",
    )

One root, ``study(kind=…, part=…, units=…)``, for every kind. A kind adds its own tags (``register_study_kind``); this
module declares ``structural``. ``criterion`` and ``revise`` are every kind's. A record is an element and its fields are
its attributes (snake_case keywords of the native names: ``load_case`` is ``loadCase``). A load's tag is its ``type``.
Nothing adds a default.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .documents import Vocabulary, register_vocabulary
from .element import define

STUDY_UNITS = "mm-N-MPa-t"
STUDY_ROOT_FIELDS = ["kind", "part", "units", "title"]

_FACES = "faces"
#: Each tag: its rule, the field of its parent record it fills, whether a list, whether the tag is the record's type,
#: and its kind (None: every kind's).
_TAGS: Dict[str, Dict[str, Any]] = {
    "criterion": {"rule": {"parents": ["study"], "key": "id", "required": ["id", "quantity", "limit"],
                           "attrs": ["id", "quantity", "limit", "region", "loadCase", "note"]}, "field": "criteria", "list": True},
    "revise": {"rule": {"parents": ["study"], "key": "parameter", "required": ["parameter", "min", "max"],
                        "attrs": ["parameter", "min", "max"]}, "field": "revise", "list": True},
}
STUDY_KINDS: set = set()
_VOCAB_TAGS: Dict[str, Dict[str, Any]] = {"study": {"parents": [], "required": ["kind", "part"], "attrs": STUDY_ROOT_FIELDS}}
for _t, _v in _TAGS.items():
    _VOCAB_TAGS[_t] = _v["rule"]

_HOLDS: Dict[str, Any] = {"holds": "children"}
#: Every tag of a study: what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"study": _HOLDS, "criterion": {}, "revise": {}}


def register_study_kind(kind: str, tags: Dict[str, Dict[str, Any]]) -> None:
    """Add a kind of study and its tags (``{tag: {"rule", "field", "list"?, "typed"?}}``). One tag name means one thing
    in every kind. A tag that holds children (a load case) says so with ``"holds": True``."""
    for tag, t in tags.items():
        was = _TAGS.get(tag)
        if was and (was["field"] != t["field"] or bool(was.get("list")) != bool(t.get("list"))):
            raise ValueError(f"<{tag}> of a {kind} study fills {t['field']}, but it already fills {was['field']}")
        _TAGS[tag] = was or {**t, "kind": kind}
        rule = _VOCAB_TAGS.get(tag)
        _VOCAB_TAGS[tag] = {**rule, "parents": sorted(set(rule["parents"]) | set(t["rule"]["parents"]))} if rule else dict(t["rule"])
        if tag not in SIGNATURES:
            SIGNATURES[tag] = _HOLDS if t.get("holds") else {}
            define(globals(), "study", {tag: SIGNATURES[tag]})
    STUDY_KINDS.add(kind)


def _records_of(children: List[Dict[str, Any]], into: Dict[str, Any]) -> None:
    for c in children:
        t = _TAGS.get(c["tag"])
        if not t:
            continue
        rec = {**({"type": c["tag"]} if t.get("typed") else {}), **c["attrs"]}
        _records_of(c["children"], rec)
        if t.get("list"):
            into.setdefault(t["field"], []).append(rec)
        else:
            into[t["field"]] = rec


def _tags_in(parent: str):
    return [(n, t) for n, t in _TAGS.items() if parent in t["rule"]["parents"]]


def _elements_of(parent: str, rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    done = set()
    for tag, t in _tags_in(parent):
        if t["field"] in done or rec.get(t["field"]) is None:
            continue
        v = rec[t["field"]]
        items = v if t.get("list") else [v]
        if t.get("typed"):
            done.add(t["field"])
        for item in items:
            item_tag = str(item.get("type")) if t.get("typed") else tag
            it = _TAGS.get(item_tag)
            if not it or it["field"] != t["field"]:
                raise ValueError(f"{t['field']}: \"{item_tag}\" is not a tag of a study")
            child_fields = {x["field"] for _, x in _tags_in(item_tag)}
            keys = it["rule"].get("attrs") or list(item)
            attrs = {k: item[k] for k in keys if item.get(k) is not None and not (k == "type" and it.get("typed")) and k not in child_fields}
            out.append({"tag": item_tag, "attrs": attrs, "children": _elements_of(item_tag, item)})
    return out


def _from_tree(t: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(t["attrs"])
    if doc.get("kind") not in STUDY_KINDS:
        raise ValueError(f"<study> kind is one of {', '.join(sorted(STUDY_KINDS))}, not {doc.get('kind')!r}")
    for c in t["children"]:
        k = (_TAGS.get(c["tag"]) or {}).get("kind")
        if k and k != doc["kind"]:
            raise ValueError(f"<{c['tag']}> belongs to a {k} study, not to a {doc['kind']} one")
    _records_of(t["children"], doc)
    return doc


def _to_tree(d: Dict[str, Any]) -> Dict[str, Any]:
    return {"tag": "study", "attrs": {k: d[k] for k in STUDY_ROOT_FIELDS if d.get(k) is not None}, "children": _elements_of("study", d)}


study_vocabulary = Vocabulary(format="study", noun="a study", root="study", tags=_VOCAB_TAGS, from_tree=_from_tree, to_tree=_to_tree,
                              empty=lambda name: {"kind": "structural", "part": "", "units": STUDY_UNITS})

__all__ = ["STUDY_UNITS", "STUDY_ROOT_FIELDS", "STUDY_KINDS", "SIGNATURES", "register_study_kind", "study_vocabulary", "STUDY",
           *define(globals(), "study", SIGNATURES)]

register_study_kind("structural", {
    "material": {"rule": {"parents": ["study"], "single": True, "required": ["grade"], "attrs": ["grade", "body", "poisson"]}, "field": "material"},
    "fixture": {"rule": {"parents": ["study"], "key": "id", "required": ["id", "type", _FACES], "attrs": ["id", "type", _FACES, "region"]}, "field": "fixtures", "list": True},
    "loadCase": {"rule": {"parents": ["study"], "key": "id", "required": ["id"], "attrs": ["id"]}, "field": "loadCases", "list": True, "holds": True},
    "force": {"rule": {"parents": ["loadCase"], "key": "id", "required": ["id", _FACES, "total"], "attrs": ["id", _FACES, "total"]}, "field": "loads", "list": True, "typed": True},
    "pressure": {"rule": {"parents": ["loadCase"], "key": "id", "required": ["id", _FACES, "value"], "attrs": ["id", _FACES, "value"]}, "field": "loads", "list": True, "typed": True},
    "mesh": {"rule": {"parents": ["study"], "single": True, "attrs": ["order", "size", "refine"]}, "field": "mesh"},
    "solver": {"rule": {"parents": ["study"], "single": True, "attrs": ["kind", "analysis", "timeout"]}, "field": "solver"},
})
# A flow study (kind="flow", units="m-kg-s"): the fluid is one body of the part; the inlet's and the outlet's faces are
# picks on it, every other face is a wall (study.ts in the TypeScript SDK says the rest).
register_study_kind("flow", {
    "fluid": {"rule": {"parents": ["study"], "single": True, "required": ["nu"], "attrs": ["nu", "body"]}, "field": "fluid"},
    "inlet": {"rule": {"parents": ["study"], "single": True, "required": [_FACES, "velocity"], "attrs": [_FACES, "velocity"]}, "field": "inlet"},
    "outlet": {"rule": {"parents": ["study"], "single": True, "required": [_FACES], "attrs": [_FACES]}, "field": "outlet"},
    "flowMesh": {"rule": {"parents": ["study"], "single": True, "required": ["cells"], "attrs": ["cells", "levels", "iterations", "wallModel"]}, "field": "flowMesh"},
})
__all__ += [n for n in SIGNATURES if n not in __all__]

register_vocabulary(study_vocabulary, "study")

#: The vocabulary of studies, by format.
STUDY = {"study": study_vocabulary}
