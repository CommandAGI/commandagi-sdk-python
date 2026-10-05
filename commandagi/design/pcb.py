"""A BOARD IN CODE — the board half of a circuit, declared as the same nodes the TypeScript SDK's ``pcb.ts`` declares
from JSX: ``eda.board`` and ``eda.stack`` (the outline and cross-section), one ``eda.footprint`` per component (its
footprint and where it sits), and ``eda.conductor`` copper whose ends say what they land on. The board names its
schematic by relative path; the schematic says what the parts are and what is connected.

    from commandagi.design import pcb_board, pcb_component, pcb_trace, pcb_via

    result = pcb_board(
        "Divider.sch.tsx", width=40, height=30, core=1.5, copper=0.035,
        children=[
            pcb_component("R1", "smd-0805", x=10, y=10),
            pcb_component("R2", "smd-0805", x=25, y=10, rotation=90, layer="bottom"),
            pcb_trace("F.Cu", 0.25, [(11, 10), (24, 10)], from_=".R1 > .pin2", to=".R2 > .pin1"),
            pcb_via(18, 14, drill=0.4, diameter=0.8, name="VIA1"),
        ],
    )

Coordinates are the board's own: millimetres, Y down, from the outline's corner. A trace's end is ".R1 > .pin2" (a pin
of a component, by number), ".VIA1" (a via, by name) or ".T1 > .end" (a point of another trace: start, end or its
index). Anything else is refused by name.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .ir import Declaration, Out, Scope, slug, using

BOARD_PART = "eda.footprint"
CONDUCTOR = "eda.conductor"
BOARD_FOOTPRINTS = ("smd-0805", "axial-7.62", "header-2.54")
_LAYERS = [{"ordinal": 0, "name": "F.Cu", "type": "signal"}, {"ordinal": 31, "name": "B.Cu", "type": "signal"},
           {"ordinal": 36, "name": "B.SilkS", "type": "user"}, {"ordinal": 37, "name": "F.SilkS", "type": "user"},
           {"ordinal": 44, "name": "Edge.Cuts", "type": "user"}]
_COPPER = ("F.Cu", "B.Cu")


def pcb_component(name: str, footprint: str, x: Optional[float] = None, y: Optional[float] = None,
                  rotation: Optional[float] = None, layer: Optional[str] = None, library: Optional[str] = None) -> Dict[str, Any]:
    """The schematic's part ``name`` on the board (the ``<component>`` element). ``footprint`` is one of the editor's
    land patterns, or a library footprint by its ref ("Package_SO:SOIC-8") in the ``.pretty`` folder ``library``."""
    return {"tag": "component", "name": name, "footprint": footprint, "x": x, "y": y, "rotation": rotation, "layer": layer, "library": library}


def pcb_trace(layer: str, width: float, points: Sequence[Tuple[float, float]], from_: Optional[str] = None,
              to: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
    """A copper run (the ``<trace>`` element)."""
    return {"tag": "trace", "layer": layer, "width": width, "points": [list(p) for p in points], "from": from_, "to": to, "name": name}


def pcb_via(x: float, y: float, drill: float, diameter: float, layers: Sequence[str] = ("F.Cu", "B.Cu"), name: Optional[str] = None) -> Dict[str, Any]:
    """A plated barrel (the ``<via>`` element)."""
    return {"tag": "via", "x": x, "y": y, "drill": drill, "diameter": diameter, "layers": list(layers), "name": name}


def trace_point_id(index: int, count: int) -> str:
    return "start" if index == 0 else "end" if index == count - 1 else f"p{index}"


def _where(e: Dict[str, Any]) -> str:
    return f"<{e['tag']}" + (f' name="{e["name"]}"' if e.get("name") else "") + ">"


def _positive(e: Dict[str, Any], key: str, value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not value > 0:
        raise ValueError(f"{_where(e)}: {key} is a number more than 0, not {value!r}")
    return value


def pcb_board(schematic: str, width: Optional[float] = None, height: Optional[float] = None, core: Optional[float] = None,
              copper: Optional[float] = None, children: Sequence[Dict[str, Any]] = (), name: Optional[str] = None) -> Declaration:
    """Declare a board in code (the ``<board schematic=…>`` root)."""
    if not isinstance(schematic, str) or not schematic.strip() or schematic.startswith("/"):
        raise ValueError("<board>: schematic is the schematic file's path, relative to this file")
    title = name or "Board"
    root = {"tag": "board"}
    if (width is None) != (height is None):
        raise ValueError("<board>: give width and height together")
    if (core is None) != (copper is None):
        raise ValueError("<board>: give core and copper together")
    if core is not None and width is None:
        raise ValueError("<board>: core and copper need the outline (width and height)")
    s = Scope(f"eda:{slug(title)}", {"domain": "eda", "rung": "board", "name": title, "schematic": schematic})
    with using(s):
        if width is not None and height is not None:
            board_inputs: Dict[str, Any] = {"layers": _LAYERS}
            if core is not None and copper is not None:
                _positive(root, "core", core), _positive(root, "copper", copper)
                s.add("eda.stack", {"id": "stack", "domain": "pcb", "units": "mm", "layers": [
                    {"name": "F.Cu", "role": "conductor", "thickness": copper},
                    {"name": "core", "role": "dielectric", "thickness": core},
                    {"name": "B.Cu", "role": "conductor", "thickness": copper}]}, id="stack", label="Cross-section")
                board_inputs["thicknessMm"] = core + 2 * copper
                board_inputs["stack"] = Out("stack", "stack")
            board_inputs["boardArtwork"] = {"graphics": [{"id": "outline", "kind": "rect", "points": [{"x": 0, "y": 0}, {"x": _positive(root, "width", width), "y": _positive(root, "height", height)}],
                                                          "widthMm": 0.05, "layer": "Edge.Cuts", "filled": False}], "texts": []}
            s.add("eda.board", board_inputs, id="board", label="Board")
            s.output("board")

        components: set = set()
        conductors: Dict[str, Dict[str, Any]] = {}
        for e in children:
            nm = e.get("name")
            if e.get("tag") == "component":
                if not nm:
                    raise ValueError("<component> needs the name of the schematic's part")
                if nm in components or nm in conductors:
                    raise ValueError(f"two elements are called {nm}")
                components.add(nm)
            elif e.get("tag") in ("trace", "via"):
                if nm is None:
                    continue
                if not re.fullmatch(r"[A-Za-z0-9_\-]+", str(nm)):
                    raise ValueError(f"{_where(e)}: a name is letters, digits, _ and -")
                if nm in components or nm in conductors:
                    raise ValueError(f"two elements are called {nm}")
                conductors[nm] = e
            else:
                raise ValueError(f"<{e.get('tag')}> is not read on a board (see commandagi.design pcb)")
        ids: Dict[int, str] = {id(e): nm for nm, e in conductors.items()}
        n = 0
        for e in children:
            if e["tag"] in ("trace", "via") and id(e) not in ids:
                while True:
                    n += 1
                    cand = f"cu_{n}"
                    if cand not in conductors and cand not in components:
                        break
                ids[id(e)] = cand

        def end(sel: Any, e: Dict[str, Any], point: int) -> Dict[str, Any]:
            if not isinstance(sel, str):
                raise ValueError(f'{_where(e)}: an end is a selector (".R1 > .pin2", ".V1", ".T1 > .end")')
            one = re.fullmatch(r"\s*\.([A-Za-z0-9_#\-]+)\s*", sel)
            if one:
                target = conductors.get(one.group(1))
                if not target or target["tag"] != "via":
                    raise ValueError(f"{_where(e)}: there is no via {one.group(1)}")
                return {"point": point, "via": one.group(1)}
            two = re.fullmatch(r"\s*\.([A-Za-z0-9_#\-]+)\s*>\s*\.([A-Za-z0-9_+\-]+)\s*", sel)
            if not two:
                raise ValueError(f'{_where(e)}: {sel!r} is not ".REF > .pin1", ".VIA" or ".TRACE > .end"')
            owner, which = two.group(1), two.group(2)
            if owner in components:
                m = re.fullmatch(r"pin(.+)", which, re.I)
                return {"point": point, "ref": owner, "number": m.group(1) if m else which}
            run = conductors.get(owner)
            if not run or run["tag"] != "trace":
                raise ValueError(f"{_where(e)}: there is no component or trace {owner}")
            count = len(run["points"])
            index = 0 if which == "start" else count - 1 if which == "end" else int(which) if which.isdigit() else -1
            if not 0 <= index < count:
                raise ValueError(f"{_where(e)}: trace {owner} has no point {which}")
            return {"point": point, "run": owner, "runPoint": trace_point_id(index, count)}

        for e in children:
            if e["tag"] == "component":
                fp = e["footprint"]
                library = e.get("library")
                if library is not None:
                    if not isinstance(library, str) or not re.search(r"\.pretty/?$", library, re.I):
                        raise ValueError(f"{_where(e)}: library names a footprint library folder (a .pretty), not {library!r}")
                    if not isinstance(fp, str) or not re.match(r"^[^:]+:[^:/]+$", fp):
                        raise ValueError(f'{_where(e)}: a library footprint is its ref, "Library:Footprint" ("Package_SO:SOIC-8"), not {fp!r}')
                elif fp not in BOARD_FOOTPRINTS:
                    raise ValueError(f"{_where(e)}: footprint is one of {', '.join(BOARD_FOOTPRINTS)}, or a library footprint with its library, not {fp!r}")
                x, y = e.get("x"), e.get("y")
                if (x is None) != (y is None):
                    raise ValueError(f"{_where(e)}: give pcbX and pcbY together")
                if x is None and (e.get("rotation") is not None or e.get("layer") is not None):
                    raise ValueError(f"{_where(e)}: pcbRotation and layer need pcbX and pcbY")
                side = e.get("layer") or "top"
                if side not in ("top", "bottom"):
                    raise ValueError(f'{_where(e)}: layer is "top" or "bottom"')
                inputs: Dict[str, Any] = {"ref": e["name"], **({"footprint": fp, "library": library.rstrip("/")} if library is not None else {"footprint": f"Authored:{fp}"})}
                if x is not None:
                    inputs["placement"] = {"x": x, "y": y, "rot": e.get("rotation") or 0, "side": side}
                s.add(BOARD_PART, inputs, id=f"fp_{e['name']}", label=e["name"])
            elif e["tag"] == "trace":
                pts = e["points"]
                if len(pts) < 2 or not all(len(p) == 2 for p in pts):
                    raise ValueError(f"{_where(e)}: points is a list of at least two [x, y]")
                if e["layer"] not in _COPPER:
                    raise ValueError(f'{_where(e)}: layer is a copper layer ("F.Cu" or "B.Cu")')
                terminals = ([end(e["from"], e, 0)] if e.get("from") is not None else []) + \
                            ([end(e["to"], e, len(pts) - 1)] if e.get("to") is not None else [])
                inputs = {"kind": "run", "points": [{"x": p[0], "y": p[1], "id": trace_point_id(i, len(pts))} for i, p in enumerate(pts)],
                          "widthMm": _positive(e, "width", e["width"]), "layer": e["layer"], "rule": "any"}
                if terminals:
                    inputs["terminals"] = terminals
                s.add(CONDUCTOR, inputs, id=ids[id(e)], label="Trace")
            else:
                if len(e["layers"]) < 2 or not all(l in _COPPER for l in e["layers"]):
                    raise ValueError(f"{_where(e)}: layers is two or more copper layers")
                drill, diameter = _positive(e, "drill", e["drill"]), _positive(e, "diameter", e["diameter"])
                if diameter <= drill:
                    raise ValueError(f"{_where(e)}: the diameter is more than the drill")
                s.add(CONDUCTOR, {"kind": "via", "points": [{"x": e["x"], "y": e["y"]}], "drillMm": drill, "padDiameterMm": diameter, "layers": e["layers"]},
                      id=ids[id(e)], label="Via")
    return Declaration("board", s.build())
