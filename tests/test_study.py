"""A study declared in Python gives what the TypeScript SDK's JSX gives (study.test.ts there): the question's JSON in
the run's one shape, loads typed by their tag, a tag of another kind refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import study as s
from commandagi.design.documents import declare_document

FACE = {"kind": "face", "select": {"normal": [0, 0, -1]}}


class StudyTests(unittest.TestCase):
    def test_a_structural_study_is_its_question(self):
        d = declare_document(s.study(
            s.material(grade="PETG", poisson=0.38),
            s.fixture(id="mount", type="fixed", faces=FACE),
            s.loadCase(s.force(id="grip", faces=FACE, total=[-40, 0, 0]), s.pressure(id="air", faces=FACE, value=0.1), id="clamp"),
            s.mesh(order=2, size=2, refine=[1, 0.7, 0.5]),
            s.criterion(id="safety", quantity="vonMises.max", limit="yield / 2", load_case="clamp"),
            kind="structural", part="Jaw.3d.tsx", units="mm-N-MPa-t",
        ))
        self.assertEqual(d["format"], "study")
        doc = {
            "kind": "structural", "part": "Jaw.3d.tsx", "units": "mm-N-MPa-t",
            "material": {"grade": "PETG", "poisson": 0.38},
            "fixtures": [{"id": "mount", "type": "fixed", "faces": FACE}],
            "loadCases": [{"id": "clamp", "loads": [{"type": "force", "id": "grip", "faces": FACE, "total": [-40, 0, 0]},
                                                    {"type": "pressure", "id": "air", "faces": FACE, "value": 0.1}]}],
            "mesh": {"order": 2, "size": 2, "refine": [1, 0.7, 0.5]},
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
        d = declare_document(s.study(
            s.fluid(nu=1e-6), s.inlet(faces=inlet, velocity=0.5), s.outlet(faces=outlet),
            s.flowMesh(cells=[20, 3, 3], levels=[1, 2, 4]), s.criterion(id="drop", quantity="pressureDrop", limit=2),
            kind="flow", part="Channel.3d.tsx", units="m-kg-s",
        ))
        self.assertEqual(d["document"], {
            "kind": "flow", "part": "Channel.3d.tsx", "units": "m-kg-s", "fluid": {"nu": 1e-6},
            "inlet": {"faces": inlet, "velocity": 0.5}, "outlet": {"faces": outlet},
            "flowMesh": {"cells": [20, 3, 3], "levels": [1, 2, 4]},
            "criteria": [{"id": "drop", "quantity": "pressureDrop", "limit": 2}],
        })
        with self.assertRaisesRegex(ValueError, r"<mesh> belongs to a structural study, not to a flow one"):
            declare_document(s.study(s.mesh(size=2), kind="flow", part="a.3d.tsx"))


if __name__ == "__main__":
    unittest.main()
