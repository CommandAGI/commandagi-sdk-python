"""Tasks and projects, declared in Python: the same documents and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``tasks.ts``), each element a call::

    from commandagi.design.tasks import project, subtask, task, view

    result = task(subtask(ref="Ship it/Draft.task.py"), id="ship", title="Ship it", status="doing", due_at="2026-10-20")
    result = project(view(id="board", name="Board", mode="board", group_by="status"), id="launch", name="Launch")

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``due_at`` is ``dueAt``). A task's subtasks are ``subtask(ref=…)`` children (each its own file, by path from
this one), in order; a project's views are ``view`` children. Times (``startAt``, ``dueAt``, ``closedAt``,
``expires``, ``approvedAt``, ``createdAt``, ``updatedAt``) are epoch milliseconds in the document and may be written as
a date (``"2026-10-20"``, UTC midnight) or a UTC time. A run gives back ``{"format", "document", "sources"}`` beside an
empty graph; ``sources`` names each element's call by its path (``""``, ``subtask#Ship it/Draft.task.py``,
``view#board``).

A proposal is a task with status ``proposed``: ``sketch(ref=…)`` names the file that shows what it will do, and each
``asks(…)`` has the shape of one standing grant (``world``, ``units``, ``channels``, ``verbs``; or ``folder`` and
``files``; or ``folder``, ``venues``, ``symbols``, ``max_qty``, ``max_notional``, ``per_day``; each with ``hours`` and
``note``)::

    result = task(
        sketch(ref="../worlds/shop/runs/cut/run.json"),
        asks(world="../worlds/shop/world.tsx", units=["cnc-1"], channels=["gcode"], verbs=["open", "arm", "run"], hours=4),
        id="cut", title="Cut the bracket", status="proposed", assignees=["agent:claude"], expires="2026-10-11T18:00:00Z",
    )

A change proposal carries the files it changes: each ``change(file=…, base=…, proposed=…)`` names the design file
(a ref), the content id (SHA-256, hex) of the version the edit was made from, and the edited copy (a ref).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

TASK_FIELDS = ["id", "title", "status", "priority", "glyph", "assignees", "projects", "blockedBy", "labels", "startAt", "dueAt",
               "closedAt", "threadId", "createdBy", "readme", "expires", "approvedBy", "approvedAt", "grants", "createdAt",
               "updatedAt"]
ASK_FIELDS = ["world", "units", "channels", "verbs", "folder", "files", "venues", "symbols", "maxQty", "maxNotional", "perDay",
              "hours", "note"]
CHANGE_FIELDS = ["file", "base", "proposed"]
PROJECT_FIELDS = ["id", "name", "glyph", "defaultViewId", "subprojects", "archived", "readme", "createdAt", "updatedAt"]
VIEW_FIELDS = ["id", "name", "mode", "groupBy", "filter", "laneOrder"]
TIME_FIELDS = ["startAt", "dueAt", "closedAt", "expires", "approvedAt", "createdAt", "updatedAt"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "task": {"holds": "children"},
    "sketch": {},
    "asks": {},
    "change": {},
    "subtask": {},
    "project": {"holds": "children"},
    "view": {},
}

__all__ = ["TASK_FIELDS", "ASK_FIELDS", "CHANGE_FIELDS", "PROJECT_FIELDS", "VIEW_FIELDS", "TIME_FIELDS", "SIGNATURES", "time_of", "TASK_VOCABULARY",
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
    sketches = [c["attrs"].get("ref") for c in t["children"] if c["tag"] == "sketch"]
    for ref in sketches:
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"<sketch> ref is a path to the file that shows the work, not {ref!r}")
    asks = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "asks"]
    changes = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "change"]
    for c in changes:
        for k in ("file", "proposed"):
            if not isinstance(c.get(k), str) or not c.get(k):
                raise ValueError(f"<change> {k} is a path from this file, not {c.get(k)!r}")
        base = c.get("base")
        if not isinstance(base, str) or len(base) != 64 or any(ch not in "0123456789abcdef" for ch in base):
            raise ValueError(f'<change file="{c.get("file")}"> base is the content id (SHA-256, hex) of the version the edit was made from, not {base!r}')
    return {**_fields(t), **({"sketch": sketches[0]} if sketches else {}), **({"asks": asks} if asks else {}),
            **({"changes": changes} if changes else {}), **({"subtasks": subtasks} if subtasks else {})}


def _project(t: DocTree) -> Dict[str, Any]:
    views = [dict(c["attrs"]) for c in t["children"] if c["tag"] == "view"]
    return {**_fields(t), **({"views": views} if views else {})}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


TASK_VOCABULARY = Vocabulary("task", "a task", "task", {
    "task": {"parents": [], "required": ["id"], "attrs": TASK_FIELDS},
    "sketch": {"parents": ["task"], "single": True, "required": ["ref"], "attrs": ["ref"]},
    "asks": {"parents": ["task"], "attrs": ASK_FIELDS},
    "change": {"parents": ["task"], "key": "file", "required": ["file", "base", "proposed"], "attrs": CHANGE_FIELDS},
    "subtask": {"parents": ["task"], "key": "ref", "required": ["ref"], "attrs": ["ref"]},
}, _task, _never)

PROJECT_VOCABULARY = Vocabulary("project", "a project", "project", {
    "project": {"parents": [], "required": ["id"], "attrs": PROJECT_FIELDS},
    "view": {"parents": ["project"], "key": "id", "required": ["id"], "attrs": VIEW_FIELDS},
}, _project, _never)

for _v in (TASK_VOCABULARY, PROJECT_VOCABULARY):
    register_vocabulary(_v, "tasks")
