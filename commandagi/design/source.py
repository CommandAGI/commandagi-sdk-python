"""WHERE A ``.py`` FILE'S CALLS ARE — the source map a Python code part's run carries, computed by the interpreter
that runs the file (Python's own ``ast``), so the write-back engine can write an edit back into the file as the
smallest text edit.

It is the Python half of the TypeScript sandbox's ``jsx-source.ts``: there a JSX element declares a node; here a call
does (``resistor("R1", resistance="3k", sch_x=114.3)``). ``SourceMap(text, path)`` lists every call of a function by
name or path (``rect(…)``, ``twod.rect(…)``) in source order, in the one shape every SDK's map has (the write-back
contract, § the source map): its span, its keywords (``props``), its positional arguments (``args``), the element it is
written in (``parent``), its place among its parent's positional arguments (``slot``), and whether it runs in a loop
(``looped``). While the file runs, an element asks ``here()`` which call made it; the run counts each call's
evaluations, and ``finish`` turns each index a declaration kept into the call's ``element_source``.

Offsets are UTF-16 code units from the start of the text, lines and columns 1-based: what a JavaScript editor indexes
the same text with. ``ast`` gives byte columns; they are converted here.

PURE apart from ``here()``, which reads the running frames.
"""
from __future__ import annotations

import ast
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["SourceMap", "running", "here", "finish"]


class _NotData(Exception):
    pass


def _data(v: Any) -> Any:
    """A literal's value as JSON data; anything JSON cannot hold is not one."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            raise _NotData()
        return int(v) if v.is_integer() else v
    if isinstance(v, (list, tuple)):
        return [_data(x) for x in v]
    if isinstance(v, dict):
        if not all(isinstance(k, str) for k in v):
            raise _NotData()
        return {k: _data(x) for k, x in v.items()}
    raise _NotData()


def _path(f: ast.expr) -> Optional[str]:
    """The callee's last name when it is a name or a dotted path of names (``rect``, ``twod.rect``), else None."""
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute) and _path(f.value) is not None:
        return f.attr
    return None


# What runs more than once, or not where it is written: a loop's body, a comprehension, a lambda.
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


class SourceMap:
    """Every call of a Python file, in source order (``elements``), its ``from … import`` lines (``imports``), and the
    run's count of each call's evaluations."""

    def __init__(self, text: str, path: str):
        self.text = text
        self.path = path
        # The UTF-16 offset of each character index, and each line's first character index.
        self._u16 = [0] * (len(text) + 1)
        for k, ch in enumerate(text):
            self._u16[k + 1] = self._u16[k] + (2 if ord(ch) > 0xFFFF else 1)
        self._line_starts = [0]
        k = 0
        while k < len(text):
            ch = text[k]
            if ch == "\r" and k + 1 < len(text) and text[k + 1] == "\n":
                k += 1
            if ch in "\r\n":
                self._line_starts.append(k + 1)
            k += 1
        self.length = self._u16[-1]
        self.evaluations: Dict[int, int] = {}
        self.elements: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self._spans: List[Tuple[int, int, int, int]] = []
        self._positions: Dict[Any, List[Any]] = {}
        self._scan(ast.parse(text, path))

    # ── Offsets ──────────────────────────────────────────────────────────────────────────────────────────────────

    def _char(self, lineno: int, col: int) -> int:
        """The character index of ``ast``'s (line, byte column)."""
        if not 0 < lineno <= len(self._line_starts):
            return len(self.text)
        start = self._line_starts[lineno - 1]
        end = self._line_starts[lineno] if lineno < len(self._line_starts) else len(self.text)
        return start + len(self.text[start:end].encode("utf-8")[:col].decode("utf-8", "ignore"))

    def offset(self, lineno: int, col: int) -> int:
        """The UTF-16 offset of ``ast``'s (line, byte column)."""
        return self._u16[self._char(lineno, col)]

    def _span(self, node: ast.AST) -> Tuple[int, int]:
        return self.offset(node.lineno, node.col_offset), self.offset(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    def _chars(self, node: ast.AST) -> Tuple[int, int]:
        return self._char(node.lineno, node.col_offset), self._char(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    def _skip(self, k: int) -> int:
        """The first character at or after ``k`` that is not blank space or a comment."""
        t = self.text
        while k < len(t):
            if t[k] in " \t\r\n\f\\":
                k += 1
            elif t[k] == "#":
                while k < len(t) and t[k] not in "\r\n":
                    k += 1
            else:
                break
        return k

    # ── The scan ─────────────────────────────────────────────────────────────────────────────────────────────────

    def _scan(self, tree: ast.AST) -> None:
        # Each call: (call, parent call, the call whose direct positional argument it is, looped).
        found: List[Tuple[ast.Call, Optional[ast.Call], Optional[ast.Call], bool]] = []

        def visit(node: ast.AST, parent: Optional[ast.Call], looped: bool) -> None:
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                star = any(a.name == "*" for a in node.names)
                s0, e0 = self._span(node)
                self.imports.append({"module": node.module, "star": star, "start": s0, "end": e0,
                                     "names": [] if star else [{"name": a.name, "asname": a.asname, **dict(zip(("start", "end"), self._span(a)))}
                                                               for a in node.names]})
                return
            if isinstance(node, ast.Call) and _path(node.func) is not None:
                found.append((node, parent, None, looped))
                visit_inside(node, looped)
                return
            if isinstance(node, (ast.For, ast.AsyncFor)):
                visit(node.target, parent, looped)
                visit(node.iter, parent, looped)
                for s in node.body + node.orelse:
                    visit(s, parent, True)
                return
            if isinstance(node, ast.While):
                for s in [node.test, *node.body, *node.orelse]:
                    visit(s, parent, True)
                return
            if isinstance(node, _COMPREHENSIONS):
                gens = node.generators
                # The first iterable is evaluated once, where it is written; everything else runs per item.
                visit(gens[0].iter, parent, looped)
                for g in gens:
                    if g is not gens[0]:
                        visit(g.iter, parent, True)
                    visit(g.target, parent, True)
                    for c in g.ifs:
                        visit(c, parent, True)
                for part in ((node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,)):
                    visit(part, parent, True)
                return
            if isinstance(node, ast.Lambda):
                visit(node.args, parent, looped)
                visit(node.body, parent, True)
                return
            for child in ast.iter_child_nodes(node):
                visit(child, parent, looped)

        def visit_inside(call: ast.Call, looped: bool) -> None:
            """A call already listed: its own callee and arguments."""
            visit(call.func, call, looped)
            for a in call.args:
                if isinstance(a, ast.Call) and _path(a.func) is not None:
                    found.append((a, call, call, looped))
                    visit_inside(a, looped)
                else:
                    visit(a.value if isinstance(a, ast.Starred) else a, call, looped)
            for kw in call.keywords:
                visit(kw.value, call, looped)

        visit(tree, None, False)
        found.sort(key=lambda f: (self._span(f[0])[0], -self._span(f[0])[1]))
        index = {id(f[0]): i for i, f in enumerate(found)}
        for i, (call, parent, holder, looped) in enumerate(found):
            el = self._element(i, call, index.get(id(parent)) if parent is not None else None, index)
            el["slot"] = self._slot(holder, call) if holder is not None else None
            el["looped"] = looped
            el["placed"] = el["slot"] is not None and not looped
            self.elements.append(el)
            self._spans.append((call.lineno, call.col_offset, call.end_lineno, call.end_col_offset))  # type: ignore[arg-type]

    def _open(self, call: ast.Call) -> int:
        """The character index just after the call's ``(``."""
        k = self._skip(self._chars(call.func)[1])
        return k + 1 if k < len(self.text) and self.text[k] == "(" else k

    def _element(self, i: int, call: ast.Call, parent: Optional[int], index: Dict[int, int]) -> Dict[str, Any]:
        start, end = self._span(call)
        f = call.func
        tag = _path(f) or ""
        _, end_char = self._chars(call)
        el: Dict[str, Any] = {"index": i, "tag": tag, "callee": ast.get_source_segment(self.text, f) or tag, "start": start, "end": end,
                              "line": call.lineno, "column": start - self._u16[self._line_starts[call.lineno - 1]] + 1,
                              "parent": parent, "props": [], "args": [],
                              "open": self._u16[self._open(call)], "close": self._u16[end_char - 1], "spread": None}
        # A `*parts` stays in `args` and a `**extra` in `props`, each in its place (the engine inserts beside them), and
        # each also sets `spread`: an attribute or a child the call does not write may come from there.
        for a in call.args:
            s, e = self._span(a)
            if isinstance(a, ast.Starred):
                expr = ast.get_source_segment(self.text, a) or "*"
                el["spread"] = el["spread"] or {"line": a.lineno, "expr": expr}
                el["args"].append({"start": s, "end": e, "line": a.lineno, "literal": False, "expr": expr, "starred": True})
                continue
            arg = {"start": s, "end": e, "line": a.lineno, **self._value(a)}
            if isinstance(a, ast.Call) and id(a) in index:
                arg["element"] = index[id(a)]
            el["args"].append(arg)
        for kw in call.keywords:
            s, e = self._span(kw)
            vs, ve = self._span(kw.value)
            if kw.arg is None:
                expr = ast.get_source_segment(self.text, kw) or "**"
                el["spread"] = el["spread"] or {"line": kw.lineno, "expr": expr}
                el["props"].append({"name": "**", "start": s, "end": e, "valueStart": vs, "valueEnd": ve, "literal": False, "expr": expr,
                                    "line": kw.lineno})
                continue
            el["props"].append({"name": kw.arg, "start": s, "end": e, "valueStart": vs, "valueEnd": ve, "line": kw.lineno, **self._value(kw.value)})
        return el

    def _slot(self, holder: ast.Call, call: ast.Call) -> Dict[str, Any]:
        """Where a direct positional argument sits among its call's arguments (keywords included, in source order)."""
        args = sorted([*holder.args, *holder.keywords], key=lambda a: self._chars(a)[0])
        k = next(n for n, a in enumerate(args) if a is call)
        before = self._chars(args[k - 1])[1] if k > 0 else self._open(holder)
        end_char = self._chars(call)[1]
        after = self._chars(args[k + 1])[0] if k + 1 < len(args) else self._chars(holder)[1] - 1
        nxt = self._skip(end_char)
        return {"before": self._u16[before], "after": self._u16[after], "comma": nxt < len(self.text) and self.text[nxt] == ","}

    def _value(self, node: ast.expr) -> Dict[str, Any]:
        try:
            return {"literal": True, "value": _data(ast.literal_eval(node))}
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError, _NotData):
            return {"literal": False, "expr": ast.get_source_segment(self.text, node) or ""}

    # ── At run time ──────────────────────────────────────────────────────────────────────────────────────────────

    def call_at(self, lineno: Optional[int], col: Optional[int], fallback_line: int) -> Optional[int]:
        """The innermost call whose span holds (line, byte column); without a column, the one call on the line."""
        if lineno is None or col is None:
            on = [i for i, s in enumerate(self._spans) if s[0] == fallback_line]
            return on[0] if len(on) == 1 else None
        best: Optional[int] = None
        for i, (l0, c0, l1, c1) in enumerate(self._spans):
            if (l0, c0) <= (lineno, col) < (l1, c1):
                if best is None or (l0, c0) >= self._spans[best][:2]:
                    best = i
        return best

    def element_source(self, i: int) -> Dict[str, Any]:
        """What a node's ``meta.source`` holds for the call it came from (the JSX map's ``ElementSource``)."""
        el = self.elements[i]
        props = {p["name"]: {"start": p["valueStart"], "end": p["valueEnd"], "literal": p["literal"], "line": p["line"],
                             **({"value": p["value"]} if p["literal"] else {"expr": p["expr"]})} for p in el["props"] if p["name"] != "**"}
        out = {"element": i, "tag": el["tag"], "line": el["line"], "column": el["column"], "start": el["start"], "end": el["end"],
               "evaluations": self.evaluations.get(i, 0), "props": props}
        if el["spread"]:
            out["spread"] = el["spread"]
        return out

    def to_json(self) -> Dict[str, Any]:
        """The file's map, as the graph's ``meta.sourceMap`` (what a write-back finds the calls with)."""
        return {"language": "py", "length": self.length, "elements": self.elements, "imports": self.imports}


# ── The run's map ───────────────────────────────────────────────────────────────────────────────────────────────

_current: List[Optional[SourceMap]] = []


class running:
    """``with running(text, path) as run:`` — the file's map (``run.map``) while it runs; re-entered to call ``main``."""

    def __init__(self, text: str, path: str):
        try:
            self.map: Optional[SourceMap] = SourceMap(text, path)
        except SyntaxError:
            self.map = None  # the run itself reports it

    def __enter__(self) -> "running":
        _current.append(self.map)
        return self

    def __exit__(self, *exc: Any) -> None:
        _current.pop()


def here() -> Optional[int]:
    """The call of the running file that is executing now (the innermost one written in the file), counted once."""
    m = _current[-1] if _current else None
    if m is None:
        return None
    f = sys._getframe(1)
    while f is not None and f.f_code.co_filename != m.path:
        f = f.f_back  # type: ignore[assignment]
    if f is None:
        return None
    lineno = col = None
    positions = getattr(f.f_code, "co_positions", None)
    if positions is not None:
        table = m._positions.get(f.f_code)
        if table is None:
            table = m._positions[f.f_code] = list(positions())
        k = f.f_lasti // 2
        if 0 <= k < len(table):
            lineno, _, col, _ = table[k]
    i = m.call_at(lineno, col, f.f_lineno)
    if i is not None:
        m.evaluations[i] = m.evaluations.get(i, 0) + 1
    return i


def _resolved(v: Any, m: SourceMap) -> Any:
    """A kept call index as the call's ``element_source``; ``None`` stays ``None``; anything else is left as it is."""
    if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(m.elements):
        return m.element_source(v)
    return v


def _resolve_map(values: Dict[str, Any], m: SourceMap) -> Dict[str, Any]:
    """Each value of a ``sources`` map resolved; an element made outside the file (no call) is left out, as TS leaves
    out an element without ``__source``."""
    return {k: r for k, r in ((k, _resolved(v, m)) for k, v in values.items()) if r is not None}


def _resolve_meta(meta: Any, m: SourceMap) -> None:
    """A ``meta``'s ``source`` and each of its ``sources``, resolved in place."""
    if not isinstance(meta, dict):
        return
    if "source" in meta:
        meta["source"] = _resolved(meta["source"], m)
        if meta["source"] is None:
            del meta["source"]
    if isinstance(meta.get("sources"), dict):
        meta["sources"] = _resolve_map(meta["sources"], m)


def finish(graph: Dict[str, Any], m: Optional[SourceMap], document: Optional[Dict[str, Any]] = None) -> None:
    """Turn every kept call index (each node's ``meta.source`` and ``meta.sources``, the graph's own ``meta``, a
    document's ``sources``) into where the call is, and give the graph the file's map in ``meta.sourceMap``."""
    if m is None:
        return
    for node in (graph.get("nodes") or {}).values():
        _resolve_meta(node.get("meta"), m)
        if isinstance(node.get("meta"), dict) and not node["meta"]:
            del node["meta"]
    _resolve_meta(graph.get("meta"), m)
    if document is not None and isinstance(document.get("sources"), dict):
        document["sources"] = _resolve_map(document["sources"], m)
    if m.evaluations:
        graph["meta"] = {**(graph.get("meta") or {}), "sourceMap": m.to_json()}
