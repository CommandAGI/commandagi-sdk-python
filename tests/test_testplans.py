"""A test plan, a firmware release and a rollout declared in Python give what the TypeScript SDK's JSX gives
(testplans.test.ts there): each document both ways, steps in order, what a tag may not say refused by name, and a
unit's serial and revision read from a world.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.firmware import FIRMWARE, firmware, health, rollout, supports, target
from commandagi.design.ontology import unit, world
from commandagi.design.testplans import TESTPLANS, condition, fixture, step, testplan

SHA = "9f2c".ljust(64, "0")


class TestPlanTests(unittest.TestCase):
    def test_a_test_plan_is_its_steps_in_order(self):
        d = declare_document(testplan(
            condition(id="ambient", quantity="temperature", min=15, max=35, unit="C"),
            fixture(id="supply", kind="instrument", unit="psu-1", channel="output"),
            step(id="rail-3v3", channel="power", command={"verb": "read"}, read="v3v3", min=3.2, max=3.4, unit="V", verifies=["req.tsx#rail"]),
            step(id="current", fixture="supply", read="current", max=0.4, settle_ms=500),
            title="Cam-001 power rail", device="../devices/cam/definition.tsx",
        ))
        self.assertEqual(d["format"], "testplan")
        doc = {
            "title": "Cam-001 power rail", "device": "../devices/cam/definition.tsx",
            "conditions": [{"id": "ambient", "quantity": "temperature", "min": 15, "max": 35, "unit": "C"}],
            "fixtures": [{"id": "supply", "kind": "instrument", "unit": "psu-1", "channel": "output"}],
            "steps": [
                {"id": "rail-3v3", "channel": "power", "command": {"verb": "read"}, "read": "v3v3", "min": 3.2, "max": 3.4, "unit": "V", "verifies": ["req.tsx#rail"]},
                {"id": "current", "fixture": "supply", "read": "current", "max": 0.4, "settleMs": 500},
            ],
        }
        self.assertEqual(d["document"], doc)
        v = TESTPLANS["testplan"]
        self.assertEqual(v.from_tree(v.to_tree(doc)), doc, "both ways")
        with self.assertRaisesRegex(ValueError, "<step> needs id"):
            declare_document(testplan(step(read="x")))
        with self.assertRaisesRegex(ValueError, "limit is not read"):
            declare_document(testplan(step(id="a", limit=3)))
        with self.assertRaisesRegex(ValueError, "verifies is a list of refs"):
            declare_document(testplan(step(id="a", verifies="req.tsx")))
        with self.assertRaisesRegex(ValueError, 'two <step> in <testplan> have id "a"'):
            declare_document(testplan(step(id="a"), step(id="a")))

    def test_a_run_names_each_record_by_its_call(self):
        out = run_module(
            "from commandagi.design.testplans import fixture, step, testplan\n"
            "result = testplan(\n"
            "    fixture(id=\"bed\", kind=\"jig\"),\n"
            "    step(id=\"rail\", channel=\"power\", read=\"v3v3\", min=3.2),\n"
            "    title=\"Rail\",\n"
            ")\n", "Rail.testplan.py")
        self.assertEqual(out["document"]["format"], "testplan")
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "fixture#bed", "step#rail"])
        self.assertEqual((sources["step#rail"]["tag"], sources["step#rail"]["line"]), ("step", 4))


class FirmwareTests(unittest.TestCase):
    def test_a_release_states_its_digest_sbom_device_and_revisions(self):
        d = declare_document(firmware(supports(revision="B"), supports(revision="C"), version="1.4.0", image="build/cam.bin", sha256=SHA,
                                      size=1024, sbom="build/cam.cdx.json", device="../devices/cam/definition.tsx", security_version=2))
        self.assertEqual(d["format"], "firmware")
        doc = {"version": "1.4.0", "image": "build/cam.bin", "sha256": SHA, "size": 1024, "sbom": "build/cam.cdx.json",
               "device": "../devices/cam/definition.tsx", "securityVersion": 2, "supports": [{"revision": "B"}, {"revision": "C"}]}
        self.assertEqual(d["document"], doc)
        v = FIRMWARE["firmware"]
        self.assertEqual(v.from_tree(v.to_tree(doc)), doc)
        with self.assertRaisesRegex(ValueError, "<firmware> needs sbom"):
            declare_document(firmware(version="1", image="a.bin", sha256=SHA, device="d.tsx"))
        with self.assertRaisesRegex(ValueError, "64 lowercase hex digits"):
            declare_document(firmware(version="1", image="a.bin", sha256="ABC", sbom="s.json", device="d.tsx"))

    def test_a_rollout_its_stages_health_checks_and_targets(self):
        d = declare_document(rollout(
            health(id="no-crash", channel="state", command={"verb": "read"}, read="crashes", max=0),
            target(unit="cam-1"), target(unit="cam-2"),
            firmware="cam.firmware.tsx", world="worlds/fleet/world.tsx", channel="firmware", canary=10, waves=[50, 100], settle_ms=5000,
        ))
        self.assertEqual(d["format"], "rollout")
        doc = {"firmware": "cam.firmware.tsx", "world": "worlds/fleet/world.tsx", "channel": "firmware", "canary": 10, "waves": [50, 100],
               "settleMs": 5000, "health": [{"id": "no-crash", "channel": "state", "command": {"verb": "read"}, "read": "crashes", "max": 0}],
               "targets": [{"unit": "cam-1"}, {"unit": "cam-2"}]}
        self.assertEqual(d["document"], doc)
        v = FIRMWARE["rollout"]
        self.assertEqual(v.from_tree(v.to_tree(doc)), doc)
        with self.assertRaisesRegex(ValueError, "<rollout> needs waves"):
            declare_document(rollout(firmware="a.firmware.tsx", world="w.tsx", channel="firmware", canary=10))


class UnitTests(unittest.TestCase):
    def test_a_unit_says_its_serial_and_its_hardware_revision(self):
        d = declare_document(world(unit(uid="cam-1", name="cam", device="d.tsx", serial="CAM-000123", revision="B", position=[0, 0, 0], rotation=0),
                                   name="fleet", kind="physical"))
        self.assertEqual(d["document"]["units"][0], {"uid": "cam-1", "name": "cam", "device": "d.tsx", "serial": "CAM-000123", "revision": "B",
                                                      "position": [0, 0, 0], "rotation": 0})


if __name__ == "__main__":
    unittest.main()
