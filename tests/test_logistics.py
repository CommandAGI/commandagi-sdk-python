"""A design's logistics in code (docs/formats.md § logistics): a schematic part's and a circuit component's suppliers and
facets as KiCad property forms, read back by part_fields; a circuit's logistics check(options=); a board's fab(...); a
3D document's item(...), assemble(...) and the logistics fields of body(engineering=). The same cases as the TypeScript
SDK's sdk/typescript/src/design/logistics.test.ts, with the same forms byte for byte.
Run: python -m unittest discover -s tests"""
import copy
import unittest

from commandagi.design import circuit, component, footprints
from commandagi.design import pcb, schematic, threed
from commandagi.design.element import declarer_of
from commandagi.design.part_fields import js_json
from commandagi.design.schematic import part_fields

LCSC = {"name": "LCSC", "sku": "C21264512", "currency": "USD", "priceBreaks": [{"quantity": 1, "unitPrice": 9.4}, {"quantity": 10, "unitPrice": 9.15}],
        "stock": 1, "leadTimeDays": 3, "source": "lcsc.com", "date": "2026-10-15"}
LOGISTICS = {
    "suppliers": [LCSC, {"name": "DigiKey", "sku": "A7670G-ND"}],
    "alternates": [{"manufacturer": "SIMCom", "mpn": "A7670E-LASE"}],
    "datasheet": "https://www.simcom.com/product/A7670X.html",
    "lifecycle": {"status": "active", "onHand": 2, "reorderPoint": 5},
    "compliance": {"rohs": "compliant", "reach": "compliant", "eccn": "5A992.c", "certifications": ["FCC ID 2AJYU-8BAE003", "CE"]},
    "shipping": {"hsCode": "8517.62", "origin": "CN", "hazmat": "none"},
}
FORMS = [
    ["MPN", "A7670G-LLSE"],
    ["LCSC Part", "C21264512"],
    ["LCSC Terms", '{"currency":"USD","priceBreaks":[[1,9.4],[10,9.15]],"leadTimeDays":3,"stock":1,"source":"lcsc.com","date":"2026-10-15"}'],
    ["DigiKey Part", "A7670G-ND"],
    ["Alternates", '[{"manufacturer":"SIMCom","mpn":"A7670E-LASE"}]'],
    ["Datasheet", "https://www.simcom.com/product/A7670X.html"],
    ["Lifecycle", "active"],
    ["On Hand", "2"],
    ["Reorder Point", "5"],
    ["RoHS", "compliant"],
    ["REACH", "compliant"],
    ["ECCN", "5A992.c"],
    ["Certifications", "FCC ID 2AJYU-8BAE003, CE"],
    ["HS Code", "8517.62"],
    ["Country of Origin", "CN"],
    ["Hazmat", "none"],
]


def props(inputs):
    return [[f["items"][1]["v"], f["items"][2]["v"]] for f in inputs["foreign"]]


def declared(root):
    return declarer_of(root)(root, "L")["graph"]


def sheet(*children):
    return declared(schematic.group("L", *children))


def board(*children):
    return pcb.declare_board_file(pcb.board(*children, schematic="L.sch.tsx", width=20, height=20)).ir


class LogisticsTests(unittest.TestCase):
    def test_a_schematic_part_states_its_suppliers_and_facets_as_kicad_properties_read_back_by_part_fields(self):
        g = sheet(schematic.part("U4", pins=["1", "2"], mpn="A7670G-LLSE", **copy.deepcopy(LOGISTICS)))
        self.assertEqual(props(g["nodes"]["U4"]["inputs"]), FORMS)
        self.assertEqual(part_fields(g["nodes"]["U4"]["inputs"]), {"mpn": "A7670G-LLSE", **LOGISTICS})

    def test_a_circuits_component_takes_the_same_fields_as_the_same_forms(self):
        def body():
            component(ref="U4", footprint=footprints.chip("0603", "R"), mpn="A7670G-LLSE", **copy.deepcopy(LOGISTICS))
        g = circuit("C", body).ir
        part = next(n for n in g["nodes"].values() if n["inputs"].get("ref") == "U4")
        self.assertEqual(props(part["inputs"]), FORMS)

    def test_a_wrong_logistics_field_is_refused_by_name_and_attrs_cannot_say_what_an_argument_says(self):
        for kw, message in (
            ({"suppliers": [{"name": "LCSC", "price": 3}]}, r"suppliers\[0\]: price is not a term of an offer"),
            ({"suppliers": [{"name": "LCSC", "priceBreaks": [{"quantity": 0, "unitPrice": 1}]}]}, r"priceBreaks is a list of \{ quantity, unitPrice \}"),
            ({"suppliers": [{"name": "LCSC", "currency": "usd"}]}, r"currency is an ISO 4217 code"),
            ({"lifecycle": {"onHand": 3}}, r"lifecycle needs its status"),
            ({"lifecycle": {"status": "dead"}}, r"lifecycle.status is one of active, nrnd, eol, obsolete"),
            ({"compliance": {"rohs": "yes"}}, r"compliance.rohs is one of compliant, exempt, non-compliant"),
            ({"shipping": {"origin": "China"}}, r"shipping.origin is an ISO 3166 alpha-2 code"),
            ({"attrs": {"LCSC Part": "C1"}}, r"attrs names LCSC Part: say it with suppliers="),
            ({"attrs": {"RoHS": "compliant"}}, r"attrs names RoHS: say it with compliance="),
            ({"attrs": {"Datasheet": "x"}}, r"attrs names Datasheet: say it with datasheet="),
        ):
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, message):
                sheet(schematic.part("U4", pins=["1"], **kw))

    def test_terms_print_numbers_as_javascript_does(self):
        self.assertEqual(js_json({"a": [1.0, 9.4, 0.1 + 0.2, 1e-7, 0.00001, 1e21, 2.5e-10, -0.5]}),
                         '{"a":[1,9.4,0.30000000000000004,1e-7,0.00001,1e+21,2.5e-10,-0.5]}')

    def test_a_circuits_logistics_check_keeps_its_options_a_boards_fab_is_one_board_fact_checked_by_name(self):
        s = sheet(schematic.check(id="cost", kind="cost", options={"quantities": [10, 100]}))
        self.assertEqual(s["meta"]["checks"], [{"id": "cost", "kind": "cost", "options": {"quantities": [10, 100]}}])
        fab = {"suppliers": [{"name": "JLCPCB", "currency": "USD", "priceBreaks": [{"quantity": 5, "unitPrice": 2}], "leadTimeDays": 7,
                              "source": "jlcpcb.com quote", "date": "2026-10-15"}],
               "finish": "ENIG", "mask": "green", "silk": "white", "minTrack": 0.09, "minSpace": 0.09, "minDrill": 0.15, "minAnnularRing": 0.13,
               "maxLayers": 6, "thicknesses": [1.6], "assembly": {"house": "JLCPCB", "sides": ["top"]},
               "inspection": {"electrical": "flying-probe", "acceptance": "boots"},
               "compliance": {"rohs": "compliant", "reach": "compliant", "eccn": "EAR99"},
               "shipping": {"hsCode": "8534.00", "origin": "CN", "hazmat": "none"}}
        g = board(pcb.fab(suppliers=fab["suppliers"], finish="ENIG", mask="green", silk="white", min_track=0.09, min_space=0.09, min_drill=0.15,
                          min_annular_ring=0.13, max_layers=6, thicknesses=[1.6], assembly=fab["assembly"], inspection=fab["inspection"],
                          compliance=fab["compliance"], shipping=fab["shipping"]))
        facts = [n for n in g["nodes"].values() if n["type"] == "eda.boardfact" and n["inputs"].get("fact") == "fab"]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["inputs"], {"fact": "fab", **fab})
        for children, message in (
            ((pcb.fab(), pcb.fab()), r"a board has one <fab>"),
            ((pcb.fab(layers=4),), r"prop layers is not read on a board"),
            ((pcb.fab(assembly={"house": "JLCPCB", "sides": ["left"]}),), r'assembly.sides is a list of "top", "bottom"'),
            ((pcb.fab(inspection={"electrical": "x-ray"}),), r"inspection.electrical is one of flying-probe, fixture, none"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                board(*children)

    def test_a_3d_documents_item_and_assemble_are_lists_of_the_document_and_body_engineering_takes_the_logistics_fields(self):
        g = threed.declare_threed(threed.part(
            threed.box(id="b", center=[0, 0, 5], size=[10, 10, 10], operation="new"),
            threed.body(id="b", engineering={"process": "fdm-printing",
                                             "make": {"device": "devices/ender/definition.tsx", "cycleMinutes": 30, "ratePerHour": 2, "currency": "USD"},
                                             "inspection": {"procedure": "look", "acceptance": "flat"}}),
            threed.item(id="tape", name="Foam tape", qty=2, engineering={"process": "purchased", "suppliers": [{"name": "DigiKey", "sku": "3M4026-ND"}]}),
            threed.assemble(id="s1", order=1, parts=["b", "tape"], by="in-house", minutes=2),
            name="P"))
        self.assertEqual(g["nodes"]["items"]["inputs"]["value"],
                         [{"id": "tape", "name": "Foam tape", "qty": 2, "engineering": {"process": "purchased", "suppliers": [{"name": "DigiKey", "sku": "3M4026-ND"}]}}])
        self.assertEqual(g["nodes"]["assemblySteps"]["inputs"]["value"], [{"id": "s1", "order": 1, "parts": ["b", "tape"], "by": "in-house", "minutes": 2}])
        for el, message in (
            (threed.body(id="b", engineering={"vendor": {"name": "X"}}), "vendor"),
            (threed.item(id="t", name="T", qty=0), "qty"),
            (threed.body(id="b", engineering={"lifecycle": {"status": "dead"}}), "status"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                threed.declare_threed(threed.part(el, name="P"))


if __name__ == "__main__":
    unittest.main()
