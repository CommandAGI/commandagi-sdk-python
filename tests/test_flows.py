"""A process flow declared in Python gives what the TypeScript SDK's JSX gives (flows.test.ts there): its tools and its
steps, each step with its params and measures; a wrong field refused with the same sentence.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.flows import expect, flow, input, measure, param, step, tool, visit


class FlowsTests(unittest.TestCase):
    def test_a_flow(self):
        d = declare_document(flow(
            tool(id="coater", ref="Kit.3d.tsx#coater", rate_per_hour=40, currency="USD"),
            step(id="why", kind="note", instruction="Marks first."),
            step(param(name="speed", value=3000, unit="rpm"),
                 measure(id="resist", name="resist thickness", nominal=1.2, plus=0.1, minus=0.1, unit="um"),
                 visit(tool="oven", minutes=2, instruction="soft bake"),
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
                 "measures": [{"id": "resist", "name": "resist thickness", "nominal": 1.2, "plus": 0.1, "minus": 0.1, "unit": "um"}],
                 "visits": [{"tool": "oven", "minutes": 2, "instruction": "soft bake"}]},
            ]})

    def test_a_workflow(self):
        d = declare_document(flow(
            input(name="ticket", type="text"),
            input(name="token", type="text", private=True, required=True),
            tool(id="arm", ref="Kit.3d.tsx#arm"),
            step(expect(name="reply", equals="read", within=5), id="read", kind="message", channel="orders",
                 instruction="Read the ticket ${input:ticket}.", surprise="parent"),
            step(expect(name="exit", equals=0, tolerance=0), id="go", kind="command", channel="arm",
                 command="move ${env:ARM_TOKEN}", after="read", minutes=2, surprise="person", surprise_to="ops@example.com"),
            step(expect(name="done", equals=True), id="call", kind="workflow", ref="Inspect.flow.tsx", after="go",
                 surprise="agent", surprise_to="claude"),
            name="Ship a fix"))
        self.assertEqual(d["document"], {
            "name": "Ship a fix",
            "inputs": [{"name": "ticket", "type": "text"}, {"name": "token", "type": "text", "private": True, "required": True}],
            "tools": [{"id": "arm", "ref": "Kit.3d.tsx#arm"}],
            "steps": [
                {"id": "read", "kind": "message", "channel": "orders", "instruction": "Read the ticket ${input:ticket}.",
                 "surprise": "parent", "expects": [{"name": "reply", "equals": "read", "within": 5}]},
                {"id": "go", "kind": "command", "channel": "arm", "command": "move ${env:ARM_TOKEN}", "after": "read",
                 "minutes": 2, "surprise": "person", "surpriseTo": "ops@example.com", "expects": [{"name": "exit", "equals": 0, "tolerance": 0}]},
                {"id": "call", "kind": "workflow", "ref": "Inspect.flow.tsx", "after": "go", "surprise": "agent",
                 "surpriseTo": "claude", "expects": [{"name": "done", "equals": True}]},
            ]})

    def test_refusals(self):
        refused = [
            (flow(step(id="a", kind="rest")), r'<step id="a">: kind must be one of work, note, message, command, computer, robot, chain, workflow, decision, agent \(got "rest"\)'),
            (flow(input(name="t", type="date")), r'<input name="t">: type is one of text, number, boolean \(got "date"\)'),
            (flow(input(name="t", private=True, default="x")), r'<input name="t">: a private input states no default'),
            (flow(input(name="t", type="number", default="x")), r'<input name="t">: default is a number'),
            (flow(step(expect(name="e", equals=1), id="a", kind="message", channel="c", surprise="parent")), r'<step id="a">: a message step states its instruction'),
            (flow(step(id="a", kind="command", channel="c", command="ls", surprise="parent")), r'<step id="a">: an action step declares what must be observed after it'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls")), r'<step id="a">: an action step says where a surprise goes'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls", surprise="person")), r'<step id="a">: surprise "person" names who handles it'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls", surprise="parent", surprise_to="x")), r'<step id="a">: a surprise that goes to the parent names no surpriseTo'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls", surprise="parent", after="b")), r'<step id="a">: after names the step "b", which this flow does not declare'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls", surprise="parent", after="a")), r'<step id="a">: after does not name the step itself'),
            (flow(step(expect(name="e", equals=1), id="a", kind="command", channel="c", command="ls ${input:nope}", surprise="parent")), r'<step id="a">: \$\{input:nope\} is not a bound value'),
            (flow(step(expect(name="e", equals="ok", tolerance=1), id="a", kind="command", channel="c", command="ls", surprise="parent")), r'<expect name="e">: a tolerance holds of a number'),
            (flow(step(expect(name="e", equals=1, within=0), id="a", kind="command", channel="c", command="ls", surprise="parent")), r'<expect name="e">: within is a number of seconds, more than 0'),
            (flow(step(id="a", minutes=-1)), r'<step id="a">: minutes is a number of at least 0'),
            (flow(step(id="a", order=0)), r'<step id="a">: order is a whole number from 1'),
            (flow(step(id="a", kind="note", minutes=5)), r'<step id="a">: a note step names no tool, takes no time'),
            (flow(step(id="a", currency="usd")), r'<step id="a">: currency is an ISO 4217 code'),
            (flow(tool(id="t", rate_per_hour=-2)), r'<tool id="t">: ratePerHour is a number of at least 0'),
            (flow(step(param(name="gas", value=["SF6"]), id="a")), r'<param name="gas">: value is a number, a text or true/false'),
            (flow(step(measure(id="m", plus=0.1), id="a")), r'<measure id="m">: plus and minus are tolerances of the nominal: give nominal'),
            (flow(step(measure(id="m", min=2, max=1), id="a")), r'<measure id="m">: min is at most max'),
            (flow(param(name="x", value=1)), r'<param> stands in <step>, not in <flow>'),
            (flow(step(visit(tool="oven", minutes=-1), id="a")), r'<step id="a"> <visit tool="oven">: minutes is a number of at least 0'),
            (flow(step(visit(tool="oven"), id="a", kind="note")), r'<step id="a">: a note step names no tool, takes no time .* no param, measure, visit or expect'),
            (flow(step(measure(id="m", max=1), id="a"), step(measure(id="m", max=2), id="b")), r'<measure id="m">: two measures have this id'),
            (flow(step(param(name="t", value=1), param(name="t", value=2), id="a")), r'<step id="a">: two params are named "t"'),
        ]
        for root, why in refused:
            with self.assertRaisesRegex(ValueError, why):
                declare_document(root)


if __name__ == "__main__":
    unittest.main()
