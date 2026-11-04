"""A supplier and a logistics plan declared in Python give what the TypeScript SDK's JSX gives (logistics-plan.test.ts
there): a supplier's location, carriers and contacts; a plan's BOM designs, builder and legs, a leg with no place
ending at the builder; and what the vocabulary has no words for refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.logistics import ahead, bom, builder, contact, fee, leg, location, logistics, route, service, ships, source, stock, supplier, use


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
            "contacts": [{"role": "sales", "email": "support@jlcpcb.com"}], "services": []})
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
                {"carrier": "DHL", "service": "Express Worldwide", "transitDays": 4, "cost": 32, "currency": "USD"}]}], "sources": []})
        with self.assertRaisesRegex(ValueError, "cost states its currency"):
            declare_document(logistics(route(leg(carrier="UPS", cost=5), supplier="s.supplier.tsx")))
        with self.assertRaisesRegex(ValueError, "whole number"):
            declare_document(logistics(quantity=2.5))


    def test_a_leg_that_says_quote_this_states_its_want_parcel_and_postal_codes(self):
        d = declare_document(logistics(
            builder(name="the builder, San Francisco", lat=37.72, lon=-122.44, country="US", postal="94112"),
            route(leg(carrier="USPS", quote="cheapest", kg=2.5, mm=[300, 250, 220], to="a buyer, Berlin", lat=52.52, lon=13.4,
                      country="DE", postal="10115"), supplier="suppliers/x.supplier.tsx"),
            name="helmet"))
        self.assertEqual(d["document"]["builder"], {"name": "the builder, San Francisco", "lat": 37.72, "lon": -122.44, "country": "US", "postal": "94112"})
        self.assertEqual(d["document"]["routes"][0]["legs"][0], {"carrier": "USPS", "quote": "cheapest", "kg": 2.5, "mm": [300, 250, 220],
                                                               "to": {"name": "a buyer, Berlin", "lat": 52.52, "lon": 13.4, "country": "DE", "postal": "10115"}})
        for bad, words in [({"quote": "the cheap one"}, "quote is cheapest, fastest"), ({"quote": "ups/03"}, "quote needs its parcel"),
                           ({"quote": "fastest", "kg": 2, "mm": [300, 250]}, "mm is the parcel")]:
            with self.assertRaisesRegex(ValueError, words):
                declare_document(logistics(route(leg(carrier="UPS", **bad), supplier="s.supplier.tsx")))

    def test_a_supplier_offers_services_with_their_days_and_fees(self):
        d = declare_document(supplier(
            service(fee(amount=20, currency="USD", per="line", note="connectors and batteries"), fee(amount=0.017, currency="USD", per="unit"),
                    id="global-sourcing", name="Global sourcing", review_days=1, review_days_high=3, lead_time_days=9, lead_time_days_high=20),
            name="JLCPCB"))
        self.assertEqual(d["document"]["services"], [{
            "id": "global-sourcing", "name": "Global sourcing", "reviewDays": 1, "reviewDaysHigh": 3, "leadTimeDays": 9, "leadTimeDaysHigh": 20,
            "fees": [{"amount": 20, "currency": "USD", "per": "line", "note": "connectors and batteries"},
                     {"amount": 0.017, "currency": "USD", "per": "unit"}]}])
        with self.assertRaisesRegex(ValueError, "fee> needs currency"):
            declare_document(supplier(service(fee(amount=70, per="line", each=50), id="consignment"), name="JLCPCB"))

    def test_a_plan_states_its_build_date_and_how_a_line_is_filled(self):
        d = declare_document(logistics(
            source(use(offer="JLCPCB parts library", qty=1984), use(offer="LCSC"), part="KH-205580-DZ", strategy="split"),
            name="helmets", quantity=10, build="2027-01-15"))
        self.assertEqual(d["document"]["build"], "2027-01-15")
        self.assertEqual(d["document"]["sources"], [{"part": "KH-205580-DZ", "strategy": "split",
                                                     "uses": [{"offer": "JLCPCB parts library", "qty": 1984}, {"offer": "LCSC"}]}])
        with self.assertRaisesRegex(ValueError, "strategy is single, fill, split or dual"):
            declare_document(logistics(source(use(offer="LCSC"), part="X", strategy="cheapest")))

    def test_buying_ahead_and_stock_on_hand_a_plan_buys_past_its_need_for_a_later_plan_which_counts_it_a_service_counted_in_business_days(self):
        ten = declare_document(logistics(
            source(use(offer="JLCPCB parts library"), use(offer="JLCPCB parts library", mpn="FT2232HL-TRAY"),
                   ahead(qty=157, for_="Helmet 100.logistics.tsx"), part="FT2232HL-REEL", strategy="fill"),
            source(ahead(qty=500, for_="Helmet 100.logistics.tsx", note="the reel's rest"), part="TLV333IDCKR"),
            quantity=10, build="2027-01-15"))["document"]
        self.assertEqual(ten["sources"], [
            {"part": "FT2232HL-REEL", "strategy": "fill", "uses": [{"offer": "JLCPCB parts library"}, {"offer": "JLCPCB parts library", "mpn": "FT2232HL-TRAY"}],
             "ahead": {"qty": 157, "for": "Helmet 100.logistics.tsx"}},
            {"part": "TLV333IDCKR", "uses": [], "ahead": {"qty": 500, "for": "Helmet 100.logistics.tsx", "note": "the reel's rest"}}])
        self.assertNotIn("stocks", ten, "a plan that holds no stock states none")
        hundred = declare_document(logistics(stock(from_="Helmet 10.logistics.tsx"),
                                             stock(part="KH-205580-DZ", qty=2000, arrives="2027-03-01", note="consigned at JLCPCB"), quantity=100))["document"]
        self.assertEqual(hundred["stocks"], [{"from": "Helmet 10.logistics.tsx"},
                                             {"part": "KH-205580-DZ", "qty": 2000, "arrives": "2027-03-01", "note": "consigned at JLCPCB"}])
        for children, words in [
            ((stock(from_="a.logistics.tsx", qty=3),), "<stock from> takes what that plan bought ahead"),
            ((stock(part="X"),), "names the part and its qty, or the plan it is from"),
            ((stock(part="X", qty=3, arrives="soon"),), "arrives is a date"),
            ((source(ahead(qty=1.5, for_="b.logistics.tsx"), part="X"),), "<ahead> qty is a whole number"),
            ((source(part="X"),), "names no <use> and no <ahead>"),
            ((source(use(offer="A"), part="X"),), "strategy is single, fill, split or dual"),
        ]:
            with self.subTest(words=words), self.assertRaisesRegex(ValueError, words):
                declare_document(logistics(*children))
        jlc = declare_document(supplier(service(id="global-sourcing", review_days=1, review_days_high=3, lead_time_days=9, lead_time_days_high=20,
                                                business_days=True), name="JLCPCB"))["document"]
        self.assertEqual(jlc["services"], [{"id": "global-sourcing", "reviewDays": 1, "reviewDaysHigh": 3, "leadTimeDays": 9, "leadTimeDaysHigh": 20,
                                            "businessDays": True, "fees": []}])
        with self.assertRaisesRegex(ValueError, "businessDays is true or false"):
            declare_document(supplier(service(id="s", business_days="yes"), name="X"))


if __name__ == "__main__":
    unittest.main()
