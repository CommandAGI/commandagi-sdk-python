"""THE CHECKS A CIRCUIT DECLARES: ``check(...)`` and ``accept(...)`` in a ``.sch.py`` or a ``.pcb.py`` (the TypeScript
SDK's ``design/circuit-checks.ts``, element for element):

    check(id="erc", kind="erc")                                  the electrical rule check (a schematic, a board)
    check(id="drc", kind="drc", severity="warning")              the design rule check (a board); its errors as warnings
    check(id="pinout", kind="pinout")                            every part's pinout checked against its datasheet or
                                                                 measured (its pinout_verified, ``part_fields.py``)
    check(id="footprint", kind="footprint")                      every part's pads checked, and its footprint's pad
                                                                 count, pitch and body equal to its package_dimensions
    check(id="cost", kind="cost", options={"quantities": [10, 100]})
                                                                 a logistics check (sourcing, process, assembly,
                                                                 inspection, compliance, shipping, lifecycle, cost:
                                                                 docs/formats.md § logistics), with its own options
    accept(id="lbl", check="sourcing", rule="no-supplier", refs=["J9"], reason="…")   a logistics finding of one part
    accept(id="tx", check="erc", rule="pin_conflict", refs=["U1", "U3"], reason="the bus is open-drain")
    accept(id="edge", check="drc", rule="clearance", region={"min": [0, 0], "max": [3, 3]}, reason="…")

They are no node of the circuit: the reader keeps them in the graph's ``meta`` (``checks``, ``accepted``).
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

from .element import Element
from .ir import Scope

CIRCUIT_CHECK_TAGS = {"check", "accept"}
_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _where(el: Element) -> str:
    return f'<{el.tag} id="{el.props["id"]}">' if isinstance(el.props.get("id"), str) else f"<{el.tag}>"


def _text(el: Element, prop: str, what: str, required: bool = True) -> Optional[str]:
    v = el.props.get(prop)
    if v is None and not required:
        return None
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{_where(el)}: {prop} is {what}")
    return v


def _only(el: Element, allowed: List[str]) -> None:
    for k in el.props:
        if k not in allowed:
            raise ValueError(f"{_where(el)}: prop {k} is not read (it takes {', '.join(allowed)})")


def _point(v: Any) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in v)


def declare_circuit_checks(s: Scope, elements: List[Element]) -> List[Element]:
    """Read the circuit's check and accept elements into its scope's meta; the other elements are returned."""
    checks: List[Dict[str, Any]] = list(s.meta.get("checks") or [])
    accepted: List[Dict[str, Any]] = list(s.meta.get("accepted") or [])
    rest: List[Element] = []
    for el in elements:
        at = {} if el.source is None else {"source": el.source}
        if el.tag == "check":
            _only(el, ["id", "kind", "severity", "options"])
            id_ = _text(el, "id", "the check's name (erc)")
            if not _ID.match(id_):
                raise ValueError(f"{_where(el)}: id is letters, digits, _ . -")
            if any(c["id"] == id_ for c in checks + accepted):
                raise ValueError(f"two checks or accepts are called {id_}")
            kind = _text(el, "kind", "what is checked: erc, drc, pinout, footprint, or a logistics kind (sourcing, process, assembly, inspection, compliance, shipping, lifecycle, cost)")
            severity = el.props.get("severity")
            if severity is not None and severity not in ("error", "warning"):
                raise ValueError(f"{_where(el)}: severity is error or warning")
            options = el.props.get("options")
            if options is not None and not isinstance(options, dict):
                raise ValueError(f"{_where(el)}: options is an object (the cost check's {{ quantities: [10, 100] }})")
            checks.append({"id": id_, "kind": kind, **({"severity": severity} if severity else {}),
                           **({"options": copy.deepcopy(options)} if options is not None else {}), **at})
        elif el.tag == "accept":
            _only(el, ["id", "check", "rule", "refs", "net", "region", "reason"])
            id_ = _text(el, "id", "the accept's name")
            if not _ID.match(id_):
                raise ValueError(f"{_where(el)}: id is letters, digits, _ . -")
            if any(c["id"] == id_ for c in checks + accepted):
                raise ValueError(f"two checks or accepts are called {id_}")
            refs = el.props.get("refs")
            if refs is not None and not (isinstance(refs, (list, tuple)) and refs and all(isinstance(r, str) and r for r in refs)):
                raise ValueError(f'{_where(el)}: refs is a list of part references (["U1", "U3"])')
            region = el.props.get("region")
            if region is not None and not (isinstance(region, dict) and _point(region.get("min")) and _point(region.get("max"))):
                raise ValueError(f"{_where(el)}: region is {{ min: [x, y], max: [x, y] }} in board millimetres")
            net = _text(el, "net", "a net's name", required=False)
            accepted.append({
                "id": id_, "check": _text(el, "check", "the id of the check whose finding it accepts"),
                "rule": _text(el, "rule", "the rule of the finding it accepts (pin_conflict, clearance)"),
                **({"refs": list(refs)} if refs else {}), **({"net": net} if net else {}),
                **({"region": {"min": list(region["min"]), "max": list(region["max"])}} if region else {}),
                "reason": _text(el, "reason", "why the finding is right on purpose"), **at,
            })
        else:
            rest.append(el)
    if checks:
        s.meta["checks"] = checks
    if accepted:
        s.meta["accepted"] = accepted
    return rest
