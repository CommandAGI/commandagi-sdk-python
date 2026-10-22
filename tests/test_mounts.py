"""A thread's mounts declared in Python give what the TypeScript vocabulary's JSX gives (mounts.ts in the CommandAGI
repository): each mount is its record, one task or a list, and a mount that does not read is refused with why.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.mounts import mount, mounts

EXAMPLE = {"mounts": [
    {"label": "launch", "folder": "../../Tasks/launch"},
    {"label": "ship it", "task": "../../Tasks/Ship it.task.tsx"},
    {"label": "owner inbox", "assignee": "user:u_1", "status": ["todo", "doing", "blocked"]},
]}


class MountTests(unittest.TestCase):
    def test_the_example_is_its_document(self):
        d = declare_document(mounts(
            mount(label="launch", folder="../../Tasks/launch"),
            mount(label="ship it", task="../../Tasks/Ship it.task.tsx"),
            mount(label="owner inbox", assignee="user:u_1", status=["todo", "doing", "blocked"]),
        ))
        self.assertEqual(d, {"format": "mounts", "sources": {}, "document": EXAMPLE})
        self.assertEqual(declare_document(mounts())["document"], {"mounts": []})

    def test_a_bad_mount_is_refused(self):
        bad = {
            "mounts one task, or a list": mount(label="a", task="x.task.tsx", folder="Tasks"),
            "mounts nothing": mount(label="a"),
            "labels is a list of texts\Z": mount(label="a", labels=None),
            "assignee is user:<id> or agent:<id>": mount(label="a", assignee="ada"),
            "status is a list of proposed, todo, doing": mount(label="a", status=["later"]),
            "labels is a list of texts": mount(label="a", labels=[""]),
            "folder is a text": mount(label="a", folder=""),
            "label is a short text": mount(label="x" * 201, folder="Tasks"),
            "needs label": mount(folder="Tasks"),
            "colour is not read": mount(label="a", folder="Tasks", colour="red"),
        }
        for why, m in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(mounts(m))
        with self.assertRaisesRegex(ValueError, 'two <mount> in <mounts> have label "a"'):
            declare_document(mounts(mount(label="a", folder="x"), mount(label="a", folder="y")))
        with self.assertRaisesRegex(ValueError, "<mounts> stands in"):
            declare_document(mounts(mounts(mount(label="a", folder="x"))))

    def test_a_run_names_each_mount_by_its_label(self):
        out = run_module(
            "from commandagi.design.mounts import mount, mounts\n"
            "result = mounts(\n"
            "    mount(label=\"launch\", folder=\"../../Tasks/launch\"),\n"
            "    mount(label=\"ship it\", task=\"../../Tasks/Ship it.task.tsx\"),\n"
            "    mount(label=\"owner inbox\", assignee=\"user:u_1\", status=[\"todo\", \"doing\", \"blocked\"]),\n"
            ")\n", "runs/thread-1/mounts.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "mounts")
        self.assertEqual(out["document"]["document"], EXAMPLE)
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "mount#launch", "mount#owner inbox", "mount#ship it"])
        self.assertEqual((sources["mount#ship it"]["tag"], sources["mount#ship it"]["line"]), ("mount", 4))


if __name__ == "__main__":
    unittest.main()
