"""A study declared in Python gives what the TypeScript SDK's JSX gives (study.test.ts there): the question's JSON in
the run's one shape, loads typed by their tag, a tag of another kind refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import study as s
from commandagi.design.documents import declare_document

FACE = {"kind": "face", "select": {"normal": [0, 0, -1]}}
HINGE = {"inBox": {"min": [0, -5, 0], "max": [0, 5, 0]}}


class StudyTests(unittest.TestCase):
    def test_a_structural_study_is_its_question(self):
        d = declare_document(s.study(
            s.material(grade="PETG", poisson=0.38),
            s.fixture(id="mount", type="fixed", faces=FACE),
            s.fixture(id="hinge", type="fixed", faces=FACE, region=HINGE),
            s.loadCase(s.force(id="grip", faces=FACE, total=[-40, 0, 0]), s.pressure(id="air", faces=FACE, value=0.1), id="clamp"),
            s.mesh(order=2, size=2, refine=[1, 0.7, 0.5]),
            s.solver(kind="calculix", analysis="static", timeout=1800),
            s.criterion(id="safety", quantity="vonMises.max", limit="yield / 2", load_case="clamp"),
            kind="structural", part="Jaw.3d.tsx", units="mm-N-MPa-t",
        ))
        self.assertEqual(d["format"], "study")
        doc = {
            "kind": "structural", "part": "Jaw.3d.tsx", "units": "mm-N-MPa-t",
            "material": {"grade": "PETG", "poisson": 0.38},
            "fixtures": [{"id": "mount", "type": "fixed", "faces": FACE}, {"id": "hinge", "type": "fixed", "faces": FACE, "region": HINGE}],
            "loadCases": [{"id": "clamp", "loads": [{"type": "force", "id": "grip", "faces": FACE, "total": [-40, 0, 0]},
                                                    {"type": "pressure", "id": "air", "faces": FACE, "value": 0.1}]}],
            "mesh": {"order": 2, "size": 2, "refine": [1, 0.7, 0.5]},
            "solver": {"kind": "calculix", "analysis": "static", "timeout": 1800},
            "criteria": [{"id": "safety", "quantity": "vonMises.max", "limit": "yield / 2", "loadCase": "clamp"}],
        }
        self.assertEqual(d["document"], doc)
        v = s.study_vocabulary
        self.assertEqual(v.from_tree(v.to_tree(doc)), doc)
        with self.assertRaisesRegex(ValueError, r"<study> needs part"):
            declare_document(s.study(kind="structural"))
        with self.assertRaisesRegex(ValueError, r"kind is one of"):
            declare_document(s.study(kind="thermal", part="a.3d.tsx"))
        with self.assertRaisesRegex(ValueError, r"<force> stands in <loadCase>, not in <study>"):
            declare_document(s.study(s.force(id="f", faces=FACE, total=[0, 0, 1]), kind="structural", part="a.3d.tsx"))

    def test_a_flow_study_is_the_fluid_the_inlet_and_the_outlet(self):
        inlet, outlet = {"kind": "face", "select": {"normal": [-1, 0, 0]}}, {"kind": "face", "select": {"normal": [1, 0, 0]}}
        side = {"kind": "face", "select": {"normal": [0, 1, 0]}}
        d = declare_document(s.study(
            s.fluid(nu=1e-6), s.inlet(id="inlet", faces=inlet, velocity=0.5), s.inlet(id="side", faces=side, velocity=0.2),
            s.outlet(id="outlet", faces=outlet),
            s.flowMesh(cells=[20, 3, 3], levels=[1, 2, 4]), s.criterion(id="drop", quantity="pressureDrop", limit=2),
            kind="flow", part="Channel.3d.tsx", units="m-kg-s",
        ))
        self.assertEqual(d["document"], {
            "kind": "flow", "part": "Channel.3d.tsx", "units": "m-kg-s", "fluid": {"nu": 1e-6},
            "inlets": [{"id": "inlet", "faces": inlet, "velocity": 0.5}, {"id": "side", "faces": side, "velocity": 0.2}],
            "outlets": [{"id": "outlet", "faces": outlet}],
            "flowMesh": {"cells": [20, 3, 3], "levels": [1, 2, 4]},
            "criteria": [{"id": "drop", "quantity": "pressureDrop", "limit": 2}],
        })
        with self.assertRaisesRegex(ValueError, r"<mesh> belongs to a structural study, not to a flow one"):
            declare_document(s.study(s.mesh(size=2), kind="flow", part="a.3d.tsx"))

    def test_a_step_response_study_names_its_steps_gains_and_window(self):
        d = declare_document(s.study(
            s.step(id="lift", joint="shoulder_lift", from_=0.54, to=0.84),
            s.gains(joint="shoulder_lift", kp=12, kv=0.6),
            s.response(duration=1, dt=0.001, band=0.02),
            s.criterion(id="settle", quantity="settlingTime", limit=0.3, step="lift"),
            kind="step-response", part="../worlds/arm-cell/world.tsx#arm", units=s.STEP_RESPONSE_UNITS,
        ))
        doc = {
            "kind": "step-response", "part": "../worlds/arm-cell/world.tsx#arm", "units": "rad-s",
            "steps": [{"id": "lift", "joint": "shoulder_lift", "from": 0.54, "to": 0.84}],
            "gains": [{"joint": "shoulder_lift", "kp": 12, "kv": 0.6}],
            "response": {"duration": 1, "dt": 0.001, "band": 0.02},
            "criteria": [{"id": "settle", "quantity": "settlingTime", "limit": 0.3, "step": "lift"}],
        }
        self.assertEqual(d["document"], doc)
        v = s.study_vocabulary
        self.assertEqual(v.from_tree(v.to_tree(doc)), doc)
        with self.assertRaisesRegex(ValueError, r"<mesh> belongs to a structural study, not to a step-response one"):
            declare_document(s.study(s.mesh(size=2), kind="step-response", part="definition.tsx"))
        with self.assertRaisesRegex(ValueError, r'<step id="a"> needs to'):
            declare_document(s.study(s.step(id="a", joint="j", from_=0), kind="step-response", part="definition.tsx"))


if __name__ == "__main__":
    unittest.main()
