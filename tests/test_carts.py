"""A cart declared in Python gives what the TypeScript vocabulary's JSX gives (carts.ts in the CommandAGI repository):
a buyer's lines at one seller, by SKU and by listing, and never a price.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.carts import cart, item, offer
from commandagi.design.documents import declare_document

CART = {"seller": "acct:org:helmetworks", "items": [{"sku": "helmet-stl", "qty": 1}], "offers": [{"listing": "lst_print-farm-hour", "qty": 3}]}


class CartTests(unittest.TestCase):
    def test_the_example_is_its_document(self):
        d = declare_document(cart(item(sku="helmet-stl", qty=1), offer(listing="lst_print-farm-hour", qty=3), seller="acct:org:helmetworks"))
        self.assertEqual(d, {"format": "cart", "sources": {}, "document": CART})
        out = run_module(
            "from commandagi.design.carts import cart, item, offer\n"
            "result = cart(item(sku=\"helmet-stl\", qty=1), offer(listing=\"lst_print-farm-hour\", qty=3), seller=\"acct:org:helmetworks\")\n",
            "Carts/helmetworks.cart.py")
        self.assertEqual(out["document"]["document"], CART)
        self.assertEqual(sorted(out["document"]["sources"]), ["", "item#helmet-stl", "offer#lst_print-farm-hour"])

    def test_a_bad_cart_is_refused(self):
        u = "acct:user:jacob"
        bad = {
            "seller is an account, acct:user:<id> or acct:org:<id>": lambda: cart(seller="helmetworks"),
            "qty is a whole number from 1 to 999": lambda: cart(item(sku="a", qty=0), seller=u),
            "qty is a whole number from 1 to 999 ": lambda: cart(offer(listing="l", qty=1000), seller=u),
            "priceCents is not read": lambda: cart(item(sku="a", qty=1, price_cents=100), seller=u),
            "amountCents is not read": lambda: cart(offer(listing="l", qty=1, amount_cents=100), seller=u),
            "totalCents is not read": lambda: cart(seller=u, total_cents=100),
            'two <item> in <cart> have sku "a"': lambda: cart(item(sku="a", qty=1), item(sku="a", qty=2), seller=u),
            'two <offer> in <cart> have listing "l"': lambda: cart(offer(listing="l", qty=1), offer(listing="l", qty=2), seller=u),
            "at most 100 lines": lambda: cart(*[item(sku=f"s{i}", qty=1) for i in range(101)], seller=u),
        }
        for why, make in bad.items():
            with self.assertRaisesRegex(ValueError, why.strip(), msg=why):
                declare_document(make())


if __name__ == "__main__":
    unittest.main()
