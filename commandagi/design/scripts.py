"""A script, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``scripts.ts``; docs/scripts.md in the CommandAGI repository), each element a call. A
``<name>.script.py`` declares one script, anywhere in a Drive; its id is the file's own path in the account's Drive,
never written in the file, and a folder may hold several scripts. Its run, beside the file, holds the records its
parts append::

    from commandagi.design.scripts import script, source, tail, wake

    def corporation(cik, ticker, name):  # a class of things is a function; an instance is one call
        return script(source(id="filings", adapter="sec-filings", params={"cik": cik}, every="30m"),
                      tail(of="../../central-banks/fed/fed.script.tsx", when={"class": "fomc.statement"}),
                      title=f"{name} ({ticker})", class_="corporation", about=f"cik:{cik}")

    result = corporation("0001045810", "NVDA", "NVIDIA")

A script's ``class`` is written ``class_`` (a Python keyword). A tail names the file it tails (``of``: a ref from this
script's folder to a script file, a run's ``records.jsonl``, or a statistics series by its id, ``fred:DGS10``), never
a folder, and takes the records its ``when`` (a record predicate) holds for. A wake wakes the agent on the script's own
records (``when``) or on a clock (``every="7d"``), never both. ``stream`` names the stream of the run a part appends to
(absent: ``records``). Nothing adds a default: what the file does not say, the document does not have;
``script_with_defaults`` gives the document as the platform reads it. A script's ``sameAs``, ``sources``, ``tails``,
``derives``, ``wakes``, ``discovers``, ``judges`` and ``params`` are always lists. A script with ``param`` parts is a
template: each ``${id}`` placeholder is filled when it is copied, and a placeholder as a whole value passes the checks
of the file it will name.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

#: The fields of a script.
SCRIPT_FIELDS = ["title", "class", "about", "readme", "sameAs"]
#: A subject: ``<scheme>:<id>`` (``cik:0001045810``, ``ticker:NVDA``, ``fomc:``).
SUBJECT = re.compile(r"^[a-z][a-z0-9-]*:\S*$")
SOURCE_FIELDS = ["id", "adapter", "params", "every", "via", "exit", "host", "mode", "retain", "since",
                 "session", "snapshot", "profile", "keep", "maxCostPerDay", "unit", "vantage", "connection", "stream"]
TAIL_FIELDS = ["of", "when", "stream"]
DISCOVER_FIELDS = ["into", "of", "when", "slug", "class", "props", "name", "max", "visibility"]
#: The most new folders a discover writes a tick.
DISCOVER_MAX = 50
#: Who may read a file a discover writes (docs/scripts.md § a script file).
VISIBILITIES = ["private", "unlisted", "public"]
WAKE_FIELDS = ["when", "every", "prompt", "agent", "maxSpend"]
JUDGE_FIELDS = ["id", "of", "rubric", "model"]
#: What a judge judges: each turn of the thread's agents, or each turn on a mounted task.
JUDGE_OF = ["turn", "task"]
DERIVE_FIELDS = ["id", "op", "inputs", "params", "since", "stream"]
#: A template's parameter (docs/scripts.md § the catalogue): its ``${id}`` placeholders are filled when it is copied.
SCRIPT_PARAM_FIELDS = ["id", "type", "label", "default", "required", "choices", "accept"]
#: What a parameter is: the same types a dashboard template's parameters have.
SCRIPT_PARAM_TYPES = ["file", "device", "world", "unit", "channel", "run", "stream", "number", "string", "choice"]
#: The paths a source's reads take (docs/sources.md § fetch paths).
VIAS = ["worker", "host", "vpn", "browser", "vm", "android-vm", "phone"]
#: The paths that launch a machine from a snapshot (a logged-in state), and so cost money per read.
VM_VIAS = ["vm", "android-vm"]
#: ``poll`` reads at each ``every``; ``stream`` holds a connection open on a host.
MODES = ["poll", "stream"]
#: What a stream source's thread keeps: every record, the derived records only, or one per series per duration.
RETAIN = re.compile(r"^(all|derived|sample:[1-9]\d*(s|m|h|d))$")
#: A source's first day.
SINCE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
#: The shortest and the longest ``every`` a source may have.
EVERY_BOUNDS = {"min": "30s", "max": "7d"}
#: A script's file name: ``<name>.script.tsx`` (or ``.jsx``, ``.py``, ``.rs``), anywhere in a Drive.
SCRIPT_FILE = re.compile(r"^[^/]+\.script\.(?:[jt]sx|py|rs)$", re.I)
#: A stream of the run a part appends to (``records``, ``ticks``): a word.
STREAM_NAME = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
#: A phone unit: ``<world.tsx ref>#<uid>``.
UNIT_REF = re.compile(r"^[^#\s]+/world\.tsx#[a-z0-9][a-z0-9-]{0,47}$")

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "script": {"holds": "children"},
    "source": {},
    "tail": {},
    "derive": {},
    "wake": {},
    "discover": {},
    "judge": {},
    "param": {},
}

__all__ = ["SCRIPT_FIELDS", "SUBJECT", "SOURCE_FIELDS", "TAIL_FIELDS", "DERIVE_FIELDS", "WAKE_FIELDS", "DISCOVER_FIELDS",
           "JUDGE_FIELDS", "JUDGE_OF", "SCRIPT_PARAM_FIELDS", "SCRIPT_PARAM_TYPES", "DISCOVER_MAX", "VISIBILITIES", "VIAS", "VM_VIAS", "MODES", "RETAIN", "SINCE",
           "EVERY_BOUNDS", "SCRIPT_FILE", "STREAM_NAME", "UNIT_REF", "SIGNATURES", "duration_seconds", "tail_ref_problem",
           "script_with_defaults", "SCRIPT_VOCABULARY", "SCRIPTS",
           *define(globals(), "scripts", SIGNATURES)]

_DURATION = re.compile(r"^([1-9]\d*)(s|m|h|d)$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def duration_seconds(text: Any) -> Optional[int]:
    """A duration (``30s``, ``15m``, ``6h``, ``7d``) in seconds, or None when it is not one."""
    m = _DURATION.match(text) if isinstance(text, str) else None
    return int(m.group(1)) * _UNIT[m.group(2)] if m else None


_LO, _HI = duration_seconds(EVERY_BOUNDS["min"]), duration_seconds(EVERY_BOUNDS["max"])


def _j(v: Any) -> str:
    """JavaScript's ``JSON.stringify(v)``, so a message reads as the TypeScript SDK's."""
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def _where(t: DocTree, key: str = "id") -> str:
    v = t["attrs"].get(key)
    return f'<{t["tag"]} {key}="{v}">' if isinstance(v, str) else f"<{t['tag']}>"


def _text(t: DocTree, k: str, key: str = "id") -> None:
    v = t["attrs"].get(k)
    if v is not None and (not isinstance(v, str) or not v):
        raise ValueError(f"{_where(t, key)} {k} is a word, not {_j(v)}")


def _one_of(t: DocTree, k: str, values: List[str], key: str = "id") -> None:
    v = t["attrs"].get(k)
    if v is not None and v not in values:
        raise ValueError(f"{_where(t, key)} {k} is {', '.join(chr(34) + x + chr(34) for x in values)}, not {_j(v)}")


def _said(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if attrs.get(k) is not None}


def _price(v: Any) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def _source(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    w = _where(t)
    for k in ("id", "adapter", "exit", "host", "retain", "since", "session", "snapshot", "profile", "keep", "unit", "vantage", "connection"):
        _text(t, k)
    p = a.get("params")
    if p is not None and not isinstance(p, dict):
        raise ValueError(f'{w} params is an object ({{ series: "CPIAUCSL" }}), not {_j(p)}')
    s = duration_seconds(a.get("every"))
    if s is None:
        raise ValueError(f'{w} every is a duration ("30s", "15m", "6h", "7d"), not {_j(a.get("every"))}')
    if s < _LO or s > _HI:
        raise ValueError(f'{w} every is from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {_j(a["every"])}')
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
    if cost is not None and not _price(cost):
        raise ValueError(f"{w} maxCostPerDay is a price in USD (2.5), not {_j(cost)}")
    if has("keep") and not on_vm:
        raise ValueError(f'{w} keep is how long a via="vm" or "android-vm" machine stays up')
    if has("keep"):
        k = duration_seconds(a["keep"])
        if k is None or k < _LO or k > _HI:
            raise ValueError(f'{w} keep is a duration from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {_j(a["keep"])}')
    if has("unit") and via != "phone":
        raise ValueError(f'{w} unit names the phone a via="phone" read runs on')
    if via == "phone" and not has("unit"):
        raise ValueError(f'{w} via="phone" names its phone: unit="<world.tsx>#<uid>"')
    if has("unit") and not UNIT_REF.match(a["unit"]):
        raise ValueError(f'{w} unit is "<world.tsx ref>#<uid>" ("../../worlds/fleet/world.tsx#android-01"), not {_j(a["unit"])}')
    if a.get("mode") == "stream" and via != "host":
        raise ValueError(f'{w} mode="stream" holds a connection open, which runs on a host (via="host")')
    if has("retain") and a.get("mode") != "stream":
        raise ValueError(f'{w} retain is for mode="stream" only')
    if has("retain") and not RETAIN.match(a["retain"]):
        raise ValueError(f'{w} retain is "all", "derived" or "sample:<duration>", not {_j(a["retain"])}')
    if has("since") and not SINCE.match(a["since"]):
        raise ValueError(f'{w} since is a day ("2024-01-01"), not {_j(a["since"])}')
    if has("since") and a.get("mode") == "stream":
        raise ValueError(f"{w} since is for a polled source; a stream starts when it connects")
    if has("connection") and a.get("via", "worker") != "worker":
        raise ValueError(f'{w} connection names a connected account, which the api worker reads (via="worker")')
    return _said(a, SOURCE_FIELDS)


_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_DATA_PATH = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
#: A term's name in a ``when``: a record field, or a path of its data.
_WHEN_NAME = re.compile(r"^(class|about|key|title|data(\.[A-Za-z_]\w*)+)$")
_WHEN_OPS = ["eq", "ne", "gt", "gte", "lt", "lte", "in", "glob", "contains", "exists"]
_CLASS_REF = re.compile(r"^[^#\s]+\.[jt]sx?#[A-Z][A-Za-z0-9_]{0,59}$")
_PROP = re.compile(r"^[a-z][A-Za-z0-9]*$")
_OWN = re.compile(r"^\./?$")
#: A statistics series by its id (``fred:DGS10``): a scheme and no ``/``.
_SERIES = re.compile(r"^[a-z][a-z0-9-]*:[^\s/:][^\s/]*$")
#: A tailed file: a script file or a run's records file, by a ref or an address.
#: A template's parameter as a whole value: ``${of}``.
_PLACEHOLDER = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
_PARAM_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")
_TAILED_FILE = re.compile(r"(?:^|/)[^/]+\.script\.(?:[jt]sx|py|rs)$|(?:^|/)records\.jsonl$", re.I)


def tail_ref_problem(ref: str) -> Optional[str]:
    """Why a ref cannot be what a tail (a derive's port, a discover's ``of``) reads, or None: it names a file, never a
    folder. The TypeScript SDK's ``tailRefProblem``."""
    # A template's placeholder is a file once its copy fills it (docs/scripts.md § the catalogue).
    if _SERIES.match(ref) or _TAILED_FILE.search(ref) or _PLACEHOLDER.match(ref):
        return None
    if _OWN.match(ref):
        return "names this script's folder; a tail names another file"
    return f'names a file: a script ("../nvidia/nvidia.script.tsx"), a run\'s records.jsonl, or a series ("fred:DGS10"), not {_j(ref)}'


def _when_shape(when: Any) -> Optional[str]:
    """The shape of a ``when`` (the platform reads its meaning: packages/domain/world/predicate.js)."""
    conditions = when if isinstance(when, list) else [when]
    if not conditions or len(conditions) > 16:
        return "one condition, or a list of one to 16"
    for c in conditions:
        if not isinstance(c, dict):
            return f'a condition is an object of terms ({{ class: "security.kev" }}), not {_j(c)}'
        for name, test in c.items():
            if not isinstance(name, str) or not _WHEN_NAME.match(name):
                return f"{_j(name)} is class, about, key, title or a data path (data.cvss3)"
            if isinstance(test, dict):
                for op in test:
                    if op not in _WHEN_OPS:
                        return f"{name}: {op} is not an operator ({', '.join(_WHEN_OPS)})"
    return None


def _discover(t: DocTree) -> Dict[str, Any]:
    """A discovering script's part (docs/scripts.md § a script file): one folder, an instance of ``class``, for each
    thing a record names by its ``slug`` that has none yet. It never deletes a folder."""
    a = t["attrs"]
    at = f'<discover into="{a.get("into") or "./"}">'
    for k in ("into", "class", "name"):
        _text(t, k, "into")
    of = a.get("of")
    if of is not None and not ((isinstance(of, str) and of) or
                               (isinstance(of, list) and of and all(isinstance(x, str) and x for x in of))):
        raise ValueError(f'{at} of is a script file or a list of them (["../kev/kev.script.tsx"]), not {_j(of)}')
    for ref in [] if of is None else [of] if isinstance(of, str) else of:
        bad = tail_ref_problem(ref)
        if bad:
            raise ValueError(f"{at} of {bad}")
    if a.get("when") is not None:
        bad = _when_shape(a["when"])
        if bad:
            raise ValueError(f"{at} when: {bad}")
    slug = a.get("slug")
    slug_ok = (isinstance(slug, str) and bool(_DATA_PATH.match(slug))) or (
        isinstance(slug, dict) and isinstance(slug.get("paths"), list) and len(slug["paths"]) > 0
        and all(isinstance(p, str) and _DATA_PATH.match(p) for p in slug["paths"])
        and all(k in ("paths", "pattern") for k in slug))
    if not slug_ok:
        raise ValueError(f"{at} slug is a data path (data.cve) or {{ paths: [...], pattern }}, not {_j(slug)}")
    if not isinstance(a.get("class"), str) or not (_CLASS_REF.match(a["class"]) or _PLACEHOLDER.match(a["class"])):
        raise ValueError(f'{at} class is the class file and its exported name ("../exploit.tsx#Exploit"), not {_j(a.get("class"))}')
    if a.get("name") is not None and not _DATA_PATH.match(a["name"]):
        raise ValueError(f"{at} name is a data path (fromName), not {_j(a['name'])}")
    props = a.get("props")
    if props is not None:
        if not isinstance(props, dict):
            raise ValueError(f'{at} props maps each prop to a data path ({{ conversation: "conversation" }}), not {_j(props)}')
        for k, v in props.items():
            if not isinstance(k, str) or not _PROP.match(k) or not isinstance(v, str) or not (_DATA_PATH.match(v) or v == "$slug"):
                raise ValueError(f'{at} props.{k} is a data path or "$slug", not {_j(v)}')
    mx = a.get("max")
    if mx is not None and (isinstance(mx, bool) or not isinstance(mx, int) or not 1 <= mx <= DISCOVER_MAX):
        raise ValueError(f"{at} max is a whole number from 1 to {DISCOVER_MAX}, not {_j(mx)}")
    vis = a.get("visibility")
    if vis is not None and vis not in VISIBILITIES:
        raise ValueError(f"{at} visibility is {', '.join(VISIBILITIES)}, not {_j(vis)}")
    return _said(a, DISCOVER_FIELDS)


def _derive(t: DocTree) -> Dict[str, Any]:
    """A derived stream (docs/records.md § 6): an operator folds the records of other files into records of this
    script; each port names what a tail names (a script file, a run's records file, a series), or ``./`` for its own."""
    a = t["attrs"]
    for k in ("id", "op", "since"):
        _text(t, k)
    if not _WORD.match(a.get("id") or ""):
        raise ValueError(f"{_where(t)} id is a word (letters, digits, _ and -)")
    inputs = a.get("inputs")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError(f'{_where(t)} inputs maps each port to a file it tails ({{ quotes: "../quotes/quotes.script.tsx" }}), not {_j(inputs)}')
    for port, ref in inputs.items():
        if not isinstance(port, str) or not _WORD.match(port):
            raise ValueError(f"{_where(t)} a port is a word, not {_j(port)}")
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"{_where(t)} inputs.{port} is a file it tails, not {_j(ref)}")
        # A derive may fold its own script's records: "./".
        bad = None if _OWN.match(ref) else tail_ref_problem(ref)
        if bad:
            raise ValueError(f"{_where(t)} inputs.{port} {bad}")
    p = a.get("params")
    if p is not None and not isinstance(p, dict):
        raise ValueError(f'{_where(t)} params is an object ({{ window: "1m" }}), not {_j(p)}')
    if a.get("since") is not None and not SINCE.match(a["since"]):
        raise ValueError(f'{_where(t)} since is a day ("2024-01-01"), not {_j(a["since"])}')
    return _said(a, DERIVE_FIELDS)


def _tail(t: DocTree) -> Dict[str, Any]:
    _text(t, "of", "of")
    of = t["attrs"].get("of")
    if t["attrs"].get("when") is not None:
        bad = _when_shape(t["attrs"]["when"])
        if bad:
            raise ValueError(f'<tail of="{of}"> when: {bad}')
    bad = tail_ref_problem(of)
    if bad:
        raise ValueError(f'<tail of="{of}"> {bad}')
    return _said(t["attrs"], TAIL_FIELDS)


def _wake(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    _text(t, "prompt", "every")
    _text(t, "agent", "every")
    spend = a.get("maxSpend")
    if spend is not None and not _price(spend):
        raise ValueError(f"<wake> maxSpend is a price in USD (0.5), not {_j(spend)}")
    if a.get("when") is not None:
        bad = _when_shape(a["when"])
        if bad:
            raise ValueError(f"<wake> when: {bad}")
    every = a.get("every")
    if every is not None:
        if a.get("when") is not None:
            raise ValueError(f'<wake every="{every}"> wakes on records (when) or on a clock (every), not both')
        s = duration_seconds(every)
        if s is None or s < _LO or s > _HI:
            raise ValueError(f'<wake> every is a duration from {EVERY_BOUNDS["min"]} to {EVERY_BOUNDS["max"]}, not {_j(every)}')
    return _said(a, WAKE_FIELDS)


def _judge(t: DocTree) -> Dict[str, Any]:
    """A judge of the script's run (docs/scripts.md § how a trigger runs a script): when a span of the thread's trace
    ends, the model reads it with the rubric, and its verdict is a record of the thread (an opinion, never evidence)."""
    for k in ("id", "rubric", "model"):
        _text(t, k)
    if not _WORD.match(t["attrs"].get("id") or ""):
        raise ValueError(f"{_where(t)} id is a word (letters, digits, _ and -)")
    _one_of(t, "of", JUDGE_OF)
    if not re.search(r"\.md$", t["attrs"].get("rubric") or "", re.I):
        raise ValueError(f'{_where(t)} rubric is a .md file ("./rubric.md"), not {_j(t["attrs"].get("rubric"))}')
    return _said(t["attrs"], JUDGE_FIELDS)


def _param(t: DocTree) -> Dict[str, Any]:
    """A template's parameter, as a dashboard template's ``<param>`` is."""
    a = t["attrs"]
    if not isinstance(a.get("id"), str) or not _PARAM_ID.match(a["id"]):
        raise ValueError(f"{_where(t)} id is letters, digits and _, not {_j(a.get('id'))}")
    _one_of(t, "type", SCRIPT_PARAM_TYPES)
    _text(t, "label")
    d = a.get("default")
    if d is not None and not isinstance(d, str) and not (isinstance(d, (int, float)) and not isinstance(d, bool) and math.isfinite(d)):
        raise ValueError(f"{_where(t)} default is a text or a number, not {_j(d)}")
    if a.get("required") is not None and not isinstance(a["required"], bool):
        raise ValueError(f"{_where(t)} required is true or false")
    for k in ("choices", "accept"):
        v = a.get(k)
        if v is not None and not (isinstance(v, list) and v and all(isinstance(x, str) and x for x in v)):
            raise ValueError(f"{_where(t)} {k} is a list of texts")
    if a.get("type") == "choice" and a.get("choices") is None:
        raise ValueError(f"{_where(t)} a choice names its choices")
    return _said(a, SCRIPT_PARAM_FIELDS)


def _stream(t: DocTree) -> None:
    """A part's ``stream``, when it says one: a word."""
    v = t["attrs"].get("stream")
    if v is not None and not (isinstance(v, str) and STREAM_NAME.match(v)):
        raise ValueError(f'{_where(t, "of" if t["tag"] == "tail" else "id")} stream is a word ("records", "ticks"), not {_j(v)}')


def _script(t: DocTree) -> Dict[str, Any]:
    for k in SCRIPT_FIELDS:
        if k != "sameAs":
            _text(t, k)
    same = t["attrs"].get("sameAs")
    if same is not None and not (isinstance(same, list) and all(isinstance(x, str) and SUBJECT.match(x) for x in same)):
        raise ValueError(f'<script> sameAs is a list of subjects ("ticker:NVDA"), not {_j(same)}')
    parts = lambda tag: [c for c in t["children"] if c["tag"] == tag]  # noqa: E731
    for c in t["children"]:
        _stream(c)
    tails = [_tail(c) for c in parts("tail")]
    derives = [_derive(c) for c in parts("derive")]
    wakes = [_wake(c) for c in parts("wake")]
    judges = [_judge(c) for c in parts("judge")]
    params = [_param(c) for c in parts("param")]
    ids = set()
    for p in params:
        if p["id"] in ids:
            raise ValueError(f'<param id="{p["id"]}"> is declared twice')
        ids.add(p["id"])
    return {**_said(t["attrs"], SCRIPT_FIELDS), "sources": [_source(c) for c in parts("source")], "tails": tails,
            "derives": derives, "wakes": wakes, "discovers": [_discover(c) for c in parts("discover")], "judges": judges,
            "params": params}


def _attrs_of(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """The fields code writes: a value that says nothing (absent, None or "") is not written."""
    return {k: o[k] for k in keys if o.get(k) is not None and o.get(k) != ""}


def _to_tree(m: Dict[str, Any]) -> DocTree:
    def parts(tag: str, items: List[Dict[str, Any]], keys: List[str]) -> List[DocTree]:
        return [{"tag": tag, "attrs": _attrs_of(x, keys), "children": []} for x in items]
    return {"tag": "script", "attrs": _attrs_of(m, SCRIPT_FIELDS), "children": [
        *parts("source", m.get("sources") or [], SOURCE_FIELDS),
        *parts("tail", m.get("tails") or [], TAIL_FIELDS),
        *parts("derive", m.get("derives") or [], DERIVE_FIELDS),
        *parts("wake", m.get("wakes") or [], WAKE_FIELDS),
        *parts("discover", m.get("discovers") or [], DISCOVER_FIELDS),
        *parts("judge", m.get("judges") or [], JUDGE_FIELDS),
        *parts("param", m.get("params") or [], SCRIPT_PARAM_FIELDS),
    ]}


# A tail names a file by its ref: the platform checks that the file is there and has a run.
SCRIPT_VOCABULARY = Vocabulary("script", "a script", "script", {
    "script": {"parents": [], "attrs": SCRIPT_FIELDS},
    "source": {"parents": ["script"], "key": "id", "required": ["id", "adapter", "every"], "attrs": SOURCE_FIELDS},
    "tail": {"parents": ["script"], "key": "of", "required": ["of"], "attrs": TAIL_FIELDS},
    "derive": {"parents": ["script"], "key": "id", "required": ["id", "op", "inputs"], "attrs": DERIVE_FIELDS},
    "wake": {"parents": ["script"], "required": ["prompt"], "attrs": WAKE_FIELDS},
    "discover": {"parents": ["script"], "required": ["slug", "class"], "attrs": DISCOVER_FIELDS},
    "judge": {"parents": ["script"], "key": "id", "required": ["id", "of", "rubric", "model"], "attrs": JUDGE_FIELDS},
    "param": {"parents": ["script"], "key": "id", "required": ["id", "type"], "attrs": SCRIPT_PARAM_FIELDS},
}, _script, _to_tree, lambda _format: {"sources": [], "tails": [], "derives": [], "wakes": [], "discovers": [], "judges": [], "params": []})

register_vocabulary(SCRIPT_VOCABULARY, "scripts")

#: The vocabulary of a script, by format.
SCRIPTS = {"script": SCRIPT_VOCABULARY}


def script_with_defaults(m: Dict[str, Any]) -> Dict[str, Any]:
    """A script as the platform reads it: what the file does not say, filled (``via: "worker"``, ``mode: "poll"``,
    ``stream: "records"``, the others None; a stream source's ``retain`` "derived"). The TypeScript SDK's
    ``scriptWithDefaults``."""
    def src(s: Dict[str, Any]) -> Dict[str, Any]:
        stream = s.get("mode") == "stream"
        return {"id": s["id"], "adapter": s["adapter"], "params": s.get("params", {}), "every": s["every"],
                "via": s.get("via", "worker"), "exit": s.get("exit"), "host": s.get("host"), "mode": s.get("mode", "poll"),
                "retain": s.get("retain", "derived") if stream else None, "since": s.get("since"),
                "session": s.get("session"), "snapshot": s.get("snapshot"), "profile": s.get("profile"),
                "keep": s.get("keep"), "maxCostPerDay": s.get("maxCostPerDay"), "unit": s.get("unit"),
                "vantage": s.get("vantage"), "connection": s.get("connection"), "stream": s.get("stream", "records")}

    def disc(d: Dict[str, Any]) -> Dict[str, Any]:
        of = d.get("of")
        return {"into": d.get("into", "./"), "of": [] if of is None else [of] if isinstance(of, str) else of,
                "when": d.get("when"), "slug": d["slug"], "class": d["class"], "props": d.get("props", {}),
                "name": d.get("name"), "max": d.get("max", 10), "visibility": d.get("visibility")}
    return {"title": m.get("title"), "class": m.get("class"), "about": m.get("about"), "readme": m.get("readme"),
            "sameAs": m.get("sameAs", []), "sources": [src(s) for s in m.get("sources", [])],
            "tails": [{"of": f["of"], "when": f.get("when"), "stream": f.get("stream", "records")} for f in m.get("tails", [])],
            "derives": [{"id": d["id"], "op": d["op"], "inputs": d["inputs"], "params": d.get("params", {}),
                         "since": d.get("since"), "stream": d.get("stream", "records")} for d in m.get("derives", [])],
            "wakes": [{"when": w.get("when"), "every": w.get("every"), "prompt": w["prompt"], "agent": w.get("agent"),
                       "maxSpend": w.get("maxSpend")} for w in m.get("wakes", [])],
            "discovers": [disc(d) for d in m.get("discovers", [])],
            "judges": [{"id": j["id"], "of": j["of"], "rubric": j["rubric"], "model": j["model"]} for j in m.get("judges", [])],
            "params": [{"id": p["id"], "type": p["type"], "label": p.get("label"), "default": p.get("default"),
                        "required": p.get("required", True), "choices": p.get("choices"), "accept": p.get("accept")}
                       for p in m.get("params", [])]}
