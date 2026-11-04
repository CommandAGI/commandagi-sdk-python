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

A supplier's ``service(fee(...), id=...)`` is a way to buy through it (pre-order, global sourcing, consignment) with its
review and buying days and its fees (per order, line or unit). A plan's ``build`` is the day the parts must be at the
builder, and ``source(use(offer=...), part=..., strategy=...)`` says how one line is filled (single, fill, split, dual).
A service whose days are ``business_days=True`` counts Monday to Friday only.

A plan may buy ahead for a later plan: ``ahead(qty=..., for_=...)`` in a ``source`` buys ``qty`` more than this order
needs, by the same offers, for the plan ``for`` names (a ref). That plan counts them as stock on hand:
``stock(from_=...)`` names the earlier plan and takes what it bought ahead for this one (``part`` narrows it to one
line). Stock held otherwise (left from a build, consigned) is ``stock(part=..., qty=..., arrives=...)``; ``arrives`` is
the day it is there (with ``from``, the earlier plan's build date). A ``source`` with only an ``ahead`` keeps the default
fill and needs no strategy::

    ten = logistics(
        source(use(offer="JLCPCB parts library"), use(offer="JLCPCB parts library", mpn="FT2232HL-TRAY"),
               ahead(qty=157, for_="Helmet 100.logistics.tsx"), part="FT2232HL-REEL", strategy="fill"),
        name="helmet, 10", quantity=10, build="2027-01-15")
    hundred = logistics(stock(from_="Helmet 10.logistics.tsx"), name="helmet, 100", quantity=100, build="2027-06-01")

A route's legs run in order from the supplier's ``location``; a leg that names a place (``to``, ``lat``, ``lon``) ends
there, and a leg that names none ends at the builder. Refs are by the plan's folder. Nothing adds a default.

A leg that says ``quote="cheapest"`` (or ``fastest``, a carrier ``usps``, a carrier and its service code
``usps/PRIORITY_MAIL``) with its parcel ``kg=2.5, mm=[300, 250, 220]`` is quoted live by the shipping interface, beside
its stated cost (docs/shipping.md); a place's ``postal`` is the postal code the carriers rate by.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

PLACE_FIELDS = ["name", "lat", "lon", "country", "postal", "address"]
SUPPLIER_FIELDS = ["name", "url", "leadTimeDays", "note"]
SHIPS_FIELDS = ["carrier", "service", "transitDays", "note"]
CONTACT_FIELDS = ["name", "role", "email", "phone"]
SERVICE_FIELDS = ["id", "name", "reviewDays", "reviewDaysHigh", "leadTimeDays", "leadTimeDaysHigh", "businessDays", "note"]
FEE_FIELDS = ["amount", "currency", "per", "each", "note"]
LOGISTICS_FIELDS = ["name", "quantity", "build"]
SOURCE_FIELDS = ["part", "strategy"]
USE_FIELDS = ["offer", "mpn", "qty", "share"]
AHEAD_FIELDS = ["qty", "for", "note"]
STOCK_FIELDS = ["part", "qty", "from", "arrives", "note"]
FEE_PER = ["order", "line", "unit"]
STRATEGIES = ["single", "fill", "split", "dual"]
BOM_FIELDS = ["ref", "qty"]
LEG_FIELDS = ["carrier", "service", "transitDays", "cost", "currency", "quote", "kg", "mm", "to", "lat", "lon", "country", "postal"]
#: What a leg's quote asks for: cheapest, fastest, a carrier, or a carrier and its service code.
WANT = re.compile(r"(?:cheapest|fastest|[a-z][a-z0-9-]{1,31}(?:/[A-Za-z0-9_.-]{1,64})?)")

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "supplier": {"holds": "children"},
    "location": {},
    "ships": {},
    "contact": {},
    "service": {"holds": "children"},
    "fee": {},
    "logistics": {"holds": "children"},
    "bom": {},
    "builder": {},
    "route": {"holds": "children"},
    "leg": {},
    "source": {"holds": "children"},
    "use": {},
    "ahead": {},
    "stock": {},
}

__all__ = ["PLACE_FIELDS", "SUPPLIER_FIELDS", "SHIPS_FIELDS", "CONTACT_FIELDS", "SERVICE_FIELDS", "FEE_FIELDS", "LOGISTICS_FIELDS",
           "BOM_FIELDS", "LEG_FIELDS", "SOURCE_FIELDS", "USE_FIELDS", "AHEAD_FIELDS", "STOCK_FIELDS",
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
    _text(tag, a, ["postal", "address"])
    return {"name": a[name], "lat": a["lat"], "lon": a["lon"], **({"country": a["country"]} if a.get("country") else {}),
            **({"postal": a["postal"]} if a.get("postal") else {}), **({"address": a["address"]} if a.get("address") else {})}


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
    services = [_service(c) for c in t["children"] if c["tag"] == "service"]
    return {**_fields(a, SUPPLIER_FIELDS), **({"location": _place("location", location["attrs"])} if location else {}),
            "ships": ships, "contacts": contacts, "services": services}


def _currency(tag: str, a: Dict[str, Any]) -> None:
    if "currency" in a and not (isinstance(a["currency"], str) and re.fullmatch(r"[A-Z]{3}", a["currency"])):
        raise ValueError(f'<{tag}> currency is ISO 4217 ("USD")')


def _service(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("service", a, ["id", "name", "note"])
    _count("service", a, ["reviewDays", "reviewDaysHigh", "leadTimeDays", "leadTimeDaysHigh"])
    if "businessDays" in a and not isinstance(a["businessDays"], bool):
        raise ValueError("<service> businessDays is true or false")
    fees = []
    for c in t["children"]:
        if c["tag"] != "fee":
            continue
        f = c["attrs"]
        _text("fee", f, ["note"])
        if not (_number(f.get("amount")) and f["amount"] >= 0):
            raise ValueError("<fee> amount is a number, 0 or more")
        if "currency" not in f:
            raise ValueError("<fee> states its currency")
        _currency("fee", f)
        if f.get("per") not in FEE_PER:
            raise ValueError("<fee> per is order, line or unit")
        if "each" in f and not (isinstance(f["each"], int) and not isinstance(f["each"], bool) and f["each"] >= 1):
            raise ValueError("<fee> each is a whole number, 1 or more")
        fees.append(_fields(f, FEE_FIELDS))
    return {**_fields(a, SERVICE_FIELDS), "fees": fees}


def _leg(c: DocTree) -> Dict[str, Any]:
    a = c["attrs"]
    _text("leg", a, ["carrier", "service", "to"])
    _count("leg", a, ["transitDays", "cost"])
    _currency("leg", a)
    if "cost" in a and "currency" not in a:
        raise ValueError("<leg> cost states its currency")
    if "quote" in a and not (isinstance(a["quote"], str) and WANT.fullmatch(a["quote"])):
        raise ValueError("<leg> quote is cheapest, fastest, a carrier (usps), or a carrier and its service code (usps/PRIORITY_MAIL)")
    if "kg" in a and not (_number(a["kg"]) and a["kg"] > 0):
        raise ValueError("<leg> kg is the parcel's weight in kilograms, above 0")
    if "mm" in a and not (isinstance(a["mm"], (list, tuple)) and len(a["mm"]) == 3 and all(_number(x) and x > 0 for x in a["mm"])):
        raise ValueError("<leg> mm is the parcel's [length, width, height] in millimetres")
    if "quote" in a and ("kg" not in a or "mm" not in a):
        raise ValueError("<leg> quote needs its parcel: kg and mm")
    somewhere = any(k in a for k in ("to", "lat", "lon", "country"))
    out = _fields(a, ["carrier", "service", "transitDays", "cost", "currency", "quote", "kg", "mm"])
    if "mm" in out:
        out["mm"] = list(out["mm"])
    return {**out, **({"to": _place("leg", a, "to")} if somewhere else {})}


def _logistics(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("logistics", a, ["name", "build"])
    if "build" in a and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["build"]):
        raise ValueError("<logistics> build is YYYY-MM-DD")
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
    sources = [_source(c) for c in t["children"] if c["tag"] == "source"]
    stocks = [_stock(c) for c in t["children"] if c["tag"] == "stock"]
    return {**_fields(a, LOGISTICS_FIELDS), "boms": boms, **({"builder": _place("builder", builder["attrs"])} if builder else {}), "routes": routes,
            "sources": sources, **({"stocks": stocks} if stocks else {})}


def _source(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("source", a, ["part"])
    named = any(c["tag"] == "use" for c in t["children"])
    if (named or "strategy" in a) and a.get("strategy") not in STRATEGIES:
        raise ValueError("<source> strategy is single, fill, split or dual")
    uses = []
    for c in t["children"]:
        if c["tag"] != "use":
            continue
        u = c["attrs"]
        _text("use", u, ["offer", "mpn"])
        if "qty" in u and not (_number(u["qty"]) and u["qty"] > 0):
            raise ValueError("<use> qty is a number above 0")
        if "share" in u and not (_number(u["share"]) and 0 < u["share"] <= 1):
            raise ValueError("<use> share is a number above 0, at most 1")
        uses.append(_fields(u, USE_FIELDS))
    ahead = next((c["attrs"] for c in t["children"] if c["tag"] == "ahead"), None)
    if ahead is not None:
        q = ahead.get("qty")
        if not (_number(q) and float(q).is_integer() and q >= 1):
            raise ValueError("<ahead> qty is a whole number, 1 or more")
        _text("ahead", ahead, ["for", "note"])
    if not named and ahead is None:
        raise ValueError(f'<source part="{a.get("part")}"> names no <use> and no <ahead>')
    return {**_fields(a, SOURCE_FIELDS), "uses": uses, **({"ahead": _fields(ahead, AHEAD_FIELDS)} if ahead is not None else {})}


def _stock(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text("stock", a, ["part", "from", "note"])
    if "arrives" in a and not (isinstance(a["arrives"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["arrives"])):
        raise ValueError("<stock> arrives is a date, YYYY-MM-DD")
    if "from" in a and "qty" in a:
        raise ValueError("<stock from> takes what that plan bought ahead for this one: it states no qty")
    if "from" not in a and ("part" not in a or "qty" not in a):
        raise ValueError("<stock> names the part and its qty, or the plan it is from (from)")
    if "qty" in a and not (_number(a["qty"]) and a["qty"] > 0):
        raise ValueError("<stock> qty is a number above 0")
    return _fields(a, STOCK_FIELDS)


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


SUPPLIER_VOCABULARY = Vocabulary("supplier", "a supplier", "supplier", {
    "supplier": {"parents": [], "required": ["name"], "attrs": SUPPLIER_FIELDS},
    "location": {"parents": ["supplier"], "single": True, "required": ["name", "lat", "lon"], "attrs": PLACE_FIELDS},
    "ships": {"parents": ["supplier"], "required": ["carrier"], "attrs": SHIPS_FIELDS},
    "contact": {"parents": ["supplier"], "attrs": CONTACT_FIELDS},
    "service": {"parents": ["supplier"], "required": ["id"], "attrs": SERVICE_FIELDS},
    "fee": {"parents": ["service"], "required": ["amount", "currency", "per"], "attrs": FEE_FIELDS},
}, _supplier, _never)

LOGISTICS_VOCABULARY = Vocabulary("logistics", "a logistics plan", "logistics", {
    "logistics": {"parents": [], "attrs": LOGISTICS_FIELDS},
    "bom": {"parents": ["logistics"], "required": ["ref"], "attrs": BOM_FIELDS},
    "builder": {"parents": ["logistics"], "single": True, "required": ["name", "lat", "lon"], "attrs": PLACE_FIELDS},
    "route": {"parents": ["logistics"], "required": ["supplier"], "attrs": ["supplier"]},
    "leg": {"parents": ["route"], "required": ["carrier"], "attrs": LEG_FIELDS},
    "source": {"parents": ["logistics"], "required": ["part"], "attrs": SOURCE_FIELDS},
    "use": {"parents": ["source"], "required": ["offer"], "attrs": USE_FIELDS},
    "ahead": {"parents": ["source"], "single": True, "required": ["qty", "for"], "attrs": AHEAD_FIELDS},
    "stock": {"parents": ["logistics"], "attrs": STOCK_FIELDS},
}, _logistics, _never)

for _v in (SUPPLIER_VOCABULARY, LOGISTICS_VOCABULARY):
    register_vocabulary(_v, "logistics")
