"""A company, an RFC or a case declared in Python — the same documents the CommandAGI company app and contract editor
open as ``<Name>.company.py``, ``<name>.rfc.py`` and ``<name>.case.py``, and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``business.ts``)::

    from commandagi.design.business import Books, CapTable, Company, Entity, Registration

    result = Company(
        Entity(jurisdiction="US-DE", form="llc", formed="2024-01-31", fiscal_year_end="12-31"),
        Books(journal="Northwind/books/main.journal"),
        CapTable(ocf="Northwind/captable/"),
        Registration(kind="tax-id", jurisdiction="US", id="12-3456789"),
        name="Northwind",
        files=["Northwind/"],
    )

Each call is one element (``./element.py``): its children positional, its attributes as snake_case keywords
(``fiscal_year_end=`` is ``fiscalYearEnd``). ``document_of`` reads one into the document the apps use: the company
itself, or an RFC's or a case's ``{"id"?, "draft"}``. The standard's parts REF their files (the journal stays hledger,
the cap table Open Cap Table Format). A change's ``parameter`` is the draft's ``key``. Beside the document, ``sources``
names the call each part was written in, by path (``""`` the root, ``entity``, ``options/0/changes/1``). An unknown
attribute or child is refused by name.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .element import Element, child_elements, declares, define

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

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``): a tag that takes child tags holds children.
SIGNATURES: Dict[str, Dict[str, Any]] = {t: ({"holds": "children"} if s.get("one") or s.get("many") else {}) for t, s in BUSINESS_TAGS.items()}

__all__ = ["BUSINESS_TAGS", "SIGNATURES", "read_business_node", "sources_of", "company_of", "rfc_of", "case_of", "document_of",
           *define(globals(), "business", SIGNATURES)]


def _plain(v: Any, what: str) -> Any:
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{what}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items()}
    raise ValueError(f"{what} is plain data (text, numbers, true or false, lists, objects)")


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
    if kind == _TEXTS:
        return list(v)
    if kind in (_RECORD, _DATA):
        return _plain(v, f"<{tag}> {prop}")
    return v


def read_business_node(el: Element) -> Dict[str, Any]:
    """Read one element of the vocabulary and its children: ``{tag, props, one, many, source?}``."""
    tag = el.tag
    spec = BUSINESS_TAGS.get(tag)
    if not spec:
        raise ValueError(f"<{tag}> is not a tag of a company, an RFC or a case")
    props: Dict[str, Any] = {}
    for k, v in el.props.items():
        if k == "key" or v is None:
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
    for child in child_elements(el):
        field = next(((f, "one") for f, t in spec.get("one", {}).items() if t == child.tag), None) or \
            next(((f, "many") for f, t in spec.get("many", {}).items() if t == child.tag), None)
        if not field:
            takes = [*spec.get("one", {}).values(), *spec.get("many", {}).values()]
            raise ValueError(f"<{tag}> does not take <{child.tag}> (it takes {', '.join(f'<{t}>' for t in takes) or 'no children'})")
        node = read_business_node(child)
        if field[1] == "one":
            if one[field[0]]:
                raise ValueError(f"<{tag}> has two <{child.tag}>")
            one[field[0]] = node
        else:
            many[field[0]].append(node)
    out: Dict[str, Any] = {"tag": tag, "props": props, "one": one, "many": many}
    if el.source is not None:
        out["source"] = el.source
    return out


def sources_of(node: Dict[str, Any], at: str = "", out: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Every element's source, by path (``""`` the root, ``entity``, ``options/0/changes/1``)."""
    out = {} if out is None else out
    if "source" in node:
        out[at] = node["source"]

    def join(f: str) -> str:
        return f"{at}/{f}" if at else f
    for f, n in node["one"].items():
        if n:
            sources_of(n, join(f), out)
    for f, items in node["many"].items():
        for i, n in enumerate(items):
            sources_of(n, join(f"{f}/{i}"), out)
    return out


def company_of(node: Dict[str, Any]) -> Dict[str, Any]:
    """A company document from a <Company> (docs/formats.md § companies)."""
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
    if not isinstance(value, Element) or value.tag not in _ROOTS:
        return None
    kind, read = _ROOTS[value.tag]
    node = read_business_node(value)
    return {"format": kind, "document": read(node), "sources": sources_of(node)}


for _root in _ROOTS:
    declares("business", _root, lambda root, stem: {"document": document_of(root)})
