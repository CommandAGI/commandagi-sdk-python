"""WHERE A ``.py`` FILE'S CALLS ARE — the source map a Python code part's run carries, computed by the interpreter
that runs the file (Python's own ``ast``), so an editor can write an edit back into the file as a minimal text edit.

It is the Python half of the TypeScript sandbox's ``jsx-source.ts``: there a JSX element declares a node; here a call
does (``resistor("R1", resistance="3k", sch_x=114.3)``). ``SourceMap(text, path)`` lists every call in source order:
its name, its span, the span of each keyword argument with its value when the value is a literal (else the
expression), the ``with`` block it is written in, and whether it is a statement of its own. While the file runs, a
primitive asks ``here()`` which call it is; the run counts each call's evaluations (more than one: a loop, or a
function called more than once), and the node the call declared carries ``meta.source`` (``element_source``).

Offsets are UTF-16 code units from the start of the text, lines and columns 1-based: what a JavaScript editor
indexes the same text with. ``ast`` gives byte columns; they are converted here.

PURE apart from ``here()``, which reads the running frames.
"""
from __future__ import annotations

import ast
import math
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_LINES = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)?")


def _units(s: str) -> int:
    """UTF-16 code units of ``s`` (what a JavaScript string's length counts)."""
    return len(s.encode("utf-16-le")) // 2


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


class SourceMap:
    """Every call of a Python file, in source order (``elements``), and the run's count of each one's evaluations."""

    def __init__(self, text: str, path: str):
        self.text = text
        self.path = path
        lines = [m.group(0) for m in _LINES.finditer(text)]
        self._lines = lines
        self._starts: List[int] = []
        at = 0
        for line in lines:
            self._starts.append(at)
            at += _units(line)
        self.length = _units(text)
        self.evaluations: Dict[int, int] = {}
        self.elements: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self._spans: List[Tuple[int, int, int, int]] = []
        self._positions: Dict[Any, List[Any]] = {}
        self._scan(ast.parse(text, path))

    # ── Offsets ──────────────────────────────────────────────────────────────────────────────────────────────────

    def offset(self, lineno: int, col: int) -> int:
        """The UTF-16 offset of ``ast``'s (line, byte column)."""
        line = self._lines[lineno - 1] if 0 < lineno <= len(self._lines) else ""
        return (self._starts[lineno - 1] if 0 < lineno <= len(self._starts) else self.length) + _units(line.encode("utf-8")[:col].decode("utf-8", "ignore"))

    def _span(self, node: ast.AST) -> Tuple[int, int]:
        return self.offset(node.lineno, node.col_offset), self.offset(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    # ── The scan ─────────────────────────────────────────────────────────────────────────────────────────────────

    def _scan(self, tree: ast.AST) -> None:
        found: List[Tuple[ast.Call, Optional[ast.Call], Optional[ast.stmt], Optional[List[ast.stmt]], Optional[ast.With], bool]] = []

        def visit(node: ast.AST, block: Optional[ast.Call], stmt: Optional[ast.stmt], body: Optional[List[ast.stmt]], direct: bool) -> None:
            if isinstance(node, ast.ImportFrom) and node.module:
                star = any(a.name == "*" for a in node.names)
                s0, e0 = self._span(node)
                self.imports.append({"module": node.module, "star": star, "start": s0, "end": e0,
                                     "names": [] if star else [{"name": a.name, "asname": a.asname, **dict(zip(("start", "end"), self._span(a)))} for a in node.names]})
                return
            if isinstance(node, ast.With):
                # Its items are written outside its block; its body inside the block of the last call it opens.
                opener = next((i.context_expr for i in reversed(node.items) if isinstance(i.context_expr, ast.Call)), None)
                for item in node.items:
                    if item.context_expr is opener:
                        found.append((opener, block, None, None, node, False))
                        for child in ast.iter_child_nodes(opener):
                            visit(child, block, None, None, False)
                    else:
                        visit(item, block, None, None, False)
                for s in node.body:
                    visit(s, opener or block, s, node.body, opener is not None)
                return
            if isinstance(node, ast.Expr):
                visit(node.value, block, node, body, direct)
                return
            if isinstance(node, ast.Call):
                own = isinstance(stmt, ast.Expr) and stmt.value is node
                found.append((node, block, stmt if own else None, body if own else None, None, direct and own))
            for field, value in ast.iter_fields(node):
                if isinstance(value, list) and value and all(isinstance(s, ast.stmt) for s in value):
                    for s in value:
                        visit(s, block, s, value, False)
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, ast.AST):
                            visit(v, block, None, None, False)
                elif isinstance(value, ast.AST):
                    visit(value, block, None, None, False)

        for s in getattr(tree, "body", []):
            visit(s, None, s, tree.body, False)  # type: ignore[attr-defined]
        found.sort(key=lambda f: (f[0].lineno, f[0].col_offset, -f[0].end_lineno, -f[0].end_col_offset))  # type: ignore[operator]
        index = {id(f[0]): i for i, f in enumerate(found)}
        for i, (call, block, stmt, body, with_, child) in enumerate(found):
            el = self._element(i, call, index.get(id(block)) if block is not None else None, stmt, body, with_)
            el["child"] = child
            self.elements.append(el)
            self._spans.append((call.lineno, call.col_offset, call.end_lineno, call.end_col_offset))  # type: ignore[arg-type]

    def _element(self, i: int, call: ast.Call, parent: Optional[int], stmt: Optional[ast.stmt], body: Optional[List[ast.stmt]],
                 with_: Optional[ast.With]) -> Dict[str, Any]:
        start, end = self._span(call)
        f = call.func
        tag = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        el: Dict[str, Any] = {"index": i, "tag": tag, "start": start, "end": end, "line": call.lineno,
                              "column": self.offset(call.lineno, call.col_offset) - self._starts[call.lineno - 1] + 1,
                              "parent": parent, "props": [], "args": [], "spread": None, "callee": ast.get_source_segment(self.text, f) or tag,
                              # A statement of its own: removing the call removes the statement; the last one of its
                              # block leaves `pass`.
                              "statement": stmt is not None,
                              "body": {"key": self._span(body[0])[0], "size": len(body)} if stmt is not None and body else None}
        for a in call.args:
            if isinstance(a, ast.Starred):
                el["spread"] = el["spread"] or {"line": a.lineno, "expr": ast.get_source_segment(self.text, a) or "*"}
                continue
            s, e = self._span(a)
            el["args"].append({"start": s, "end": e, **self._value(a)})
        for kw in call.keywords:
            if kw.arg is None:
                el["spread"] = el["spread"] or {"line": kw.lineno, "expr": ast.get_source_segment(self.text, kw) or "**"}
                continue
            s, e = self._span(kw)
            vs, ve = self._span(kw.value)
            el["props"].append({"name": kw.arg, "start": s, "end": e, "valueStart": vs, "valueEnd": ve, "line": kw.lineno, **self._value(kw.value)})
        if with_ is not None and with_.body:
            # Where a call written in this block goes: after the block's last statement, at its indent.
            first, last = with_.body[0], with_.body[-1]
            el["block"] = {"end": self.offset(last.end_lineno, last.end_col_offset),  # type: ignore[arg-type]
                           "indent": re.match(r"[ \t]*", self._lines[first.lineno - 1]).group(0),  # type: ignore[union-attr]
                           "pass": list(self._span(first)) if len(with_.body) == 1 and isinstance(first, ast.Pass) else None}
        return el

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
                             **({"value": p["value"]} if p["literal"] else {"expr": p["expr"]})} for p in el["props"]}
        out = {"element": i, "tag": el["tag"], "line": el["line"], "column": el["column"], "start": el["start"], "end": el["end"],
               "evaluations": self.evaluations.get(i, 0), "props": props}
        if el["spread"]:
            out["spread"] = el["spread"]
        return out

    def to_json(self) -> Dict[str, Any]:
        """The file's map, as the graph's ``meta.sourceMap`` (what a write-back finds the calls with)."""
        return {"language": "py", "length": self.length, "elements": self.elements, "imports": self.imports}


# ── The run's map ───────────────────────────────────────────────────────────────────────────────────────────────

_current: List[SourceMap] = []
_declared: List[List[Any]] = []


class running:
    """``with running(text, path) as m:`` — the map while the file runs; ``declared()`` collects what it declares."""

    def __init__(self, text: str, path: str):
        try:
            self.map: Optional[SourceMap] = SourceMap(text, path)
        except SyntaxError:
            self.map = None  # the run itself reports it
        self.declared: List[Any] = []

    def __enter__(self) -> "running":
        _current.append(self.map)  # type: ignore[arg-type]
        _declared.append(self.declared)
        return self

    def __exit__(self, *exc: Any) -> None:
        _current.pop()
        _declared.pop()


def declare(value: Any) -> None:
    """A finished top-level declaration (a ``with group(...)`` block): the file's result if it names no other."""
    if _declared:
        _declared[-1].append(value)


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


def finish(graph: Dict[str, Any], m: Optional[SourceMap]) -> None:
    """Replace each node's ``meta.source`` (a call's index) with where the call is; give the graph the file's map when a
    primitive of the file asked where it was."""
    if m is None:
        return
    used = False
    for node in graph.get("nodes", {}).values():
        src = (node.get("meta") or {}).get("source")
        if isinstance(src, int) and not isinstance(src, bool) and 0 <= src < len(m.elements):
            node["meta"] = {**node["meta"], "source": m.element_source(src)}
            used = True
    if used or m.evaluations:  # a declared block with nothing in it yet is mapped too (a first call goes there)
        graph["meta"] = {**(graph.get("meta") or {}), "sourceMap": m.to_json()}
