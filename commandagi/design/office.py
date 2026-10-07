"""Office documents — a workbook (``.sheet.py``), a page (``.page.py``) and a deck (``.deck.py``) — declared as the very
document the CommandAGI sheets, docs and decks editors open. The same elements as the TypeScript SDK's office JSX
(``commandagi/design`` ``office.ts``), one call per tag::

    from commandagi.design.office import a, b, bullet, cell, column, deck, h1, p, page, shape, sheet, slide, text, workbook

    result = workbook(
        sheet(
            column(at="A", width=160),
            cell(at="A1", value="Item", bold=True),
            cell(at="B1", value=1200, num_fmt="$#,##0"),
            cell(at="B2", formula="=B1*12"),
            name="Q1",
        ),
        title="Budget",
    )

    result = page(
        h1("Launch notes"),
        p("The first sentence. The second, with ", b("bold"), " and a ", a("link", href="https://commandagi.com"), "."),
        bullet("a list item"),
        title="Notes",
    )

    result = deck(
        slide(text("Pitch", placeholder="title"), layout="Title"),
        slide(shape(shape="rect", x=100, y=120, w=400, h=200, fill="#dbeafe"), layout="Blank"),
        name="Pitch",
    )

The tags (keywords are snake_case of the TypeScript attribute: ``frozen_rows``, ``num_fmt``, ``font_size``):
    workbook(*sheets, title)                                  the workbook
    sheet(*cells, name, rows, cols, frozen_rows, frozen_cols, color)
    cell(at, value | formula, num_fmt, bold, italic, align, bg, color, wrap)   one cell; a formula starts with "="
    column(at, width)  row(at, height)                        a column's width or a row's height, in pixels
    page(*blocks, title, paper, font)                         the page; paper "letter" or "a4"; font "sans", "serif", "mono"
    h1 h2 h3 p quote (*text, align)                           a text block: its text and marks; align "left", "center" …
    bullet numbered (*text)  todo(*text, checked)             a list item, a checklist item
    pre(text, lang)  divider()  image(src, alt)               a code block, a rule, a picture
    b i u s code a(*text, href) br()                          marks inside a text
    deck(*slides, name, width, height, dpi, style)            the deck (1280 x 720 slide units unless it says); style
                                                              "plain", "ink", "editorial" or "signal"
    slide(*elements, layout, name, notes, background, hidden)
    text(*text, placeholder, x, y, w, h, rotation, font_size, color, bold, italic, underline, align, valign,
         columns, gutter, inset)                              a text box; columns, gutter and inset frame its text
    shape(shape, x, y, w, h, fill, stroke, stroke_width, corner_radius)  image(src, x, y, w, h, fit, alt)
                                                              every element also takes opacity, label and locked
    group(*elements, name)                                    elements (and groups) that select and move as one
    master(*parts, background)                                how the master differs from the stock one: its own
                                                              elements, and its text styles and layouts:
    textStyle(role, font_size, color, bold, italic, font_family, line_height, align)
                                                              the text style of a role ("title", "body" …)
    layout(*placeholders, name)  placeholder(name, role, x, y, w, h, valign, prompt, font_size, color, bold …)
                                                              a layout's placeholders, saying what differs from stock

A workbook and a page are documents of their own: ``run_module`` hands them back beside an empty graph, with where
each part was written in ``sources`` (``workbook``, ``sheet:<id>``, ``cell:<id>!A1``, ``column:<id>!B``,
``row:<id>!3``, ``page``, ``block:<id>``). A deck is the deck's own op graph (``deck.doc``, ``deck.slide``,
``deck.text`` …), each node with ``meta.source``. Anything the editors' documents cannot hold is refused by name.
"""
from __future__ import annotations

import builtins
import json
import math
import re
from typing import Any, Dict, List, Optional

from .element import Element, child_elements, declares, define
from .ir import channels

_C: Dict[str, Any] = {"holds": "children"}
_T: Dict[str, Any] = {"holds": "text"}
#: Every tag of the office documents: what it holds (absent: a leaf). The TypeScript SDK's ``SIGNATURES.office``.
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "workbook": _C, "sheet": _C, "cell": {}, "column": {}, "row": {},
    "page": _C, "h1": _T, "h2": _T, "h3": _T, "p": _T, "bullet": _T, "numbered": _T, "todo": _T, "quote": _T, "pre": _T,
    "divider": {}, "image": {},
    "b": _T, "i": _T, "u": _T, "s": _T, "code": _T, "a": _T, "br": {},
    "deck": _C, "slide": _C, "text": _T, "shape": {}, "group": _C,
    "master": _C, "textStyle": {}, "layout": _C, "placeholder": {},
}

__all__ = ["SIGNATURES", "OFFICE_ROOTS", "DECK_TYPES", "read_workbook", "read_page", "read_deck", "inline_html", "rich_text",
           *define(globals(), "office", SIGNATURES)]

#: The document roots this module reads.
OFFICE_ROOTS = ("workbook", "page", "deck")


def _where(el: Element) -> str:
    if isinstance(el.props.get("name"), builtins.str):
        return f'<{el.tag} name="{el.props["name"]}">'
    if isinstance(el.props.get("at"), builtins.str):
        return f'<{el.tag} at="{el.props["at"]}">'
    return f"<{el.tag}>"


def _get(el: Element, prop: str) -> Any:
    return el.props.get(prop)


def _only(el: Element, allowed: List[str]) -> None:
    for k, v in el.props.items():
        if k != "key" and k not in allowed and v is not None:
            raise ValueError(f"{_where(el)}: {k} is not read on a <{el.tag}> (it takes {', '.join(allowed) or 'nothing'})")


def _str(el: Element, prop: str) -> Optional[str]:
    v = _get(el, prop)
    if v is None:
        return None
    if not isinstance(v, builtins.str):
        raise ValueError(f"{_where(el)}: {prop} is text, not {json.dumps(v)}")
    return v


def _num(el: Element, prop: str) -> Any:
    v = _get(el, prop)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{_where(el)}: {prop} is a number, not {json.dumps(v)}")
    return v


def _bool(el: Element, prop: str) -> Optional[bool]:
    v = _get(el, prop)
    if v is None:
        return None
    if not isinstance(v, bool):
        raise ValueError(f"{_where(el)}: {prop} is true or false, not {json.dumps(v)}")
    return v


def _one_of(el: Element, prop: str, values: List[str]) -> Optional[str]:
    v = _str(el, prop)
    if v is not None and v not in values:
        raise ValueError(f"{_where(el)}: {prop} is one of {', '.join(values)}")
    return v


def _defined(o: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in o.items() if v is not None}


def _text(n: Any) -> str:
    """A text child as JavaScript's ``String`` writes it (1.0 -> "1")."""
    if isinstance(n, float) and n.is_integer():
        return builtins.str(int(n))
    return builtins.str(n)


# ── Workbook ───────────────────────────────────────────────────────────────────────────────────────────────────

_A1 = re.compile(r"^([A-Z]{1,3})([1-9]\d{0,6})$")
_ALIGN = ["left", "center", "right"]


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_workbook(root: Element) -> Dict[str, Any]:
    """A ``workbook(...)`` as the workbook JSON the sheets editor opens, with where each part was written."""
    _only(root, ["title"])
    sources: Dict[str, Any] = {"workbook": root.source}
    names = set()
    sheets = []
    for i, el in enumerate(child_elements(root)):
        if el.tag != "sheet":
            raise ValueError(f"<{el.tag}> is not read in a <workbook> (it holds <sheet>s)")
        _only(el, ["name", "rows", "cols", "frozenRows", "frozenCols", "color"])
        sid = f"sheet-{i + 1}"
        name = _str(el, "name")
        name = f"Sheet {i + 1}" if name is None else name
        if name.lower() in names:
            raise ValueError(f"two sheets are called {name}")
        names.add(name.lower())
        sources[f"sheet:{sid}"] = el.source
        cells: Dict[str, Dict[str, Any]] = {}
        col_widths: Dict[int, Any] = {}
        row_heights: Dict[int, Any] = {}
        rows = _num(el, "rows")
        rows = 200 if rows is None else rows
        cols = _num(el, "cols")
        cols = 26 if cols is None else cols
        for c in child_elements(el):
            if c.tag in ("column", "row"):
                size_prop = "width" if c.tag == "column" else "height"
                _only(c, ["at", size_prop])
                at = _get(c, "at")
                index: Optional[int] = None
                if c.tag == "column":
                    if isinstance(at, builtins.str) and re.match(r"^[A-Z]{1,3}$", at):
                        index = _col_index(at)
                elif isinstance(at, int) and not isinstance(at, bool) and at >= 1:
                    index = at - 1
                if index is None:
                    what = "a column's letters (\"B\")" if c.tag == "column" else "a row's number (1 is the first)"
                    raise ValueError(f"{_where(c)}: at is {what}")
                size = _num(c, size_prop)
                if size is None or size <= 0:
                    raise ValueError(f"{_where(c)}: {size_prop} is a number of pixels")
                key = builtins.str(at) if c.tag == "column" else builtins.str(index + 1)
                (col_widths if c.tag == "column" else row_heights)[index] = size
                sources[f"{c.tag}:{sid}!{key}"] = c.source
                continue
            if c.tag != "cell":
                raise ValueError(f"<{c.tag}> is not read in a <sheet> (it holds <cell>, <column> and <row>)")
            _only(c, ["at", "value", "formula", "numFmt", "bold", "italic", "align", "bg", "color", "wrap"])
            at = _str(c, "at")
            at = at.upper() if at is not None else None
            m = _A1.match(at) if at else None
            if not at or not m:
                raise ValueError(f"<cell>: at is an A1 reference (\"B4\"), not {json.dumps(_get(c, 'at'))}")
            if at in cells:
                raise ValueError(f"two cells of {name} are at {at}")
            v = _get(c, "value")
            if v is not None and not isinstance(v, (builtins.str, int, float, bool)):
                raise ValueError(f"{_where(c)}: value is text, a number or true/false")
            f = _str(c, "formula")
            if f is not None and not f.startswith("="):
                raise ValueError(f"{_where(c)}: a formula starts with = (\"=SUM(B2:B4)\")")
            if f is not None and v is not None:
                raise ValueError(f"{_where(c)}: a cell has a value or a formula, not both")
            fmt = _defined({"numFmt": _str(c, "numFmt"), "bold": _bool(c, "bold"), "italic": _bool(c, "italic"),
                            "align": _one_of(c, "align", _ALIGN), "bg": _str(c, "bg"), "color": _str(c, "color"), "wrap": _bool(c, "wrap")})
            cells[at] = _defined({"v": v if f is None else None, "f": f, "fmt": fmt or None})
            rows = max(rows, int(m.group(2)))
            cols = max(cols, _col_index(m.group(1)) + 1)
            sources[f"cell:{sid}!{at}"] = c.source
        fr, fc = _num(el, "frozenRows"), _num(el, "frozenCols")
        sheets.append(_defined({
            "id": sid, "name": name, "color": _str(el, "color"), "kind": "grid", "rows": rows, "cols": cols, "cells": cells,
            "colWidths": col_widths or None, "rowHeights": row_heights or None,
            "frozen": {"rows": fr or 0, "cols": fc or 0} if fr is not None or fc is not None else None,
        }))
    if not sheets:
        raise ValueError("a <workbook> holds at least one <sheet>")
    title = _str(root, "title")
    document = {"format": "workbook", "version": 1, "sheets": sheets, **({"meta": {"title": title}} if title is not None else {})}
    return {"format": "workbook", "document": document, "sources": sources}


# ── Page ───────────────────────────────────────────────────────────────────────────────────────────────────────

_TEXT_BLOCKS = {"h1": "h1", "h2": "h2", "h3": "h3", "p": "p", "bullet": "ul", "numbered": "ol", "todo": "todo", "quote": "quote"}
#: The blocks that take an alignment, and the page's paper and typefaces (a few, not a font menu).
_ALIGNED = ("h1", "h2", "h3", "p", "quote")
_BLOCK_ALIGN = ["left", "center", "right", "justify"]
PAPERS = ["letter", "a4"]
PAGE_FONTS = ["sans", "serif", "mono"]
_MARKS = {"b", "i", "u", "s", "code"}


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_html(children: List[Any], at: str) -> str:
    """A text block's children as the block's inline HTML (the docs editor's subset: b, i, u, s, code, a, br)."""
    out: List[str] = []

    def walk(c: Any) -> None:
        if not isinstance(c, Element):
            out.append(_escape(_text(c)))
            return
        if c.tag == "br":
            _only(c, [])
            out.append("<br>")
            return
        if c.tag == "a":
            _only(c, ["href"])
            href = _str(c, "href") or ""
            out.append('<a href="' + href.replace("&", "&amp;").replace('"', "&quot;") + '">')
            for x in c.children:
                walk(x)
            out.append("</a>")
            return
        if c.tag not in _MARKS:
            raise ValueError(f"{at}: <{c.tag}> is not a mark (the marks are b, i, u, s, code, a and br)")
        _only(c, [])
        out.append(f"<{c.tag}>")
        for x in c.children:
            walk(x)
        out.append(f"</{c.tag}>")

    for c in children:
        walk(c)
    return "".join(out)


def _plain_text(children: List[Any], at: str) -> str:
    """The plain text of a ``pre``'s children."""
    for c in children:
        if isinstance(c, Element):
            raise ValueError(f"{at}: a code block holds text, not elements")
    return "".join(_text(c) for c in children)


def read_page(root: Element) -> Dict[str, Any]:
    """A ``page(...)`` as the page the docs editor opens, with where each block was written."""
    _only(root, ["title", "paper", "font"])
    sources: Dict[str, Any] = {"page": root.source}
    blocks = []
    for i, el in enumerate(child_elements(root)):
        bid = f"block-{i + 1}"
        sources[f"block:{bid}"] = el.source
        kind = _TEXT_BLOCKS.get(el.tag)
        if kind:
            _only(el, ["checked"] if kind == "todo" else ["align"] if el.tag in _ALIGNED else [])
            checked = _bool(el, "checked")
            blocks.append(_defined({"id": bid, "type": kind, "html": inline_html(el.children, f"<{el.tag}>"),
                                    "checked": (checked if checked is not None else False) if kind == "todo" else None,
                                    "align": _one_of(el, "align", _BLOCK_ALIGN) if el.tag in _ALIGNED else None}))
        elif el.tag == "pre":
            _only(el, ["lang"])
            blocks.append(_defined({"id": bid, "type": "code", "html": _escape(_plain_text(el.children, "<pre>")), "lang": _str(el, "lang")}))
        elif el.tag == "divider":
            _only(el, [])
            blocks.append({"id": bid, "type": "divider", "html": ""})
        elif el.tag == "image":
            _only(el, ["src", "alt"])
            blocks.append(_defined({"id": bid, "type": "image", "html": "", "src": _str(el, "src") or "", "alt": _str(el, "alt")}))
        else:
            raise ValueError(f"<{el.tag}> is not a block of a <page> (the blocks are h1, h2, h3, p, bullet, numbered, todo, quote, pre, "
                             f"divider and image)")
    title = _str(root, "title")
    setup = _defined({"paper": _one_of(root, "paper", PAPERS), "font": _one_of(root, "font", PAGE_FONTS)})
    document = {"format": "page", "version": 1, "blocks": blocks, **({"meta": {"title": title}} if title is not None else {}),
                **({"page": setup} if setup else {})}
    return {"format": "page", "document": document, "sources": sources}


# ── Deck ───────────────────────────────────────────────────────────────────────────────────────────────────────

#: The deck's node types (the decks editor's own).
DECK_TYPES = {"doc": "deck.doc", "slide": "deck.slide", "text": "deck.text", "image": "deck.image", "shape": "deck.shape"}
_BOX = ["x", "y", "w", "h", "rotation"]
_COMMON = [*_BOX, "placeholder", "z", "visible", "opacity", "label", "locked"]
#: A text frame's columns, the gutter between them and the inset from its edges, in slide units.
_TEXT_FRAME = ["columns", "gutter", "inset"]
#: The deck's styles: a few curated looks (the decks editor's own themes), not a theme editor.
DECK_STYLES = ["plain", "ink", "editorial", "signal"]
_MARK_STYLE = {"b": "bold", "i": "italic", "u": "underline", "s": "strike"}


def rich_text(children: List[Any], at: str) -> Dict[str, Any]:
    """A text box's children as the deck's rich text: a ``p`` per paragraph, or text and marks for one paragraph."""

    def runs_of(c: Any, style: Dict[str, Any], out: List[Dict[str, Any]]) -> None:
        if not isinstance(c, Element):
            if out and {k: v for k, v in out[-1].items() if k != "text"} == style:
                out[-1]["text"] += _text(c)
            else:
                out.append({"text": _text(c), **style})
            return
        if c.tag == "a":
            _only(c, ["href"])
            for x in c.children:
                runs_of(x, {**style, "link": _str(c, "href") or ""}, out)
            return
        if c.tag not in _MARK_STYLE:
            raise ValueError(f"{at}: <{c.tag}> is not a mark of a text box (b, i, u, s, a; a <p> per paragraph)")
        _only(c, [])
        for x in c.children:
            runs_of(x, {**style, _MARK_STYLE[c.tag]: True}, out)

    if any(isinstance(c, Element) and c.tag == "p" for c in children):
        paragraphs = []
        for c in children:
            if not isinstance(c, Element) or c.tag != "p":
                raise ValueError(f"{at}: a text with paragraphs holds only <p>s")
            _only(c, [])
            runs: List[Dict[str, Any]] = []
            for x in c.children:
                runs_of(x, {}, runs)
            paragraphs.append({"runs": runs})
    else:
        runs = []
        for x in children:
            runs_of(x, {}, runs)
        paragraphs = [{"runs": runs}]
    return {"paragraphs": paragraphs or [{"runs": []}]}


_ROLES = ["title", "subtitle", "body", "image", "caption", "footer", "slideNumber"]
_TEXT_STYLE = ["fontSize", "color", "bold", "italic", "fontFamily", "lineHeight", "align"]
_TEXT_ALIGN = ["left", "center", "right", "justify"]


def _text_style(el: Element) -> Dict[str, Any]:
    return _defined({"fontSizePx": _num(el, "fontSize"), "color": _str(el, "color"), "bold": _bool(el, "bold"), "italic": _bool(el, "italic"),
                     "fontFamily": _str(el, "fontFamily"), "lineHeight": _num(el, "lineHeight"), "align": _one_of(el, "align", _TEXT_ALIGN)})


def _meta(el: Element, sources: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if el.source is None:
        return {}
    return {"meta": {"source": el.source, **({"sources": sources} if sources else {})}}


def _read_element(c: Element, eid: str, k: int, at: str, groups: List[str]) -> Dict[str, Any]:
    box = _defined({p: _num(c, p) for p in _BOX})
    common = _defined({"box": box or None, "placeholder": _str(c, "placeholder"), "z": _num(c, "z"), "visible": _bool(c, "visible"),
                       "opacity": _num(c, "opacity"), "label": _str(c, "label"), "locked": _bool(c, "locked"), "groups": list(groups) or None})
    if c.tag == "text":
        _only(c, [*_COMMON, "fontSize", "color", "bold", "italic", "underline", "align", "valign", "fontFamily", "lineHeight", "overflow", *_TEXT_FRAME])
        kind = DECK_TYPES["text"]
        columns = _num(c, "columns")
        if columns is not None and (columns != int(columns) or columns < 1):
            raise ValueError(f"{_where(c)}: columns is a whole number from 1")
        inputs = _defined({**common, "text": rich_text(c.children, f"<text> of {at}"), "fontSizePx": _num(c, "fontSize"),
                           "color": _str(c, "color"), "bold": _bool(c, "bold"), "italic": _bool(c, "italic"), "underline": _bool(c, "underline"),
                           "align": _one_of(c, "align", _TEXT_ALIGN),
                           "valign": _one_of(c, "valign", ["top", "middle", "bottom"]), "fontFamily": _str(c, "fontFamily"),
                           "lineHeight": _num(c, "lineHeight"), "overflow": _one_of(c, "overflow", ["visible", "clip", "ellipsis"]),
                           "columns": columns, "gutter": _num(c, "gutter"), "inset": _num(c, "inset")})
    elif c.tag == "shape":
        _only(c, [*_COMMON, "shape", "fill", "stroke", "strokeWidth", "cornerRadius"])
        kind = DECK_TYPES["shape"]
        inputs = _defined({**common, "shape": _one_of(c, "shape", ["rect", "ellipse", "triangle", "line"]) or "rect", "fill": _str(c, "fill"),
                           "stroke": _str(c, "stroke"), "strokeWidth": _num(c, "strokeWidth"), "cornerRadius": _num(c, "cornerRadius")})
    elif c.tag == "image":
        _only(c, [*_COMMON, "src", "fit", "alt"])
        kind = DECK_TYPES["image"]
        inputs = _defined({**common, "src": _str(c, "src") or "", "fit": _one_of(c, "fit", ["fill", "contain", "cover", "none"]),
                           "alt": _str(c, "alt")})
    else:
        raise ValueError(f"<{c.tag}> is not an element of {at} (text, shape, image, group)")
    if not common.get("placeholder") and any(box.get(p) is None for p in ("x", "y", "w", "h")):
        raise ValueError(f"the <{c.tag}> {k} of {at} needs x, y, w and h (or a placeholder to take them from)")
    return {"id": eid, "type": kind, "inputs": inputs, **_meta(c)}


def _read_elements(children: List[Element], owner: str, at: str, nodes: Dict[str, Dict[str, Any]], sources: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The elements of a slide or a master in paint order, each naming the groups around it (outermost first)."""
    wires: List[Dict[str, Any]] = []
    names: set = set()

    def walk(kids: List[Element], groups: List[str]) -> None:
        for c in kids:
            if c.tag == "group":
                _only(c, ["name"])
                name = _str(c, "name")
                if not name:
                    raise ValueError(f"a <group> of {at} needs a name")
                if name in names:
                    raise ValueError(f"two groups of {at} are called {name}")
                names.add(name)
                if not child_elements(c):
                    raise ValueError(f'the <group name="{name}"> of {at} holds no element')
                sources[f"group:{name}"] = c.source
                walk(child_elements(c), [*groups, name])
                continue
            eid = f"{owner}.{len(wires) + 1}"
            nodes[eid] = _read_element(c, eid, len(wires) + 1, at, groups)
            wires.append({"wire": {"node": eid, "port": "out"}})

    walk(children, [])
    return wires


def _read_master(el: Element, nodes: Dict[str, Dict[str, Any]]) -> None:
    _only(el, ["background"])
    sources: Dict[str, Any] = {}
    text_styles: Dict[str, Any] = {}
    layouts: List[str] = []
    decoration: List[Element] = []
    for c in child_elements(el):
        if c.tag == "textStyle":
            _only(c, ["role", *_TEXT_STYLE])
            role = _one_of(c, "role", _ROLES)
            if not role:
                raise ValueError(f"a <textStyle> needs a role ({', '.join(_ROLES)})")
            if role in text_styles:
                raise ValueError(f"two text styles of the master are for {role}")
            text_styles[role] = _text_style(c)
            sources[f"textStyle:{role}"] = c.source
        elif c.tag == "layout":
            _only(c, ["name"])
            name = _str(c, "name")
            if not name:
                raise ValueError("a <layout> needs a name")
            if name in layouts:
                raise ValueError(f"two layouts are called {name}")
            layouts.append(name)
            lid = f"master.layout-{len(layouts)}"
            own: Dict[str, Any] = {}
            placeholders = []
            for p in child_elements(c):
                if p.tag != "placeholder":
                    raise ValueError(f"<{p.tag}> is not read in a <layout> (it holds <placeholder>s)")
                _only(p, ["name", "role", "x", "y", "w", "h", "valign", "prompt", *_TEXT_STYLE])
                pname = _str(p, "name")
                if not pname:
                    raise ValueError(f"a <placeholder> of the layout {name} needs a name")
                if f"placeholder:{pname}" in own:
                    raise ValueError(f"two placeholders of the layout {name} are called {pname}")
                own[f"placeholder:{pname}"] = p.source
                box = _defined({k: _num(p, k) for k in ("x", "y", "w", "h")})
                placeholders.append(_defined({"name": pname, "role": _one_of(p, "role", _ROLES), "box": box or None, **_text_style(p),
                                              "valign": _one_of(p, "valign", ["top", "middle", "bottom"]), "prompt": _str(p, "prompt")}))
            nodes[lid] = {"id": lid, "type": "deck.layout", "inputs": {"name": name, "placeholders": placeholders}, **_meta(c, own)}
        else:
            decoration.append(c)
    wires = _read_elements(decoration, "master", "the master", nodes, sources)
    nodes["master"] = {"id": "master", "type": "deck.master",
                       "inputs": _defined({"background": _str(el, "background"), "textStyles": text_styles or None, **channels("elements", wires)}),
                       **({} if el.source is None else {"meta": {"source": el.source, "sources": sources}})}


def read_deck(root: Element) -> Dict[str, Any]:
    """A ``deck(...)`` as the deck's op graph: ``doc``, then ``slide-N``, then ``slide-N.M`` for its elements. A slide
    names its layout by name (``layout``); the editor binds that name to its layouts. A ``master(...)`` says how the
    deck's master and layouts differ from the stock ones."""
    _only(root, ["name", "width", "height", "dpi", "style"])
    nodes: Dict[str, Dict[str, Any]] = {}
    slides = []
    for el in child_elements(root):
        if el.tag == "master":
            if "master" in nodes:
                raise ValueError("a <deck> has one <master>")
            _read_master(el, nodes)
            continue
        if el.tag != "slide":
            raise ValueError(f"<{el.tag}> is not read in a <deck> (it holds a <master> and <slide>s)")
        _only(el, ["layout", "name", "notes", "background", "hidden"])
        sid = f"slide-{len(slides) + 1}"
        sources: Dict[str, Any] = {}
        elements = _read_elements(child_elements(el), sid, sid, nodes, sources)
        nodes[sid] = {"id": sid, "type": DECK_TYPES["slide"],
                      "inputs": _defined({"layout": _str(el, "layout") or "Title and body", "name": _str(el, "name"), "notes": _str(el, "notes"),
                                          "background": _str(el, "background"), "hidden": _bool(el, "hidden"), **channels("elements", elements)}),
                      **_meta(el, sources)}
        slides.append({"wire": {"node": sid, "port": "out"}})
    name = _str(root, "name") or "Deck"
    width, height = _num(root, "width"), _num(root, "height")
    nodes["doc"] = {"id": "doc", "type": DECK_TYPES["doc"],
                    "inputs": _defined({"name": name, "width": 1280 if width is None else width, "height": 720 if height is None else height,
                                        "dpi": _num(root, "dpi"), "style": _one_of(root, "style", DECK_STYLES),
                                        **channels("slides", slides)}), **_meta(root)}
    return {"id": f"deck:{name}", "nodes": nodes, "outputs": ["doc"], "meta": {"domain": "deck", "name": name}}


declares("office", "workbook", lambda root, stem: {"document": read_workbook(root)})
declares("office", "page", lambda root, stem: {"document": read_page(root)})
declares("office", "deck", lambda root, stem: {"graph": read_deck(root)})
