"""``commandagi.design`` — compositional primitives that DECLARE structure as the CommandAGI op graph.

The same primitives as the TypeScript SDK's ``commandagi/design``: CAD (``part``, ``sketch``, features),
EDA (``circuit``, ``component``, ``net``, ``board``), any graph (``graph``, ``node``, ``input_``, ``code``),
and a CadQuery-style importer (``commandagi.design.cadquery``). Structure only — no kernel, solver, router
or renderer. A ``.py`` file using these is a CODE PART: a graph's code node runs it (in the browser, under
Pyodide, with no network) and the editor evaluates what it declares.

A code part is a script. Its result is, first found: ``main(**inputs)`` if it defines ``main``; else what
it passed to ``show_object``; else its ``result`` variable. A result that is the root element of a document
(``group(...)`` of ``commandagi.design.schematic``, ``drawing(...)`` of ``commandagi.design.twod`` …) declares that
document. Each element carries the call that made it, and each node or record it declares carries where the call is
(``meta.source``, ``sources``; ``./source.py``). ``param(name, default, unit=…)`` reads an input
(declaring it); a ``params`` dict declares inputs too.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .ir import Declaration, NodeRef, Out, Scope, channels, check_ir, is_ir_graph
from .graph import CODE_OP, INPUT_OP, code, graph, input_, node
from .cad import (PLANES, Body, SketchBuilder, SketchRef, assembly, box, chamfer, circular_pattern, cone, copy, cylinder,
                  extrude, fillet, hole, instance, intersect, linear_pattern, mirror, part, revolve, sketch, sphere,
                  subtract, union)
from .eda import PartRef, board, circuit, component, connect, footprints, net, part_type_for
from . import cadquery as _cq
from .solids import declare_solids
from . import source as _source
from .element import Element, declarer_of
# The document vocabularies, one module each (``from commandagi.design.twod import drawing, rect``). Importing them
# registers what each root element declares.
from . import business, fab, media, office, ontology, pcb, records, schematic, tasks, threed, twod  # noqa: F401

__all__ = [
    "Declaration", "NodeRef", "Out", "Scope", "channels", "check_ir", "is_ir_graph",
    "CODE_OP", "INPUT_OP", "code", "graph", "input_", "node",
    "PLANES", "Body", "SketchBuilder", "SketchRef", "assembly", "box", "chamfer", "circular_pattern", "cone", "copy",
    "cylinder", "extrude", "fillet", "hole", "instance", "intersect", "linear_pattern", "mirror", "part", "revolve",
    "sketch", "sphere", "subtract", "union",
    "PartRef", "board", "circuit", "component", "connect", "footprints", "net", "part_type_for",
    "Element", "graph_of", "run_module",
]


def graph_of(value: Any, name: str = "Part") -> Dict[str, Any]:
    """The op graph a declared value is: a declaration, a plain IR graph, or CadQuery-style workplanes."""
    if isinstance(value, Declaration):
        return value.ir
    if is_ir_graph(value):
        return value
    if isinstance(value, _cq.Workplane) or (isinstance(value, (list, tuple)) and value and all(isinstance(v, _cq.Workplane) for v in value)):
        return declare_solids(name, _cq.solids_of(value)).ir
    raise ValueError("the script declared something that is not a document, a part, a circuit, a graph or a Workplane solid")


def _stem(path: str) -> str:
    """The file's name without ``.py`` and a graph format's extension (``Poster.draw.py`` -> ``Poster``): the name the
    TypeScript sandbox gives the same file (``declare.ts``)."""
    name = path.split("/")[-1]
    return re.sub(r"\.(part|circuit|graph|sch|pcb|3d|draw|nest|paint|img|sheet|page|deck|vid|mus|company|rfc|case|opgraph|dashboard|geo)?\.?py$",
                  "", name, flags=re.IGNORECASE) or "Part"


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
    stem = _stem(path)
    if callable(ns.get("main")):
        values = {k: p["default"] for k, p in params.items()}
        values.update(inputs)
        with run:
            value = ns["main"](**values)
    elif shown:
        value = shown if len(shown) > 1 else shown[0]
    elif "result" in ns:
        value = ns["result"]
    else:
        raise ValueError("the script declared nothing (define main(), call show_object() or set result)")
    declare = declarer_of(value)
    if declare is None and isinstance(value, Element):
        raise ValueError(f"<{value.tag}> is not the root of a document (commandagi.design.{value.module})")
    with run:
        declared = declare(value, stem) if declare else {"graph": graph_of(value, stem)}
    # A document that is not a graph (a workbook, a world, a company …) leaves beside an empty graph.
    document = declared.get("document")
    g = declared["graph"] if document is None else {"id": stem, "nodes": {}}
    g = json.loads(json.dumps(g))
    document = json.loads(json.dumps(document)) if document is not None else None
    _source.finish(g, run.map, document)
    problems = check_ir(g)
    if problems:
        raise ValueError("the declared graph is not well formed: " + "; ".join(problems[:5]))
    out: Dict[str, Any] = {"graph": g, "params": params}
    if document is not None:
        out["document"] = document
    return json.loads(json.dumps(out))
