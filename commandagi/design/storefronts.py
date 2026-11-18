"""A storefront, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``storefronts.ts``; CommandAGI's docs/formats.md § a storefront in code).
``<name>.storefront.py`` declares one storefront its holder lists: the store, who sells there, and what it offers::

    from commandagi.design.storefronts import Offers, Storefront

    result = Storefront(
        Offers(listings="Inventory/listings.csv", read="Inventory/read.mjs"),
        name="DigiKey", venue="digikey", seller="DigiKey", url="https://www.digikey.com", checkout="agent", hold="10 minutes",
    )

The holder is the account whose Drive holds the file, never an attribute. ``checkout`` says who completes a relisted
purchase: ``"agent"`` (the holder buys or books it for the person) or ``"seller"`` (the person is sent to the seller's
own checkout). ``Offer(name=…, kind="service"|"good",
price="25.00 USD", unit=…, codes=["unspsc:…"], tags=[…])`` is one offer, by its name.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .classification import PRODUCT_SCHEMES, classification_problem
from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

STOREFRONT_FIELDS = ["name", "venue", "seller", "sellerRecord", "sellerId", "url", "source", "checkout", "hold"]
STOREFRONT_MIRROR_FIELDS = ["listings", "read"]
STOREFRONT_OFFER_FIELDS = ["name", "kind", "price", "unit", "codes", "tags"]
STOREFRONT_OFFER_KINDS = ["service", "good"]
STOREFRONT_CHECKOUTS = ["agent", "seller"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "Storefront": {"holds": "children"},
    "Offers": {},
    "Offer": {},
}

__all__ = ["STOREFRONT_FIELDS", "STOREFRONT_MIRROR_FIELDS", "STOREFRONT_OFFER_FIELDS", "STOREFRONT_OFFER_KINDS", "STOREFRONT_CHECKOUTS", "SIGNATURES",
           "storefront_of", "STOREFRONT_VOCABULARY", *define(globals(), "storefronts", SIGNATURES)]

_VENUE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_HOLD = re.compile(r"^[1-9]\d{0,3} (second|minute|hour|day)s?$")
_PRICE = re.compile(r"^\d+(\.\d+)? [A-Z]{3}$")


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= mx


def _optional(a: Dict[str, Any], k: str, mx: int, at: str, out: Dict[str, Any]) -> None:
    if a.get(k) is None:
        return
    if not _text(a[k], mx):
        raise ValueError(f"{at} {k} is a short text (at most {mx}), not {_json(a[k])}")
    out[k] = a[k]


def _offer_of(a: Dict[str, Any]) -> Dict[str, Any]:
    if not _text(a.get("name"), 200):
        raise ValueError(f"<Offer> name is a short text (at most 200), not {_json(a.get('name'))}")
    at = f'<Offer name="{a["name"]}">'
    if a.get("kind") not in STOREFRONT_OFFER_KINDS:
        raise ValueError(f"{at} kind is service or good, not {_json(a.get('kind'))}")
    out: Dict[str, Any] = {"name": a["name"], "kind": a["kind"]}
    if a.get("price") is not None:
        if not isinstance(a["price"], str) or not _PRICE.match(a["price"]):
            raise ValueError(f'{at} price is an amount and an ISO currency ("25.00 USD"), not {_json(a["price"])}')
        out["price"] = a["price"]
    _optional(a, "unit", 40, at, out)
    # What kind of offer it is (classification.py): product schemes and free tags, by the one grammar.
    problem = classification_problem(a.get("codes"), a.get("tags"), PRODUCT_SCHEMES)
    if problem:
        raise ValueError(f"{at} {problem}")
    if a.get("codes") is not None:
        out["codes"] = list(a["codes"])
    if a.get("tags") is not None:
        out["tags"] = list(a["tags"])
    return out


def storefront_of(t: DocTree) -> Dict[str, Any]:
    """A storefront as its tree declares it (the TypeScript SDK's ``storefrontOf``)."""
    a = t["attrs"]
    if not _text(a.get("name"), 120):
        raise ValueError(f"<Storefront> name is a short text (at most 120), not {_json(a.get('name'))}")
    at = f'<Storefront name="{a["name"]}">'
    if not isinstance(a.get("venue"), str) or not _VENUE.match(a["venue"]):
        raise ValueError(f'{at} venue is the platform\'s word, lower-case letters, digits and dashes ("digikey", "amazon"), not {_json(a.get("venue"))}')
    if not _text(a.get("seller"), 200):
        raise ValueError(f"{at} seller is the seller's name, a short text (at most 200), not {_json(a.get('seller'))}")
    out: Dict[str, Any] = {"name": a["name"], "venue": a["venue"], "seller": a["seller"]}
    _optional(a, "sellerRecord", 500, at, out)
    _optional(a, "sellerId", 200, at, out)
    if a.get("url") is not None:
        if not _text(a["url"], 500) or not a["url"].startswith("https://"):
            raise ValueError(f"{at} url is an https:// address (at most 500), not {_json(a['url'])}")
        out["url"] = a["url"]
    _optional(a, "source", 500, at, out)
    if a.get("checkout") is not None:
        if a["checkout"] not in STOREFRONT_CHECKOUTS:
            raise ValueError(f"{at} checkout is agent or seller, not {_json(a['checkout'])}")
        out["checkout"] = a["checkout"]
    if a.get("hold") is not None:
        if not isinstance(a["hold"], str) or not _HOLD.match(a["hold"]):
            raise ValueError(f'{at} hold is a term like "10 minutes" (seconds, minutes, hours or days), not {_json(a["hold"])}')
        out["hold"] = a["hold"]
    mirrors = [c for c in t["children"] if c["tag"] == "Offers"]
    if len(mirrors) > 1:
        raise ValueError(f"{at} has one <Offers>, not {len(mirrors)}")
    if mirrors:
        m = mirrors[0]["attrs"]
        if not _text(m.get("listings"), 500):
            raise ValueError(f'{at} <Offers> listings is a ref to the listings file ("Inventory/listings.csv"), not {_json(m.get("listings"))}')
        mirror = {"listings": m["listings"]}
        if m.get("read") is not None:
            if not _text(m["read"], 500):
                raise ValueError(f'{at} <Offers> read is a ref to the script that reads the store ("Inventory/read.mjs"), not {_json(m["read"])}')
            mirror["read"] = m["read"]
        out["mirror"] = mirror
    offers = [c for c in t["children"] if c["tag"] == "Offer"]
    if len(offers) > 500:
        raise ValueError(f"{at} has at most 500 <Offer>s, not {len(offers)}")
    out["offers"] = [_offer_of(c["attrs"]) for c in offers]
    names: set = set()
    for o in out["offers"]:
        if o["name"] in names:
            raise ValueError(f'{at} has two <Offer>s named "{o["name"]}"')
        names.add(o["name"])
    return out


def _attrs(fields: List[str], r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: r[k] for k in fields if r.get(k) is not None}


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "Storefront", "attrs": _attrs(STOREFRONT_FIELDS, d), "children": [
        *([{"tag": "Offers", "attrs": _attrs(STOREFRONT_MIRROR_FIELDS, d["mirror"]), "children": []}] if d.get("mirror") else []),
        *({"tag": "Offer", "attrs": _attrs(STOREFRONT_OFFER_FIELDS, o), "children": []} for o in d.get("offers") or []),
    ]}


STOREFRONT_VOCABULARY = Vocabulary("storefront", "a storefront", "Storefront", {
    "Storefront": {"parents": [], "required": ["name", "venue", "seller"], "attrs": STOREFRONT_FIELDS},
    "Offers": {"parents": ["Storefront"], "single": True, "required": ["listings"], "attrs": STOREFRONT_MIRROR_FIELDS},
    "Offer": {"parents": ["Storefront"], "key": "name", "required": ["name", "kind"], "attrs": STOREFRONT_OFFER_FIELDS},
}, storefront_of, _tree, lambda stem: {"name": stem or "Storefront", "venue": "commandagi", "seller": stem or "Storefront", "offers": []})

register_vocabulary(STOREFRONT_VOCABULARY, "storefronts")
