"""Graphs of any domain: ``graph``, ``node``, ``input_``, ``code`` — as in the TypeScript SDK."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from .ir import Declaration, NodeRef, Scope, current_scope, using

INPUT_OP = "input"
CODE_OP = "code"


def graph(name: str, fn: Callable[[], Union[NodeRef, List[NodeRef], None]], id: Optional[str] = None,
          domain: Optional[str] = None) -> Declaration:
    meta: Dict[str, Any] = {"name": name}
    if domain:
        meta["domain"] = domain
    s = Scope(id or name, meta)
    with using(s):
        result = fn()
    if result is not None:
        s.output(*(result if isinstance(result, list) else [result]))
    return Declaration("graph", s.build())


def node(type: str, inputs: Optional[Dict[str, Any]] = None, id: Optional[str] = None, label: Optional[str] = None) -> NodeRef:
    return current_scope(f'node("{type}")').add(type, inputs or {}, id=id, label=label)


def input_(name: str, value: Any, unit: Optional[str] = None, min: Optional[float] = None, max: Optional[float] = None,
           step: Optional[float] = None, comment: Optional[str] = None) -> NodeRef:
    """One of the graph's own inputs (the built-in ``input`` op): its id is its name."""
    inputs: Dict[str, Any] = {"value": value}
    for k, v in (("unit", unit), ("min", min), ("max", max), ("step", step), ("comment", comment)):
        if v is not None:
            inputs[k] = v
    return current_scope("input_()").add(INPUT_OP, inputs, id=name, label=name)


def code(source: str, inputs: Optional[Dict[str, Any]] = None, label: Optional[str] = None) -> NodeRef:
    """A node that runs another code file (relative to this one) with these inputs."""
    return current_scope("code()").add(CODE_OP, {"source": source, **(inputs or {})}, label=label or source.split("/")[-1])
