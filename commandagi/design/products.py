"""A product, declared in Python: the same document and the same elements as the TypeScript SDK's JSX (``commandagi/design``
``products.ts``), each element a call. ``<name>.product.py`` declares one ``product``; each ``variant`` is one record of
it, by its ``sku``, and each ``discount`` one, by its ``code`` (keywords are the attributes in snake_case: ``price_cents``
is ``priceCents``)::

    from commandagi.design.products import discount, product, variant

    result = product(
        variant(sku="helmet-stl", name="STL pack", price_cents=1500, file="./helmet.zip"),
        discount(code="LAUNCH10", percent=10, ends_at="2026-12-01"),
        name="Helmet files", kind="digital", status="active",
    )

``kind`` is ``physical`` (``shipping`` is its policy, required) or ``digital`` (each variant names the ``file`` it sells;
no shipping, weight, stock or deposit). A physical variant with no ``stock`` is made to order. A ``deposit``
(``{"percent": 1..99}`` or ``{"cents": n}``, at least 50 and less than the price) makes a variant a pre-order. A
``discount`` takes ``percent`` or ``amount_cents`` off, between ``starts_at`` and ``ends_at`` (ISO 8601; a date-time with
no offset is UTC), for at most ``usage_limit`` orders. A run gives back ``{"format": "product", "document": {...},
"sources"}`` beside an empty graph; ``sources`` names each variant's call by its sku (``variant#helmet-stl``).
"""
from __future__ import annotations

import calendar
import re
from typing import Any, Dict, Optional

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

PRODUCT_KINDS = ["physical", "digital"]
PRODUCT_STATUSES = ["draft", "active", "archived"]
PRODUCT_FIELDS = ["name", "kind", "slug", "subtitle", "description", "images", "status", "shipping", "fulfilment", "quantityTerms", "embodimentKind"]
VARIANT_FIELDS = ["sku", "name", "priceCents", "compareAtCents", "stock", "options", "weightGrams", "file", "deposit"]
DISCOUNT_FIELDS = ["code", "percent", "amountCents", "startsAt", "endsAt", "usageLimit"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "product": {"holds": "children"},
    "variant": {},
    "discount": {},
}

__all__ = ["PRODUCT_KINDS", "PRODUCT_STATUSES", "PRODUCT_FIELDS", "VARIANT_FIELDS", "DISCOUNT_FIELDS", "SIGNATURES", "product_of",
           "variant_of", "discount_of", "deposit_of", "PRODUCT_VOCABULARY", *define(globals(), "products", SIGNATURES)]

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
_CODE = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})?)?$")


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= mx


def _int(v: Any, mn: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and mn <= v <= 2**53 - 1


def _said(v: Any) -> str:
    return _json(v)


def _instant(v: Any) -> Optional[int]:
    """The instant an ISO 8601 date or date-time names, in ms (a date-time with no offset is UTC), or None."""
    m = _ISO.match(v) if isinstance(v, str) else None
    if not m:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    h, mi, s = int(m[4] or 0), int(m[5] or 0), int(m[6] or 0)
    if not (1 <= mo <= 12) or not (1 <= d <= calendar.monthrange(y, mo)[1]) or h > 23 or mi > 59 or s > 59:
        return None
    ms = int((m[7] or "0").ljust(3, "0"))
    off = 0
    if m[8] and m[8] != "Z":
        off = (-1 if m[8][0] == "-" else 1) * (int(m[8][1:3]) * 60 + int(m[8][4:6]))
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0)) * 1000 + ms - off * 60_000


def deposit_of(v: Any, price: int, at: str) -> Dict[str, int]:
    """A deposit as a variant declares it (the TypeScript SDK's ``depositOf``)."""
    if not isinstance(v, dict) or len(v) != 1:
        raise ValueError(f"{at} deposit is {{ percent }} or {{ cents }}, not {_said(v)}")
    if "percent" in v:
        if not _int(v["percent"], 1) or v["percent"] > 99:
            raise ValueError(f"{at} deposit.percent is a whole number from 1 to 99, not {_said(v['percent'])}")
        return {"percent": v["percent"]}
    if "cents" in v:
        if not _int(v["cents"], 50) or v["cents"] >= price:
            raise ValueError(f"{at} deposit.cents is a whole number of cents, at least 50 and less than the price ({price}), not {_said(v['cents'])}")
        return {"cents": v["cents"]}
    raise ValueError(f"{at} deposit is {{ percent }} or {{ cents }}, not {_said(v)}")


def variant_of(attrs: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """One variant as its element declares it, for a product of ``kind`` (the TypeScript SDK's ``variantOf``)."""
    sku = attrs.get("sku")
    if not _text(sku, 80):
        raise ValueError(f"<variant> sku is a short text (at most 80), not {_said(sku)}")
    at = f'<variant sku="{sku}">'
    if not _text(attrs.get("name"), 120):
        raise ValueError(f"{at} name is a short text (at most 120), not {_said(attrs.get('name'))}")
    price = attrs.get("priceCents")
    if not _int(price, 50):
        raise ValueError(f"{at} priceCents is a whole number of cents, at least 50, not {_said(price)}")
    out: Dict[str, Any] = {"sku": sku, "name": attrs["name"], "priceCents": price}
    if "compareAtCents" in attrs:
        if not _int(attrs["compareAtCents"], price + 1):
            raise ValueError(f"{at} compareAtCents is a whole number of cents, more than the price ({price}), not {_said(attrs['compareAtCents'])}")
        out["compareAtCents"] = attrs["compareAtCents"]
    if "options" in attrs:
        o = attrs["options"]
        ok = isinstance(o, dict) and len(o) <= 20 and all(
            isinstance(k, str) and k.strip() and isinstance(x, (str, int, float)) for k, x in o.items())
        if not ok:
            raise ValueError(f"{at} options is an object of at most 20 names, each a text, a number or a boolean, not {_said(o)}")
        out["options"] = dict(o)
    if kind == "digital":
        if "stock" in attrs:
            raise ValueError(f"{at} is digital: it has no stock (a file does not run out)")
        if "weightGrams" in attrs:
            raise ValueError(f"{at} is digital: it has no weightGrams")
        if "deposit" in attrs:
            raise ValueError(f"{at} is digital: it takes no deposit (a deposit is a pre-order of a physical product)")
        if not _text(attrs.get("file"), 1000):
            raise ValueError(f"{at} is digital: file names the file it sells (a path from this file's folder, or an address), not {_said(attrs.get('file'))}")
        out["file"] = attrs["file"]
        return out
    if "file" in attrs:
        raise ValueError(f"{at} is physical: it ships, so it names no file")
    if "stock" in attrs:
        if not _int(attrs["stock"], 0):
            raise ValueError(f"{at} stock is a whole number, at least 0 (no stock: made to order), not {_said(attrs['stock'])}")
        out["stock"] = attrs["stock"]
    if "weightGrams" in attrs:
        if not _int(attrs["weightGrams"], 0):
            raise ValueError(f"{at} weightGrams is a whole number of grams, not {_said(attrs['weightGrams'])}")
        out["weightGrams"] = attrs["weightGrams"]
    if "deposit" in attrs:
        out["deposit"] = deposit_of(attrs["deposit"], price, at)
    return out


def discount_of(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """One discount as its element declares it (the TypeScript SDK's ``discountOf``)."""
    code = attrs.get("code")
    if not isinstance(code, str) or not _CODE.match(code):
        raise ValueError(f"<discount> code is letters, digits, - and _ (3 to 40), not {_said(code)}")
    at = f'<discount code="{code}">'
    out: Dict[str, Any] = {"code": code}
    if ("percent" in attrs) == ("amountCents" in attrs):
        raise ValueError(f"{at} takes off one of percent or amountCents, not {'both' if 'percent' in attrs else 'neither'}")
    if "percent" in attrs:
        if not _int(attrs["percent"], 1) or attrs["percent"] > 100:
            raise ValueError(f"{at} percent is a whole number from 1 to 100, not {_said(attrs['percent'])}")
        out["percent"] = attrs["percent"]
    if "amountCents" in attrs:
        if not _int(attrs["amountCents"], 1):
            raise ValueError(f"{at} amountCents is a whole number of cents, at least 1, not {_said(attrs['amountCents'])}")
        out["amountCents"] = attrs["amountCents"]
    start = None
    if "startsAt" in attrs:
        start = _instant(attrs["startsAt"])
        if start is None:
            raise ValueError(f'{at} startsAt is an ISO 8601 date or date-time ("2026-11-08", "2026-11-08T09:00:00Z"), not {_said(attrs["startsAt"])}')
        out["startsAt"] = attrs["startsAt"]
    if "endsAt" in attrs:
        end = _instant(attrs["endsAt"])
        if end is None:
            raise ValueError(f'{at} endsAt is an ISO 8601 date or date-time ("2026-11-08", "2026-11-08T09:00:00Z"), not {_said(attrs["endsAt"])}')
        if start is not None and end <= start:
            raise ValueError(f"{at} endsAt ({attrs['endsAt']}) is after startsAt ({attrs['startsAt']})")
        out["endsAt"] = attrs["endsAt"]
    if "usageLimit" in attrs:
        if not _int(attrs["usageLimit"], 1):
            raise ValueError(f"{at} usageLimit is a whole number, at least 1, not {_said(attrs['usageLimit'])}")
        out["usageLimit"] = attrs["usageLimit"]
    return out


def product_of(t: DocTree) -> Dict[str, Any]:
    """A product as its tree declares it (the TypeScript SDK's ``productOf``)."""
    a = t["attrs"]
    if not _text(a.get("name"), 120):
        raise ValueError(f"<product> name is a short text (at most 120), not {_said(a.get('name'))}")
    at = f'<product name="{a["name"]}">'
    kind = a.get("kind")
    if kind not in PRODUCT_KINDS:
        raise ValueError(f"{at} kind is {' or '.join(PRODUCT_KINDS)}, not {_said(kind)}")
    out: Dict[str, Any] = {"name": a["name"], "kind": kind}
    if "slug" in a:
        if not isinstance(a["slug"], str) or not _SLUG.match(a["slug"]):
            raise ValueError(f"{at} slug is lower-case letters, digits and dashes (2 to 80), not {_said(a['slug'])}")
        out["slug"] = a["slug"]
    if "subtitle" in a:
        if not _text(a["subtitle"], 200):
            raise ValueError(f"{at} subtitle is a short text (at most 200), not {_said(a['subtitle'])}")
        out["subtitle"] = a["subtitle"]
    if "description" in a:
        if not isinstance(a["description"], str) or len(a["description"]) > 8000:
            raise ValueError(f"{at} description is a text (at most 8000)")
        out["description"] = a["description"]
    if "images" in a:
        im = a["images"]
        if not isinstance(im, list) or len(im) > 20 or not all(_text(i, 500) for i in im):
            raise ValueError(f"{at} images is a list of at most 20 paths or URLs")
        out["images"] = list(im)
    if "status" in a:
        if a["status"] not in PRODUCT_STATUSES:
            raise ValueError(f"{at} status is {', '.join(PRODUCT_STATUSES)}, not {_said(a['status'])}")
        out["status"] = a["status"]
    if kind == "digital" and "shipping" in a:
        raise ValueError(f"{at} is digital: it ships nothing, so it has no shipping")
    if kind == "physical":
        if not isinstance(a.get("shipping"), dict):
            raise ValueError(f"{at} is physical: shipping is its shipping policy ({{ zones, from?, parcel? }}), not {_said(a.get('shipping'))}")
        out["shipping"] = a["shipping"]
    if "fulfilment" in a:
        if not isinstance(a["fulfilment"], dict):
            raise ValueError(f"{at} fulfilment is an object (how a paid line is fulfilled), not {_said(a['fulfilment'])}")
        out["fulfilment"] = a["fulfilment"]
    if "quantityTerms" in a:
        if not isinstance(a["quantityTerms"], dict):
            raise ValueError(f"{at} quantityTerms is an object, not {_said(a['quantityTerms'])}")
        out["quantityTerms"] = a["quantityTerms"]
    if "embodimentKind" in a:
        if not _text(a["embodimentKind"], 80):
            raise ValueError(f"{at} embodimentKind is a short text (at most 80), not {_said(a['embodimentKind'])}")
        out["embodimentKind"] = a["embodimentKind"]
    variants = [c for c in t["children"] if c["tag"] == "variant"]
    # A file not finished yet may hold none; the checkout refuses a product that sells nothing.
    if len(variants) > 50:
        raise ValueError(f"{at} sells at most 50 <variant>s, not {len(variants)}")
    out["variants"] = [variant_of(c["attrs"], kind) for c in variants]
    discounts = [c for c in t["children"] if c["tag"] == "discount"]
    if len(discounts) > 50:
        raise ValueError(f"{at} has at most 50 <discount>s, not {len(discounts)}")
    out["discounts"] = [discount_of(c["attrs"]) for c in discounts]
    # A buyer types a code in any case, so two codes that differ only in case are one code.
    codes: Dict[str, str] = {}
    for d in out["discounts"]:
        was = codes.get(d["code"].lower())
        if was is not None:
            raise ValueError(f'{at} has two <discount>s with one code: "{was}" and "{d["code"]}" (a code is read in any case)')
        codes[d["code"].lower()] = d["code"]
    return out


def _attrs(fields, r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: r[k] for k in fields if r.get(k) is not None}


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "product", "attrs": _attrs(PRODUCT_FIELDS, d), "children": [
        *({"tag": "variant", "attrs": _attrs(VARIANT_FIELDS, v), "children": []} for v in d.get("variants") or []),
        *({"tag": "discount", "attrs": _attrs(DISCOUNT_FIELDS, x), "children": []} for x in d.get("discounts") or []),
    ]}


PRODUCT_VOCABULARY = Vocabulary("product", "a product", "product", {
    "product": {"parents": [], "required": ["name", "kind"], "attrs": PRODUCT_FIELDS},
    "variant": {"parents": ["product"], "key": "sku", "required": ["sku", "name", "priceCents"], "attrs": VARIANT_FIELDS},
    "discount": {"parents": ["product"], "key": "code", "required": ["code"], "attrs": DISCOUNT_FIELDS},
}, product_of, _tree, lambda stem: {"name": stem or "Product", "kind": "physical", "status": "draft", "shipping": {"zones": []},
                                    "variants": [], "discounts": []})

register_vocabulary(PRODUCT_VOCABULARY, "products")
