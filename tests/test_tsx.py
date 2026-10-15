"""``to_tsx(element)``: a Python document written as the TypeScript SDK's code file, for a place that reads only TSX
(feedback #10). That the TSX declares the same document as the Python is checked in the repository, where both run
(tests/workbench/sdk-python-tsx.test.mjs). Run: python -m unittest tests.test_tsx"""
import unittest

from commandagi.design import to_tsx
from commandagi.design.office import b, p
from commandagi.design.pcb import board, component, trace
from commandagi.design.schematic import group, resistor
from commandagi.design.threed import extrude, parameter, part


class ToTsx(unittest.TestCase):
    def test_a_document_is_its_default_export(self):
        self.assertEqual(
            to_tsx(group("Divider", resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9))),
            'export default () => (\n'
            '  <group name="Divider">\n'
            '    <resistor name="R1" resistance="3k" schX={114.3} schY={88.9} />\n'
            '  </group>\n'
            ');\n',
        )

    def test_values_are_javascript_literals(self):
        tsx = to_tsx(part(
            parameter(name="t", value=6.0, unit="mm", bindings=[{"target": "e1", "field": "distance"}]),
            extrude(id="e1", profile={"sketch": "s1"}, distance=-2.5, through=True, consumes=None),
            name='The "plate" & co',
        ))
        self.assertIn('<part name={"The \\"plate\\" & co"}>', tsx)
        self.assertIn('<parameter name="t" value={6} unit="mm" bindings={[{ target: "e1", field: "distance" }]} />', tsx)
        self.assertIn('<extrude id="e1" profile={{ sketch: "s1" }} distance={-2.5} through={true} />', tsx)

    def test_a_snake_case_keyword_is_written_by_its_attribute_name(self):
        tsx = to_tsx(board(trace(layer="F.Cu", points=[[9, 22], [9, 10]], from_=".V1 > .pin1", to=".R1 > .pin1"),
                           component(name="R1", footprint="smd-0805", pcb_x=10, pcb_y=10), width=40))
        self.assertIn('from=".V1 > .pin1"', tsx)
        self.assertIn('pcbX={10}', tsx)
        self.assertIn('points={[[9, 22], [9, 10]]}', tsx)

    def test_text_is_inline_and_kept_exactly(self):
        tsx = to_tsx(p("The run ", b("passed"), " {twice} <ok>"))
        self.assertIn('<p>The run <b>passed</b>{" {twice} <ok>"}</p>', tsx)

    def test_a_long_tag_puts_one_attribute_on_a_line(self):
        tsx = to_tsx(group("G", resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9, footprint="Resistor_SMD:R_0402_1005Metric_Pad0.72x0.64mm_HandSolder")))
        self.assertIn('    <resistor\n      name="R1"\n      resistance="3k"\n', tsx)
        self.assertIn('      footprint="Resistor_SMD:R_0402_1005Metric_Pad0.72x0.64mm_HandSolder"\n    />\n', tsx)

    def test_what_javascript_cannot_say_is_refused(self):
        with self.assertRaisesRegex(ValueError, "distance: nan"):
            to_tsx(part(extrude(id="e1", distance=float("nan"))))
        with self.assertRaisesRegex(TypeError, "a document's root element"):
            to_tsx({"nodes": {}})


if __name__ == "__main__":
    unittest.main()
