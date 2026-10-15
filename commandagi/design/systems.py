"""Systems, declared in Python: requirements (``.req.py``), a system's budgets (``.system.py``) and an interface between
two parts (``.interface.py``), the same documents and the same elements as the TypeScript SDK's JSX (``commandagi/design``
``systems.ts``)::

    from commandagi.design.systems import requirements, requirement

    result = requirements(
        requirement(id="mass", text="The rover weighs at most 500 g.", method="analysis",
                    verified_by="Rover.system.py#mass", design=["cad/Rover.3d.py"]),
        name="Rover",
    )

    from commandagi.design.systems import system, mode, rail, load, bom, budget

    result = system(
        mode(id="drive"),
        rail(id="vbat", voltage=7.4, source="2S Li-ion, nominal"),
        load(id="motors", part="M1 M2", rail="vbat", mode="drive", current=1.2, source="motor datasheet"),
        bom(ref="bom.csv"),
        budget(id="drive-power", quantity="power", rail="vbat", mode="drive", limit=15, unit="W", margin=0.2),
        budget(id="cost-100", quantity="cost", per=100, currency="USD", limit=40, design="Rover.3d.py"),
        name="Rover",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``verified_by`` is ``verifiedBy``). A requirement is named by a ref, never by an id alone
(``Rover.req.py#mass``). Nothing adds a default. A ``bom`` gives masses; a cost budget reads the logistics roll-up of
the design it names (``design``: a 3D document, a schematic or a board with a cost check), the one source of cost, so
no contribution is a cost. The checks are the host's (``commandagi check``, ``commandagi trace``).
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

VERIFICATION_METHODS = ["test", "analysis", "inspection", "demonstration"]
BUDGET_QUANTITIES = ["mass", "power", "cost", "thermal"]
SYSTEM_CHECK_KINDS = ["interface", "trace"]
SIDE_KINDS = ["circuit", "3d", "firmware"]

REQUIREMENT_FIELDS = ["id", "text", "rationale", "method", "verifiedBy", "design", "parent"]
MODE_FIELDS = ["id", "description"]
RAIL_FIELDS = ["id", "voltage", "description", "source"]
CONVERTER_FIELDS = ["id", "input", "output", "efficiency", "source"]
LOAD_FIELDS = ["id", "part", "rail", "mode", "current", "power", "voltage", "source"]
CONTRIBUTION_FIELDS = ["id", "quantity", "part", "value", "unit", "qty", "mode", "rail", "source"]
BUDGET_FIELDS = ["id", "quantity", "limit", "unit", "mode", "rail", "per", "currency", "design", "resistance", "margin", "source",
                 "description"]
PIN_FIELDS = ["number", "signal", "dir", "voltage", "gpio", "at", "required", "description"]
HOLE_FIELDS = ["id", "at", "diameter", "description"]
MESSAGE_FIELDS = ["id", "text", "code", "define", "dir", "description"]
PARAM_FIELDS = ["id", "value", "unit", "description"]
SIDE_FIELDS = ["id", "ref", "kind", "part", "parts", "origin", "defines", "pins", "params", "files", "description"]

_CHILDREN = {"holds": "children"}
#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "requirements": _CHILDREN, "requirement": {},
    "system": _CHILDREN, "mode": {}, "rail": {}, "converter": {}, "load": {}, "contribution": {}, "bom": {}, "budget": {}, "check": {},
    "interface": _CHILDREN, "frame": {}, "pin": {}, "hole": {}, "message": {}, "param": {}, "side": {},
}

__all__ = ["VERIFICATION_METHODS", "BUDGET_QUANTITIES", "SYSTEM_CHECK_KINDS", "SIDE_KINDS", "SIGNATURES",
           "REQUIREMENTS_VOCABULARY", "SYSTEM_VOCABULARY", "INTERFACE_VOCABULARY", *define(globals(), "systems", SIGNATURES)]


def _own(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: o[k] for k in keys if k in o}


def _where(tag: str, key: str, a: Dict[str, Any]) -> str:
    return f"<{tag} {key}={json.dumps(a[key], ensure_ascii=False)}>" if key in a else f"<{tag}>"


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _refs(v: Any) -> bool:
    return isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))


def _pair(v: Any, n: int) -> bool:
    return isinstance(v, list) and len(v) == n and all(_num(x) for x in v)


def _check(cond: Any, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _lists(children: List[DocTree], by_tag: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for c in children:
        out.setdefault(by_tag[c["tag"]], []).append(dict(c["attrs"]))
    return out


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


def _requirements(t: DocTree) -> Dict[str, Any]:
    for c in t["children"]:
        a = c["attrs"]
        at = _where("requirement", "id", a)
        _check(isinstance(a.get("id"), str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", a["id"]),
               f'{at}: id is letters, digits, ".", "_" and "-" (a ref names it as <file>#<id>)')
        _check(isinstance(a.get("text"), str) and a["text"].strip(), f"{at}: text says what is required")
        _check("method" not in a or a["method"] in VERIFICATION_METHODS,
               f"{at}: method must be one of {', '.join(VERIFICATION_METHODS)} (got {json.dumps(a.get('method'))})")
        for k in ("verifiedBy", "design"):
            _check(k not in a or _refs(a[k]), f"{at}: {k} is a ref or a list of refs")
        _check("parent" not in a or isinstance(a["parent"], str), f"{at}: parent is a ref to the requirement this one is derived from")
    return {**_own(t["attrs"], ["name", "description"]), **_lists(t["children"], {"requirement": "requirements"})}


_SYSTEM_LISTS = {"mode": "modes", "rail": "rails", "converter": "converters", "load": "loads", "contribution": "contributions",
                 "bom": "boms", "budget": "budgets", "check": "checks"}


def _system(t: DocTree) -> Dict[str, Any]:
    for c in t["children"]:
        a, tag = c["attrs"], c["tag"]
        at = _where(tag, "ref" if tag == "bom" else "id", a)
        if tag == "rail":
            _check(_num(a.get("voltage")), f"{at}: voltage is a number of volts")
        if tag == "converter":
            e = a.get("efficiency")
            _check(_num(e) and 0 < e <= 1, f"{at}: efficiency is a number in (0, 1] (0.88 for 88 %)")
        if tag == "load":
            _check("current" in a or "power" in a, f"{at}: a load states its current (A) or its power (W)")
            for k in ("current", "power", "voltage"):
                _check(k not in a or _num(a[k]), f"{at}: {k} is a number")
        if tag == "contribution":
            _check(a.get("quantity") in BUDGET_QUANTITIES,
                   f"{at}: quantity must be one of {', '.join(BUDGET_QUANTITIES)} (got {json.dumps(a.get('quantity'))})")
            _check(a.get("quantity") != "cost",
                   f"{at}: a cost is stated in the design's logistics (a part's suppliers, a made part's rate), which a cost "
                   "budget's design rolls up, not as a contribution")
            _check(_num(a.get("value")), f"{at}: value is a number")
            _check(isinstance(a.get("source"), str) and a["source"].strip(),
                   f'{at}: source says where the number was read (a datasheet, a measurement, "estimate: …")')
        if tag == "budget":
            _check(a.get("quantity") in BUDGET_QUANTITIES,
                   f"{at}: quantity must be one of {', '.join(BUDGET_QUANTITIES)} (got {json.dumps(a.get('quantity'))})")
            _check(_num(a.get("limit")), f"{at}: limit is a number")
            m = a.get("margin")
            _check("margin" not in a or (_num(m) and 0 <= m < 1), f"{at}: margin is a fraction of the limit kept free, in [0, 1)")
            if a.get("quantity") == "power":
                _check(isinstance(a.get("rail"), str) and isinstance(a.get("mode"), str), f"{at}: a power budget names its rail and its mode")
            if a.get("quantity") == "cost":
                _check(isinstance(a.get("design"), str) and a["design"].strip(),
                       f'{at}: a cost budget names the design whose logistics roll-up it reads (design="cad/Assembly.3d.py")')
            if a.get("quantity") == "thermal":
                _check(isinstance(a.get("mode"), str) and _num(a.get("resistance")),
                       f"{at}: a thermal budget names its mode and the thermal resistance to the ambient (resistance, K/W)")
        if tag == "check":
            _check(a.get("kind") in SYSTEM_CHECK_KINDS,
                   f"{at}: kind must be one of {', '.join(SYSTEM_CHECK_KINDS)} (got {json.dumps(a.get('kind'))})")
    return {**_own(t["attrs"], ["name", "description"]), **_lists(t["children"], _SYSTEM_LISTS)}


_INTERFACE_LISTS = {"pin": "pins", "hole": "holes", "message": "messages", "param": "params", "side": "sides"}


def _interface(t: DocTree) -> Dict[str, Any]:
    frame = None
    for c in t["children"]:
        a, tag = c["attrs"], c["tag"]
        at = _where(tag, "number" if tag == "pin" else "id", a)
        if tag == "frame":
            frame = dict(a)
            _check(a.get("unit", "mm") == "mm", f'{at}: positions are in mm (unit "mm")')
        if tag == "pin":
            n = a.get("number")
            _check(isinstance(n, int) and not isinstance(n, bool) and n > 0, f"{at}: number is the pin's number, 1, 2, 3 …")
            _check("at" not in a or _pair(a["at"], 2), f"{at}: at is [x, y] mm in the interface's frame")
            _check("gpio" not in a or (isinstance(a["gpio"], int) and not isinstance(a["gpio"], bool)),
                   f"{at}: gpio is the GPIO number of the pin on the side that has one")
            _check("required" not in a or isinstance(a["required"], bool), f"{at}: required is true or false")
        if tag == "hole":
            _check(_pair(a.get("at"), 2), f"{at}: at is [x, y] mm in the interface's frame")
            _check("diameter" not in a or _num(a["diameter"]), f"{at}: diameter is mm")
        if tag == "message":
            _check("text" in a or "code" in a, f"{at}: a message has its text, its code, or both")
        if tag == "param":
            _check(_num(a.get("value")), f"{at}: value is a number (its unit in unit)")
        if tag == "side":
            _check("kind" not in a or a["kind"] in SIDE_KINDS,
                   f"{at}: kind must be one of {', '.join(SIDE_KINDS)} (got {json.dumps(a.get('kind'))})")
            _check("origin" not in a or _pair(a["origin"], 2) or _pair(a["origin"], 3),
                   f"{at}: origin is where the interface's frame sits in this side's frame, [x, y] or [x, y, z] mm")
            _check("parts" not in a or (isinstance(a["parts"], list) and all(isinstance(p, str) for p in a["parts"])),
                   f"{at}: parts is a list of part references, whose pins are the interface's in turn")
    rest = [c for c in t["children"] if c["tag"] != "frame"]
    return {**_own(t["attrs"], ["name", "description"]), **({"frame": frame} if frame is not None else {}), **_lists(rest, _INTERFACE_LISTS)}


REQUIREMENTS_VOCABULARY = Vocabulary("requirements", "a requirements document", "requirements", {
    "requirements": {"parents": [], "attrs": ["name", "description"]},
    "requirement": {"parents": ["requirements"], "key": "id", "required": ["id", "text"], "attrs": REQUIREMENT_FIELDS},
}, _requirements, _never, lambda name: {"name": name})

SYSTEM_VOCABULARY = Vocabulary("system", "a system", "system", {
    "system": {"parents": [], "attrs": ["name", "description"]},
    "mode": {"parents": ["system"], "key": "id", "required": ["id"], "attrs": MODE_FIELDS},
    "rail": {"parents": ["system"], "key": "id", "required": ["id", "voltage"], "attrs": RAIL_FIELDS},
    "converter": {"parents": ["system"], "key": "id", "required": ["id", "input", "output", "efficiency"], "attrs": CONVERTER_FIELDS},
    "load": {"parents": ["system"], "key": "id", "required": ["id", "part", "rail", "mode"], "attrs": LOAD_FIELDS},
    "contribution": {"parents": ["system"], "key": "id", "required": ["id", "quantity", "part", "value"], "attrs": CONTRIBUTION_FIELDS},
    "bom": {"parents": ["system"], "key": "ref", "required": ["ref"], "attrs": ["ref"]},
    "budget": {"parents": ["system"], "key": "id", "required": ["id", "quantity", "limit"], "attrs": BUDGET_FIELDS},
    "check": {"parents": ["system"], "key": "id", "required": ["id", "kind", "of"], "attrs": ["id", "kind", "of"]},
}, _system, _never, lambda name: {"name": name})

INTERFACE_VOCABULARY = Vocabulary("interface", "an interface", "interface", {
    "interface": {"parents": [], "attrs": ["name", "description"]},
    "frame": {"parents": ["interface"], "single": True, "attrs": ["description", "unit"]},
    "pin": {"parents": ["interface"], "key": "number", "required": ["number", "signal"], "attrs": PIN_FIELDS},
    "hole": {"parents": ["interface"], "key": "id", "required": ["id", "at"], "attrs": HOLE_FIELDS},
    "message": {"parents": ["interface"], "key": "id", "required": ["id"], "attrs": MESSAGE_FIELDS},
    "param": {"parents": ["interface"], "key": "id", "required": ["id", "value"], "attrs": PARAM_FIELDS},
    "side": {"parents": ["interface"], "key": "id", "required": ["id", "ref"], "attrs": SIDE_FIELDS},
}, _interface, _never, lambda name: {"name": name})

for _v in (REQUIREMENTS_VOCABULARY, SYSTEM_VOCABULARY, INTERFACE_VOCABULARY):
    register_vocabulary(_v, "systems")
