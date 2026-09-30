"""The op-graph IR every ``commandagi.design`` primitive produces: plain JSON, the op graph every CommandAGI
editor stores. The same declarations give the same JSON as the TypeScript SDK's ``commandagi/design``.

    {"id", "nodes": {<id>: {"id", "type", "label"?, "inputs", "meta"?}}, "outputs"?, "meta"?}

A node has one map of ports, ``inputs``: a literal, or one wire ``{"wire": {"node", "port"}}``. Structure
only: nothing here evaluates a graph (no kernel, no solver, no router, no renderer).
"""
from __future__ import annotations

import copy
import json
import math
import re
from typing import Any, Dict, List, Optional

_ID_SAFE = re.compile(r"[^A-Za-z0-9_.\-]+")


def slug(raw: str, fallback: str = "node") -> str:
    s = _ID_SAFE.sub("_", raw).strip("_")
    return s or fallback


class Out:
    """One output port of a declared node."""

    def __init__(self, node: str, port: str):
        self.node = node
        self.port = port

    def to_wire(self) -> Dict[str, Any]:
        return {"wire": {"node": self.node, "port": self.port}}


class NodeRef:
    """A declared node. Used as a port value, it wires that port to the node's ``out``."""

    def __init__(self, scope: "Scope", id: str):
        self.scope = scope
        self.id = id

    def out(self, port: str = "out") -> Out:
        return Out(self.id, port)

    @property
    def node(self) -> Dict[str, Any]:
        return self.scope.nodes[self.id]


def _check_literal(value: Any, where: str, depth: int = 0) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, (Out, NodeRef)):
        raise ValueError(f"{where}: a wire drives a whole port, not a field inside one")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{where}: {value} is not a finite number")
        return
    if depth > 64:
        raise ValueError(f"{where}: nested too deep")
    if isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _check_literal(v, f"{where}[{i}]", depth + 1)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{where}: keys are strings")
            _check_literal(v, f"{where}.{k}", depth + 1)
        return
    raise ValueError(f"{where}: a {type(value).__name__} is not plain data (ports hold JSON)")


def port_value(value: Any, where: str) -> Any:
    if isinstance(value, Out):
        return value.to_wire()
    if isinstance(value, NodeRef):
        return value.out().to_wire()
    _check_literal(value, where)
    return _plain(value)


def _plain(v: Any) -> Any:
    if isinstance(v, tuple):
        return [_plain(x) for x in v]
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def channels(set_id: str, values: List[Any]) -> Dict[str, Any]:
    """Numbered channels of one set: ``channels("layers", [a, b])`` -> ``{"layers.1": a, "layers.2": b}``."""
    return {f"{set_id}.{i + 1}": v for i, v in enumerate(values)}


class Scope:
    """One graph being declared. Ids are deterministic (from the label or type, numbered on collision)."""

    def __init__(self, id: str, meta: Optional[Dict[str, Any]] = None):
        self.id = id
        self.meta = dict(meta or {})
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.outputs: List[str] = []
        self._taken: set = set()
        self._next: Dict[str, int] = {}
        self.state: Dict[str, Any] = {}

    def unique_id(self, base: str) -> str:
        b = slug(base)
        i, n = b, self._next.get(b, 2)
        while i in self._taken:
            i = f"{b}_{n}"
            n += 1
        self._next[b] = n
        self._taken.add(i)
        return i

    def add(self, type: str, inputs: Optional[Dict[str, Any]] = None, id: Optional[str] = None,
            label: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> NodeRef:
        if id is not None:
            nid = slug(id)
            if nid in self._taken:
                raise ValueError(f"{self.id}: two nodes are called {nid}")
            self._taken.add(nid)
        else:
            nid = self.unique_id(label if label is not None else type)
        stored = {}
        for port, v in (inputs or {}).items():
            stored[port] = port_value(v, f"{nid}.{port}")
        node: Dict[str, Any] = {"id": nid, "type": type, "inputs": stored}
        if label is not None:
            node["label"] = label
        if meta:
            node["meta"] = dict(meta)
        self.nodes[nid] = node
        return NodeRef(self, nid)

    def output(self, *refs: Any) -> None:
        for r in refs:
            i = r if isinstance(r, str) else r.id
            if i not in self.outputs:
                self.outputs.append(i)

    def sinks(self) -> List[str]:
        used = set()
        for n in self.nodes.values():
            for v in n["inputs"].values():
                if isinstance(v, dict) and "wire" in v:
                    used.add(v["wire"]["node"])
        return [i for i in self.nodes if i not in used]

    def build(self) -> Dict[str, Any]:
        outputs = list(self.outputs) or self.sinks()
        g: Dict[str, Any] = {"id": self.id, "nodes": self.nodes}
        if outputs:
            g["outputs"] = outputs
        g["meta"] = self.meta
        return json.loads(json.dumps(g))


_stack: List[Scope] = []


def current_scope(what: str = "this primitive") -> Scope:
    if not _stack:
        raise RuntimeError(f"{what} declares structure and must be called inside part(), circuit() or graph() (commandagi.design)")
    return _stack[-1]


class _Using:
    def __init__(self, scope: Scope):
        self.scope = scope

    def __enter__(self) -> Scope:
        _stack.append(self.scope)
        return self.scope

    def __exit__(self, *exc: Any) -> None:
        _stack.pop()


def using(scope: Scope) -> _Using:
    return _Using(scope)


class Declaration:
    """A finished declaration: its op graph, and what kind of thing it declares."""

    def __init__(self, kind: str, ir: Dict[str, Any]):
        self.kind = kind
        self.ir = ir

    def to_json(self) -> Dict[str, Any]:
        return copy.deepcopy(self.ir)


def is_ir_graph(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not isinstance(value.get("nodes"), dict):
        return False
    return all(isinstance(n, dict) and n.get("id") == k and isinstance(n.get("type"), str) and isinstance(n.get("inputs"), dict)
               for k, n in value["nodes"].items())


def check_ir(g: Dict[str, Any]) -> List[str]:
    if not is_ir_graph(g):
        return ["not an op graph ({id, nodes: {<id>: {id, type, inputs}}})"]
    out = []
    for n in g["nodes"].values():
        for port, v in n["inputs"].items():
            if isinstance(v, dict) and "wire" in v:
                w = v["wire"]
                if not isinstance(w, dict) or not isinstance(w.get("node"), str) or not isinstance(w.get("port"), str):
                    out.append(f"{n['id']}.{port}: a wire names {{node, port}}")
                elif w["node"] not in g["nodes"]:
                    out.append(f"{n['id']}.{port}: wired from {w['node']}, which is not declared")
    for o in g.get("outputs") or []:
        if o not in g["nodes"]:
            out.append(f"output {o} is not declared")
    return out
