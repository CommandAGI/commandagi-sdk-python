"""A storefront declared in Python gives what the TypeScript vocabulary's JSX gives (storefronts.ts in the CommandAGI
repository): the store its holder lists, a mirrored store's listings or its offers by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.storefronts import Offer, Offers, Storefront

DIGIKEY = {
    "name": "DigiKey", "venue": "digikey", "seller": "DigiKey", "url": "https://www.digikey.com", "hold": "10 minutes",
    "mirror": {"listings": "Inventory/listings.csv", "read": "Inventory/read.mjs"}, "offers": [],
}
UBER = {
    "name": "Uber", "venue": "uber", "seller": "Uber Technologies",
    "sellerRecord": "cloud://home/user-commandagi/records/companies/uber-technologies-inc-de/",
    "offers": [
        {"name": "Ride", "kind": "service", "unit": "ride", "codes": ["unspsc:78111804"], "tags": ["transport"]},
        {"name": "Courier, one hour", "kind": "service", "price": "25.00 USD", "unit": "hour"},
    ],
}


class StorefrontTests(unittest.TestCase):
    def test_a_relisted_store_is_its_document(self):
        out = run_module(
            "from commandagi.design.storefronts import Offers, Storefront\n"
            "result = Storefront(Offers(listings=\"Inventory/listings.csv\", read=\"Inventory/read.mjs\"), name=\"DigiKey\", venue=\"digikey\", seller=\"DigiKey\", url=\"https://www.digikey.com\", hold=\"10 minutes\")\n",
            "relisting/digikey/digikey.storefront.py")
        self.assertEqual(out["document"]["format"], "storefront")
        self.assertEqual(out["document"]["document"], DIGIKEY)
        self.assertEqual(sorted(out["document"]["sources"]), ["", "Offers"])

    def test_a_service_store_is_its_document(self):
        d = declare_document(Storefront(
            Offer(name="Ride", kind="service", unit="ride", codes=["unspsc:78111804"], tags=["transport"]),
            Offer(name="Courier, one hour", kind="service", price="25.00 USD", unit="hour"),
            name="Uber", venue="uber", seller="Uber Technologies",
            seller_record="cloud://home/user-commandagi/records/companies/uber-technologies-inc-de/"))
        self.assertEqual(d["document"], UBER)

    def test_a_bad_storefront_is_refused(self):
        at = {"name": "Shop", "venue": "ebay", "seller": "A seller"}
        bad = {
            "holder is not read": lambda: Storefront(**at, holder="acct:org:org-commandagi"),
            "venue is the platform's word": lambda: Storefront(**{**at, "venue": "eBay"}),
            'hold is a term like "10 minutes"': lambda: Storefront(**at, hold="ten minutes"),
            "url is an https:// address": lambda: Storefront(**at, url="http://x"),
            "price is an amount and an ISO currency": lambda: Storefront(Offer(name="A", kind="service", price="25 dollars"), **at),
            "kind is service or good": lambda: Storefront(Offer(name="A", kind="thing"), **at),
            "codes is a list of at most 20 classification codes": lambda: Storefront(Offer(name="A", kind="good", codes=["43211500"]), **at),
            'two <Offer> in <Storefront> have name "A"': lambda: Storefront(Offer(name="A", kind="good"), Offer(name="A", kind="good"), **at),
            "<Storefront> has one <Offers>": lambda: Storefront(Offers(listings="a.csv"), Offers(listings="b.csv"), **at),
            "needs seller": lambda: Storefront(name="Shop", venue="ebay"),
        }
        for why, make in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(make())


if __name__ == "__main__":
    unittest.main()
