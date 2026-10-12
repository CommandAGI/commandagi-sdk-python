"""A monitor, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``monitors.ts``; docs/monitors.md in the CommandAGI repository), each element a call. One
``monitor.py`` declares one monitor, in the folder of the thing it follows; its id is that folder's path in the
account's Drive, never written in the file::

    from commandagi.design.monitors import follows, monitor, source, wake

    def corporation(cik, ticker, name):  # a class of things is a function; an instance is one call
        return monitor(source(id="filings", adapter="sec-filings", params={"cik": cik}, every="15m"),
                       follows(monitor="../../central-banks/fed", match="fomc.*"),
                       title=f"{name} ({ticker})", class_="corporation", about=f"cik:{cik}")

    result = corporation("0001045810", "NVDA", "NVIDIA")

A monitor's ``class`` is written ``class_`` (a Python keyword). A follow names the followed monitor's folder, relative
to this monitor's folder. Nothing adds a default: what the file does not say, the document does not have. A monitor's
``sources``, ``follows`` and ``wakes`` are always lists.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

MONITOR_FIELDS = ["title", "class", "about", "readme"]
SOURCE_FIELDS = ["id", "adapter", "params", "every", "via", "exit"]
FOLLOW_FIELDS = ["monitor", "match"]
WAKE_FIELDS = ["match", "prompt"]
VIAS = ["worker", "host", "vpn"]
EVERY_BOUNDS = {"min": "30s", "max": "7d"}

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "monitor": {"holds": "children"},
    "source": {},
    "follows": {},
    "wake": {},
}

__all__ = ["MONITOR_FIELDS", "SOURCE_FIELDS", "FOLLOW_FIELDS", "WAKE_FIELDS", "VIAS",
           "SIGNATURES", "duration_seconds", "MONITOR_VOCABULARY", *define(globals(), "monitors", SIGNATURES)]

_DURATION = re.compile(r"^([1-9]\d*)(s|m|h|d)$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def duration_seconds(text: Any):
    """A duration (``30s``, ``15m``, ``6h``, ``7d``) in seconds, or None when it is not one."""
    m = _DURATION.match(text) if isinstance(text, str) else None
    return int(m.group(1)) * _UNIT[m.group(2)] if m else None


def _where(t: DocTree, key: str = "id") -> str:
    v = t["attrs"].get(key)
    return f'<{t["tag"]} {key}="{v}">' if isinstance(v, str) else f"<{t['tag']}>"


def _text(t: DocTree, k: str, key: str = "id") -> None:
    v = t["attrs"].get(k)
    if v is not None and (not isinstance(v, str) or not v):
        raise ValueError(f"{_where(t, key)} {k} is a word, not {v!r}")


def _one_of(t: DocTree, k: str, values: List[str]) -> None:
    v = t["attrs"].get(k)
    if v is not None and v not in values:
        raise ValueError(f"{_where(t)} {k} is {', '.join(chr(34) + x + chr(34) for x in values)}, not {v!r}")


def _said(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if attrs.get(k) is not None}


def _source(t: DocTree) -> Dict[str, Any]:
    for k in ("id", "adapter", "exit"):
        _text(t, k)
    p = t["attrs"].get("params")
    if p is not None and not isinstance(p, dict):
        raise ValueError(f'{_where(t)} params is an object ({{"series": "CPIAUCSL"}}), not {p!r}')
    s = duration_seconds(t["attrs"].get("every"))
    if s is None:
        raise ValueError(f'{_where(t)} every is a duration ("30s", "15m", "6h", "7d"), not {t["attrs"].get("every")!r}')
    if s < duration_seconds(EVERY_BOUNDS["min"]) or s > duration_seconds(EVERY_BOUNDS["max"]):
        raise ValueError(f'{_where(t)} every is from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {t["attrs"]["every"]!r}')
    _one_of(t, "via", VIAS)
    if t["attrs"].get("exit") is not None and t["attrs"].get("via") != "vpn":
        raise ValueError(f'{_where(t)} exit names a country for via="vpn" only')
    return _said(t["attrs"], SOURCE_FIELDS)


def _monitor(t: DocTree) -> Dict[str, Any]:
    for k in MONITOR_FIELDS:
        _text(t, k)
    parts = lambda tag: [c for c in t["children"] if c["tag"] == tag]  # noqa: E731
    follows = []
    for c in parts("follows"):
        _text(c, "monitor", "monitor")
        _text(c, "match", "monitor")
        if re.match(r"^\./?$", c["attrs"].get("monitor") or ""):
            raise ValueError(f'<follows monitor="{c["attrs"]["monitor"]}"> names this monitor; a follow names another monitor\'s folder')
        follows.append(_said(c["attrs"], FOLLOW_FIELDS))
    wakes = []
    for c in parts("wake"):
        _text(c, "match", "match")
        _text(c, "prompt", "match")
        wakes.append(_said(c["attrs"], WAKE_FIELDS))
    return {**_said(t["attrs"], MONITOR_FIELDS), "sources": [_source(c) for c in parts("source")], "follows": follows, "wakes": wakes}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


MONITOR_VOCABULARY = Vocabulary("monitor", "a monitor", "monitor", {
    "monitor": {"parents": [], "attrs": MONITOR_FIELDS},
    "source": {"parents": ["monitor"], "key": "id", "required": ["id", "adapter", "every"], "attrs": SOURCE_FIELDS},
    "follows": {"parents": ["monitor"], "key": "monitor", "required": ["monitor"], "attrs": FOLLOW_FIELDS},
    "wake": {"parents": ["monitor"], "required": ["prompt"], "attrs": WAKE_FIELDS},
}, _monitor, _never)

register_vocabulary(MONITOR_VOCABULARY, "monitors")
