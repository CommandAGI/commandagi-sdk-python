"""A brand declared in Python gives what the TypeScript SDK's JSX gives (brands.test.ts there): its names, voice,
logos, domains, sites, handles and marks in the file's order, and what the vocabulary has no words for refused by name.
A company names each brand file with ``Brand(file=…)``.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.brands import Alias, BrandSurface, Domain, Handle, Logo, Mark, Site
from commandagi.design.business import Brand, Company, document_of
from commandagi.design.documents import declare_document


class BrandTests(unittest.TestCase):
    def test_a_brand_is_its_records_in_order(self):
        d = declare_document(BrandSurface(
            Alias(name="Northwind Survey", kind="legal"),
            Logo(file="../design/logo.svg", kind="mark", background="light"),
            Domain(name="northwind.example", registrar="Porkbun LLC", expires="2027-05-18", auto_renew=True, site="../sites/northwind/", mail=True),
            Site(folder="../sites/northwind/"),
            Handle(platform="x", handle="northwindsurvey", connection="x"),
            Mark(title="NORTHWIND", jurisdiction="US", number="99123456"),
            name="Northwind", tagline="Drone surveys.", voice=["plain", "warm"], design_system="../design/brand-book.json"))
        self.assertEqual(d, {"format": "brand", "sources": {}, "document": {
            "name": "Northwind", "tagline": "Drone surveys.", "voice": ["plain", "warm"], "designSystem": "../design/brand-book.json",
            "aliases": [{"name": "Northwind Survey", "kind": "legal"}],
            "logos": [{"file": "../design/logo.svg", "kind": "mark", "background": "light"}],
            "domains": [{"name": "northwind.example", "registrar": "Porkbun LLC", "expires": "2027-05-18", "autoRenew": True,
                         "site": "../sites/northwind/", "mail": True}],
            "sites": [{"folder": "../sites/northwind/"}],
            "handles": [{"platform": "x", "handle": "northwindsurvey", "connection": "x"}],
            "marks": [{"title": "NORTHWIND", "jurisdiction": "US", "number": "99123456"}]}})

    def test_a_brand_refuses_by_name(self):
        with self.assertRaisesRegex(ValueError, "<BrandSurface> needs name"):
            declare_document(BrandSurface())
        with self.assertRaisesRegex(ValueError, "dns is not read"):
            declare_document(BrandSurface(Domain(name="n.example", dns="1.2.3.4"), name="N"))
        with self.assertRaisesRegex(ValueError, "<Domain> mail is true or false"):
            declare_document(BrandSurface(Domain(name="n.example", mail="yes"), name="N"))
        with self.assertRaisesRegex(ValueError, "voice is a list of words"):
            declare_document(BrandSurface(name="N", voice="warm"))
        with self.assertRaisesRegex(ValueError, 'two <Domain> in <BrandSurface> have name "n.example"'):
            declare_document(BrandSurface(Domain(name="n.example"), Domain(name="n.example"), name="N"))

    def test_a_company_names_each_brand_file(self):
        c = document_of(Company(Brand(file="Northwind/brands/Northwind.brand.py"), name="Northwind", files=["Northwind/"]))["document"]
        self.assertEqual(c["brands"], [{"file": "Northwind/brands/Northwind.brand.py"}])
        self.assertEqual(c["standard"], {"enabled": False})
        self.assertNotIn("brands", document_of(Company(name="Northwind", files=["Northwind/"]))["document"])


if __name__ == "__main__":
    unittest.main()
