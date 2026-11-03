"""A supplier and a logistics plan declared in Python give what the TypeScript SDK's JSX gives (logistics-plan.test.ts
there): a supplier's location, carriers and contacts; a plan's BOM designs, builder and legs, a leg with no place
ending at the builder; and what the vocabulary has no words for refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.logistics import bom, builder, contact, leg, location, logistics, route, ships, supplier


class LogisticsTests(unittest.TestCase):
    def test_a_supplier_is_its_location_carriers_and_contacts(self):
        d = declare_document(supplier(location(name="JLCPCB, Shenzhen", lat=22.543, lon=114.058, country="CN"),
                                      ships(carrier="DHL", service="Express Worldwide", transit_days=5),
                                      contact(role="sales", email="support@jlcpcb.com"),
                                      name="JLCPCB", url="https://jlcpcb.com", lead_time_days=8))
        self.assertEqual(d["format"], "supplier")
        self.assertEqual(d["document"], {
            "name": "JLCPCB", "url": "https://jlcpcb.com", "leadTimeDays": 8,
            "location": {"name": "JLCPCB, Shenzhen", "lat": 22.543, "lon": 114.058, "country": "CN"},
            "ships": [{"carrier": "DHL", "service": "Express Worldwide", "transitDays": 5}],
            "contacts": [{"role": "sales", "email": "support@jlcpcb.com"}]})
        with self.assertRaisesRegex(ValueError, "lat is degrees north"):
            declare_document(supplier(location(name="Y", lat=95, lon=0), name="X"))

    def test_a_plan_is_its_boms_builder_and_legs(self):
        d = declare_document(logistics(
            bom(ref="Tile kit.3d.tsx"),
            builder(name="Austin", lat=30.267, lon=-97.743, country="US"),
            route(leg(carrier="DHL", service="Express pickup", to="DHL hub, Hong Kong", lat=22.308, lon=113.918, country="HK",
                      transit_days=1, cost=6, currency="USD"),
                  leg(carrier="DHL", service="Express Worldwide", transit_days=4, cost=32, currency="USD"),
                  supplier="suppliers/jlcpcb.supplier.tsx"),
            name="tile kit", quantity=10))
        self.assertEqual(d["document"], {
            "name": "tile kit", "quantity": 10, "boms": [{"ref": "Tile kit.3d.tsx"}],
            "builder": {"name": "Austin", "lat": 30.267, "lon": -97.743, "country": "US"},
            "routes": [{"supplier": "suppliers/jlcpcb.supplier.tsx", "legs": [
                {"carrier": "DHL", "service": "Express pickup", "transitDays": 1, "cost": 6, "currency": "USD",
                 "to": {"name": "DHL hub, Hong Kong", "lat": 22.308, "lon": 113.918, "country": "HK"}},
                {"carrier": "DHL", "service": "Express Worldwide", "transitDays": 4, "cost": 32, "currency": "USD"}]}]})
        with self.assertRaisesRegex(ValueError, "cost states its currency"):
            declare_document(logistics(route(leg(carrier="UPS", cost=5), supplier="s.supplier.tsx")))
        with self.assertRaisesRegex(ValueError, "whole number"):
            declare_document(logistics(quantity=2.5))


if __name__ == "__main__":
    unittest.main()
