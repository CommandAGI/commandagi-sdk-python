"""A process flow declared in Python gives what the TypeScript SDK's JSX gives (flows.test.ts there): its tools and its
steps, each step with its params and measures; a wrong field refused with the same sentence.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.flows import flow, measure, param, step, tool


class FlowsTests(unittest.TestCase):
    def test_a_flow(self):
        d = declare_document(flow(
            tool(id="coater", ref="Kit.3d.tsx#coater", rate_per_hour=40, currency="USD"),
            step(id="why", kind="note", instruction="Marks first."),
            step(param(name="speed", value=3000, unit="rpm"),
                 measure(id="resist", name="resist thickness", nominal=1.2, plus=0.1, minus=0.1, unit="um"),
                 id="coat", order=1, tool="coater", by="in-house", minutes=6),
            name="Marks", of="Kit.3d.tsx#wafer"))
        self.assertEqual(d["format"], "flow")
        self.assertEqual(d["document"], {
            "name": "Marks", "of": "Kit.3d.tsx#wafer",
            "tools": [{"id": "coater", "ref": "Kit.3d.tsx#coater", "ratePerHour": 40, "currency": "USD"}],
            "steps": [
                {"id": "why", "kind": "note", "instruction": "Marks first."},
                {"id": "coat", "order": 1, "tool": "coater", "by": "in-house", "minutes": 6,
                 "params": [{"name": "speed", "value": 3000, "unit": "rpm"}],
                 "measures": [{"id": "resist", "name": "resist thickness", "nominal": 1.2, "plus": 0.1, "minus": 0.1, "unit": "um"}]},
            ]})

    def test_refusals(self):
        refused = [
            (flow(step(id="a", kind="rest")), r'<step id="a">: kind must be one of work, note \(got "rest"\)'),
            (flow(step(id="a", minutes=-1)), r'<step id="a">: minutes is a number of at least 0'),
            (flow(step(id="a", order=0)), r'<step id="a">: order is a whole number from 1'),
            (flow(step(id="a", kind="note", minutes=5)), r'<step id="a">: a note step names no tool, takes no time'),
            (flow(step(id="a", currency="usd")), r'<step id="a">: currency is an ISO 4217 code'),
            (flow(tool(id="t", rate_per_hour=-2)), r'<tool id="t">: ratePerHour is a number of at least 0'),
            (flow(step(param(name="gas", value=["SF6"]), id="a")), r'<param name="gas">: value is a number, a text or true/false'),
            (flow(step(measure(id="m", plus=0.1), id="a")), r'<measure id="m">: plus and minus are tolerances of the nominal: give nominal'),
            (flow(step(measure(id="m", min=2, max=1), id="a")), r'<measure id="m">: min is at most max'),
            (flow(param(name="x", value=1)), r'<param> stands in <step>, not in <flow>'),
            (flow(step(measure(id="m", max=1), id="a"), step(measure(id="m", max=2), id="b")), r'<measure id="m">: two measures have this id'),
            (flow(step(param(name="t", value=1), param(name="t", value=2), id="a")), r'<step id="a">: two params are named "t"'),
        ]
        for root, why in refused:
            with self.assertRaisesRegex(ValueError, why):
                declare_document(root)


if __name__ == "__main__":
    unittest.main()
