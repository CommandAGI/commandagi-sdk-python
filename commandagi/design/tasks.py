"""Tasks and projects, declared in Python: the same documents as the TypeScript SDK's JSX (``commandagi/design``
``tasks.ts``), with calls in place of tags. Each call is one record; its keyword arguments are the record's fields,
verbatim; its positional arguments are its children::

    result = task("ship", subtask("Ship it/Draft.task.py"), title="Ship it", status="doing", dueAt="2026-10-20")
    result = project("launch", project_view(id="board", name="Board", mode="board", groupBy="status"), name="Launch")

A task's subtasks are ``subtask(ref)`` records (each its own file, by path from this one), in order; a project's views
are ``project_view`` records. Times (``startAt``, ``dueAt``, ``closedAt``, ``createdAt``, ``updatedAt``) are epoch
milliseconds in the document and may be written as a date (``"2026-10-20"``, UTC midnight) or a UTC time. A run gives
back the run's one shape (``{"format", "document", "sources"}`` beside an empty graph).
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .ontology import Element, _fields

TASK_FIELDS = ["id", "title", "status", "priority", "glyph", "assignees", "projects", "blockedBy", "labels", "startAt", "dueAt",
               "closedAt", "threadId", "createdBy", "readme", "createdAt", "updatedAt"]
PROJECT_FIELDS = ["id", "name", "glyph", "defaultViewId", "subprojects", "archived", "readme", "createdAt", "updatedAt"]
VIEW_FIELDS = ["id", "name", "mode", "groupBy", "filter", "laneOrder"]
TIME_FIELDS = ["startAt", "dueAt", "closedAt", "createdAt", "updatedAt"]

_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?$")


def time_of(value: Any, what: str) -> int:
    """A time as the document holds it: epoch ms from an int, a date or a UTC time (as the TypeScript SDK's ``timeOf``)."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and _TIME.match(value):
        text = value + "T00:00:00Z" if len(value) == 10 else value
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return int(round(moment.timestamp() * 1000))
    raise ValueError(f'{what} is a date ("2026-10-20"), a UTC time ("2026-10-20T14:30:00Z") or epoch milliseconds, not {value!r}')


def _record(el: Element, keys: List[str]) -> Dict[str, Any]:
    name = f'<{el.tag} id="{el.attrs["id"]}">' if isinstance(el.attrs.get("id"), str) else f"<{el.tag}>"
    for k in el.attrs:
        if k not in keys:
            raise ValueError(f"{name}: {k} is not read ({', '.join(keys)})")
    if el.tag in ("task", "project", "view") and el.attrs.get("id") is None:
        raise ValueError(f"{name} needs id")
    return {k: (time_of(v, f"{name} {k}") if k in TIME_FIELDS else copy.deepcopy(v)) for k, v in el.attrs.items()}


def _task(root: Element) -> Dict[str, Any]:
    doc = _record(root, TASK_FIELDS)
    refs: List[str] = []
    for c in root.children:
        if c.tag != "subtask":
            raise ValueError(f"<{c.tag}> stands in a task only as <subtask ref>; a task holds no other task")
        ref = c.attrs.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"<subtask> ref is a path to a .task.tsx file, not {ref!r}")
        if ref in refs:
            raise ValueError(f'two <subtask> in <task> have ref "{ref}"')
        refs.append(ref)
    if refs:
        doc["subtasks"] = refs
    return doc


def _project(root: Element) -> Dict[str, Any]:
    doc = _record(root, PROJECT_FIELDS)
    views: List[Dict[str, Any]] = []
    for c in root.children:
        if c.tag != "view":
            raise ValueError(f"<{c.tag}> is not a tag of a project (<view>)")
        v = _record(c, VIEW_FIELDS)
        if any(x["id"] == v["id"] for x in views):
            raise ValueError(f'two <view> in <project> have id "{v["id"]}"')
        views.append(v)
    if views:
        doc["views"] = views
    return doc


def is_task_document(value: Any) -> bool:
    """Whether a value is the root record of a task or a project."""
    return isinstance(value, Element) and value.tag in ("task", "project")


def declare_task_document(root: Element) -> Dict[str, Any]:
    """The task or project a root record declares, in the run's one shape: ``{"format", "document", "sources"}``."""
    if root.tag == "task":
        return {"format": "task", "document": _task(root), "sources": {}}
    if root.tag == "project":
        return {"format": "project", "document": _project(root), "sources": {}}
    raise ValueError(f"<{root.tag}> is not a task or a project")


def task(id: str, *subtasks: Element, **fields: Any) -> Element:
    """A task (``<name>.task.py``): its fields, and its subtasks' files in order."""
    return Element("task", {"id": id, **_fields(fields)}, subtasks)


def subtask(ref: str) -> Element:
    """A subtask: its own file, by path from the task's file."""
    return Element("subtask", {"ref": ref})


def project(id: str, *views: Element, **fields: Any) -> Element:
    """A project (``<name>.project.py``): its fields and its named views."""
    return Element("project", {"id": id, **_fields(fields)}, views)


def project_view(**fields: Any) -> Element:
    """A project's view (``<view>`` in JSX): id, name, mode, groupBy, filter, laneOrder."""
    return Element("view", _fields(fields))
