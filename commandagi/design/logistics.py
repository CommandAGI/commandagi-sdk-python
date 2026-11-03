"""A supplier and a logistics plan, declared in Python: a ``.supplier.py`` and a ``.logistics.py``. The same documents
and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``logistics.ts``)::

    from commandagi.design.logistics import contact, location, ships, supplier

    result = supplier(
        location(name="JLCPCB, Shenzhen", lat=22.543, lon=114.058, country="CN"),
        ships(carrier="DHL", service="Express Worldwide", transit_days=5),
        contact(role="sales", email="support@jlcpcb.com"),
        name="JLCPCB", url="https://jlcpcb.com", lead_time_days=8,
    )

    from commandagi.design.logistics import bom, builder, leg, logistics, route

    result = logistics(
        bom(ref="Tile kit.3d.tsx"),
        builder(name="the builder's bench, Austin", lat=30.267, lon=-97.743, country="US"),
        route(
            leg(carrier="DHL", service="Express pickup", to="DHL hub, Hong Kong", lat=22.308, lon=113.918, country="HK",
                transit_days=1, cost=6, currency="USD"),
            leg(carrier="DHL", service="Express Worldwide", transit_days=4, cost=32, currency="USD"),
            supplier="suppliers/jlcpcb.supplier.tsx",
        ),
        name="tile kit", quantity=10,
    )

A route's legs run in order from the supplier's ``location``; a leg that names a place (``to``, ``lat``, ``lon``) ends
there, and a leg that names none ends at the builder. Refs are by the plan's folder. Nothing adds a default.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

PLACE_FIELDS = ["name", "lat", "lon", "country", "address"]
SUPPLIER_FIELDS = ["name", "url", "leadTimeDays", "note"]
SHIPS_FIELDS = ["carrier", "service", "transitDays", "note"]
CONTACT_FIELDS = ["name", "role", "email", "phone"]
LOGISTICS_FIELDS = ["name", "quantity"]
BOM_FIELDS = ["ref", "qty"]
LEG_FIELDS = ["carrier", "service", "transitDays", "cost", "currency", "to", "lat", "lon", "country"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "supplier": {"holds": "children"},
    "location": {},
    "ships": {},
    "contact": {},
    "logistics": {"holds": "children"},
    "bom": {},
    "builder": {},
    "route": {"holds": "children"},
    "leg": {},
}

__all__ = ["PLACE_FIELDS", "SUPPLIER_FIELDS", "SHIPS_FIELDS", "CONTACT_FIELDS", "LOGISTICS_FIELDS", "BOM_FIELDS", "LEG_FIELDS",
           "SIGNATURES", "SUPPLIER_VOCABULARY", "LOGISTICS_VOCABULARY", *define(globals(), "logistics", SIGNATURES)]


def _fields(o: Dict[str, Any], keys: Any) -> Dict[str, Any]:
    return {k: o[k] for k in keys if k in o and o[k] != ""}


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _text(tag: str, a: Dict[str, Any], keys: Any) -> None:
    for k in keys:
        if k in a and not isinstance(a[k], str):
            raise ValueError(f"<{tag}> {k} is text")


def _count(tag: str, a: Dict[str, Any], keys: Any) -> None:
    for k in keys:
        if k in a and not (_number(a[k]) and a[k] >= 0):
            raise ValueError(f"<{tag}> {k} is a number, 0 or more")


def _place(tag: str, a: Dict[str, Any], name: str = "name") -> Dict[str, Any]:
    if not isinstance(a.get(name), str) or not a[name].strip():
        raise ValueError(f"<{tag}> {name} is the place's name")
    if not _number(a.get("lat")) or not -90 <= a["lat"] <= 90:
        raise ValueError(f"<{tag}> lat is degrees north, -90 to 90")
    if not _number(a.get("lon")) or not -180 <= a["lon"] <= 180:
        raise ValueError(f"<{tag}> lon is degrees east, -180 to 180")
    if "country" in a and not (isinstance(a["country"], str) and re.fullmatch(r"[A-Z]{2}", a["country"])):
        raise ValueError(f'<{tag}> country is ISO 3166 alpha-2 ("CN")')
    _text(tag, a, ["address"])
    return {"name": a[name], "lat": a["lat"], "lon": a["lon"], **({"country": a["country"]} if a.get("country") else {}),
            **({"address": a["address"]} if a.get("address") else {})}


def _supplier(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("supplier", a, ["name", "url", "note"])
    _count("supplier", a, ["leadTimeDays"])
    location = next((c for c in t["children"] if c["tag"] == "location"), None)
    ships = []
    for c in t["children"]:
        if c["tag"] == "ships":
            _text("ships", c["attrs"], ["carrier", "service", "note"])
            _count("ships", c["attrs"], ["transitDays"])
            ships.append(_fields(c["attrs"], SHIPS_FIELDS))
    contacts = []
    for c in t["children"]:
        if c["tag"] == "contact":
            _text("contact", c["attrs"], CONTACT_FIELDS)
            contacts.append(_fields(c["attrs"], CONTACT_FIELDS))
    return {**_fields(a, SUPPLIER_FIELDS), **({"location": _place("location", location["attrs"])} if location else {}),
            "ships": ships, "contacts": contacts}


def _leg(c: DocTree) -> Dict[str, Any]:
    a = c["attrs"]
    _text("leg", a, ["carrier", "service", "to"])
    _count("leg", a, ["transitDays", "cost"])
    if "currency" in a and not (isinstance(a["currency"], str) and re.fullmatch(r"[A-Z]{3}", a["currency"])):
        raise ValueError('<leg> currency is ISO 4217 ("USD")')
    if "cost" in a and "currency" not in a:
        raise ValueError("<leg> cost states its currency")
    somewhere = any(k in a for k in ("to", "lat", "lon", "country"))
    return {**_fields(a, ["carrier", "service", "transitDays", "cost", "currency"]), **({"to": _place("leg", a, "to")} if somewhere else {})}


def _logistics(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("logistics", a, ["name"])
    if "quantity" in a and not (isinstance(a["quantity"], int) and not isinstance(a["quantity"], bool) and a["quantity"] > 0):
        raise ValueError("<logistics> quantity is a whole number, 1 or more")
    boms = []
    for c in t["children"]:
        if c["tag"] == "bom":
            _text("bom", c["attrs"], ["ref"])
            if "qty" in c["attrs"] and not (_number(c["attrs"]["qty"]) and c["attrs"]["qty"] > 0):
                raise ValueError("<bom> qty is a number above 0")
            boms.append(_fields(c["attrs"], BOM_FIELDS))
    builder = next((c for c in t["children"] if c["tag"] == "builder"), None)
    routes = []
    for r in t["children"]:
        if r["tag"] == "route":
            _text("route", r["attrs"], ["supplier"])
            routes.append({"supplier": r["attrs"]["supplier"], "legs": [_leg(c) for c in r["children"] if c["tag"] == "leg"]})
    return {**_fields(a, LOGISTICS_FIELDS), "boms": boms, **({"builder": _place("builder", builder["attrs"])} if builder else {}), "routes": routes}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


SUPPLIER_VOCABULARY = Vocabulary("supplier", "a supplier", "supplier", {
    "supplier": {"parents": [], "required": ["name"], "attrs": SUPPLIER_FIELDS},
    "location": {"parents": ["supplier"], "single": True, "required": ["name", "lat", "lon"], "attrs": PLACE_FIELDS},
    "ships": {"parents": ["supplier"], "required": ["carrier"], "attrs": SHIPS_FIELDS},
    "contact": {"parents": ["supplier"], "attrs": CONTACT_FIELDS},
}, _supplier, _never)

LOGISTICS_VOCABULARY = Vocabulary("logistics", "a logistics plan", "logistics", {
    "logistics": {"parents": [], "attrs": LOGISTICS_FIELDS},
    "bom": {"parents": ["logistics"], "required": ["ref"], "attrs": BOM_FIELDS},
    "builder": {"parents": ["logistics"], "single": True, "required": ["name", "lat", "lon"], "attrs": PLACE_FIELDS},
    "route": {"parents": ["logistics"], "required": ["supplier"], "attrs": ["supplier"]},
    "leg": {"parents": ["route"], "required": ["carrier"], "attrs": LEG_FIELDS},
}, _logistics, _never)

for _v in (SUPPLIER_VOCABULARY, LOGISTICS_VOCABULARY):
    register_vocabulary(_v, "logistics")
