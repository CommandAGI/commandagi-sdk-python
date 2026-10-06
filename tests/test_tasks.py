"""Tasks and projects declared in Python give what the TypeScript SDK's JSX gives (tasks.test.ts there): the task's or
the project's body in the run's one shape, subtasks as refs in order, times as epoch ms, each record named by its call.
Run: python -m unittest discover -s tests"""
import unittest
from datetime import datetime, timezone

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.tasks import project, subtask, task, time_of, view

OCT_20 = int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp() * 1000)


class TaskTests(unittest.TestCase):
    def test_a_task_is_its_body(self):
        d = declare_document(task(subtask(ref="Ship it/Draft.task.py"), subtask(ref="Ship it/Send.task.tsx"),
                                  id="ship", title="Ship it", status="doing", priority="high", assignees=["agent:writer"],
                                  due_at="2026-10-20", readme="Ship it.md"))
        self.assertEqual(d, {"format": "task", "sources": {}, "document": {
            "id": "ship", "title": "Ship it", "status": "doing", "priority": "high", "assignees": ["agent:writer"],
            "dueAt": OCT_20, "readme": "Ship it.md", "subtasks": ["Ship it/Draft.task.py", "Ship it/Send.task.tsx"]}})
        with self.assertRaisesRegex(ValueError, "subtasks is not read"):
            declare_document(task(id="a", subtasks=["x.task.tsx"]))
        with self.assertRaisesRegex(ValueError, 'two <subtask> in <task> have ref "x.task.tsx"'):
            declare_document(task(subtask(ref="x.task.tsx"), subtask(ref="x.task.tsx"), id="a"))
        with self.assertRaisesRegex(ValueError, "dueAt is a date"):
            declare_document(task(id="a", due_at="next week"))
        with self.assertRaisesRegex(TypeError, "dueAt is written due_at"):
            task(id="a", dueAt="2026-10-20")

    def test_times(self):
        self.assertEqual(time_of("2026-10-20", "t"), OCT_20)
        self.assertEqual(time_of("2026-10-20T14:30:00Z", "t"), OCT_20 + (14 * 60 + 30) * 60000)
        self.assertEqual(time_of(1, "t"), 1)

    def test_a_project(self):
        d = declare_document(project(view(id="board", name="Board", mode="board", group_by="status"), id="launch", name="Launch", archived=False))
        self.assertEqual(d["document"], {"id": "launch", "name": "Launch", "archived": False,
                                         "views": [{"id": "board", "name": "Board", "mode": "board", "groupBy": "status"}]})

    def test_a_run_names_each_record_by_its_call(self):
        out = run_module(
            "from commandagi.design.tasks import subtask, task\n"
            "result = task(\n"
            "    subtask(ref=\"Water/Fill the can.task.py\"),\n"
            "    id=\"t1\",\n"
            "    title=\"Water the plants\",\n"
            ")\n", "Tasks/Water.task.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["document"], {"id": "t1", "title": "Water the plants", "subtasks": ["Water/Fill the can.task.py"]})
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "subtask#Water/Fill the can.task.py"])
        self.assertEqual((sources[""]["tag"], sources[""]["line"]), ("task", 2))
        self.assertEqual(sources[""]["props"]["title"]["value"], "Water the plants")
        self.assertEqual((sources["subtask#Water/Fill the can.task.py"]["tag"], sources["subtask#Water/Fill the can.task.py"]["line"]), ("subtask", 3))


if __name__ == "__main__":
    unittest.main()
