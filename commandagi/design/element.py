"""ONE ELEMENT MODEL for every document vocabulary — the Python form of the TypeScript SDK's JSX element.

A document is a tree of elements. A call writes one: ``tag(*positional_attributes, *children, **attributes)``.

- The tag is the TypeScript SDK's JSX tag. Its function is named by it: ``-`` becomes ``_`` (``brush_stroke``), a
  Python keyword gets a trailing ``_`` (``from_``), the case is kept (``Company``).
- Positional attributes: a fixed list per tag, written first. Only the schematic has them (``resistor("R1")``).
- Children: the other positional arguments, in order. A list or tuple is spread (a loop is
  ``layer(*[rect(x=i * 10) for i in range(3)])``); ``None`` and booleans are skipped, as JSX skips them. A tag that
  holds text takes texts and inline elements (``p("The run ", b("passed"), ".")``); a leaf takes nothing.
- Attributes: keywords in snake_case of the TypeScript name (``frozen_rows`` is ``frozenRows``: each ``_x`` is ``X``;
  a trailing ``_`` is dropped). A keyword with an uppercase letter is refused by name.

Each element asks ``source.here()`` which call of the running file made it and keeps that index (``source``); a
declaration copies it where the TypeScript SDK copies an element's ``source``.

A vocabulary module declares its tags with ``define(globals(), "module", {tag: signature})``; a signature is the
TypeScript SDK's ``SIGNATURES`` entry: ``{"args": [...], "holds": "children" | "text"}`` (absent: a leaf), and
``"snake": [...]``, the attribute names that are snake_case in TypeScript too (read as written). A root
tag's declaration is registered with ``declares(module, tag, fn)``; ``run_module`` finds it with ``declarer_of``.
"""
from __future__ import annotations

import keyword
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

from .source import here

__all__ = ["Element", "define", "declares", "declarer_of", "child_elements", "texts", "attr_name", "is_element"]

_UPPER = re.compile(r"[A-Z]")
_SNAKE = re.compile(r"_([a-z0-9])")


def attr_name(written: str, where: str = "") -> str:
    """The TypeScript attribute name of a keyword as written (``frozen_rows`` -> ``frozenRows``, ``from_`` -> ``from``)."""
    if _UPPER.search(written):
        snake = _UPPER.sub(lambda m: "_" + m.group(0).lower(), written)
        raise TypeError(f"{where}{written} is written {snake} (keywords are snake_case of the attribute's name)")
    name = written[:-1] if written.endswith("_") and len(written) > 1 else written
    return _SNAKE.sub(lambda m: m.group(1).upper(), name)


class Element:
    """One element: its tag, its attributes by their TypeScript names, its children, and the call that made it."""

    __slots__ = ("tag", "props", "children", "source", "module")

    def __init__(self, tag: str, props: Dict[str, Any], children: List[Any], source: Optional[int], module: str = ""):
        self.tag = tag
        self.props = props
        self.children = children
        self.source = source
        self.module = module

    @property
    def type(self) -> str:
        """The tag (the TypeScript element's ``type``)."""
        return self.tag

    def where(self, key: Optional[str] = None) -> str:
        """``<rect>``, or ``<unit uid="arm">`` with the attribute that names it."""
        for k in ([key] if key else []) + ["name", "id"]:
            v = self.props.get(k)
            if isinstance(v, str):
                return f'<{self.tag} {k}="{v}">'
        return f"<{self.tag}>"

    def __repr__(self) -> str:
        return f"Element({self.tag!r}, {self.props!r}, {len(self.children)} children)"


def is_element(value: Any) -> bool:
    return isinstance(value, Element)


def _flatten(values: Sequence[Any], out: List[Any]) -> List[Any]:
    for v in values:
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, (list, tuple)):
            _flatten(v, out)
        else:
            out.append(v)
    return out


def _make(module: str, tag: str, signature: Dict[str, Any]) -> Callable[..., Element]:
    args: Sequence[str] = tuple(signature.get("args") or ())
    holds: Optional[str] = signature.get("holds")
    # An attribute whose TypeScript name is itself snake_case (a world's `size_mm`) is written as it is: the snake_case
    # of `size_mm` is `size_mm`, so a writer needs nothing more; only the reading needs the tag's list.
    keep = frozenset(signature.get("snake") or ())

    def make(*given: Any, **attributes: Any) -> Element:
        source = here()
        where = f"{fn_name}(): "
        props: Dict[str, Any] = {}
        for name, value in zip(args, given):
            props[name] = value
        for written, value in attributes.items():
            name = written if written in keep else attr_name(written, where)
            if name in props:
                raise TypeError(f"{where}{written} is given twice")
            props[name] = value
        children = _flatten(given[len(args):], [])
        if children and holds is None:
            raise TypeError(f"{where}<{tag}> holds nothing (write its attributes as keywords)")
        for c in children:
            if isinstance(c, Element):
                continue
            if holds == "text" and isinstance(c, (str, int, float)):
                continue
            what = "text" if isinstance(c, (str, int, float)) else type(c).__name__
            raise TypeError(f"{where}<{tag}> holds {'texts and elements' if holds == 'text' else 'elements'}, not {what}")
        return Element(tag, props, children, source, module)

    fn_name = tag.replace("-", "_")
    if keyword.iskeyword(fn_name):
        fn_name += "_"
    make.__name__ = make.__qualname__ = fn_name
    make.__doc__ = f"The <{tag}> element" + (f" ({', '.join(args)} first)" if args else "") + "."
    return make


def define(namespace: Dict[str, Any], module: str, signatures: Dict[str, Dict[str, Any]]) -> List[str]:
    """Put one function per tag in a module's namespace; return their names (for ``__all__``)."""
    names = []
    for tag, signature in signatures.items():
        fn = _make(module, tag, signature)
        namespace[fn.__name__] = fn
        names.append(fn.__name__)
    return names


_DECLARERS: Dict[Any, Callable[[Element, str], Dict[str, Any]]] = {}


def declares(module: str, tag: str, fn: Callable[[Element, str], Dict[str, Any]]) -> None:
    """Register what a root element declares: ``fn(root, stem)`` returns ``{"graph": g}`` or ``{"document": d}``."""
    _DECLARERS[(module, tag)] = fn


def declarer_of(value: Any) -> Optional[Callable[[Element, str], Dict[str, Any]]]:
    return _DECLARERS.get((value.module, value.tag)) if isinstance(value, Element) else None


def child_elements(el: Element) -> List[Element]:
    """The element's children that are elements (texts skipped)."""
    return [c for c in el.children if isinstance(c, Element)]


def texts(el: Element) -> List[str]:
    """The element's children that are texts, as strings."""
    return [c if isinstance(c, str) else _number_text(c) for c in el.children if not isinstance(c, Element)]


def _number_text(n: Any) -> str:
    """A number as JavaScript's ``String(n)`` writes it (1.0 -> "1")."""
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)
