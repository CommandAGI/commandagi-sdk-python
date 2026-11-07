"""A connector, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``connectors.ts``), each element a call. ``<name>.connector.py`` declares a remote API as a
folder tree, so a mount can list it and read its files (docs/namespace.md § connectors, in the CommandAGI repository)::

    from commandagi.design.connectors import connector, dir, each, folder

    result = connector(
        folder(dir(name="models"), path=""),
        folder(
            each(dir(name="{a}", title="{a/name}"), in_="$", as_="a"),
            path="models", get="/assets?type=models",
        ),
        name="Poly Haven", base="https://api.polyhaven.com", rate=2, cache=86400, licence="CC0-1.0",
    )

Elements: ``connector`` (``name``, ``base``, ``rate``, ``cache``, ``home``, ``terms``, ``robots``, ``hosts``, and every
entry's ``title``, ``author``, ``licence``, ``source``, ``credit``), ``credential``, ``licence`` (``value`` -> ``spdx``),
``folder`` (``path``, ``get``, ``decode``, ``page``, ``page_size``, ``total``, ``next``), ``request``, ``here``, ``each``
(``in_``, ``as_``, ``where``, ``is_``, ``not_``: a trailing ``_`` names the JSX attributes ``in``, ``as``, ``is`` and ``not``), ``dir`` and
``file``. A text attribute is a template (``{a}``, ``{a/name}``, ``{slug}``, ``|keys``, ``|join:<sep>``, ``|base``, ``|stem``, ``|ext``, ``|text``, ``|name``, ``|lower``, ``|first``, ``|unique``; ``{@}`` is the
folder's own entry). The document
is the TypeScript SDK's ``ConnectorDoc``; a connector that would make an impolite or unreadable request is refused with
why.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from .documents import DocTree, Vocabulary, _json, _text as _js_string, register_vocabulary
from .element import define

PROVENANCE_FIELDS = ["title", "author", "licence", "source", "credit"]
CONNECTOR_DECODES = ["json", "gzip-json"]

CONNECTOR_ATTRS = ["name", "base", "rate", "cache", "home", "terms", "robots", "hosts", *PROVENANCE_FIELDS]
CREDENTIAL_ATTRS = ["service", "field", "query", "header", "prefix", "hosts", "optional"]
FOLDER_ATTRS = ["path", "get", "decode", "page", "pageSize", "total", "next"]
EACH_ATTRS = ["in", "as", "where", "is", "not"]
DIR_ATTRS = ["name", "id", "zip", *PROVENANCE_FIELDS]
FILE_ATTRS = ["path", "url", "zip", "member", "size", *PROVENANCE_FIELDS]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "connector": {"holds": "children"},
    "credential": {},
    "licence": {},
    "folder": {"holds": "children"},
    "request": {},
    "here": {},
    "each": {"holds": "children"},
    "dir": {},
    "file": {},
}

__all__ = ["PROVENANCE_FIELDS", "CONNECTOR_DECODES", "SIGNATURES", "connector_of", "CONNECTORS_VOCABULARY",
           *define(globals(), "connectors", SIGNATURES)]

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HOST = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", re.I)
_PATH_SEGMENT = re.compile(r"(?:\{[A-Za-z_][A-Za-z0-9_]*\}|[^{}/]+)")
_SERVICE = re.compile(r"[a-z0-9][a-z0-9-]*")
_FIELD = re.compile(r"[A-Z0-9_]+")


def _js_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _whole(v: Any) -> bool:
    return _num(v) and (isinstance(v, int) or v.is_integer())


def _text(v: Any, max_: int = 2000) -> bool:
    return isinstance(v, str) and 0 < _js_len(v) <= max_


def _https(v: Any) -> bool:
    if not _text(v):
        return False
    try:
        u = urlparse(v)
    except ValueError:
        return False
    return u.scheme == "https" and bool(u.netloc)


def _hosts(v: Any) -> bool:
    return isinstance(v, (list, tuple)) and all(isinstance(h, str) and _HOST.fullmatch(h) for h in v)


def _said(attrs: Dict[str, Any], k: str) -> str:
    return _json(attrs[k]) if k in attrs else "undefined"


def _only(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if k in attrs}


def _provenance(attrs: Dict[str, Any], at: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in PROVENANCE_FIELDS:
        if k not in attrs:
            continue
        if not _text(attrs[k], 1000):
            raise ValueError(f"{at} {k} is a text, not {_said(attrs, k)}")
        out[k] = attrs[k]
    return out


def _producer(t: DocTree, at: str) -> Dict[str, Any]:
    a = t["attrs"]
    tag = t["tag"]
    if tag == "each":
        if not _text(a.get("in"), 500):
            raise ValueError(f"{at} <each> in is a pointer ($/x, a/y), not {_said(a, 'in')}")
        if not _text(a.get("as"), 64) or not _NAME.fullmatch(a["as"]) or a["as"] == "$":
            raise ValueError(f"{at} <each> as is a name, not {_said(a, 'as')}")
        if "where" in a and not _text(a["where"], 500):
            raise ValueError(f"{at} <each> where is a pointer, not {_said(a, 'where')}")
        if ("where" in a) != ("is" in a or "not" in a) or ("is" in a and "not" in a):
            raise ValueError(f"{at} <each> where goes with is or with not: one of them")
        for k in ("is", "not"):
            if k in a and not isinstance(a[k], (str, int, float, bool)):
                raise ValueError(f"{at} <each> {k} is a text, a number or true/false")
        return {"kind": "each", **_only(a, EACH_ATTRS),
                "produce": [_producer(c, f'{at} <each in="{a["in"]}">') for c in t["children"]]}
    if tag == "dir":
        if not _text(a.get("name"), 500):
            raise ValueError(f"{at} <dir> name is a text (a template), not {_said(a, 'name')}")
        if "zip" in a and not _text(a["zip"]):
            raise ValueError(f"{at} <dir> zip is a url (a template), not {_said(a, 'zip')}")
        if "id" in a and not _text(a["id"], 500):
            raise ValueError(f"{at} <dir> id is a text (a template), not {_said(a, 'id')}")
        out = {"kind": "dir", "name": a["name"]}
        if "id" in a:
            out["id"] = a["id"]
        if "zip" in a:
            out["zip"] = a["zip"]
        out.update(_provenance(a, f'{at} <dir name="{a["name"]}">'))
        return out
    if tag == "file":
        where = f'{at} <file path="{_js_string(a.get("path"))}">'
        if not _text(a.get("path"), 1000):
            raise ValueError(f"{at} <file> path is a text (a template), not {_said(a, 'path')}")
        for k in ("url", "zip", "member"):
            if k in a and not _text(a[k]):
                raise ValueError(f"{where} {k} is a text (a template), not {_said(a, k)}")
        if ("zip" in a) != ("member" in a):
            raise ValueError(f"{where} zip and member go together")
        if ("url" in a) == ("zip" in a):
            raise ValueError(f"{where} reads its bytes from url, or from zip and member: one of them")
        if "size" in a and not (_num(a["size"]) and a["size"] >= 0) and not _text(a["size"], 500):
            raise ValueError(f"{where} size is a number or a template")
        return {"kind": "file", **_only(a, ["path", "url", "zip", "member", "size"]), **_provenance(a, where)}
    raise ValueError(f"{at} <{tag}> is not a level's entry (<each>, <dir>, <file>)")


def _folder(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    p = a.get("path")
    if not isinstance(p, str) or _js_len(p) > 500:
        raise ValueError(f'<folder> path is a text ("" is the root), not {_said(a, "path")}')
    at = f'<folder path="{p}">'
    if p != "" and not all(_PATH_SEGMENT.fullmatch(s) for s in p.split("/")):
        raise ValueError(f'{at} path is names and {{var}} segments, separated by "/"')
    if "get" in a and not _text(a["get"]):
        raise ValueError(f"{at} get is a path or url (a template), not {_said(a, 'get')}")
    if "decode" in a and a["decode"] not in CONNECTOR_DECODES:
        raise ValueError(f"{at} decode is {' or '.join(CONNECTOR_DECODES)}")
    if "page" in a and (not _text(a["page"], 64) or (a["page"] != "link" and not _NAME.fullmatch(a["page"]))):
        raise ValueError(f'{at} page is "link" or a query parameter\'s name')
    if "page" in a and a["page"] != "link" and "next" not in a and not (_whole(a.get("pageSize")) and a["pageSize"] > 0):
        raise ValueError(f"{at} pages by {_js_string(a['page'])}: it needs pageSize (by offset) or next (by a token)")
    if "total" in a and not _text(a["total"], 500):
        raise ValueError(f"{at} total is a template, not {_said(a, 'total')}")
    if "next" in a and (not _text(a["next"], 500) or "page" not in a or a["page"] == "link"):
        raise ValueError(f"{at} next is the template of the next page's token, with page naming its query parameter")
    if "get" not in a and ("page" in a or "decode" in a):
        raise ValueError(f"{at} pages and decodes a request: it needs get")
    requests: List[Dict[str, Any]] = []
    here = None
    produce: List[Dict[str, Any]] = []
    for c in t["children"]:
        ca = c["attrs"]
        if c["tag"] == "request":
            if not _text(ca.get("as"), 64) or not _NAME.fullmatch(ca["as"]):
                raise ValueError(f"{at} <request> as is a name, not {_said(ca, 'as')}")
            if not _text(ca.get("get")):
                raise ValueError(f'{at} <request as="{ca["as"]}"> get is a path or url')
            if "decode" in ca and ca["decode"] not in CONNECTOR_DECODES:
                raise ValueError(f"{at} <request> decode is {' or '.join(CONNECTOR_DECODES)}")
            requests.append(_only(ca, ["as", "get", "decode"]))
        elif c["tag"] == "here":
            here = _provenance(ca, f"{at} <here>")
        else:
            produce.append(_producer(c, at))
    out = _only(a, FOLDER_ATTRS)
    if requests:
        out["requests"] = requests
    if here is not None:
        out["here"] = here
    out["produce"] = produce
    return out


def connector_of(t: DocTree) -> Dict[str, Any]:
    """A connector as its elements declare it; raises with why it does not read (the TypeScript SDK's ``connectorOf``)."""
    a = t["attrs"]
    if not _text(a.get("name"), 200):
        raise ValueError(f"<connector> name is the source's name, not {_said(a, 'name')}")
    at = f'<connector name="{a["name"]}">'
    if not _https(a.get("base")):
        raise ValueError(f"{at} base is the API's https url, not {_said(a, 'base')}")
    if not (_num(a.get("rate")) and 0 < a["rate"] <= 10):
        raise ValueError(f"{at} rate is the requests a second it makes at most (above 0, at most 10), not {_said(a, 'rate')}")
    if not (_whole(a.get("cache")) and a["cache"] >= 60):
        raise ValueError(f"{at} cache is the seconds a listing is kept (a whole number, at least 60), not {_said(a, 'cache')}")
    for k in ("home", "terms", "robots"):
        if k in a and not _https(a[k]):
            raise ValueError(f"{at} {k} is an https url, not {_said(a, k)}")
    if "hosts" in a and not _hosts(a["hosts"]):
        raise ValueError(f"{at} hosts is a list of host names")
    doc: Dict[str, Any] = {**_only(a, CONNECTOR_ATTRS), **_provenance(a, at), "folders": []}
    if isinstance(a.get("hosts"), (list, tuple)):
        doc["hosts"] = list(a["hosts"])
    licences: List[Dict[str, Any]] = []
    paths = set()
    for c in t["children"]:
        ca = c["attrs"]
        if c["tag"] == "credential":
            if "credential" in doc:
                raise ValueError(f"{at} has one <credential>")
            if not _text(ca.get("service"), 64) or not _SERVICE.fullmatch(ca["service"]):
                raise ValueError(f"{at} <credential> service is a service's name (docs/services.md), not {_said(ca, 'service')}")
            if not _text(ca.get("field"), 64) or not _FIELD.fullmatch(ca["field"]):
                raise ValueError(f"{at} <credential> field is a field's name (API_KEY), not {_said(ca, 'field')}")
            if ("query" in ca) == ("header" in ca):
                raise ValueError(f"{at} <credential> goes as a query parameter or a header: one of them")
            for k in ("query", "header", "prefix"):
                if k in ca and not _text(ca[k], 64):
                    raise ValueError(f"{at} <credential> {k} is a text")
            if "hosts" in ca and not _hosts(ca["hosts"]):
                raise ValueError(f"{at} <credential> hosts is a list of host names")
            if "optional" in ca and not isinstance(ca["optional"], bool):
                raise ValueError(f"{at} <credential> optional is true or false")
            doc["credential"] = _only(ca, CREDENTIAL_ATTRS)
        elif c["tag"] == "licence":
            if not _text(ca.get("value"), 200) or not _text(ca.get("spdx"), 200):
                raise ValueError(f"{at} <licence> maps a value the API writes to an spdx id: both are texts")
            licences.append({"value": ca["value"], "spdx": ca["spdx"]})
        elif c["tag"] == "folder":
            f = _folder(c)
            if f["path"] in paths:
                raise ValueError(f'{at} has two <folder path="{f["path"]}">')
            paths.add(f["path"])
            doc["folders"].append(f)
        else:
            raise ValueError(f"{at} <{c['tag']}> is not read (<credential>, <licence>, <folder>)")
    if licences:
        doc["licences"] = licences
    if not doc["folders"]:
        raise ValueError(f"{at} declares no <folder>: a connector lists at least its root")
    return doc


def _producer_tree(p: Dict[str, Any]) -> DocTree:
    attrs = {k: v for k, v in p.items() if k != "kind"}
    if p["kind"] == "each":
        produce = attrs.pop("produce")
        return {"tag": "each", "attrs": attrs, "children": [_producer_tree(x) for x in produce]}
    return {"tag": p["kind"], "attrs": attrs, "children": []}


def _tree(d: Dict[str, Any]) -> DocTree:
    attrs = {k: v for k, v in d.items() if k not in ("folders", "licences", "credential")}
    children: List[DocTree] = []
    if d.get("credential"):
        children.append({"tag": "credential", "attrs": dict(d["credential"]), "children": []})
    children += [{"tag": "licence", "attrs": dict(x), "children": []} for x in d.get("licences") or []]
    for f in d["folders"]:
        fa = {k: v for k, v in f.items() if k not in ("requests", "here", "produce")}
        kids = [{"tag": "request", "attrs": dict(r), "children": []} for r in f.get("requests") or []]
        if f.get("here"):
            kids.append({"tag": "here", "attrs": {k: f["here"][k] for k in PROVENANCE_FIELDS if k in f["here"]}, "children": []})
        kids += [_producer_tree(p) for p in f["produce"]]
        children.append({"tag": "folder", "attrs": fa, "children": kids})
    return {"tag": "connector", "attrs": attrs, "children": children}


CONNECTORS_VOCABULARY = Vocabulary("connector", "a connector", "connector", {
    "connector": {"parents": [], "attrs": CONNECTOR_ATTRS},
    "credential": {"parents": ["connector"], "single": True, "attrs": CREDENTIAL_ATTRS},
    "licence": {"parents": ["connector"], "key": "value", "required": ["value", "spdx"], "attrs": ["value", "spdx"]},
    "folder": {"parents": ["connector"], "key": "path", "required": ["path"], "attrs": FOLDER_ATTRS},
    "request": {"parents": ["folder"], "key": "as", "required": ["as", "get"], "attrs": ["as", "get", "decode"]},
    "here": {"parents": ["folder"], "single": True, "attrs": PROVENANCE_FIELDS},
    "each": {"parents": ["folder", "each"], "required": ["in", "as"], "attrs": EACH_ATTRS},
    "dir": {"parents": ["folder", "each"], "required": ["name"], "attrs": DIR_ATTRS},
    "file": {"parents": ["folder", "each"], "required": ["path"], "attrs": FILE_ATTRS},
}, connector_of, _tree,
    lambda stem: {"name": stem or "connector", "base": "https://example.com", "rate": 1, "cache": 86400,
                  "folders": [{"path": "", "produce": []}]})

register_vocabulary(CONNECTORS_VOCABULARY, "connectors")
