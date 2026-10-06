"""Tasks and projects, declared in Python: the same documents and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``tasks.ts``), each element a call::

    from commandagi.design.tasks import project, subtask, task, view

    result = task(subtask(ref="Ship it/Draft.task.py"), id="ship", title="Ship it", status="doing", due_at="2026-10-20")
    result = project(view(id="board", name="Board", mode="board", group_by="status"), id="launch", name="Launch")

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``due_at`` is ``dueAt``). A task's subtasks are ``subtask(ref=…)`` children (each its own file, by path from
this one), in order; a project's views are ``view`` children. Times (``startAt``, ``dueAt``, ``closedAt``,
``createdAt``, ``updatedAt``) are epoch milliseconds in the document and may be written as a date (``"2026-10-20"``,
UTC midnight) or a UTC time. A run gives back ``{"format", "document", "sources"}`` beside an empty graph; ``sources``
names each element's call by its path (``""``, ``subtask#Ship it/Draft.task.py``, ``view#board``).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

TASK_FIELDS = ["id", "title", "status", "priority", "glyph", "assignees", "projects", "blockedBy", "labels", "startAt", "dueAt",
               "closedAt", "threadId", "createdBy", "readme", "createdAt", "updatedAt"]
PROJECT_FIELDS = ["id", "name", "glyph", "defaultViewId", "subprojects", "archived", "readme", "createdAt", "updatedAt"]
VIEW_FIELDS = ["id", "name", "mode", "groupBy", "filter", "laneOrder"]
TIME_FIELDS = ["startAt", "dueAt", "closedAt", "createdAt", "updatedAt"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "task": {"holds": "children"},
    "subtask": {},
    "project": {"holds": "children"},
    "view": {},
}

__all__ = ["TASK_FIELDS", "PROJECT_FIELDS", "VIEW_FIELDS", "TIME_FIELDS", "SIGNATURES", "time_of", "TASK_VOCABULARY",
           "PROJECT_VOCABULARY", *define(globals(), "tasks", SIGNATURES)]

_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?$")


def time_of(value: Any, what: str) -> int:
    """A time as the document holds it: epoch ms from an int, a date or a UTC time (as the TypeScript SDK's ``timeOf``)."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and _TIME.match(value):
        text = value + "T00:00:00Z" if len(value) == 10 else value
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return int(round(moment.timestamp() * 1000))
    raise ValueError(f'{what} is a date ("2026-10-20"), a UTC time ("2026-10-20T14:30:00Z") or epoch milliseconds, not {value!r}')


def _where(t: DocTree) -> str:
    return f'<{t["tag"]} id="{t["attrs"]["id"]}">' if isinstance(t["attrs"].get("id"), str) else f"<{t['tag']}>"


def _fields(t: DocTree) -> Dict[str, Any]:
    """The attributes of an element as a record's fields: times as epoch ms."""
    return {k: (time_of(v, f"{_where(t)} {k}") if k in TIME_FIELDS else v) for k, v in t["attrs"].items()}


def _task(t: DocTree) -> Dict[str, Any]:
    subtasks: List[Any] = [c["attrs"].get("ref") for c in t["children"] if c["tag"] == "subtask"]
    for ref in subtasks:
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"<subtask> ref is a path to a .task.tsx file, not {ref!r}")
    return {**_fields(t), **({"subtasks": subtasks} if subtasks else {})}


def _project(t: DocTree) -> Dict[str, Any]:
    views = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "view"]
    return {**_fields(t), **({"views": views} if views else {})}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


TASK_VOCABULARY = Vocabulary("task", "a task", "task", {
    "task": {"parents": [], "required": ["id"], "attrs": TASK_FIELDS},
    "subtask": {"parents": ["task"], "key": "ref", "required": ["ref"], "attrs": ["ref"]},
}, _task, _never)

PROJECT_VOCABULARY = Vocabulary("project", "a project", "project", {
    "project": {"parents": [], "required": ["id"], "attrs": PROJECT_FIELDS},
    "view": {"parents": ["project"], "key": "id", "required": ["id"], "attrs": VIEW_FIELDS},
}, _project, _never)

for _v in (TASK_VOCABULARY, PROJECT_VOCABULARY):
    register_vocabulary(_v, "tasks")
