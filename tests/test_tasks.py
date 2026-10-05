"""Tasks and projects declared in Python give what the TypeScript SDK's JSX gives (tasks.test.ts there): the task's or
the project's body in the run's one shape, subtasks as refs in order, times as epoch ms.
Run: python -m unittest discover -s tests"""
import unittest
from datetime import datetime, timezone

from commandagi.design import project, project_view, run_module, subtask, task
from commandagi.design.tasks import declare_task_document, time_of

OCT_20 = int(datetime(2026, 10, 20, tzinfo=timezone.utc).timestamp() * 1000)


class TaskTests(unittest.TestCase):
    def test_a_task_is_its_body(self):
        d = declare_task_document(task("ship", subtask("Ship it/Draft.task.py"), subtask("Ship it/Send.task.tsx"),
                                       title="Ship it", status="doing", priority="high", assignees=["agent:writer"],
                                       dueAt="2026-10-20", readme="Ship it.md"))
        self.assertEqual(d, {"format": "task", "sources": {}, "document": {
            "id": "ship", "title": "Ship it", "status": "doing", "priority": "high", "assignees": ["agent:writer"],
            "dueAt": OCT_20, "readme": "Ship it.md", "subtasks": ["Ship it/Draft.task.py", "Ship it/Send.task.tsx"]}})
        with self.assertRaisesRegex(ValueError, "subtasks is not read"):
            declare_task_document(task("a", subtasks=["x.task.tsx"]))
        with self.assertRaisesRegex(ValueError, 'two <subtask> in <task> have ref "x.task.tsx"'):
            declare_task_document(task("a", subtask("x.task.tsx"), subtask("x.task.tsx")))
        with self.assertRaisesRegex(ValueError, "dueAt is a date"):
            declare_task_document(task("a", dueAt="next week"))

    def test_times(self):
        self.assertEqual(time_of("2026-10-20", "t"), OCT_20)
        self.assertEqual(time_of("2026-10-20T14:30:00Z", "t"), OCT_20 + (14 * 60 + 30) * 60000)
        self.assertEqual(time_of(1, "t"), 1)

    def test_a_project_and_a_run(self):
        d = declare_task_document(project("launch", project_view(id="board", name="Board", mode="board", groupBy="status"), name="Launch", archived=False))
        self.assertEqual(d["document"], {"id": "launch", "name": "Launch", "archived": False,
                                          "views": [{"id": "board", "name": "Board", "mode": "board", "groupBy": "status"}]})
        out = run_module('from commandagi.design import task\nresult = task("t1", title="Water the plants", status="todo")', "Tasks/Water.task.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"], {"format": "task", "document": {"id": "t1", "title": "Water the plants", "status": "todo"}, "sources": {}})


if __name__ == "__main__":
    unittest.main()
