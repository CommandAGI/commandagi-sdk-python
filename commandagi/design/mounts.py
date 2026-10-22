"""A thread's mounted tasks, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``mounts.ts``), each element a call. ``mounts.py`` in the thread's run folder declares one
``mounts``, and each ``mount`` is one record of it, its fields the element's attributes::

    from commandagi.design.mounts import mount, mounts

    result = mounts(
        mount(label="launch", folder="../../Tasks/launch"),
        mount(label="ship it", task="../../Tasks/Ship it.task.tsx"),
        mount(label="owner inbox", assignee="user:u_1", status=["todo", "doing", "blocked"]),
    )

``label`` names the mount in its thread (unique there). What it mounts is one task (``task``, a ref to a ``.task.tsx``),
or a list: the tasks at or under a folder (``folder``), the tasks of a project (``project``, a ref to a
``.project.tsx``), or a query (``assignee``, ``labels``, ``status``), each narrowing the others. A ref is a path relative
to the run folder, or an absolute address. A run gives back ``{"format": "mounts", "document": {"mounts": [...]},
"sources"}`` beside an empty graph; ``sources`` names each mount's call by its label (``mount#launch``).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

MOUNT_FIELDS = ["label", "task", "folder", "project", "assignee", "labels", "status"]
#: The task statuses a mount's ``status`` may name.
MOUNT_STATUSES = ["proposed", "todo", "doing", "blocked", "done", "cancelled", "declined"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "mounts": {"holds": "children"},
    "mount": {},
}

__all__ = ["MOUNT_FIELDS", "MOUNT_STATUSES", "SIGNATURES", "mount_of", "MOUNTS_VOCABULARY", *define(globals(), "mounts", SIGNATURES)]

_ASSIGNEE = re.compile(r"^(user|agent):[^\s:]+$")


def _text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= 1000


def _texts(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() and len(x) <= 200 for x in v)


def _said(v: Any) -> str:
    return _json(v)


def mount_of(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """One mount as its element declares it; raises with why it does not read (the TypeScript SDK's ``mountOf``)."""
    label = attrs.get("label")
    if not _text(label) or len(label) > 200:
        raise ValueError(f"<mount> label is a short text that names it in its thread, not {_said(label)}")
    at = f'<mount label="{label}">'
    # A field written None (null) is written, as a JSX attribute written {null} is: only an absent one is not.
    for k in ("task", "folder", "project", "assignee"):
        if k in attrs and not _text(attrs[k]):
            raise ValueError(f"{at} {k} is a text (a ref or an address), not {_said(attrs[k])}")
    if "labels" in attrs and not _texts(attrs["labels"]):
        raise ValueError(f"{at} labels is a list of texts")
    if "status" in attrs and (not _texts(attrs["status"]) or not all(s in MOUNT_STATUSES for s in attrs["status"])):
        raise ValueError(f"{at} status is a list of {', '.join(MOUNT_STATUSES)}")
    if "assignee" in attrs and not _ASSIGNEE.match(attrs["assignee"]):
        raise ValueError(f"{at} assignee is user:<id> or agent:<id>, not {_said(attrs['assignee'])}")
    query = any(k in attrs for k in ("folder", "project", "assignee", "labels", "status"))
    if "task" in attrs and query:
        raise ValueError(f"{at} mounts one task, or a list (folder, project, assignee, labels, status): not both")
    if "task" not in attrs and not query:
        raise ValueError(f"{at} mounts nothing: give task, folder, project, or a query (assignee, labels, status)")
    out: Dict[str, Any] = {"label": label}
    for k in ("task", "folder", "project", "assignee"):
        if k in attrs:
            out[k] = attrs[k]
    for k in ("labels", "status"):
        if attrs.get(k):
            out[k] = list(attrs[k])
    return out


def _mounts(t: DocTree) -> Dict[str, Any]:
    mounts: List[Dict[str, Any]] = [mount_of(c["attrs"]) for c in t["children"] if c["tag"] == "mount"]
    seen = set()
    for m in mounts:
        if m["label"] in seen:
            raise ValueError(f"two mounts are labelled {_json(m['label'])}: a label names one mount in its thread")
        seen.add(m["label"])
    return {"mounts": mounts}


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "mounts", "attrs": {}, "children": [
        {"tag": "mount", "attrs": {k: m[k] for k in MOUNT_FIELDS if m.get(k) is not None}, "children": []}
        for m in d.get("mounts") or []]}


MOUNTS_VOCABULARY = Vocabulary("mounts", "a thread's mounted tasks", "mounts", {
    "mounts": {"parents": [], "attrs": []},
    "mount": {"parents": ["mounts"], "key": "label", "required": ["label"], "attrs": MOUNT_FIELDS},
}, _mounts, _tree, lambda _stem: {"mounts": []})

register_vocabulary(MOUNTS_VOCABULARY, "mounts")
