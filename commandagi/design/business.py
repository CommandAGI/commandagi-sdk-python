"""A company, an RFC or a case declared in Python — the same documents the CommandAGI company app and contract editor
open as ``<Name>.company``, ``<name>.rfc`` and ``<name>.case``, and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``business.ts``)::

    from commandagi.design.business import Company, Entity, Books, CapTable, Registration

    result = Company(
        Entity(jurisdiction="US-DE", form="llc", formed="2024-01-31"),
        Books(journal="Northwind/books/main.journal"),
        CapTable(ocf="Northwind/captable/"),
        Registration(kind="tax-id", jurisdiction="US", id="12-3456789"),
        name="Northwind", files=["Northwind/"],
    )

Each call is an element ``{"$$design": "element", "type": "Company", "props": {..., "children": [...]}}``, the node
shape the JSX runtime makes. ``document_of`` reads one into the native document: the ``.company`` itself, or an RFC's
or a case's ``{"id"?, "draft"}``. The standard's parts REF their files (the journal stays hledger, the cap table Open
Cap Table Format). A change's ``parameter`` is the draft's ``key``. An unknown attribute or child is refused by name.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

_TEXT, _TEXTS, _BOOL, _RECORD, _DATA, _AMOUNT = "text", "texts", "bool", "record", "data", "amount"

BUSINESS_TAGS: Dict[str, Dict[str, Any]] = {
    "Company": {"props": {"name": _TEXT, "about": _TEXT, "files": _TEXTS, "dashboard": _TEXT}, "required": ["name"],
                "one": {"entity": "Entity", "books": "Books", "captable": "CapTable", "people": "People", "calendar": "Calendar", "matters": "Matters"},
                "many": {"registrations": "Registration"}},
    "Entity": {"props": {"jurisdiction": _TEXT, "form": _TEXT, "taxClassification": _TEXT, "name": _TEXT, "formed": _TEXT,
                         "fiscalYearEnd": _TEXT, "ids": _RECORD, "operatesIn": _TEXTS, "conditions": _RECORD}, "required": ["jurisdiction"]},
    "Registration": {"props": {"kind": _TEXT, "jurisdiction": _TEXT, "id": _TEXT, "issued": _TEXT, "expires": _TEXT, "file": _TEXT}, "required": ["kind"]},
    "Books": {"props": {"journal": _TEXT}, "required": ["journal"]},
    "CapTable": {"props": {"ocf": _TEXT}, "required": ["ocf"]},
    "People": {"props": {"folder": _TEXT}, "required": ["folder"]},
    "Calendar": {"props": {"folder": _TEXT}, "required": ["folder"]},
    "Matters": {"props": {"folder": _TEXT}, "required": ["folder"]},
    "Rfc": {"props": {"id": _TEXT, "procedure": _TEXT, "title": _TEXT, "body": _TEXT, "target": _TEXT, "engineJson": _TEXT}, "many": {"options": "Option"}},
    "Option": {"props": {"title": _TEXT, "summary": _TEXT}, "many": {"changes": "Change"}},
    "Change": {"props": {"op": _TEXT, "parameter": _TEXT, "value": _TEXT, "dutyId": _TEXT, "title": _TEXT, "text": _TEXT, "protects": _TEXTS,
                         "harm": _TEXT, "elements": _TEXT, "criminal": _BOOL, "kind": _TEXT, "uniqueness": _TEXT, "issuers": _TEXT, "modalities": _TEXTS},
               "required": ["op"]},
    "Case": {"props": {"id": _TEXT, "respondent": _TEXT, "filedFor": _TEXT, "criminal": _BOOL, "source": _TEXT, "dutyId": _TEXT, "article": _TEXT,
                       "agreementId": _TEXT, "term": _TEXT, "act": _TEXT, "actDate": _TEXT, "evidence": _TEXT, "media": _DATA, "reopens": _TEXT},
             "many": {"harms": "Harm", "relief": "Relief"}},
    "Harm": {"props": {"id": _TEXT, "interest": _TEXT, "description": _TEXT, "amount": _AMOUNT}, "required": ["id"]},
    "Relief": {"props": {"kind": _TEXT, "description": _TEXT, "harmIds": _TEXTS, "amount": _AMOUNT, "days": _AMOUNT}, "required": ["kind"]},
}


def _element(tag: str):
    def make(*children: Any, **props: Any) -> Dict[str, Any]:
        p = {k: v for k, v in props.items() if v is not None}
        if children:
            p["children"] = list(children)
        return {"$$design": "element", "type": tag, "props": p}
    make.__name__ = tag
    make.__doc__ = f"A <{tag}> element (commandagi.design.business)."
    return make


Company = _element("Company")
Entity = _element("Entity")
Registration = _element("Registration")
Books = _element("Books")
CapTable = _element("CapTable")
People = _element("People")
Calendar = _element("Calendar")
Matters = _element("Matters")
Rfc = _element("Rfc")
Option = _element("Option")
Change = _element("Change")
Case = _element("Case")
Harm = _element("Harm")
Relief = _element("Relief")


def _is_element(v: Any) -> bool:
    return isinstance(v, dict) and v.get("$$design") == "element"


def _children(c: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if c is None or isinstance(c, bool):
        return out
    if isinstance(c, (list, tuple)):
        for x in c:
            out.extend(_children(x))
        return out
    if _is_element(c):
        return [c]
    raise ValueError("a design element's children are elements")


def _value(tag: str, prop: str, kind: str, v: Any) -> Any:
    def bad(what: str) -> ValueError:
        return ValueError(f"<{tag}>: {prop} is {what}, not {v!r}")
    if kind == _TEXT and not isinstance(v, str):
        raise bad("text")
    if kind == _TEXTS and not (isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v)):
        raise bad("a list of text")
    if kind == _BOOL and not isinstance(v, bool):
        raise bad("true or false")
    if kind == _RECORD and not isinstance(v, dict):
        raise bad("an object")
    # An amount is as the form typed it (text) or as a file stored it (a number); each is kept as it is.
    if kind == _AMOUNT and (isinstance(v, bool) or not isinstance(v, (str, int, float)) or (isinstance(v, float) and not math.isfinite(v))):
        raise bad("text or a number")
    return list(v) if kind == _TEXTS else v


def read_business_node(el: Dict[str, Any]) -> Dict[str, Any]:
    """Read one element of the vocabulary and its children: ``{tag, props, one, many}``."""
    tag = el.get("type")
    spec = BUSINESS_TAGS.get(tag)
    if not spec:
        raise ValueError(f"<{tag}> is not a tag of a company, an RFC or a case")
    props: Dict[str, Any] = {}
    for k, v in (el.get("props") or {}).items():
        if k in ("children", "key") or v is None:
            continue
        kind = spec["props"].get(k)
        if not kind:
            raise ValueError(f"<{tag}> has no attribute {k} (it takes {', '.join(spec['props'])})")
        props[k] = _value(tag, k, kind, v)
    for k in spec.get("required", []):
        if props.get(k) in (None, ""):
            raise ValueError(f"<{tag}> needs {k}")
    one: Dict[str, Optional[Dict[str, Any]]] = {f: None for f in spec.get("one", {})}
    many: Dict[str, List[Dict[str, Any]]] = {f: [] for f in spec.get("many", {})}
    for child in _children((el.get("props") or {}).get("children")):
        field = next(((f, "one") for f, t in spec.get("one", {}).items() if t == child["type"]), None) or \
            next(((f, "many") for f, t in spec.get("many", {}).items() if t == child["type"]), None)
        if not field:
            raise ValueError(f"<{tag}> does not take <{child['type']}>")
        node = read_business_node(child)
        if field[1] == "one":
            if one[field[0]]:
                raise ValueError(f"<{tag}> has two <{child['type']}>")
            one[field[0]] = node
        else:
            many[field[0]].append(node)
    return {"tag": tag, "props": props, "one": one, "many": many}


def company_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """A ``.company`` document from a <Company> (docs/formats.md § companies)."""
    p, one = node["props"], node["one"]
    entity = None
    if one["entity"]:
        e = one["entity"]["props"]
        entity = {"jurisdiction": e["jurisdiction"], "form": e.get("form")}
        if "taxClassification" in e:
            entity["taxClassification"] = e["taxClassification"]
        entity.update({"name": e.get("name"), "formed": e.get("formed"), "fiscalYearEnd": e.get("fiscalYearEnd"),
                       "ids": e.get("ids", {}), "operatesIn": e.get("operatesIn", [])})
        if "conditions" in e:
            entity["conditions"] = e["conditions"]

    def ref(f: str, prop: str) -> Optional[str]:
        return one[f]["props"].get(prop) if one[f] else None
    registrations = [dict(r["props"]) for r in node["many"]["registrations"]]
    on = any(one[f] for f in ("books", "captable", "people", "calendar", "matters")) or bool(registrations)
    standard = {"enabled": True, "books": ref("books", "journal"), "captable": ref("captable", "ocf"), "people": ref("people", "folder"),
                "calendar": ref("calendar", "folder"), "registrations": registrations, "matters": ref("matters", "folder")} if on else {"enabled": False}
    return {"format": "commandagi-company", "name": p["name"], "about": p.get("about", ""), "files": p.get("files", []),
            "dashboard": p.get("dashboard"), "entity": entity, "standard": standard}


def _with_id(node: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
    return ({"id": node["props"]["id"]} if "id" in node["props"] else {}) | {"draft": draft}


def rfc_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """An RFC from a <Rfc>: ``{"draft"}``, and ``id`` once the contract opened it."""
    def change(c: Dict[str, Any]) -> Dict[str, Any]:
        props = {k: v for k, v in c["props"].items() if k != "parameter"}
        return props | ({"key": c["props"]["parameter"]} if "parameter" in c["props"] else {})
    draft = {k: v for k, v in node["props"].items() if k != "id"}
    draft["options"] = [dict(o["props"]) | {"changes": [change(c) for c in o["many"]["changes"]]} for o in node["many"]["options"]]
    return _with_id(node, draft)


def case_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """A case from a <Case>: ``{"draft"}``, and ``id`` once it was filed."""
    draft = {k: v for k, v in node["props"].items() if k != "id"}
    draft["harms"] = [dict(h["props"]) for h in node["many"]["harms"]]
    draft["relief"] = [dict(r["props"]) for r in node["many"]["relief"]]
    return _with_id(node, draft)


_ROOTS = {"Company": ("company", company_of), "Rfc": ("rfc", rfc_of), "Case": ("case", case_of)}


def document_of(value: Any) -> Optional[Dict[str, Any]]:
    """``{"format", "document", "sources"}`` for a <Company>, <Rfc> or <Case> element, else None (``run_module`` hands it
    back beside an empty graph, as the TypeScript SDK's ``declarationOf`` does)."""
    if not _is_element(value) or value["type"] not in _ROOTS:
        return None
    kind, read = _ROOTS[value["type"]]
    return {"format": kind, "document": read(read_business_node(value)), "sources": {}}
