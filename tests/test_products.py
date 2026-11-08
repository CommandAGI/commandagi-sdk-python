"""A product declared in Python gives what the TypeScript vocabulary's JSX gives (products.ts in the CommandAGI
repository): a digital product, and a physical product with options, stock, a pre-order deposit and a discount; each
refusal with why.
Run: python -m unittest discover -s tests"""
import re
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.products import discount, product, variant

SHIPPING = {"zones": [{"rule": "included", "countries": ["US"], "allowanceCents": 2000}]}
DIGITAL = {"name": "Helmet files", "kind": "digital", "status": "active",
           "variants": [{"sku": "helmet-stl", "name": "STL pack", "priceCents": 1500, "file": "./helmet.zip"}], "discounts": []}
PREORDER = {"name": "Desk assistant", "kind": "physical", "shipping": SHIPPING, "variants": [
    {"sku": "da-1-black", "name": "Assembled, black", "priceCents": 349600, "compareAtCents": 399600, "stock": 12,
     "options": {"colour": "black", "assembled": True}, "weightGrams": 4200},
    {"sku": "da-1-preorder", "name": "Pre-order, 20% now", "priceCents": 349600, "deposit": {"percent": 20}},
], "discounts": [{"code": "Launch10", "percent": 10, "startsAt": "2026-11-08", "endsAt": "2026-12-01T00:00:00Z", "usageLimit": 100}]}


def kw(v):
    """A record's attributes as its call's keywords."""
    return {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): x for k, x in v.items()}


class ProductTests(unittest.TestCase):
    def test_the_examples_are_their_documents(self):
        d = declare_document(product(variant(sku="helmet-stl", name="STL pack", price_cents=1500, file="./helmet.zip"),
                                     name="Helmet files", kind="digital", status="active"))
        self.assertEqual(d, {"format": "product", "sources": {}, "document": DIGITAL})
        p = declare_document(product(*[variant(**kw(v)) for v in PREORDER["variants"]], *[discount(**kw(x)) for x in PREORDER["discounts"]],
                                     name="Desk assistant", kind="physical", shipping=SHIPPING))
        self.assertEqual(p["document"], PREORDER)

    def test_a_bad_product_is_refused(self):
        v = {"sku": "a", "name": "b", "priceCents": 100}
        d = {"code": "SAVE5", "amountCents": 500}
        dig = {"name": "x", "kind": "digital"}
        phys = {"name": "x", "kind": "physical", "shipping": SHIPPING}
        bad = {
            "kind is physical or digital": ({"name": "x", "kind": "service"}, v),
            "is digital: it ships nothing": ({**dig, "shipping": SHIPPING}, {**v, "file": "f.zip"}),
            "is digital: file names the file it sells": (dig, v),
            "is digital: it takes no deposit": (dig, {**v, "file": "f.zip", "deposit": {"percent": 10}}),
            "is digital: it has no weightGrams": (dig, {**v, "file": "f.zip", "weightGrams": 10}),
            "is digital: it has no stock": (dig, {**v, "file": "f.zip", "stock": 3}),
            "is physical: shipping is its shipping policy": ({"name": "x", "kind": "physical"}, v),
            "is physical: it ships, so it names no file": (phys, {**v, "file": "f.zip"}),
            "stock is a whole number, at least 0": (phys, {**v, "stock": -1}),
            "inventoryQty is not read": (phys, {**v, "inventoryQty": 3}),
            r"more than the price \(100\)": (phys, {**v, "compareAtCents": 100}),
            "options is an object of at most 20 names": (phys, {**v, "options": {"colour": ["red"]}}),
            "deposit.percent is a whole number from 1 to 99": (phys, {**v, "deposit": {"percent": 100}}),
            r"less than the price \(100\)": (phys, {**v, "deposit": {"cents": 100}}),
            "priceCents is a whole number of cents, at least 50": (phys, {**v, "priceCents": 10}),
            "fulfilment is an object": ({**phys, "fulfilment": "ship"}, v),
            "colour": ({**phys, "colour": "red"}, v),
            "taxCode is a Stripe product tax code like txcd_99999999": ({**phys, "tax_code": "txcd_1"}, v),
        }
        for why, (attrs, var) in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(product(variant(**kw(var)), **attrs))
        with self.assertRaisesRegex(ValueError, 'two <variant> in <product> have sku "a"'):
            declare_document(product(variant(**kw(v)), variant(**kw(v)), **phys))
        discounts = {
            r"code is letters, digits, - and _ \(3 to 40\)": {"code": "a b c", "percent": 5},
            "takes off one of percent or amountCents, not neither": {"code": "SAVE5"},
            "takes off one of percent or amountCents, not both": {**d, "percent": 5},
            "percent is a whole number from 1 to 100": {"code": "SAVE5", "percent": 101},
            "amountCents is a whole number of cents, at least 1": {"code": "SAVE5", "amountCents": 0},
            "startsAt is an ISO 8601 date or date-time": {**d, "startsAt": "next week"},
            "endsAt is an ISO 8601 date or date-time": {**d, "endsAt": "2026-02-30"},
            r"endsAt \(.*\) is after startsAt": {**d, "startsAt": "2026-12-01", "endsAt": "2026-11-30T23:00:00+02:00"},
            "usageLimit is a whole number, at least 1": {**d, "usageLimit": 0},
        }
        for why, x in discounts.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(product(variant(**kw(v)), discount(**kw(x)), **phys))
        with self.assertRaisesRegex(ValueError, 'two <discount>s with one code: "SAVE5" and "save5"'):
            declare_document(product(variant(**kw(v)), discount(**kw(d)), discount(**kw({**d, "code": "save5"})), **phys))
        declare_document(product(variant(**kw(v)), discount(**kw({**d, "startsAt": "2026-12-01", "endsAt": "2026-11-30T23:00:00-03:00"})), **phys))

    def test_a_run_names_each_variant_by_its_sku(self):
        out = run_module(
            "from commandagi.design.products import product, variant\n"
            "result = product(\n"
            "    variant(sku=\"helmet-stl\", name=\"STL pack\", price_cents=1500, file=\"./helmet.zip\"),\n"
            "    name=\"Helmet files\", kind=\"digital\", status=\"active\",\n"
            ")\n", "Shop/Helmet files.product.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "product")
        self.assertEqual(out["document"]["document"], DIGITAL)
        self.assertEqual(sorted(out["document"]["sources"]), ["", "variant#helmet-stl"])


if __name__ == "__main__":
    unittest.main()
