"""``to_tsx(element)``: a Python document as the TypeScript SDK's code file, for a place that reads only TSX.

The element model is one (``./element.py``): a Python call is a JSX element with the same tag, its attributes by
their TypeScript names and its children in order. So the TSX is written from the element alone, and it declares the
same document: ``export default () => (<root …>…</root>);``. The file's extension (``.sch.tsx``, ``.3d.tsx`` …) is the
caller's to choose, as for a ``.py`` file.

What is written: a string attribute as ``name="…"`` (as ``{"…"}`` when it holds a quote, an ``&`` or a line break,
which JSX would read otherwise); every other value as a JavaScript literal in braces; an attribute that is ``None``
not at all (the SDKs read an absent attribute and ``undefined`` alike). Texts are written inline with their
elements, and as ``{"…"}`` when JSX would change them. A value JavaScript has no literal for (NaN, an infinity, an
object that is not data) is refused by its attribute's name.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, List

from .element import Element, _number_text

__all__ = ["to_tsx"]

_WIDTH = 120
_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_PLAIN_TEXT = re.compile(r"^[^{}<>&\n\r]*$")


def to_tsx(element: Element, indent: str = "  ") -> str:
    """The TSX code file that declares the same document as ``element`` (the root a ``.py`` document's ``result`` is)."""
    if not isinstance(element, Element):
        raise TypeError(f"to_tsx takes a document's root element (group(...), part(...), board(...) …), not {type(element).__name__}")
    # A capitalised tag (<Company>) is a value in JSX, not an intrinsic element: the file imports it from the SDK.
    named = sorted({t for t in _tags(element) if t[:1].isupper()})
    imports = f'import {{ {", ".join(named)} }} from "commandagi/design";\n\n' if named else ""
    return imports + "export default () => (\n" + "\n".join(_lines(element, 1, indent)) + "\n);\n"


def _tags(el: Element) -> List[str]:
    out = [el.tag]
    for c in list(el.children) + list(el.props.values()):
        if isinstance(c, Element):
            out += _tags(c)
    return out


def _js(value: Any, where: str) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{where}: {value} has no JavaScript literal")
        return _number_text(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, Element):
        return _inline(value, where)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_js(v, where) for v in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        fields = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{where}: a key {k!r} is not a string")
            fields.append(f"{k if _IDENT.match(k) else json.dumps(k, ensure_ascii=False)}: {_js(v, where)}")
        return "{ " + ", ".join(fields) + " }"
    raise ValueError(f"{where}: a {type(value).__name__} is not data")


def _attr(tag: str, name: str, value: Any) -> str:
    if isinstance(value, str) and not any(c in value for c in '"&\n\r'):
        return f'{name}="{value}"'
    return f"{name}={{{_js(value, f'<{tag}> {name}')}}}"


def _attrs(el: Element) -> List[str]:
    return [_attr(el.tag, k, v) for k, v in el.props.items() if v is not None]


def _children_inline(el: Element) -> str:
    out = []
    for i, c in enumerate(el.children):
        if isinstance(c, Element):
            out.append(_inline(c, f"<{el.tag}>"))
        else:
            out.append(_inline_text(c, first=i == 0, last=i == len(el.children) - 1))
    return "".join(out)


def _inline_text(value: Any, first: bool, last: bool) -> str:
    """A text between elements on one line: JSX keeps it as written unless it holds a brace, an angle bracket, an
    entity or a line break, or is only spaces at an end (JSX keeps those too, but a reader would not see them)."""
    text = value if isinstance(value, str) else _number_text(value)
    plain = bool(text) and _PLAIN_TEXT.match(text) and not ((first and text[0] == " ") or (last and text[-1] == " "))
    return text if plain else "{" + json.dumps(text, ensure_ascii=False) + "}"


def _inline(el: Element, where: str = "") -> str:
    head = " ".join([el.tag] + _attrs(el))
    if not el.children:
        return f"<{head} />"
    return f"<{head}>{_children_inline(el)}</{el.tag}>"


def _lines(el: Element, depth: int, indent: str) -> List[str]:
    pad = indent * depth
    attrs = _attrs(el)
    holds_text = any(not isinstance(c, Element) for c in el.children)
    one = pad + _inline(el) if holds_text or not el.children else None
    if one is not None and len(one) <= _WIDTH:
        return [one]
    head = " ".join([el.tag] + attrs)
    if len(pad) + len(head) + 3 <= _WIDTH:
        opening = [f"{pad}<{head}" + (" />" if not el.children else ">")]
    else:
        opening = [f"{pad}<{el.tag}"] + [pad + indent + a for a in attrs] + [pad + ("/>" if not el.children else ">")]
    if not el.children:
        return opening
    if holds_text:
        body = [pad + indent + _children_inline(el)]
    else:
        body = [line for c in el.children for line in _lines(c, depth + 1, indent)]
    return opening + body + [f"{pad}</{el.tag}>"]
