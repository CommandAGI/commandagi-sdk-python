"""Systems declared in Python give what the TypeScript SDK's JSX gives (systems.test.ts there): a requirements document,
a system and an interface, each record an element with its fields verbatim; a wrong field refused with the same
sentence. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.systems import (bom, budget, check, contribution, converter, frame, hole, interface, load, message,
                                       mode, param, pin, rail, requirement, requirements, side, system)


class SystemsTests(unittest.TestCase):
    def test_requirements(self):
        d = declare_document(requirements(
            requirement(id="mass", text="At most 500 g.", method="analysis", verified_by="Rover.system.py#mass", design=["cad/Rover.3d.py"]),
            requirement(id="drop", text="Survives a 1 m drop.", method="test", rationale="a person drops it"),
            name="Rover"))
        self.assertEqual(d["format"], "requirements")
        self.assertEqual(d["document"], {"name": "Rover", "requirements": [
            {"id": "mass", "text": "At most 500 g.", "method": "analysis", "verifiedBy": "Rover.system.py#mass", "design": ["cad/Rover.3d.py"]},
            {"id": "drop", "text": "Survives a 1 m drop.", "method": "test", "rationale": "a person drops it"}]})
        with self.assertRaisesRegex(ValueError, r'<requirement id="x">: method must be one of test, analysis, inspection, demonstration \(got "review"\)'):
            declare_document(requirements(requirement(id="x", text="t", method="review")))
        with self.assertRaisesRegex(ValueError, "id is letters, digits"):
            declare_document(requirements(requirement(id="a b", text="t")))
        with self.assertRaisesRegex(ValueError, '<requirement id="x"> needs text'):
            declare_document(requirements(requirement(id="x")))
        with self.assertRaisesRegex(ValueError, "verifiedBy is a ref or a list of refs"):
            declare_document(requirements(requirement(id="x", text="t", verified_by=3)))

    def test_a_system(self):
        d = declare_document(system(
            mode(id="lte"),
            rail(id="+5V", voltage=5, source="USB"),
            rail(id="VBAT", voltage=3.8),
            converter(id="U3", input="+5V", output="VBAT", efficiency=0.88, source="estimate"),
            load(id="modem", part="U4", rail="VBAT", mode="lte", current=0.67, peak_current=0.9, source="datasheet table 35"),
            contribution(id="shell", quantity="mass", part="P1", value=15.2, unit="g", source="check-fit.mjs"),
            bom(ref="bom.csv"),
            budget(id="power", quantity="power", rail="+5V", mode="lte", limit=10, unit="W", margin=0.2),
            budget(id="peak", quantity="power", rail="+5V", mode="lte", peak=True, limit=10, unit="W"),
            check(id="link", kind="interface", of="Link.interface.py"),
            name="Cam"))["document"]
        self.assertEqual(list(d), ["name", "modes", "rails", "converters", "loads", "contributions", "boms", "budgets", "checks"])
        self.assertEqual(d["rails"], [{"id": "+5V", "voltage": 5, "source": "USB"}, {"id": "VBAT", "voltage": 3.8}])
        self.assertEqual(d["loads"][0]["peakCurrent"], 0.9)
        self.assertEqual(d["budgets"][1]["peak"], True)
        cases = [
            (budget(id="b", quantity="mass", limit=1, peak=True), "peak is true or false, on a power budget"),
            (load(id="l", part="U1", rail="r", mode="m", current=1, peak_current="2 A"), "peakCurrent is a number"),
            (load(id="l", part="U1", rail="r", mode="m", power=1, duty=0), "duty is the share of time the load draws"),
            (budget(id="b", quantity="Exhaust flow", limit=1, unit="m3/h"),
             r"<budget id=\"b\">: quantity must be one of mass, power, cost, thermal, or a quantity's name"),
            (budget(id="b", quantity="exhaust-flow", limit=600), r'<budget id="b">: a quantity of exhaust-flow states its unit'),
            (contribution(id="c", quantity="exhaust-flow", part="P", value=35, source="datasheet"),
             r'<contribution id="c">: a quantity of exhaust-flow states its unit'),
            (budget(id="b", quantity="power", limit=1), "a power budget names its rail and its mode"),
            (budget(id="b", quantity="thermal", limit=1, mode="m"), r"thermal resistance to the ambient \(resistance, K/W\)"),
            (budget(id="b", quantity="mass", limit=1, margin=1.5), "margin is a fraction"),
            (budget(id="b", quantity="cost", per=100, limit=30), "a cost budget names the design whose logistics roll-up it reads"),
            (contribution(id="c", quantity="cost", part="P", value=1, source="a quote"), "a cost is stated in the design's logistics"),
            (converter(id="c", input="a", output="b", efficiency=88), r"efficiency is a number in \(0, 1\]"),
            (load(id="l", part="U1", rail="r", mode="m"), r"a load states its current \(A\) or its power \(W\)"),
            (contribution(id="c", quantity="mass", part="P", value=1), "source says where the number was read"),
            (check(id="k", kind="erc", of="x"), "kind must be one of interface, trace"),
            (mode(id="m", watts=3), "watts is not read"),
        ]
        for el, message in cases:
            with self.assertRaisesRegex(ValueError, message):
                declare_document(system(el))

    def test_an_interface(self):
        d = declare_document(interface(
            frame(description="the base board's top, pin 1 at the origin", unit="mm"),
            pin(number=1, signal="+5V", required=True, at=[-11.43, 0]),
            pin(number=4, signal="MODEM_TXD", gpio=13, dir="in"),
            hole(id="m2-a", at=[0, 0], diameter=2.2),
            message(id="lte-only", text="AT+CNMP=38"),
            param(id="baud", value=115200, unit="Bd"),
            param(id="framing", value="8N1"),
            side(id="base", ref="ee/base.circuit.ts", parts=["J1", "J2"], origin=[0, 1.4], rotation=90, face="back"),
            side(id="firmware", ref="fw/config.h", defines={"BOARD": 1}, pins={"RX_PIN": 4}, params={"BAUD": "baud"}),
            side(id="host", ref="devices/cam/definition.tsx", channel="modem", params={"baud": "baud"}),
            name="Header"))["document"]
        self.assertEqual(d["frame"], {"description": "the base board's top, pin 1 at the origin", "unit": "mm"})
        self.assertEqual(d["params"][1], {"id": "framing", "value": "8N1"}, "a text a channel states has no unit")
        self.assertEqual(d["sides"][0], {"id": "base", "ref": "ee/base.circuit.ts", "parts": ["J1", "J2"], "origin": [0, 1.4], "rotation": 90, "face": "back"})
        self.assertEqual(d["sides"][1], {"id": "firmware", "ref": "fw/config.h", "defines": {"BOARD": 1}, "pins": {"RX_PIN": 4}, "params": {"BAUD": "baud"}})
        self.assertEqual(d["sides"][2], {"id": "host", "ref": "devices/cam/definition.tsx", "channel": "modem", "params": {"baud": "baud"}})
        cases = [
            (pin(number=0, signal="x"), "number is the pin's number, 1, 2, 3"),
            (pin(number=1, signal="x", at=[1]), r"at is \[x, y\] mm"),
            (hole(id="h", at=[0, 0, 0]), r'<hole id="h">: at is \[x, y\] mm'),
            (message(id="m"), "a message has its text, its code, or both"),
            (side(id="s", ref="x", kind="mechanical"), "kind must be one of circuit, 3d, firmware, definition"),
            (side(id="s", ref="x", channel=3), "channel is the id of a channel of the device definition"),
            (side(id="s", ref="x", rotation="90\u00b0"), "rotation is the angle the interface's frame is turned on this side, in degrees counter-clockwise"),
            (side(id="s", ref="x", face="bottom"), r'<side id="s">: face must be one of front, back \(got "bottom"\)'),
            (param(id="p", value=True), r"value is a number with its unit in unit \(115200\), or a text a channel states"),
            (param(id="p", value="8N1", unit="Bd"), "a parameter stated as a text has no unit"),
            (frame(unit="in"), "positions are in mm"),
        ]
        for el, msg in cases:
            with self.assertRaisesRegex(ValueError, msg):
                declare_document(interface(el))
        with self.assertRaisesRegex(ValueError, "<interface> has one <frame>"):
            declare_document(interface(frame(), frame()))

    def test_a_run_names_each_record_by_its_call(self):
        out = run_module(
            "from commandagi.design.systems import requirement, requirements\n"
            "result = requirements(\n"
            "    requirement(id=\"mass\", text=\"At most 500 g.\", method=\"analysis\", verified_by=\"Rover.system.py#mass\"),\n"
            "    name=\"Rover\",\n"
            ")\n", "Rover.req.py")
        self.assertEqual(out["document"]["format"], "requirements")
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "requirement#mass"])
        self.assertEqual((sources["requirement#mass"]["tag"], sources["requirement#mass"]["line"]), ("requirement", 3))


if __name__ == "__main__":
    unittest.main()
