"""``commandagi.design`` — compositional primitives that DECLARE structure as the CommandAGI op graph.

The same primitives as the TypeScript SDK's ``commandagi/design``: CAD (``part``, ``sketch``, features),
EDA (``circuit``, ``component``, ``net``, ``board``), any graph (``graph``, ``node``, ``input_``, ``code``),
and a CadQuery-style importer (``commandagi.design.cadquery``). Structure only — no kernel, solver, router
or renderer. A ``.py`` file using these is a CODE PART: a graph's code node runs it (in the browser, under
Pyodide, with no network) and the editor evaluates what it declares.

A code part is a script. Its result is, first found: ``main(**inputs)`` if it defines ``main``; else what
it passed to ``show_object``; else its ``result`` variable; else the block it declared (``with group(...)``,
``commandagi.design.schematic``). Each node a call declared carries where the call is (``meta.source``, ``./source.py``). ``param(name, default, unit=…)`` reads an input
(declaring it); a ``params`` dict declares inputs too.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .ir import Declaration, NodeRef, Out, Scope, channels, check_ir, is_ir_graph
from .graph import CODE_OP, INPUT_OP, code, graph, input_, node
from .cad import (PLANES, Body, SketchBuilder, SketchRef, assembly, box, chamfer, circular_pattern, cone, copy, cylinder,
                  extrude, fillet, hole, instance, intersect, linear_pattern, mirror, part, revolve, sketch, sphere,
                  subtract, union)
from .eda import PartRef, board, circuit, component, connect, footprints, net, part_type_for
from . import cadquery as _cq
from . import threed as _threed
from . import twod
from .solids import declare_solids
from .business import (BUSINESS_TAGS, Books, Calendar, CapTable, Case, Change, Company, Entity, Harm, Matters, Option, People,
                       Registration, Relief, Rfc, document_of)
from . import source as _source
from .media import MEDIA_ROOTS, Element, declare_song, declare_video, from_media
from .office import (OfficeDocument, a, b, br, bullet, cell, code_, column, deck, divider, h1, h2, h3, i, image, numbered, p, page,
                     pre, quote, row, s, shape, sheet, slide, text, todo, u, workbook)

__all__ = [
    "Declaration", "NodeRef", "Out", "Scope", "channels", "check_ir", "is_ir_graph",
    "CODE_OP", "INPUT_OP", "code", "graph", "input_", "node",
    "PLANES", "Body", "SketchBuilder", "SketchRef", "assembly", "box", "chamfer", "circular_pattern", "cone", "copy",
    "cylinder", "extrude", "fillet", "hole", "instance", "intersect", "linear_pattern", "mirror", "part", "revolve",
    "sketch", "sphere", "subtract", "union",
    "PartRef", "board", "circuit", "component", "connect", "footprints", "net", "part_type_for",
    "graph_of", "run_module",
    "BUSINESS_TAGS", "Books", "Calendar", "CapTable", "Case", "Change", "Company", "Entity", "Harm", "Matters", "Option", "People",
    "Registration", "Relief", "Rfc", "document_of",
    "Element", "declare_song", "declare_video", "from_media",
    "twod",
    "OfficeDocument", "workbook", "sheet", "cell", "column", "row", "page", "h1", "h2", "h3", "p", "bullet", "numbered", "todo",
    "quote", "pre", "divider", "image", "b", "i", "u", "s", "code_", "a", "br", "deck", "slide", "text", "shape",
]
# A 3D document, element by element (the TypeScript SDK's JSX): `commandagi.design.threed` (h, document).


def graph_of(value: Any, name: str = "Part") -> Dict[str, Any]:
    """The op graph a declared value is: a declaration, a plain IR graph, or CadQuery-style workplanes."""
    if isinstance(value, Declaration):
        return value.ir
    if is_ir_graph(value):
        return value
    if isinstance(value, Element) and value.type in MEDIA_ROOTS:
        return from_media(value).ir
    if isinstance(value, _threed.Element):
        return _threed.declare_threed(value, name)
    if isinstance(value, _cq.Workplane) or (isinstance(value, (list, tuple)) and value and all(isinstance(v, _cq.Workplane) for v in value)):
        return declare_solids(name, _cq.solids_of(value)).ir
    raise ValueError("the script declared something that is not a part, a circuit, a graph or a Workplane solid")


def run_module(source: str, path: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run a code part's source with these inputs; return ``{"graph", "params"}`` (JSON-ready)."""
    inputs = dict(inputs or {})
    params: Dict[str, Dict[str, Any]] = {}
    shown: List[Any] = []

    def param(name: str, default: Any, **meta: Any) -> Any:
        params[name] = {"default": default, **{k: v for k, v in meta.items() if v is not None}}
        return inputs.get(name, default)

    def show_object(obj: Any, *a: Any, **k: Any) -> None:
        shown.append(obj)

    ns: Dict[str, Any] = {"__name__": "__code_part__", "__file__": path, "param": param, "show_object": show_object, "inputs": inputs}
    with _source.running(source, path) as run:
        exec(compile(source, path, "exec"), ns)
    declared = ns.get("params")
    if isinstance(declared, dict):
        for k, v in declared.items():
            params.setdefault(k, v if isinstance(v, dict) and "default" in v else {"default": v})
    stem = path.split("/")[-1].rsplit(".", 1)[0].replace(".part", "").replace(".circuit", "").replace(".sch", "").replace(".sheet", "").replace(".page", "").replace(".deck", "") or "Part"
    if callable(ns.get("main")):
        values = {k: p["default"] for k, p in params.items()}
        values.update(inputs)
        with run:
            value = ns["main"](**values)
    elif shown:
        value = shown if len(shown) > 1 else shown[0]
    elif "result" in ns:
        value = ns["result"]
    elif len(run.declared) == 1:
        value = run.declared[0]
    elif run.declared:
        raise ValueError(f"the script declared {len(run.declared)} blocks; a file declares one")
    else:
        raise ValueError("the script declared nothing (define main(), call show_object(), set result, or write a with group(...) block)")
    # A workbook or a page is a document of its own (office.py): it leaves beside an empty graph.
    if isinstance(value, OfficeDocument):
        return json.loads(json.dumps({"graph": {"id": stem, "nodes": {}}, "params": params, "document": value.declared()}))
    g = graph_of(value, stem)
    _source.finish(g, run.map)
    problems = check_ir(g)
    if problems:
        raise ValueError("the declared graph is not well formed: " + "; ".join(problems[:5]))
    return json.loads(json.dumps({"graph": g, "params": params}))
