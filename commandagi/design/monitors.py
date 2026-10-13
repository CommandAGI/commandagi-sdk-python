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
``sources``, ``follows``, ``derives`` and ``wakes`` are always lists. A ``derive`` names an operator and, per port, the
folder of the monitor whose records go in: ``derive(id="vwap", op="vwap", inputs={"trades": "../trades"},
params={"window": "1m"})``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

MONITOR_FIELDS = ["title", "class", "about", "readme"]
SOURCE_FIELDS = ["id", "adapter", "params", "every", "via", "exit", "host", "mode", "retain", "since",
                 "session", "snapshot", "profile", "keep", "maxCostPerDay", "unit"]
FOLLOW_FIELDS = ["monitor", "match"]
WAKE_FIELDS = ["match", "prompt"]
DERIVE_FIELDS = ["id", "op", "inputs", "params", "since"]
#: The paths a source's reads take (docs/sources.md § fetch paths).
VIAS = ["worker", "host", "vpn", "browser", "vm", "android-vm", "phone"]
#: The paths that launch a machine from a snapshot (a logged-in state), and so cost money per read.
VM_VIAS = ["vm", "android-vm"]
#: ``poll`` reads at each ``every``; ``stream`` holds a connection open on a host.
MODES = ["poll", "stream"]
EVERY_BOUNDS = {"min": "30s", "max": "7d"}
_RETAIN = re.compile(r"^(all|derived|sample:[1-9]\d*(s|m|h|d))$")
_SINCE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
#: A phone unit: ``<world.tsx ref>#<uid>``.
UNIT_REF = re.compile(r"^[^#\s]+/world\.tsx#[a-z0-9][a-z0-9-]{0,47}$")

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "monitor": {"holds": "children"},
    "source": {},
    "follows": {},
    "derive": {},
    "wake": {},
}

__all__ = ["MONITOR_FIELDS", "SOURCE_FIELDS", "FOLLOW_FIELDS", "DERIVE_FIELDS", "WAKE_FIELDS", "VIAS", "VM_VIAS", "MODES",
           "UNIT_REF", "SIGNATURES", "duration_seconds", "monitor_with_defaults", "MONITOR_VOCABULARY",
           *define(globals(), "monitors", SIGNATURES)]

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
    a = t["attrs"]
    w = _where(t)
    for k in ("id", "adapter", "exit", "host", "retain", "since", "session", "snapshot", "profile", "keep", "unit"):
        _text(t, k)
    p = a.get("params")
    if p is not None and not isinstance(p, dict):
        raise ValueError(f'{w} params is an object ({{"series": "CPIAUCSL"}}), not {p!r}')
    s = duration_seconds(a.get("every"))
    if s is None:
        raise ValueError(f'{w} every is a duration ("30s", "15m", "6h", "7d"), not {a.get("every")!r}')
    lo, hi = duration_seconds(EVERY_BOUNDS["min"]), duration_seconds(EVERY_BOUNDS["max"])
    if s < lo or s > hi:
        raise ValueError(f'{w} every is from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {a["every"]!r}')
    _one_of(t, "via", VIAS)
    if a.get("exit") is not None and a.get("via") != "vpn":
        raise ValueError(f'{w} exit names an exit country ("DE") or an exit ("fsn-1"), for via="vpn" only')
    _one_of(t, "mode", MODES)
    via = a.get("via")
    on_vm = via in VM_VIAS
    has = lambda k: a.get(k) is not None  # noqa: E731
    if has("host") and via not in ("host", "browser", "phone") and not on_vm:
        raise ValueError(f'{w} host names the host that reads it, for via="host", "browser", "phone", "vm" or "android-vm" only')
    if has("profile") and via != "browser":
        raise ValueError(f'{w} profile names a browser profile of the host, for via="browser" only')
    if has("session") and via != "browser" and not on_vm:
        raise ValueError(f'{w} session names a logged-in state, for via="browser", "vm" or "android-vm" only')
    if has("session") and has("profile"):
        raise ValueError(f"{w} names its state once: a session or a profile")
    if has("snapshot") and not on_vm:
        raise ValueError(f'{w} snapshot is what a via="vm" or "android-vm" read launches from')
    if has("session") and has("snapshot"):
        raise ValueError(f"{w} names its state once: a session or a snapshot")
    if on_vm and not has("session") and not has("snapshot"):
        raise ValueError(f'{w} via="{via}" launches from a snapshot: it names a session or a snapshot')
    cost = a.get("maxCostPerDay")
    if cost is not None and not on_vm:
        raise ValueError(f'{w} maxCostPerDay bounds what a via="vm" or "android-vm" source spends')
    if on_vm and cost is None:
        raise ValueError(f'{w} via="{via}" costs money: it says maxCostPerDay (USD a day)')
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 < cost < float("inf")):
        raise ValueError(f"{w} maxCostPerDay is a price in USD (2.5), not {cost!r}")
    if has("keep") and not on_vm:
        raise ValueError(f'{w} keep is how long a via="vm" or "android-vm" machine stays up')
    if has("keep"):
        k = duration_seconds(a["keep"])
        if k is None or k < lo or k > hi:
            raise ValueError(f'{w} keep is a duration from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {a["keep"]!r}')
    if has("unit") and via != "phone":
        raise ValueError(f'{w} unit names the phone a via="phone" read runs on')
    if via == "phone" and not has("unit"):
        raise ValueError(f'{w} via="phone" names its phone: unit="<world.tsx>#<uid>"')
    if has("unit") and not UNIT_REF.match(a["unit"]):
        raise ValueError(f'{w} unit is "<world.tsx ref>#<uid>" ("../../worlds/fleet/world.tsx#android-01"), not {a["unit"]!r}')
    if a.get("mode") == "stream" and via != "host":
        raise ValueError(f'{w} mode="stream" holds a connection open, which runs on a host (via="host")')
    if has("retain") and a.get("mode") != "stream":
        raise ValueError(f'{w} retain is for mode="stream" only')
    if has("retain") and not _RETAIN.match(a["retain"]):
        raise ValueError(f'{w} retain is "all", "derived" or "sample:<duration>", not {a["retain"]!r}')
    if has("since") and not _SINCE.match(a["since"]):
        raise ValueError(f'{w} since is a day ("2024-01-01"), not {a["since"]!r}')
    if has("since") and a.get("mode") == "stream":
        raise ValueError(f"{w} since is for a polled source; a stream starts when it connects")
    return _said(a, SOURCE_FIELDS)


_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _derive(t: DocTree) -> Dict[str, Any]:
    """A derived stream (docs/records.md § 6): an operator over other monitors' records, each port named to a folder."""
    for k in ("id", "op", "since"):
        _text(t, k)
    if not _WORD.match(t["attrs"].get("id") or ""):
        raise ValueError(f"{_where(t)} id is a word (letters, digits, _ and -)")
    inputs = t["attrs"].get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError(f"{_where(t)} inputs maps each port to a monitor's folder ({{'quotes': '../quotes'}}), not {inputs!r}")
    for port, ref in inputs.items():
        if not isinstance(port, str) or not _WORD.match(port):
            raise ValueError(f"{_where(t)} a port is a word, not {port!r}")
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"{_where(t)} inputs.{port} is a monitor's folder, not {ref!r}")
        if re.match(r"^\./?$", ref):
            raise ValueError(f"{_where(t)} inputs.{port} names this monitor; a derive takes other monitors' records")
    p = t["attrs"].get("params")
    if p is not None and not isinstance(p, dict):
        raise ValueError(f"{_where(t)} params is an object ({{'window': '1m'}}), not {p!r}")
    since = t["attrs"].get("since")
    if since is not None and not _SINCE.match(since):
        raise ValueError(f'{_where(t)} since is a day ("2024-01-01"), not {since!r}')
    return _said(t["attrs"], DERIVE_FIELDS)


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
    derives = [_derive(c) for c in parts("derive")]
    return {**_said(t["attrs"], MONITOR_FIELDS), "sources": [_source(c) for c in parts("source")], "follows": follows,
            "derives": derives, "wakes": wakes}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


MONITOR_VOCABULARY = Vocabulary("monitor", "a monitor", "monitor", {
    "monitor": {"parents": [], "attrs": MONITOR_FIELDS},
    "source": {"parents": ["monitor"], "key": "id", "required": ["id", "adapter", "every"], "attrs": SOURCE_FIELDS},
    "follows": {"parents": ["monitor"], "key": "monitor", "required": ["monitor"], "attrs": FOLLOW_FIELDS},
    "derive": {"parents": ["monitor"], "key": "id", "required": ["id", "op", "inputs"], "attrs": DERIVE_FIELDS},
    "wake": {"parents": ["monitor"], "required": ["prompt"], "attrs": WAKE_FIELDS},
}, _monitor, _never)

register_vocabulary(MONITOR_VOCABULARY, "monitors")


def monitor_with_defaults(m: Dict[str, Any]) -> Dict[str, Any]:
    """A monitor as the platform reads it: what the file does not say, filled (``via: "worker"``, ``mode: "poll"``, the
    others None; a stream's ``retain`` "derived"). The TypeScript SDK's ``monitorWithDefaults``."""
    def src(s: Dict[str, Any]) -> Dict[str, Any]:
        stream = s.get("mode") == "stream"
        return {"id": s["id"], "adapter": s["adapter"], "params": s.get("params", {}), "every": s["every"],
                "via": s.get("via", "worker"), "exit": s.get("exit"), "host": s.get("host"), "mode": s.get("mode", "poll"),
                "retain": s.get("retain", "derived") if stream else None, "since": s.get("since"),
                "session": s.get("session"), "snapshot": s.get("snapshot"), "profile": s.get("profile"),
                "keep": s.get("keep"), "maxCostPerDay": s.get("maxCostPerDay"), "unit": s.get("unit")}
    return {"title": m.get("title"), "class": m.get("class"), "about": m.get("about"), "readme": m.get("readme"),
            "sources": [src(s) for s in m.get("sources", [])],
            "follows": [{"monitor": f["monitor"], "match": f.get("match")} for f in m.get("follows", [])],
            "derives": [{"id": d["id"], "op": d["op"], "inputs": d["inputs"], "params": d.get("params", {}),
                         "since": d.get("since")} for d in m.get("derives", [])],
            "wakes": [{"match": w.get("match"), "prompt": w["prompt"]} for w in m.get("wakes", [])]}
