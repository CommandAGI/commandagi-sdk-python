"""A good declared in Python gives what the TypeScript vocabulary's JSX gives (goods.ts in the CommandAGI repository):
the goods door's body, a digital good and a physical good with a pre-order deposit, and each refusal with why.
Run: python -m unittest discover -s tests"""
import re
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.goods import good, variant

SHIPPING = {"zones": [{"rule": "included", "countries": ["US"], "allowanceCents": 2000}]}
DIGITAL = {"name": "Helmet files", "kind": "digital", "status": "active",
           "variants": [{"sku": "helmet-stl", "name": "STL pack", "priceCents": 1500, "file": "./helmet.zip"}]}
PREORDER = {"name": "Desk assistant", "kind": "physical", "shipping": SHIPPING, "variants": [
    {"sku": "da-1", "name": "Assembled", "priceCents": 349600, "inventoryQty": -1, "weightGrams": 4200},
    {"sku": "da-1-preorder", "name": "Pre-order, 20% now", "priceCents": 349600, "deposit": {"percent": 20}},
]}


def kw(v):
    """A variant's attributes as its call's keywords."""
    return {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): x for k, x in v.items()}


class GoodTests(unittest.TestCase):
    def test_the_examples_are_their_documents(self):
        d = declare_document(good(variant(sku="helmet-stl", name="STL pack", price_cents=1500, file="./helmet.zip"),
                                  name="Helmet files", kind="digital", status="active"))
        self.assertEqual(d, {"format": "good", "sources": {}, "document": DIGITAL})
        p = declare_document(good(*[variant(**kw(v)) for v in PREORDER["variants"]], name="Desk assistant", kind="physical", shipping=SHIPPING))
        self.assertEqual(p["document"], PREORDER)

    def test_a_bad_good_is_refused(self):
        v = {"sku": "a", "name": "b", "priceCents": 100}
        dig = {"name": "x", "kind": "digital"}
        phys = {"name": "x", "kind": "physical", "shipping": SHIPPING}
        bad = {
            "kind is physical or digital": ({"name": "x", "kind": "service"}, v),
            "is digital: it ships nothing": ({**dig, "shipping": SHIPPING}, {**v, "file": "f.zip"}),
            "is digital: file names the file it sells": (dig, v),
            "is digital: it takes no deposit": (dig, {**v, "file": "f.zip", "deposit": {"percent": 10}}),
            "is digital: it has no weightGrams": (dig, {**v, "file": "f.zip", "weightGrams": 10}),
            "is physical: shipping is its shipping policy": ({"name": "x", "kind": "physical"}, v),
            "is physical: it ships, so it names no file": (phys, {**v, "file": "f.zip"}),
            "deposit.percent is a whole number from 1 to 99": (phys, {**v, "deposit": {"percent": 100}}),
            r"less than the price \(100\)": (phys, {**v, "deposit": {"cents": 100}}),
            "priceCents is a whole number of cents, at least 50": (phys, {**v, "priceCents": 10}),
            "colour": ({**phys, "colour": "red"}, v),
        }
        for why, (attrs, var) in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(good(variant(**kw(var)), **attrs))
        with self.assertRaisesRegex(ValueError, 'two <variant> in <good> have sku "a"'):
            declare_document(good(variant(**kw(v)), variant(**kw(v)), **phys))

    def test_a_run_names_each_variant_by_its_sku(self):
        out = run_module(
            "from commandagi.design.goods import good, variant\n"
            "result = good(\n"
            "    variant(sku=\"helmet-stl\", name=\"STL pack\", price_cents=1500, file=\"./helmet.zip\"),\n"
            "    name=\"Helmet files\", kind=\"digital\", status=\"active\",\n"
            ")\n", "Shop/Helmet files.good.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "good")
        self.assertEqual(out["document"]["document"], DIGITAL)
        self.assertEqual(sorted(out["document"]["sources"]), ["", "variant#helmet-stl"])


if __name__ == "__main__":
    unittest.main()
