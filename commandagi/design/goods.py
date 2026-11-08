"""A good, declared in Python: the same document and the same elements as the TypeScript SDK's JSX (``commandagi/design``
``goods.ts``), each element a call. ``<name>.good.py`` declares one ``good``, and each ``variant`` is one record of it,
by its ``sku`` (keywords are the attributes in snake_case: ``price_cents`` is ``priceCents``). The document is the body of the platform's goods door (``POST /goods``)::

    from commandagi.design.goods import good, variant

    result = good(
        variant(sku="helmet-stl", name="STL pack", price_cents=1500, file="./helmet.zip"),
        name="Helmet files", kind="digital", status="active",
    )

``kind`` is ``physical`` (``shipping`` is its policy, required) or ``digital`` (each variant names the ``file`` it sells;
no shipping, weight or deposit). A ``deposit`` (``{"percent": 1..99}`` or ``{"cents": n}``, at least 50 and less than
the price) makes a variant a pre-order. A run gives back ``{"format": "good", "document": {...}, "sources"}`` beside an
empty graph; ``sources`` names each variant's call by its sku (``variant#helmet-stl``).
"""
from __future__ import annotations

import re
from typing import Any, Dict

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

GOOD_KINDS = ["physical", "digital"]
GOOD_STATUSES = ["draft", "active", "archived"]
GOOD_FIELDS = ["name", "kind", "slug", "subtitle", "description", "images", "status", "shipping"]
VARIANT_FIELDS = ["sku", "name", "priceCents", "inventoryQty", "weightGrams", "file", "deposit"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "good": {"holds": "children"},
    "variant": {},
}

__all__ = ["GOOD_KINDS", "GOOD_STATUSES", "GOOD_FIELDS", "VARIANT_FIELDS", "SIGNATURES", "good_of", "variant_of", "deposit_of",
           "GOOD_VOCABULARY", *define(globals(), "goods", SIGNATURES)]

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= mx


def _int(v: Any, mn: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and mn <= v <= 2**53 - 1


def _said(v: Any) -> str:
    return _json(v)


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
    """One variant as its element declares it, for a good of ``kind`` (the TypeScript SDK's ``variantOf``)."""
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
    if "inventoryQty" in attrs:
        if not _int(attrs["inventoryQty"], -1):
            raise ValueError(f"{at} inventoryQty is a whole number (-1: made to order), not {_said(attrs['inventoryQty'])}")
        out["inventoryQty"] = attrs["inventoryQty"]
    if kind == "digital":
        if "weightGrams" in attrs:
            raise ValueError(f"{at} is digital: it has no weightGrams")
        if "deposit" in attrs:
            raise ValueError(f"{at} is digital: it takes no deposit (a deposit is a pre-order of a physical good)")
        if not _text(attrs.get("file"), 1000):
            raise ValueError(f"{at} is digital: file names the file it sells (a path from this file's folder, or an address), not {_said(attrs.get('file'))}")
        out["file"] = attrs["file"]
        return out
    if "file" in attrs:
        raise ValueError(f"{at} is physical: it ships, so it names no file")
    if "weightGrams" in attrs:
        if not _int(attrs["weightGrams"], 0):
            raise ValueError(f"{at} weightGrams is a whole number of grams, not {_said(attrs['weightGrams'])}")
        out["weightGrams"] = attrs["weightGrams"]
    if "deposit" in attrs:
        out["deposit"] = deposit_of(attrs["deposit"], price, at)
    return out


def good_of(t: DocTree) -> Dict[str, Any]:
    """A good as its tree declares it (the TypeScript SDK's ``goodOf``)."""
    a = t["attrs"]
    if not _text(a.get("name"), 120):
        raise ValueError(f"<good> name is a short text (at most 120), not {_said(a.get('name'))}")
    at = f'<good name="{a["name"]}">'
    kind = a.get("kind")
    if kind not in GOOD_KINDS:
        raise ValueError(f"{at} kind is {' or '.join(GOOD_KINDS)}, not {_said(kind)}")
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
        if a["status"] not in GOOD_STATUSES:
            raise ValueError(f"{at} status is {', '.join(GOOD_STATUSES)}, not {_said(a['status'])}")
        out["status"] = a["status"]
    if kind == "digital" and "shipping" in a:
        raise ValueError(f"{at} is digital: it ships nothing, so it has no shipping")
    if kind == "physical":
        if not isinstance(a.get("shipping"), dict):
            raise ValueError(f"{at} is physical: shipping is its shipping policy ({{ zones, from?, parcel? }}), not {_said(a.get('shipping'))}")
        out["shipping"] = a["shipping"]
    variants = [c for c in t["children"] if c["tag"] == "variant"]
    # A file not finished yet may hold none; the goods door refuses a good that sells nothing (``variants_required``).
    if len(variants) > 50:
        raise ValueError(f"{at} sells at most 50 <variant>s, not {len(variants)}")
    out["variants"] = [variant_of(c["attrs"], kind) for c in variants]
    return out


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "good", "attrs": {k: d[k] for k in GOOD_FIELDS if d.get(k) is not None}, "children": [
        {"tag": "variant", "attrs": {k: v[k] for k in VARIANT_FIELDS if v.get(k) is not None}, "children": []}
        for v in d.get("variants") or []]}


GOOD_VOCABULARY = Vocabulary("good", "a good", "good", {
    "good": {"parents": [], "required": ["name", "kind"], "attrs": GOOD_FIELDS},
    "variant": {"parents": ["good"], "key": "sku", "required": ["sku", "name", "priceCents"], "attrs": VARIANT_FIELDS},
}, good_of, _tree, lambda stem: {"name": stem or "Good", "kind": "physical", "status": "draft", "shipping": {"zones": []}, "variants": []})

register_vocabulary(GOOD_VOCABULARY, "goods")
