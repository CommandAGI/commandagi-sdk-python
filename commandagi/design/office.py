"""Office documents — a workbook (``.sheetx``), a page (``.pagex``) and a deck (``.deckx``) — declared as the very
document the CommandAGI sheets, docs and decks editors open. The same declarations as the TypeScript SDK's
``commandagi/design`` office JSX (``office.ts``), as calls::

    result = workbook(
        sheet("Q1",
              column("A", width=180),
              cell("A1", "Item", bold=True),
              cell("B1", 1200, num_fmt="$#,##0"),
              cell("B2", formula="=B1*12")),
        title="Budget")

    result = page(
        h1("Launch notes"),
        p("The first sentence. The second, with ", b("bold"), " and a ", a("https://commandagi.com", "link"), "."),
        bullet("a list item"),
        title="Notes")

    result = deck(
        slide(text("Pitch", placeholder="title"), layout="Title"),
        slide(shape("ellipse", x=160, y=160, w=400, h=400, fill="#dbeafe"), layout="Blank"),
        name="Pitch")

A workbook and a page are documents of their own: ``run_module`` hands them back beside an empty graph, as
``document`` (the editor's own JSON). A deck is the deck's own op graph (``deck.doc``, ``deck.slide``, ``deck.text`` …).
A block's text is its arguments (text and marks). Anything the editors' documents cannot hold is refused by name.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .ir import channels

__all__ = [
    "OfficeDocument", "workbook", "sheet", "cell", "column", "row",
    "page", "h1", "h2", "h3", "p", "bullet", "numbered", "todo", "quote", "pre", "divider", "image",
    "b", "i", "u", "s", "code_", "a", "br",
    "deck", "slide", "text", "shape",
]


class Element:
    """One declared element: a tag, its props and its children (the shape of a JSX element)."""

    def __init__(self, tag: str, children: tuple, props: Dict[str, Any]):
        self.tag = tag
        self.children = [c for c in children if c is not None and c is not False and c is not True]
        self.props = {k: v for k, v in props.items() if v is not None}


class OfficeDocument:
    """A workbook or a page: the editor's own JSON (``format`` is ``sheetx`` or ``pagex``)."""

    def __init__(self, fmt: str, document: Dict[str, Any]):
        self.format = fmt
        self.document = document

    def declared(self) -> Dict[str, Any]:
        return {"format": self.format, "document": self.document, "sources": {}}


def _defined(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


# ── Workbook ─────────────────────────────────────────────────────────────────────────────────────────────────────

_A1 = re.compile(r"^([A-Z]{1,3})([1-9]\d{0,6})$")
_ALIGN = ("left", "center", "right")


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def cell(at: str, value: Any = None, formula: Optional[str] = None, num_fmt: Optional[str] = None, bold: Optional[bool] = None,
         italic: Optional[bool] = None, align: Optional[str] = None, bg: Optional[str] = None, color: Optional[str] = None,
         wrap: Optional[bool] = None) -> Element:
    """One cell: a value (text, a number, True/False) or a formula that starts with "="."""
    return Element("cell", (), {"at": at, "value": value, "formula": formula, "numFmt": num_fmt, "bold": bold, "italic": italic,
                                "align": align, "bg": bg, "color": color, "wrap": wrap})


def column(at: str, width: float) -> Element:
    """A column's width in pixels; ``at`` is its letters ("B")."""
    return Element("column", (), {"at": at, "width": width})


def row(at: int, height: float) -> Element:
    """A row's height in pixels; ``at`` is its number (1 is the first)."""
    return Element("row", (), {"at": at, "height": height})


def sheet(name: Optional[str] = None, *children: Element, rows: Optional[int] = None, cols: Optional[int] = None,
          frozen_rows: Optional[int] = None, frozen_cols: Optional[int] = None, color: Optional[str] = None) -> Element:
    """A grid sheet (200 rows and 26 columns unless it says) of cells, columns and rows."""
    return Element("sheet", children, {"name": name, "rows": rows, "cols": cols, "frozenRows": frozen_rows, "frozenCols": frozen_cols, "color": color})


def workbook(*sheets: Element, title: Optional[str] = None) -> OfficeDocument:
    """The workbook JSON the sheets editor opens."""
    out: List[Dict[str, Any]] = []
    names = set()
    for k, sh in enumerate(sheets):
        if not isinstance(sh, Element) or sh.tag != "sheet":
            raise ValueError("a workbook holds sheets")
        name = sh.props.get("name") or f"Sheet {k + 1}"
        if name.lower() in names:
            raise ValueError(f"two sheets are called {name}")
        names.add(name.lower())
        cells: Dict[str, Dict[str, Any]] = {}
        widths: Dict[int, float] = {}
        heights: Dict[int, float] = {}
        rows, cols = sh.props.get("rows", 200), sh.props.get("cols", 26)
        for c in sh.children:
            if c.tag == "column":
                widths[_col_index(c.props["at"])] = c.props["width"]
                continue
            if c.tag == "row":
                heights[int(c.props["at"]) - 1] = c.props["height"]
                continue
            if c.tag != "cell":
                raise ValueError(f"<{c.tag}> is not read in a sheet (it holds cells, columns and rows)")
            at = str(c.props.get("at", "")).upper()
            m = _A1.match(at)
            if not m:
                raise ValueError(f'cell: at is an A1 reference ("B4"), not {c.props.get("at")!r}')
            if at in cells:
                raise ValueError(f"two cells of {name} are at {at}")
            v, f = c.props.get("value"), c.props.get("formula")
            if f is not None and not f.startswith("="):
                raise ValueError(f'cell {at}: a formula starts with = ("=SUM(B2:B4)")')
            if f is not None and v is not None:
                raise ValueError(f"cell {at}: a cell has a value or a formula, not both")
            if c.props.get("align") is not None and c.props["align"] not in _ALIGN:
                raise ValueError(f"cell {at}: align is one of left, center, right")
            fmt = _defined({k: c.props.get(k) for k in ("numFmt", "bold", "italic", "align", "bg", "color", "wrap")})
            cells[at] = _defined({"v": v if f is None else None, "f": f, "fmt": fmt or None})
            rows = max(rows, int(m.group(2)))
            cols = max(cols, _col_index(m.group(1)) + 1)
        fr, fc = sh.props.get("frozenRows"), sh.props.get("frozenCols")
        out.append(_defined({
            "id": f"sheet-{k + 1}", "name": name, "color": sh.props.get("color"), "kind": "grid", "rows": rows, "cols": cols, "cells": cells,
            "colWidths": widths or None, "rowHeights": heights or None,
            "frozen": {"rows": fr or 0, "cols": fc or 0} if fr is not None or fc is not None else None,
        }))
    if not out:
        raise ValueError("a workbook holds at least one sheet")
    return OfficeDocument("sheetx", _defined({"format": "sheetx", "version": 1, "sheets": out, "meta": {"title": title} if title is not None else None}))


# ── Page ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _mark(tag: str):
    def make(*children: Any) -> Element:
        return Element(tag, children, {})
    make.__name__ = tag
    make.__doc__ = f"The <{tag}> mark inside a text."
    return make


b, i, u, s = _mark("b"), _mark("i"), _mark("u"), _mark("s")
code_ = _mark("code")


def a(href: str, *children: Any) -> Element:
    """A link inside a text."""
    return Element("a", children, {"href": href})


def br() -> Element:
    """A line break inside a text."""
    return Element("br", (), {})


def _inline_html(children: List[Any], at: str) -> str:
    out = []
    for c in children:
        if isinstance(c, (str, int, float)):
            out.append(_escape(str(c)))
        elif isinstance(c, Element) and c.tag == "br":
            out.append("<br>")
        elif isinstance(c, Element) and c.tag == "a":
            href = c.props.get("href", "").replace("&", "&amp;").replace('"', "&quot;")
            out.append(f'<a href="{href}">{_inline_html(c.children, at)}</a>')
        elif isinstance(c, Element) and c.tag in ("b", "i", "u", "s", "code"):
            out.append(f"<{c.tag}>{_inline_html(c.children, at)}</{c.tag}>")
        else:
            raise ValueError(f"{at}: a text holds text and marks (b, i, u, s, code_, a, br)")
    return "".join(out)


def _block(tag: str):
    def make(*children: Any) -> Element:
        return Element(tag, children, {})
    make.__name__ = tag
    make.__doc__ = f"A <{tag}> block: its arguments are its text and marks."
    return make


h1, h2, h3, p, bullet, numbered, quote = (_block(t) for t in ("h1", "h2", "h3", "p", "bullet", "numbered", "quote"))


def todo(*children: Any, checked: bool = False) -> Element:
    """A checklist item."""
    return Element("todo", children, {"checked": checked})


def pre(source: str, lang: Optional[str] = None) -> Element:
    """A code block."""
    return Element("pre", (source,), {"lang": lang})


def divider() -> Element:
    """A rule between blocks."""
    return Element("divider", (), {})


def image(src: str, alt: Optional[str] = None, x: Optional[float] = None, y: Optional[float] = None, w: Optional[float] = None,
          h: Optional[float] = None, fit: Optional[str] = None, placeholder: Optional[str] = None) -> Element:
    """A picture: a page's image block, or a slide's image (with a box)."""
    return Element("image", (), {"src": src, "alt": alt, "x": x, "y": y, "w": w, "h": h, "fit": fit, "placeholder": placeholder})


_TEXT_BLOCKS = {"h1": "h1", "h2": "h2", "h3": "h3", "p": "p", "bullet": "ul", "numbered": "ol", "todo": "todo", "quote": "quote"}


def page(*blocks: Element, title: Optional[str] = None) -> OfficeDocument:
    """The page the docs editor opens."""
    out = []
    for k, el in enumerate(blocks):
        bid = f"block-{k + 1}"
        if not isinstance(el, Element):
            raise ValueError("a page holds blocks")
        kind = _TEXT_BLOCKS.get(el.tag)
        if kind:
            out.append(_defined({"id": bid, "type": kind, "html": _inline_html(el.children, f"<{el.tag}>"),
                                 "checked": bool(el.props.get("checked")) if kind == "todo" else None}))
        elif el.tag == "pre":
            out.append(_defined({"id": bid, "type": "code", "html": _escape("".join(str(c) for c in el.children)), "lang": el.props.get("lang")}))
        elif el.tag == "divider":
            out.append({"id": bid, "type": "divider", "html": ""})
        elif el.tag == "image":
            out.append(_defined({"id": bid, "type": "image", "html": "", "src": el.props.get("src", ""), "alt": el.props.get("alt")}))
        else:
            raise ValueError(f"<{el.tag}> is not a block of a page (h1, h2, h3, p, bullet, numbered, todo, quote, pre, divider, image)")
    return OfficeDocument("pagex", _defined({"format": "pagex", "version": 1, "blocks": out, "meta": {"title": title} if title is not None else None}))


# ── Deck ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def text(*children: Any, x: Optional[float] = None, y: Optional[float] = None, w: Optional[float] = None, h: Optional[float] = None,
         rotation: Optional[float] = None, placeholder: Optional[str] = None, font_size: Optional[float] = None, color: Optional[str] = None,
         bold: Optional[bool] = None, italic: Optional[bool] = None, underline: Optional[bool] = None, align: Optional[str] = None,
         valign: Optional[str] = None) -> Element:
    """A text box; its arguments are its text (``p(...)`` per paragraph, or text and marks for one)."""
    return Element("text", children, {"x": x, "y": y, "w": w, "h": h, "rotation": rotation, "placeholder": placeholder, "fontSizePx": font_size,
                                      "color": color, "bold": bold, "italic": italic, "underline": underline, "align": align, "valign": valign})


def shape(kind: str = "rect", x: Optional[float] = None, y: Optional[float] = None, w: Optional[float] = None, h: Optional[float] = None,
          rotation: Optional[float] = None, fill: Optional[str] = None, stroke: Optional[str] = None, stroke_width: Optional[float] = None,
          corner_radius: Optional[float] = None) -> Element:
    """A shape: rect, ellipse, triangle or line."""
    if kind not in ("rect", "ellipse", "triangle", "line"):
        raise ValueError("a shape is rect, ellipse, triangle or line")
    return Element("shape", (), {"shape": kind, "x": x, "y": y, "w": w, "h": h, "rotation": rotation, "fill": fill, "stroke": stroke,
                                 "strokeWidth": stroke_width, "cornerRadius": corner_radius})


def slide(*elements: Element, layout: str = "Title and body", name: Optional[str] = None, notes: Optional[str] = None,
          background: Optional[str] = None, hidden: Optional[bool] = None) -> Element:
    """A slide on a layout, by the layout's name (Title, Title and body, Section header, Blank)."""
    return Element("slide", elements, {"layout": layout, "name": name, "notes": notes, "background": background, "hidden": hidden})


_MARK_FLAG = {"b": "bold", "i": "italic", "u": "underline", "s": "strike"}


def _runs(children: List[Any], style: Dict[str, Any], out: List[Dict[str, Any]], at: str) -> None:
    for c in children:
        if isinstance(c, (str, int, float)):
            prev = out[-1] if out else None
            if prev is not None and {k: v for k, v in prev.items() if k != "text"} == style:
                prev["text"] += str(c)
            else:
                out.append({"text": str(c), **style})
        elif isinstance(c, Element) and c.tag == "a":
            _runs(c.children, {**style, "link": c.props.get("href", "")}, out, at)
        elif isinstance(c, Element) and c.tag in _MARK_FLAG:
            _runs(c.children, {**style, _MARK_FLAG[c.tag]: True}, out, at)
        else:
            raise ValueError(f"{at}: a text box holds text and marks (b, i, u, s, a; p(...) per paragraph)")


def _rich_text(children: List[Any], at: str) -> Dict[str, Any]:
    if any(isinstance(c, Element) and c.tag == "p" for c in children):
        paragraphs = []
        for c in children:
            if not (isinstance(c, Element) and c.tag == "p"):
                raise ValueError(f"{at}: a text with paragraphs holds only p(...)")
            runs: List[Dict[str, Any]] = []
            _runs(c.children, {}, runs, at)
            paragraphs.append({"runs": runs})
        return {"paragraphs": paragraphs or [{"runs": []}]}
    runs = []
    _runs(children, {}, runs, at)
    return {"paragraphs": [{"runs": runs}]}


def deck(*slides: Element, name: str = "Deck", width: float = 1280, height: float = 720, dpi: Optional[float] = None) -> Dict[str, Any]:
    """The deck's own op graph: ``doc``, then ``slide-N``, then ``slide-N.M`` for its elements."""
    nodes: Dict[str, Dict[str, Any]] = {}
    slide_wires = []
    for n, sl in enumerate(slides, 1):
        if not isinstance(sl, Element) or sl.tag != "slide":
            raise ValueError("a deck holds slides")
        sid = f"slide-{n}"
        el_wires = []
        for k, el in enumerate(sl.children, 1):
            eid = f"{sid}.{k}"
            box = _defined({key: el.props.get(key) for key in ("x", "y", "w", "h", "rotation")})
            common = _defined({"box": box or None, "placeholder": el.props.get("placeholder")})
            if not common.get("placeholder") and any(key not in box for key in ("x", "y", "w", "h")):
                raise ValueError(f"the {el.tag} {k} of {sid} needs x, y, w and h (or a placeholder to take them from)")
            if el.tag == "text":
                inputs = _defined({**common, "text": _rich_text(el.children, f"the text {k} of {sid}"),
                                   **{key: el.props.get(key) for key in ("fontSizePx", "color", "bold", "italic", "underline", "align", "valign")}})
                kind = "deck.text"
            elif el.tag == "shape":
                inputs = _defined({**common, **{key: el.props.get(key) for key in ("shape", "fill", "stroke", "strokeWidth", "cornerRadius")}})
                kind = "deck.shape"
            elif el.tag == "image":
                inputs = _defined({**common, "src": el.props.get("src", ""), "fit": el.props.get("fit"), "alt": el.props.get("alt")})
                kind = "deck.image"
            else:
                raise ValueError(f"<{el.tag}> is not an element of a slide (text, shape, image)")
            nodes[eid] = {"id": eid, "type": kind, "inputs": inputs}
            el_wires.append({"wire": {"node": eid, "port": "out"}})
        nodes[sid] = {"id": sid, "type": "deck.slide", "inputs": _defined({
            "layout": sl.props.get("layout", "Title and body"), "name": sl.props.get("name"), "notes": sl.props.get("notes"),
            "background": sl.props.get("background"), "hidden": sl.props.get("hidden"), **channels("elements", el_wires)})}
        slide_wires.append({"wire": {"node": sid, "port": "out"}})
    nodes["doc"] = {"id": "doc", "type": "deck.doc", "inputs": _defined({"name": name, "width": width, "height": height, "dpi": dpi, **channels("slides", slide_wires)})}
    return {"id": f"deck:{name}", "nodes": nodes, "outputs": ["doc"], "meta": {"domain": "deck", "name": name}}
