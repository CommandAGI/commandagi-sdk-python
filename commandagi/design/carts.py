"""A cart, declared in Python: the same document and the same elements as the TypeScript SDK's JSX (``commandagi/design``
``carts.ts``). ``Carts/<seller>.cart.py`` is a buyer's cart at one seller: one ``item`` for each product variant, by its
``sku``, and one ``offer`` for each offer that is not a product, by its ``listing`` id::

    from commandagi.design.carts import cart, item, offer

    result = cart(
        item(sku="helmet-stl", qty=1),
        offer(listing="lst_print-farm-hour", qty=3),
        seller="acct:org:helmetworks",
    )

A cart names no price: the checkout prices each line from the seller's product files and listings when the buyer pays.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

CART_FIELDS = ["seller"]
ITEM_FIELDS = ["sku", "qty"]
OFFER_FIELDS = ["listing", "qty"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "cart": {"holds": "children"},
    "item": {},
    "offer": {},
}

__all__ = ["CART_FIELDS", "ITEM_FIELDS", "OFFER_FIELDS", "SIGNATURES", "cart_of", "CART_VOCABULARY",
           *define(globals(), "carts", SIGNATURES)]

_SELLER = re.compile(r"^acct:(user|org):\S{1,200}$")


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= mx


def _qty(v: Any, at: str) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 999:
        raise ValueError(f"{at} qty is a whole number from 1 to 999, not {_json(v)}")
    return v


def cart_of(t: DocTree) -> Dict[str, Any]:
    """A cart as its tree declares it (the TypeScript SDK's ``cartOf``)."""
    seller = t["attrs"].get("seller")
    if not isinstance(seller, str) or not _SELLER.match(seller):
        raise ValueError(f"<cart> seller is an account, acct:user:<id> or acct:org:<id>, not {_json(seller)}")
    at = f'<cart seller="{seller}">'
    lines = [c for c in t["children"] if c["tag"] in ("item", "offer")]
    if len(lines) > 100:
        raise ValueError(f"{at} holds at most 100 lines (<item>s and <offer>s), not {len(lines)}")
    items: List[Dict[str, Any]] = []
    offers: List[Dict[str, Any]] = []
    for c in lines:
        a = c["attrs"]
        if c["tag"] == "item":
            if not _text(a.get("sku"), 80):
                raise ValueError(f"<item> sku is a short text (at most 80), not {_json(a.get('sku'))}")
            items.append({"sku": a["sku"], "qty": _qty(a.get("qty"), f'<item sku="{a["sku"]}">')})
        else:
            if not _text(a.get("listing"), 200):
                raise ValueError(f"<offer> listing is a short text (at most 200), not {_json(a.get('listing'))}")
            offers.append({"listing": a["listing"], "qty": _qty(a.get("qty"), f'<offer listing="{a["listing"]}">')})
    return {"seller": seller, "items": items, "offers": offers}


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "cart", "attrs": {"seller": d["seller"]}, "children": [
        *({"tag": "item", "attrs": {"sku": i["sku"], "qty": i["qty"]}, "children": []} for i in d.get("items") or []),
        *({"tag": "offer", "attrs": {"listing": o["listing"], "qty": o["qty"]}, "children": []} for o in d.get("offers") or []),
    ]}


# A line names no price (priceCents, amountCents …): it is not read, so the file cannot hold one.
CART_VOCABULARY = Vocabulary("cart", "a cart", "cart", {
    "cart": {"parents": [], "required": ["seller"], "attrs": CART_FIELDS},
    "item": {"parents": ["cart"], "key": "sku", "required": ["sku", "qty"], "attrs": ITEM_FIELDS},
    "offer": {"parents": ["cart"], "key": "listing", "required": ["listing", "qty"], "attrs": OFFER_FIELDS},
}, cart_of, _tree, lambda stem: {"seller": "", "items": [], "offers": []})

register_vocabulary(CART_VOCABULARY, "carts")
