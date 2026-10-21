"""A PART'S FIELDS: what a part states beyond its value, each one KiCad ``property`` form on the part (``foreign``, the
form the board editor writes), so the BOM, the KiCad board and a 3D body's join read one thing (the TypeScript SDK's
``design/part-fields.ts``, form for form):

    part_number= manufacturer= mpn= rating= attrs={"Tolerance": "1%"}       its engineering data (CommandAGI IPN,
                                                                           Manufacturer, MPN, Rating, attrs by name)
    pinout_verified= footprint_verified=                                    how its pinout and its pads are known
                                                                           ("memory", "datasheet <url> p. <page>,
                                                                           <YYYY-MM-DD>", "measured <YYYY-MM-DD>[, <how>]")
    package_dimensions=                                                     its datasheet package ("<n> pins, pitch
                                                                           <mm> mm, body <l> x <w> mm")
    suppliers=[{"name", "sku", "url", "currency", "priceBreaks", "moq", "orderMultiple", "leadTimeDays", "stock",
                "source", "date"}]
    alternates=[{"manufacturer", "mpn", "note"}]  datasheet="https://…"
    lifecycle={"status", "lastTimeBuy", "onHand", "reorderPoint", "source", "date"}
    compliance={"rohs", "rohsExemption", "reach", "conflictMinerals", "eccn", "certifications"}
    shipping={"hsCode", "origin", "hazmat", "packaging"}                    its logistics (docs/formats.md § logistics)

The keys inside these dicts are the data's own (camelCase, as the JSON holds them); only the arguments are snake_case.
A supplier is two properties: ``<name> Part`` (its sku; ``LCSC Part`` is what JLCPCB's assembly BOM reads) and
``<name> Terms`` (the rest as compact JSON, a price break as [quantity, unitPrice], or [quantity, unitPrice,
unitPriceHigh] for an estimate range). ``Datasheet`` is KiCad's own field;
``Alternates`` is JSON; a facet's fields are one property each (``Lifecycle``, ``RoHS``, ``HS Code`` …).

``datasheet`` says where the part's datasheet is (KiCad's ``Datasheet`` field); it claims nothing. ``pinout_verified``
and ``footprint_verified`` claim that a page of a datasheet (or a measurement) was checked against the symbol or the
footprint, on a date: ``check(kind="pinout")`` and ``check(kind="footprint")`` read them and ``package_dimensions``.

A schematic's parts (``schematic.py``) and a circuit's ``component(...)`` (``eda.py``) take these arguments.
"""
from __future__ import annotations

import copy
import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

#: The text fields named by an argument, by the KiCad property each writes.
PART_FIELDS: Dict[str, str] = {"partNumber": "CommandAGI IPN", "manufacturer": "Manufacturer", "mpn": "MPN", "rating": "Rating",
                               "pinoutVerified": "Pinout Verified", "footprintVerified": "Footprint Verified",
                               "packageDimensions": "Package Dimensions"}
_FIELD_EXAMPLES = {"partNumber": "MF-R-3K", "manufacturer": "Yageo", "mpn": "RC0805FR-073KL", "rating": "0.125 W",
                   "pinoutVerified": "datasheet https://www.ti.com/lit/ds/symlink/sn74lvc1t45.pdf p. 3, 2026-10-15",
                   "footprintVerified": "measured 2026-10-15, calipers on the reel's part",
                   "packageDimensions": "6 pins, pitch 0.95 mm, body 2.9 x 1.6 mm"}
#: The keyword each text field is written with here.
_FIELD_ARGS = {"partNumber": "part_number", "manufacturer": "manufacturer", "mpn": "mpn", "rating": "rating",
               "pinoutVerified": "pinout_verified", "footprintVerified": "footprint_verified", "packageDimensions": "package_dimensions"}
#: How a pinout or a footprint is known, and a datasheet's package (the TypeScript SDK's ``VERIFIED``, ``PACKAGE``).
_VERIFIED = re.compile(r"^(?:memory|datasheet https?://\S+ p\. \d+, \d{4}-\d{2}-\d{2}|measured \d{4}-\d{2}-\d{2}(?:, .+)?)$")
_PACKAGE = re.compile(r"^\d+ pins, pitch \d+(?:\.\d+)? mm, body \d+(?:\.\d+)? x \d+(?:\.\d+)? mm$")
_GRAMMAR = {"pinoutVerified": _VERIFIED, "footprintVerified": _VERIFIED, "packageDimensions": _PACKAGE}

#: The logistics facets that are dicts of fields: field -> KiCad property.
FACET_FIELDS: Dict[str, Dict[str, str]] = {
    "lifecycle": {"status": "Lifecycle", "lastTimeBuy": "Last Time Buy", "onHand": "On Hand", "reorderPoint": "Reorder Point",
                  "source": "Lifecycle Source", "date": "Lifecycle Date"},
    "compliance": {"rohs": "RoHS", "rohsExemption": "RoHS Exemption", "reach": "REACH", "conflictMinerals": "Conflict Minerals",
                   "eccn": "ECCN", "certifications": "Certifications"},
    "shipping": {"hsCode": "HS Code", "origin": "Country of Origin", "hazmat": "Hazmat", "packaging": "Packaging"},
}
_CHOICES = {
    "lifecycle.status": ["active", "nrnd", "eol", "obsolete"],
    "compliance.rohs": ["compliant", "exempt", "non-compliant"],
    "compliance.reach": ["compliant", "svhc", "non-compliant"],
    "compliance.conflictMinerals": ["none", "reported", "unknown"],
}
_COUNTS = {"lifecycle.onHand", "lifecycle.reorderPoint"}
_DATES = {"lifecycle.lastTimeBuy", "lifecycle.date"}
_OFFER_TERMS = ["currency", "priceBreaks", "moq", "orderMultiple", "leadTimeDays", "stock", "url", "source", "date"]
_OFFER_KEYS = ["name", "sku", *_OFFER_TERMS]
#: The props a part's fields take, in the order their forms are written.
FIELD_ARGUMENTS: List[str] = [*PART_FIELDS, "attrs", "suppliers", "alternates", "datasheet", "lifecycle", "compliance", "shipping"]
#: Fields a part holds otherwise: its reference, its value, its footprint.
OWN_FIELDS = ("Reference", "Value", "Footprint")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

__all__ = ["PART_FIELDS", "FACET_FIELDS", "FIELD_ARGUMENTS", "field_form", "part_field_forms", "part_fields", "check_offers",
           "check_facet", "js_json"]


def field_form(name: str, value: str) -> Dict[str, Any]:
    """One field as the part carries it: ``(property "MPN" "…" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))``."""
    def sym(v: str) -> Dict[str, Any]:
        return {"kind": "atom", "v": v, "q": False}

    def lst(*items: Any) -> Dict[str, Any]:
        return {"kind": "list", "items": list(items)}
    return lst(sym("property"), {"kind": "atom", "v": name, "q": True}, {"kind": "atom", "v": value, "q": True},
               lst(sym("at"), sym("0"), sym("0"), sym("0")),
               lst(sym("effects"), lst(sym("font"), lst(sym("size"), sym("1.27"), sym("1.27"))), lst(sym("hide"), sym("yes"))))


def _js_number(x: Any) -> str:
    """A number as JavaScript's String() and JSON.stringify print it, so the forms are the TypeScript SDK's byte for byte."""
    if isinstance(x, int):
        return str(x)
    if x != x or x in (float("inf"), float("-inf")):
        return "null"
    if x.is_integer() and abs(x) < 1e21:
        return str(int(x))
    # Python's repr has JavaScript's digits; only where each switches to an exponent, and how it writes one, differ.
    r = repr(x)
    m = re.match(r"^(-?[\d.]+)e([+-]\d+)$", r)
    if not m:
        return r
    exp = int(m.group(2))
    if -7 < exp < 21:
        return format(Decimal(r), "f")
    return f"{m.group(1)}e{'+' if exp > 0 else '-'}{abs(exp)}"


def js_json(v: Any) -> str:
    """Compact JSON as JavaScript's JSON.stringify writes it (keys in their order, numbers as JavaScript prints them)."""
    if v is None or v is True or v is False:
        return json.dumps(v)
    if isinstance(v, (int, float)):
        return _js_number(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, Mapping):
        return "{" + ",".join(f"{json.dumps(str(k), ensure_ascii=False)}:{js_json(x)}" for k, x in v.items() if x is not None) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(js_json(x) for x in v) + "]"
    raise ValueError(f"{type(v).__name__} is not JSON")


def _text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _whole(v: Any, least: int) -> bool:
    return _number(v) and float(v).is_integer() and v >= least


def _argument_of(name: str) -> Optional[str]:
    """The argument that says a KiCad property, or None when ``attrs`` may hold it."""
    p3 = next((a for a, n in PART_FIELDS.items() if n == name), None)
    if p3:
        return p3
    if name == "Datasheet":
        return "datasheet"
    if name == "Alternates":
        return "alternates"
    for arg, fields in FACET_FIELDS.items():
        if name in fields.values():
            return arg
    return "suppliers" if re.search(r". (Part|Terms)$", name) else None


def check_offers(where: str, v: Any) -> List[Dict[str, Any]]:
    """Suppliers' offers, each term checked; a wrong one is refused by name. A board's ``fab(suppliers=…)`` reads them too."""
    if not isinstance(v, (list, tuple)) or not v:
        raise ValueError(f'{where}: suppliers is a list of offers ([{{ name: "LCSC", sku: "C25744", … }}])')
    names: set = set()
    out = []
    for i, s in enumerate(v):
        at = f"{where}: suppliers[{i}]"
        if not isinstance(s, dict):
            raise ValueError(f"{at} is an offer ({{ name, sku, currency, priceBreaks, … }})")
        for k in s:
            if k not in _OFFER_KEYS:
                raise ValueError(f"{at}: {k} is not a term of an offer (it takes {', '.join(_OFFER_KEYS)})")
        name = s.get("name")
        if not _text(name) or re.search(r'[{}"]', name):
            raise ValueError(f'{at}: name is the supplier\'s name ("LCSC")')
        if name in names:
            raise ValueError(f"{at}: two offers of {name}")
        names.add(name)
        if s.get("sku") is not None and not _text(s["sku"]):
            raise ValueError(f"{at}: sku is the supplier's part number, text")
        for k in ("url", "source"):
            if s.get(k) is not None and not _text(s[k]):
                raise ValueError(f"{at}: {k} is text")
        if s.get("currency") is not None and not (isinstance(s["currency"], str) and re.match(r"^[A-Z]{3}$", s["currency"])):
            raise ValueError(f'{at}: currency is an ISO 4217 code ("USD")')
        if s.get("date") is not None and not (isinstance(s["date"], str) and _DAY.match(s["date"])):
            raise ValueError(f"{at}: date is YYYY-MM-DD")
        if s.get("moq") is not None and not _whole(s["moq"], 1):
            raise ValueError(f"{at}: moq is a whole number, 1 or more")
        if s.get("orderMultiple") is not None and not _whole(s["orderMultiple"], 1):
            raise ValueError(f"{at}: orderMultiple is a whole number, 1 or more")
        if s.get("stock") is not None and not _whole(s["stock"], 0):
            raise ValueError(f"{at}: stock is a whole number")
        if s.get("leadTimeDays") is not None and not (_number(s["leadTimeDays"]) and s["leadTimeDays"] >= 0):
            raise ValueError(f"{at}: leadTimeDays is a number of days")
        breaks = s.get("priceBreaks")
        if breaks is not None:
            ok = isinstance(breaks, (list, tuple)) and all(
                isinstance(b, dict) and set(b) <= {"quantity", "unitPrice", "unitPriceHigh"} and _whole(b.get("quantity"), 1)
                and _number(b.get("unitPrice")) and b["unitPrice"] >= 0
                and ("unitPriceHigh" not in b or (_number(b["unitPriceHigh"]) and b["unitPriceHigh"] >= b["unitPrice"]))
                for b in breaks)
            if not ok:
                raise ValueError(f"{at}: priceBreaks is a list of {{ quantity, unitPrice, unitPriceHigh? }} (quantity a whole number from 1, "
                                 "unitPrice 0 or more, unitPriceHigh not under it)")
        out.append({k: copy.deepcopy(x) for k, x in s.items() if x is not None})
    return out


def _offer_forms(where: str, v: Any) -> List[Dict[str, Any]]:
    forms = []
    for s in check_offers(where, v):
        terms: Dict[str, Any] = {}
        for k in _OFFER_TERMS:
            if s.get(k) is not None:
                terms[k] = [[b["quantity"], b["unitPrice"], *([b["unitPriceHigh"]] if "unitPriceHigh" in b else [])] for b in s[k]] \
                    if k == "priceBreaks" else s[k]
        if s.get("sku") is not None:
            forms.append(field_form(f"{s['name']} Part", s["sku"]))
        if terms or s.get("sku") is None:
            forms.append(field_form(f"{s['name']} Terms", js_json(terms)))
    return forms


def check_facet(where: str, arg: str, v: Any) -> Dict[str, Any]:
    """One facet's fields (``lifecycle``, ``compliance``, ``shipping``), each checked; a board's ``fab(...)`` reads them too."""
    fields = FACET_FIELDS[arg]
    if not isinstance(v, dict):
        raise ValueError(f"{where}: {arg} is an object ({{ {', '.join(fields)} }})")
    for k in v:
        if k not in fields:
            raise ValueError(f"{where}: {arg}.{k} is not read (it takes {', '.join(fields)})")
    if arg == "lifecycle" and v.get("status") is None:
        raise ValueError(f"{where}: lifecycle needs its status ({', '.join(_CHOICES['lifecycle.status'])})")
    for k in fields:
        x = v.get(k)
        if x is None:
            continue
        key = f"{arg}.{k}"
        if key in _COUNTS:
            if not _whole(x, 0):
                raise ValueError(f"{where}: {key} is a whole number")
        elif k == "certifications":
            if not isinstance(x, (list, tuple)) or not all(_text(c) and "," not in c for c in x):
                raise ValueError(f"{where}: {key} is a list of text, each with no comma")
        else:
            if not _text(x):
                raise ValueError(f"{where}: {key} is text")
            if key in _CHOICES and x not in _CHOICES[key]:
                raise ValueError(f'{where}: {key} is one of {", ".join(_CHOICES[key])} (got "{x}")')
            if key in _DATES and not _DAY.match(x):
                raise ValueError(f"{where}: {key} is YYYY-MM-DD")
            if key == "shipping.origin" and not re.match(r"^(?:[A-Z]{2}|unknown)$", x):
                raise ValueError(f'{where}: {key} is an ISO 3166 alpha-2 code ("CN"), or "unknown"')
    return {k: copy.deepcopy(x) for k, x in v.items() if x is not None}


def part_field_forms(where: str, props: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The ``property`` forms of a part's fields, from its props (camelCase, as an element holds them): the text fields, ``attrs``,
    then its logistics. A wrong argument is refused by name, with ``where`` (the element or the call) first."""
    forms: List[Dict[str, Any]] = []
    for prop, name in PART_FIELDS.items():
        v = props.get(prop)
        if v is None:
            continue
        if not _text(v) or (prop in _GRAMMAR and not _GRAMMAR[prop].match(v)):
            raise ValueError(f'{where}: {_FIELD_ARGS[prop]} is text ("{_FIELD_EXAMPLES[prop]}")')
        forms.append(field_form(name, v))
    attrs = props.get("attrs")
    if attrs is not None:
        if not isinstance(attrs, dict) or not all(_text(v) for v in attrs.values()):
            raise ValueError(f'{where}: attrs is an object of text ({{ Tolerance: "1%" }})')
        for name, v in attrs.items():
            named = _argument_of(name) if isinstance(name, str) else None
            if named:
                raise ValueError(f"{where}: attrs names {name}: say it with {_FIELD_ARGS.get(named, named)}=")
            if not isinstance(name, str) or not name.strip() or name in OWN_FIELDS:
                raise ValueError(f"{where}: attrs names {name}, which is the part's own (its name, value or footprint)")
            forms.append(field_form(name, v))
    if props.get("suppliers") is not None:
        forms += _offer_forms(where, props["suppliers"])
    alternates = props.get("alternates")
    if alternates is not None:
        if not isinstance(alternates, (list, tuple)) or not alternates or not all(
                isinstance(a, dict) and _text(a.get("manufacturer")) and _text(a.get("mpn")) and (a.get("note") is None or _text(a["note"]))
                and all(k in ("manufacturer", "mpn", "note") for k in a) for a in alternates):
            raise ValueError(f"{where}: alternates is a list of {{ manufacturer, mpn, note? }}")
        forms.append(field_form("Alternates", js_json(alternates)))
    datasheet = props.get("datasheet")
    if datasheet is not None:
        if not _text(datasheet):
            raise ValueError(f"{where}: datasheet is a URL or a path")
        forms.append(field_form("Datasheet", datasheet))
    for arg, fields in FACET_FIELDS.items():
        v = props.get(arg)
        if v is None:
            continue
        facet = check_facet(where, arg, v)
        for k, prop in fields.items():
            x = facet.get(k)
            if x is None:
                continue
            value = ", ".join(x) if isinstance(x, (list, tuple)) else _js_number(x) if _number(x) else str(x)
            forms.append(field_form(prop, value))
    return forms


def part_fields(inputs: Mapping[str, Any]) -> Dict[str, Any]:
    """A part's fields read back from its node's inputs (the ``property`` forms it carries): the named ones by their
    prop (``partNumber``, ``manufacturer``, ``mpn``, ``rating``), the logistics by theirs (``suppliers``,
    ``alternates``, ``datasheet``, ``lifecycle``, ``compliance``, ``shipping``), any other in ``attrs``. A part with
    none gives {}."""
    out: Dict[str, Any] = {}
    attrs: Dict[str, str] = {}
    suppliers: Dict[str, Dict[str, Any]] = {}

    def supplier(name: str) -> Dict[str, Any]:
        return suppliers.setdefault(name, {"name": name})
    for form in inputs.get("foreign") or []:
        items = form.get("items") if isinstance(form, dict) and form.get("kind") == "list" else None
        if not items or len(items) < 3 or items[0].get("v") != "property":
            continue
        name, value = items[1].get("v"), items[2].get("v")
        if not isinstance(name, str) or not isinstance(value, str) or name in OWN_FIELDS:
            continue
        arg = _argument_of(name)
        if arg in PART_FIELDS:
            out[arg] = value
        elif arg == "suppliers" and name.endswith(" Part"):
            supplier(name[:-5])["sku"] = value
        elif arg == "suppliers":
            terms = json.loads(value)
            s = supplier(name[:-6])
            for k in _OFFER_TERMS:
                if terms.get(k) is not None:
                    s[k] = [{"quantity": b[0], "unitPrice": b[1], **({"unitPriceHigh": b[2]} if len(b) > 2 else {})} for b in terms[k]] \
                        if k == "priceBreaks" else terms[k]
        elif arg == "alternates":
            out["alternates"] = json.loads(value)
        elif arg == "datasheet":
            out["datasheet"] = value
        elif arg:
            key = next(k for k, p in FACET_FIELDS[arg].items() if p == name)
            facet = out.setdefault(arg, {})
            if key == "certifications":
                facet[key] = [c.strip() for c in value.split(",") if c.strip()]
            elif f"{arg}.{key}" in _COUNTS:
                n = float(value)
                facet[key] = int(n) if n.is_integer() else n
            else:
                facet[key] = value
        else:
            attrs[name] = value
    if suppliers:
        out["suppliers"] = list(suppliers.values())
    return {**out, **({"attrs": attrs} if attrs else {})}
