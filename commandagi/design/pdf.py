"""A PDF assembled in Python: a ``.pdf.py``. The same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``pdf.ts``)::

    from commandagi.design.pdf import bates, bookmark, fill, footer, highlight, note, page, pdf, reply, stamp

    result = pdf(
        page(src="Contract.pdf", n=1),
        page(
            highlight(rects=[[72, 700, 300, 712]], author="Ada", text="Check this"),
            note(reply(text="Because.", author="Bob"), at=[500, 700], text="Why?"),
            stamp(rect=[400, 40, 560, 90], name="Approved"),
            src="Contract.pdf", n=3, rotate=90,
        ),
        page(size="a4"),
        fill(name="Name", value="Ada Lovelace"),
        bookmark(bookmark(title="Payment", page=2, top=500), title="Terms", page=2),
        footer(center="Page {page} of {pages}", pages="2-"),
        bates(prefix="ACME-", digits=6, position="bottom-right"),
        title="Signed contract",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``text_color`` is ``textColor``; ``from_`` is ``from``). Pages and page numbers are 1-based; coordinates
are PDF points from the page's lower-left corner; a colour is ``[r, g, b]``, each 0..1; a ``src`` is a ref relative
to the file's folder. A header or footer is text in its ``left``, ``center`` and ``right`` slots with ``{page}``,
``{pages}``, ``{date}`` and ``{file}`` in it, on every page or ``pages``; Bates numbers run from ``start``. Nothing adds
a default. A run gives back ``{"format", "document", "sources"}`` beside an empty
graph.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

PAGE_SIZES = {"a3": [841.89, 1190.55], "a4": [595.28, 841.89], "a5": [419.53, 595.28], "letter": [612, 792],
              "legal": [612, 1008], "tabloid": [792, 1224]}
_COMMON = ["id", "author", "text", "color", "opacity", "date"]
PDF_MARKS: Dict[str, List[str]] = {
    "highlight": [*_COMMON, "rects"],
    "underline": [*_COMMON, "rects"],
    "strikeout": [*_COMMON, "rects"],
    "squiggly": [*_COMMON, "rects"],
    "note": [*_COMMON, "at", "icon", "open"],
    "textbox": [*_COMMON, "rect", "size", "textColor", "border", "fill", "align"],
    "ink": [*_COMMON, "strokes", "width"],
    "rectangle": [*_COMMON, "rect", "width", "fill"],
    "ellipse": [*_COMMON, "rect", "width", "fill"],
    "line": [*_COMMON, "from", "to", "width", "arrow"],
    "polygon": [*_COMMON, "points", "width", "fill"],
    "polyline": [*_COMMON, "points", "width"],
    "stamp": [*_COMMON, "rect", "name", "label", "image"],
    "signature": ["id", "author", "rect", "typed", "style", "image", "strokes", "color", "width"],
    "redact": ["id", "rect", "fill", "overlay"],
    "field": ["id", "kind", "name", "rect", "rects", "value", "options", "checked", "multiline", "maxLength", "required",
              "readOnly", "tooltip", "default", "editable", "size"],
}
_REQUIRED = {"highlight": ["rects"], "underline": ["rects"], "strikeout": ["rects"], "squiggly": ["rects"], "note": ["at"],
             "textbox": ["rect", "text"], "ink": ["strokes"], "rectangle": ["rect"], "ellipse": ["rect"],
             "line": ["from", "to"], "polygon": ["points"], "polyline": ["points"], "stamp": ["rect"],
             "signature": ["rect"], "redact": ["rect"], "field": ["kind", "name"]}
PDF_FIELDS = ["title", "author", "subject", "keywords", "creator"]
PAGE_FIELDS = ["id", "src", "n", "rotate", "size", "width", "height"]
BOOKMARK_FIELDS = ["id", "title", "page", "top", "open", "bold", "italic", "color", "url"]
_LABEL = ["from", "style", "prefix", "start"]
#: A review state a reply sets on its thread: "Completed" is resolved, "None" reopens it.
REVIEW_STATES = ["Accepted", "Rejected", "Cancelled", "Completed", "None"]
_REPLY = ["text", "author", "date", "state"]
_ATTACH = ["src", "name", "description", "mimeType"]
BAND_FIELDS = ["left", "center", "right", "size", "color", "family", "margin", "inset", "pages", "start", "date"]
BATES_FIELDS = ["prefix", "suffix", "start", "digits", "position", "size", "color", "family", "margin", "inset"]
BATES_POSITIONS = ["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "pdf": {"holds": "children"},
    "page": {"holds": "children"},
    **{t: ({"holds": "children"} if t == "note" else {}) for t in PDF_MARKS},
    "reply": {},
    "fill": {},
    "bookmark": {"holds": "children"},
    "label": {},
    "attach": {},
    "header": {},
    "footer": {},
    "bates": {},
}

__all__ = ["PAGE_SIZES", "REVIEW_STATES", "PDF_MARKS", "PDF_FIELDS", "PAGE_FIELDS", "BOOKMARK_FIELDS", "BAND_FIELDS", "BATES_FIELDS", "SIGNATURES", "PDF_VOCABULARY",
           *define(globals(), "pdf", SIGNATURES)]


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v: Any) -> bool:
    return _num(v) and float(v).is_integer()


def _rect(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 4 and all(_num(x) for x in v)


def _point(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)


def _color(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 3 and all(_num(x) and 0 <= x <= 1 for x in v)


def _own(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: o[k] for k in keys if k in o}


def _check_mark(c: DocTree) -> None:
    a, t = c["attrs"], c["tag"]
    where = f"<{t}>"
    if "rect" in a and not _rect(a["rect"]):
        raise ValueError(f"{where} rect is [x0, y0, x1, y1] in points")
    if "rects" in a and not (isinstance(a["rects"], list) and a["rects"] and all(_rect(r) for r in a["rects"])):
        raise ValueError(f"{where} rects is a list of [x0, y0, x1, y1]")
    for k in ("at", "from", "to"):
        if k in a and not _point(a[k]):
            raise ValueError(f"{where} {k} is [x, y] in points")
    for k in ("color", "textColor"):
        if k in a and not _color(a[k]):
            raise ValueError(f"{where} {k} is [r, g, b], each 0 to 1")
    for k in ("fill", "border"):
        if k in a and a[k] is not None and not _color(a[k]):
            raise ValueError(f"{where} {k} is [r, g, b], each 0 to 1, or null")
    if "opacity" in a and not (_num(a["opacity"]) and 0 <= a["opacity"] <= 1):
        raise ValueError(f"{where} opacity is 0 to 1")
    if "strokes" in a and not (isinstance(a["strokes"], list) and all(
            isinstance(s, list) and len(s) >= 2 and len(s) % 2 == 0 and all(_num(x) for x in s) for s in a["strokes"])):
        raise ValueError(f"{where} strokes is a list of [x, y, x, y …]")
    if "points" in a and not (isinstance(a["points"], list) and len(a["points"]) >= 4 and len(a["points"]) % 2 == 0
                              and all(_num(x) for x in a["points"])):
        raise ValueError(f"{where} points is [x, y, x, y …]")
    if "arrow" in a and a["arrow"] not in ("none", "start", "end", "both"):
        raise ValueError(f'{where} arrow is "none", "start", "end" or "both"')
    if "date" in a:
        try:
            datetime.fromisoformat(str(a["date"]).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f'{where} date is an ISO date ("2026-10-06T12:00:00Z")') from None
    if t == "field":
        if a.get("kind") not in ("text", "checkbox", "radio", "dropdown", "list", "signature"):
            raise ValueError('<field> kind is "text", "checkbox", "radio", "dropdown", "list" or "signature"')
        if a["kind"] == "radio" and not (isinstance(a.get("options"), list) and isinstance(a.get("rects"), list)
                                         and len(a["options"]) == len(a["rects"])):
            raise ValueError('<field kind="radio"> has options and rects, one rect per option')
        if a["kind"] != "radio" and not _rect(a.get("rect")):
            raise ValueError("<field> rect is [x0, y0, x1, y1] in points")
    if t == "signature" and sum(1 for k in ("typed", "image", "strokes") if k in a) != 1:
        raise ValueError("<signature> is one of typed, image or strokes")
    if t == "stamp" and not any(k in a for k in ("name", "image", "label")):
        raise ValueError("<stamp> has a name (Approved, Draft …), a label or an image")
    for k in ("text", "author", "name", "label", "image", "typed", "overlay", "tooltip"):
        if k in a and not isinstance(a[k], str):
            raise ValueError(f"{where} {k} is text")
    for k in ("required", "readOnly", "multiline", "checked", "editable"):
        if k in a and not isinstance(a[k], bool):
            raise ValueError(f"{where} {k} is true or false")
    if "default" in a and not (isinstance(a["default"], str) or (isinstance(a["default"], list) and all(isinstance(x, str) for x in a["default"]))):
        raise ValueError(f"{where} default is text, or a list of texts")
    for r in c["children"]:
        if r["tag"] == "reply" and "state" in r["attrs"] and r["attrs"]["state"] not in REVIEW_STATES:
            raise ValueError("<reply> state is " + ", ".join(f'"{x}"' for x in REVIEW_STATES))


def _check_page(p: DocTree) -> None:
    a = p["attrs"]
    if "src" in a:
        if not isinstance(a["src"], str) or not a["src"]:
            raise ValueError("<page> src is the ref of a PDF")
        if not (_int(a.get("n")) and a["n"] >= 1):
            raise ValueError("<page src> n is the page's number in it, from 1")
        if any(k in a for k in ("size", "width", "height")):
            raise ValueError("<page> is a page of src, or a blank page of a size: not both")
    else:
        if "n" in a:
            raise ValueError("<page> n is the page number in src")
        if "size" in a and a["size"] not in PAGE_SIZES:
            raise ValueError(f"<page> size is {', '.join(PAGE_SIZES)}")
        if "size" not in a and not (_num(a.get("width")) and _num(a.get("height")) and a["width"] > 0 and a["height"] > 0):
            raise ValueError("<page> is a page of a PDF (src and n) or a blank page (size, or width and height in points)")
    if "rotate" in a and not (_int(a["rotate"]) and a["rotate"] % 90 == 0):
        raise ValueError("<page> rotate is a multiple of 90")
    for c in p["children"]:
        _check_mark(c)


def _check_band(t: DocTree) -> None:
    a, where = t["attrs"], f"<{t['tag']}>"
    if t["tag"] != "bates" and not any(isinstance(a.get(k), str) and a[k].strip() for k in ("left", "center", "right")):
        raise ValueError(f"{where} has text in left, center or right")
    for k in ("left", "center", "right", "pages", "date", "prefix", "suffix"):
        if k in a and not isinstance(a[k], str):
            raise ValueError(f"{where} {k} is text")
    for k in ("size", "margin", "inset"):
        if k in a and not (_num(a[k]) and a[k] >= 0):
            raise ValueError(f"{where} {k} is points, 0 or more")
    if "color" in a and not _color(a["color"]):
        raise ValueError(f"{where} color is [r, g, b], each 0 to 1")
    if "family" in a and a["family"] not in ("sans", "serif", "mono"):
        raise ValueError(f'{where} family is "sans", "serif" or "mono"')
    if "start" in a and not (_int(a["start"]) and a["start"] >= 0):
        raise ValueError(f"{where} start is a whole number")
    if "digits" in a and not (_int(a["digits"]) and 1 <= a["digits"] <= 15):
        raise ValueError("<bates> digits is 1 to 15")
    if "position" in a and a["position"] not in BATES_POSITIONS:
        raise ValueError(f"<bates> position is {', '.join(BATES_POSITIONS)}")


def _bookmark(t: DocTree) -> Dict[str, Any]:
    b = _own(t["attrs"], BOOKMARK_FIELDS)
    if not isinstance(b.get("title"), str):
        raise ValueError("<bookmark> title is text")
    if "page" in b and not (_int(b["page"]) and b["page"] >= 1):
        raise ValueError("<bookmark> page is a page number, from 1")
    kids = [_bookmark(c) for c in t["children"] if c["tag"] == "bookmark"]
    return {**b, **({"children": kids} if kids else {})}


def _pdf(t: DocTree) -> Dict[str, Any]:
    for k in PDF_FIELDS:
        if k in t["attrs"] and not isinstance(t["attrs"][k], str):
            raise ValueError(f"<pdf> {k} is text")
    pages: List[Dict[str, Any]] = []
    fills: List[Dict[str, Any]] = []
    bookmarks: List[Dict[str, Any]] = []
    labels: List[Dict[str, Any]] = []
    attachments: List[Dict[str, Any]] = []
    bands: Dict[str, Dict[str, Any]] = {}
    for c in t["children"]:
        if c["tag"] == "page":
            _check_page(c)
            marks = []
            for m in c["children"]:
                replies = [dict(r["attrs"]) for r in m["children"] if r["tag"] == "reply"]
                marks.append({"type": m["tag"], **m["attrs"], **({"replies": replies} if replies else {})})
            pages.append({**_own(c["attrs"], PAGE_FIELDS), **({"marks": marks} if marks else {})})
        elif c["tag"] == "fill":
            v = c["attrs"]["value"]
            if not (isinstance(v, (str, bool)) or (isinstance(v, list) and all(isinstance(x, str) for x in v))):
                raise ValueError("<fill> value is text, true or false, or a list of texts")
            fills.append({"name": c["attrs"]["name"], "value": v})
        elif c["tag"] == "bookmark":
            bookmarks.append(_bookmark(c))
        elif c["tag"] == "label":
            lab = _own(c["attrs"], _LABEL)
            if not (_int(lab.get("from")) and lab["from"] >= 1):
                raise ValueError("<label> from is a page number, from 1")
            if "style" in lab and lab["style"] not in ("D", "r", "R", "a", "A"):
                raise ValueError('<label> style is "D" (1 2 3), "r" (i ii), "R" (I II), "a" (a b) or "A" (A B)')
            labels.append(lab)
        elif c["tag"] == "attach":
            attachments.append(_own(c["attrs"], _ATTACH))
        elif c["tag"] in ("header", "footer", "bates"):
            if c["tag"] in bands:
                raise ValueError(f"a PDF has one <{c['tag']}>")
            _check_band(c)
            bands[c["tag"]] = _own(c["attrs"], BATES_FIELDS if c["tag"] == "bates" else BAND_FIELDS)
    return {
        **_own(t["attrs"], PDF_FIELDS),
        "pages": pages,
        **({"fill": fills} if fills else {}),
        **({"bookmarks": bookmarks} if bookmarks else {}),
        **({"labels": labels} if labels else {}),
        **({"attachments": attachments} if attachments else {}),
        **bands,
    }


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


_TAGS: Dict[str, Dict[str, Any]] = {
    "pdf": {"parents": [], "attrs": PDF_FIELDS},
    "page": {"parents": ["pdf"], "key": "id", "attrs": PAGE_FIELDS},
    **{t: {"parents": ["page"], "key": "id", "required": _REQUIRED.get(t, []), "attrs": attrs} for t, attrs in PDF_MARKS.items()},
    "reply": {"parents": ["note"], "required": ["text"], "attrs": _REPLY},
    "fill": {"parents": ["pdf"], "key": "name", "required": ["name", "value"], "attrs": ["name", "value"]},
    "bookmark": {"parents": ["pdf", "bookmark"], "key": "id", "required": ["title"], "attrs": BOOKMARK_FIELDS},
    "label": {"parents": ["pdf"], "required": ["from"], "attrs": _LABEL},
    "attach": {"parents": ["pdf"], "required": ["src"], "attrs": _ATTACH},
    "header": {"parents": ["pdf"], "attrs": BAND_FIELDS},
    "footer": {"parents": ["pdf"], "attrs": BAND_FIELDS},
    "bates": {"parents": ["pdf"], "attrs": BATES_FIELDS},
}

PDF_VOCABULARY = Vocabulary("pdf", "a PDF", "pdf", _TAGS, _pdf, _never, lambda _: {"pages": []})

register_vocabulary(PDF_VOCABULARY, "pdf")
