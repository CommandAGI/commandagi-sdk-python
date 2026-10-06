"""A BOARD IN PYTHON — the board half of a circuit, declared as the nodes the CommandAGI circuit editor's board holds
(``eda.board``, ``eda.stack``, ``eda.conductor``) plus, for each part, the board facts that sit on the schematic's part
(``eda.footprint``: which footprint, where it sits). The same elements, node for node, as the TypeScript SDK's JSX
board (``commandagi/design`` ``pcb.ts``). A board names its schematic; the schematic says what the parts are and what
is connected, the board says where they sit and where the copper runs:

    from commandagi.design.pcb import board, component, trace, via

    result = board(
        component(name="R1", footprint="smd-0805", pcb_x=10, pcb_y=10),
        component(name="R2", footprint="smd-0805", pcb_x=25, pcb_y=10, pcb_rotation=90, layer="bottom"),
        trace(layer="F.Cu", width=0.2, points=[[11, 10], [24, 10]], from_=".R1 > .pin2", to=".R2 > .pin1"),
        via(name="V1", pcb_x=18, pcb_y=14, drill=0.4, diameter=0.8),
        schematic="Divider.sch.py", width=40, height=30, core=1.5, copper=0.035,
    )

The calls (children are positional; every attribute is a keyword):
    board(*elements, schematic, width, height, core, copper, thickness, layers, surface)
                                      the root. ``schematic`` is the schematic file, relative to this one. A width x
                                      height rectangle outline from (0, 0); core and copper make a two-layer
                                      cross-section (mm); thickness is the finished thickness when no cross-section
                                      says it; layers is the layer table ([{ordinal, name, type, userName}], the
                                      editor's blank board's when absent). ``surface`` puts the board on the faces of
                                      a CAD part: {cadRef, domain, trims, curvedTrims}.
    stack(name, label, domain, units, process, layers, overall_thickness)
                                      the cross-section, layer by layer (top first), when it is more than core and
                                      copper.
    graphic(kind, layer, points, width, filled, id, kicad)
                                      a board drawing (line, arc, circle, rect, poly) on a layer.
    text(text|field, at, rotation, layer, size, size_x, thickness, kind, id, kicad)
    dimension(points, height, layer, width, text_size, id, kicad)
                                      board text, and an aligned dimension (its text is derived, never stored).
    kicad(version, generator, forms)  the KiCad forms the board carries for exchange and nothing else reads.
    net(name, code)                   the KiCad net code of the schematic's net ``name``.
    component(name, footprint, library, pcb_x, pcb_y, pcb_rotation, layer, chart, uuid, kicad)
                                      the schematic's part ``name`` on this board: one of the editor's own land
                                      patterns (BOARD_FOOTPRINTS), or a library footprint by its ref
                                      ("Package_SO:SOIC-8") in the ``.pretty`` folder ``library`` names.
    trace(name, layer, width, points, from_, to, net, surface, uuid, segment_uuids, kicad)
                                      a copper run: its points ([[x, y], …]) on one copper layer, a finished width.
    arc(name, layer, width, points, from_, to, net, uuid, kicad)
                                      a circular copper arc: start, a point on it, end.
    via(name, pcb_x, pcb_y, drill, diameter, layers, pads, net, uuid, kicad)
                                      a plated barrel; ``layers`` defaults to ["F.Cu", "B.Cu"].
    pour(name, layers, points, terminals, net, uuid, kicad)
                                      a copper pour: its boundary on its layers.

Coordinates are the board's own: millimetres, Y DOWN, from the outline's corner. An end is bound by what it says,
never by where it is drawn: ".R1 > .pin2" (a pin of a component, by its number), ".V1" (a via, by name), ".T1 > .end"
(a point of another trace or arc: .start, .end or its index). Anything else is refused by name, never guessed. Each
node an element declares carries the element's call in ``meta.source``.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional

from .element import Element, child_elements, declares, define
from .ir import Declaration, Scope, slug, using

BOARD_PART = "eda.footprint"
CONDUCTOR = "eda.conductor"
#: A board fact a ``graphic``, ``text``, ``dimension``, ``kicad`` or ``net`` declares; the editor folds it into the circuit.
BOARD_FACT = "eda.boardfact"
#: The editor's own land patterns, by the name a ``component(footprint=…)`` gives (the circuit's id is ``Authored:<name>``).
BOARD_FOOTPRINTS = ("smd-0805", "axial-7.62", "header-2.54")
#: A new board's layer table (the circuit editor's blank board).
BOARD_LAYERS = [
    {"ordinal": 0, "name": "F.Cu", "type": "signal"},
    {"ordinal": 31, "name": "B.Cu", "type": "signal"},
    {"ordinal": 36, "name": "B.SilkS", "type": "user"},
    {"ordinal": 37, "name": "F.SilkS", "type": "user"},
    {"ordinal": 44, "name": "Edge.Cuts", "type": "user"},
]
_COPPER = re.compile(r"^[A-Za-z0-9]+\.Cu$")
_GRAPHICS: Dict[str, Optional[int]] = {"line": 2, "arc": 3, "circle": 2, "rect": 2, "poly": None}

_CHILDREN: Dict[str, Any] = {"holds": "children"}
#: Every tag of the board: what it holds (the TypeScript SDK's ``SIGNATURES``; absent: a leaf).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "board": _CHILDREN,
    "stack": {}, "graphic": {}, "text": {}, "dimension": {}, "kicad": {}, "net": {},
    "component": {}, "trace": {}, "arc": {}, "via": {}, "pour": {},
}

__all__ = ["BOARD_PART", "CONDUCTOR", "BOARD_FACT", "BOARD_FOOTPRINTS", "BOARD_LAYERS", "SIGNATURES", "trace_point_id",
           "declare_board_file", *define(globals(), "pcb", SIGNATURES)]


def _meta(el: Element) -> Optional[Dict[str, Any]]:
    return None if el.source is None else {"source": el.source}


def _where(el: Element) -> str:
    name = el.props.get("name")
    return f'<{el.tag} name="{name}">' if isinstance(name, str) else f"<{el.tag}>"


def _refuse_unknown(el: Element, allowed: List[str]) -> None:
    for k in el.props:
        if k == "key" or k in allowed:
            continue
        if k in ("schX", "schY", "schRotation", "resistance", "capacitance", "inductance", "voltage", "current"):
            raise ValueError(f"{_where(el)}: {k} is the schematic's; a board says only where its parts sit and where its copper runs")
        raise ValueError(f"{_where(el)}: prop {k} is not read on a board")


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _num(el: Element, prop: str, required: bool = False) -> Optional[float]:
    v = el.props.get(prop)
    if v is None:
        if required:
            raise ValueError(f"{_where(el)} needs {prop}")
        return None
    if _is_num(v):
        return v
    raise ValueError(f"{_where(el)}: {prop} is a number (mm or degrees), not {json.dumps(v)}")


def _positive(el: Element, prop: str, required: bool = False) -> Optional[float]:
    v = _num(el, prop, required)
    if v is not None and not v > 0:
        raise ValueError(f"{_where(el)}: {prop} is more than 0")
    return v


def _text(el: Element, prop: str, required: bool = False) -> Optional[str]:
    v = el.props.get(prop)
    if v is None:
        if required:
            raise ValueError(f"{_where(el)} needs {prop}")
        return None
    if isinstance(v, str):
        return v
    raise ValueError(f"{_where(el)}: {prop} is text, not {json.dumps(v)}")


def _point_list(el: Element, prop: str, least: int, count: Optional[int] = None) -> List[Dict[str, Any]]:
    v = el.props.get(prop)
    if not isinstance(v, (list, tuple)) or len(v) < least or (count is not None and len(v) != count):
        raise ValueError(f"{_where(el)}: {prop} is a list of {count if count is not None else f'at least {least}'} [x, y]")
    out = []
    for i, p in enumerate(v):
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_is_num(c) for c in p):
            raise ValueError(f"{_where(el)}: point {i} is [x, y] in mm, not {json.dumps(p)}")
        out.append({"x": p[0], "y": p[1]})
    return out


def _at(el: Element, prop: str) -> Dict[str, Any]:
    v = el.props.get(prop)
    if not isinstance(v, (list, tuple)) or len(v) != 2 or not all(_is_num(c) for c in v):
        raise ValueError(f"{_where(el)}: {prop} is [x, y] in mm, not {json.dumps(v)}")
    return {"x": v[0], "y": v[1]}


def _copper_layers(el: Element, fallback: Optional[List[str]] = None) -> List[str]:
    layers = el.props.get("layers")
    if layers is None:
        layers = fallback
    if not isinstance(layers, (list, tuple)) or len(layers) < 1 or not all(isinstance(l, str) and _COPPER.match(l) for l in layers):
        raise ValueError(f'{_where(el)}: layers is a list of copper layers ("F.Cu", "In1.Cu", "B.Cu")')
    return list(layers)


def _kicad(el: Element, prop: str = "kicad") -> Dict[str, Any]:
    """Carried KiCad forms, as s-expression text (``kicad="(stroke (type solid))"``)."""
    v = _text(el, prop)
    return {} if v is None else {"kicad": v}


def _plain(el: Element, prop: str, check: Any, what: str) -> Any:
    """Plain data: numbers, strings, booleans, None, lists and dicts of them."""
    v = el.props.get(prop)
    if v is None:
        return None
    if not check(v):
        raise ValueError(f"{_where(el)}: {prop} is {what}")
    return json.loads(json.dumps(v))


def _is_object(v: Any) -> bool:
    return isinstance(v, dict)


def trace_point_id(index: int, count: int) -> str:
    """A trace point's id: the editor's own (``start``, ``end``, and ``p<i>`` between them)."""
    return "start" if index == 0 else "end" if index == count - 1 else f"p{index}"


_CONDUCTORS = {"trace", "arc", "via", "pour"}
_FACTS = {"graphic", "text", "dimension", "kicad", "net"}
_PIN = re.compile(r"^\s*\.([A-Za-z0-9_#\-]+)\s*>\s*\.([A-Za-z0-9_+\-]+)\s*$")


def declare_board_file(root: Element, name: Optional[str] = None) -> Declaration:
    """Declare a board in code (its root is ``board(…, schematic="…")``)."""
    _refuse_unknown(root, ["schematic", "name", "width", "height", "core", "copper", "thickness", "layers", "surface"])
    schematic = root.props.get("schematic")
    if not isinstance(schematic, str) or not schematic.strip() or schematic.startswith("/"):
        raise ValueError("<board>: schematic is the schematic file's path, relative to this file")
    title = root.props["name"] if isinstance(root.props.get("name"), str) else (name if name is not None else "Board")
    s = Scope(f"eda:{slug(title)}", {"domain": "eda", "rung": "board", "name": title, "schematic": schematic})
    with using(s):
        _declare_board(s, root)
    return Declaration("board", s.build())


def _declare_board(s: Scope, root: Element) -> None:
    children = child_elements(root)
    w, h = _positive(root, "width"), _positive(root, "height")
    core, copper, thickness = _positive(root, "core"), _positive(root, "copper"), _positive(root, "thickness")
    layers = _plain(root, "layers",
                    lambda v: isinstance(v, (list, tuple)) and len(v) > 0 and all(
                        _is_object(l) and isinstance(l.get("name"), str) and _is_num(l.get("ordinal")) for l in v),
                    "the layer table: [{ ordinal, name, type, userName }, …]")
    if (w is None) != (h is None):
        raise ValueError("<board>: give width and height together")
    if (core is None) != (copper is None):
        raise ValueError("<board>: give core and copper together")
    stacks = [el for el in children if el.tag == "stack"]
    if len(stacks) > 1:
        raise ValueError("a board has one <stack>")
    if stacks and core is not None:
        raise ValueError("<board>: core and copper are a two-layer <stack>; give one or the other")
    if thickness is not None and core is not None:
        raise ValueError("<board>: core and copper say the thickness")
    if core is not None and w is None:
        raise ValueError("<board>: core and copper need the outline (width and height)")
    surface = _plain(root, "surface",
                     lambda v: _is_object(v) and isinstance(v.get("cadRef"), str) and _is_object(v.get("domain"))
                     and all(k in ("cadRef", "domain", "trims", "curvedTrims") for k in v),
                     "the CAD faces the board is on: { cadRef, domain, trims, curvedTrims }")
    has_board = (w is not None or thickness is not None or layers is not None or surface is not None or bool(stacks)
                 or any(el.tag in ("graphic", "text", "dimension", "kicad") for el in children))

    stack_thickness: Optional[float] = None
    if core is not None and copper is not None:
        stack_thickness = core + 2 * copper
        s.add("eda.stack", {"id": "stack", "domain": "pcb", "units": "mm", "layers": [
            {"name": "F.Cu", "role": "conductor", "thickness": copper},
            {"name": "core", "role": "dielectric", "thickness": core},
            {"name": "B.Cu", "role": "conductor", "thickness": copper},
        ]}, id="stack", label="Cross-section", meta=_meta(root))
    for el in stacks:
        _refuse_unknown(el, ["name", "label", "domain", "units", "process", "layers", "overallThickness"])
        stack_layers = _plain(el, "layers", lambda v: isinstance(v, (list, tuple)) and all(
            _is_object(l) and isinstance(l.get("name"), str) and isinstance(l.get("role"), str) for l in v),
            "the layers, top first: [{ name, role, thickness, … }, …]")
        if stack_layers is None:
            raise ValueError("<stack> needs layers")
        domain = _text(el, "domain") or "pcb"
        units = _text(el, "units") or "mm"
        if domain not in ("pcb", "ic"):
            raise ValueError('<stack>: domain is "pcb" or "ic"')
        if units not in ("mm", "um", "nm"):
            raise ValueError('<stack>: units is "mm", "um" or "nm"')
        process = _plain(el, "process", _is_object, "an object ({ name, … })")
        inputs: Dict[str, Any] = {"id": _text(el, "name") or "stack", "domain": domain, "units": units, "layers": stack_layers}
        if process is not None:
            inputs["process"] = process
        if el.props.get("overallThickness") is not None:
            inputs["overallThickness"] = _positive(el, "overallThickness")
        label = _text(el, "label")
        s.add("eda.stack", inputs, id="stack", label=label if label is not None else "Cross-section", meta=_meta(el))
    if has_board:
        inputs = {"layers": layers if layers is not None else BOARD_LAYERS}
        if stack_thickness is not None:
            inputs["thicknessMm"] = stack_thickness
        elif thickness is not None:
            inputs["thicknessMm"] = thickness
        if core is not None or stacks:
            inputs["stack"] = {"wire": {"node": "stack", "port": "stack"}}
        if w is not None and h is not None:
            inputs["boardArtwork"] = {"graphics": [{"id": "outline", "kind": "rect", "points": [{"x": 0, "y": 0}, {"x": w, "y": h}],
                                                    "widthMm": 0.05, "layer": "Edge.Cuts", "filled": False}], "texts": []}
        if surface is not None:
            inputs["surfaceMount"] = surface
        s.add("eda.board", inputs, id="board", label="Board", meta=_meta(root))
        s.output("board")

    # Names first: an end may name a trace or a via written after it.
    components: set = set()
    conductors: Dict[str, Dict[str, Any]] = {}
    nets: set = set()
    kicad_forms = 0
    for el in children:
        nm = el.props.get("name")
        if el.tag == "component":
            if not isinstance(nm, str) or not nm:
                raise ValueError("<component> needs the name of the schematic's part")
            if nm in components or nm in conductors:
                raise ValueError(f"two elements are called {nm}")
            components.add(nm)
        elif el.tag in _CONDUCTORS:
            if nm is None:
                continue
            if not isinstance(nm, str) or not re.match(r"^[A-Za-z0-9_\-]+$", nm):
                raise ValueError(f"{_where(el)}: a name is letters, digits, _ and -")
            if nm in components or nm in conductors:
                raise ValueError(f"two elements are called {nm}")
            conductors[nm] = {"el": el, "id": nm}
        elif el.tag == "net":
            if not isinstance(nm, str) or not nm:
                raise ValueError("<net> needs the name of the schematic's net")
            if nm in nets:
                raise ValueError(f"two <net> elements name {nm}")
            nets.add(nm)
        elif el.tag == "kicad":
            kicad_forms += 1
            if kicad_forms > 1:
                raise ValueError("a board has one <kicad>")
        elif el.tag != "stack" and el.tag not in _FACTS:
            raise ValueError(f"<{el.tag}> is not read on a board (see commandagi.design.pcb)")
    id_of: Dict[int, str] = {id(c["el"]): c["id"] for c in conductors.values()}
    taken = {c["id"] for c in conductors.values()}
    n = 0
    for el in children:
        if el.tag in _CONDUCTORS and id(el) not in id_of:
            while True:
                n += 1
                cid = f"cu_{n}"
                if cid not in taken and cid not in components:
                    break
            taken.add(cid)
            id_of[id(el)] = cid

    def point_count(el: Element) -> int:
        return 3 if el.tag == "arc" else len(_point_list(el, "points", 2))

    def end(sel: Any, el: Element, point: int) -> Dict[str, Any]:
        if not isinstance(sel, str):
            raise ValueError(f'{_where(el)}: an end is a selector (".R1 > .pin2", ".V1", ".T1 > .end")')
        one = re.match(r"^\s*\.([A-Za-z0-9_#\-]+)\s*$", sel)
        if one:
            v = conductors.get(one.group(1))
            if not v or v["el"].tag != "via":
                raise ValueError(f"{_where(el)}: there is no via {one.group(1)}")
            return {"point": point, "via": v["id"]}
        two = _PIN.match(sel)
        if not two:
            raise ValueError(f'{_where(el)}: {json.dumps(sel)} is not ".REF > .pin1", ".VIA" or ".TRACE > .end"')
        owner, which = two.group(1), two.group(2)
        if owner in components:
            m = re.match(r"^pin(.+)$", which, re.IGNORECASE)
            return {"point": point, "ref": owner, "number": m.group(1) if m else which}
        run = conductors.get(owner)
        if not run or run["el"].tag not in ("trace", "arc"):
            raise ValueError(f"{_where(el)}: there is no component or trace {owner}")
        count = point_count(run["el"])
        index = 0 if which == "start" else count - 1 if which == "end" else int(which) if re.match(r"^\d+$", which) else -1
        if index < 0 or index >= count:
            raise ValueError(f"{_where(el)}: trace {owner} has no point {which}")
        return {"point": point, "run": run["id"], "runPoint": trace_point_id(index, count)}

    def net_of(el: Element) -> Dict[str, Any]:
        v = _text(el, "net")
        if v is None:
            return {}
        if not v.strip():
            raise ValueError(f"{_where(el)}: net names the schematic's net")
        return {"net": v}

    def uuid_of(el: Element) -> Dict[str, Any]:
        v = _text(el, "uuid")
        return {} if v is None else {"uuid": v}

    def ends(el: Element, count: int) -> List[Dict[str, Any]]:
        out = []
        if el.props.get("from") is not None:
            out.append(end(el.props["from"], el, 0))
        if el.props.get("to") is not None:
            out.append(end(el.props["to"], el, count - 1))
        return out

    for el in children:
        if el.tag == "stack":
            continue
        if el.tag == "component":
            _refuse_unknown(el, ["name", "footprint", "library", "pcbX", "pcbY", "pcbRotation", "layer", "chart", "uuid", "kicad"])
            ref = el.props["name"]
            fp = el.props.get("footprint")
            library = el.props.get("library")
            if library is not None:
                if not isinstance(library, str) or not re.search(r"\.pretty/?$", library, re.IGNORECASE):
                    raise ValueError(f"{_where(el)}: library names a footprint library folder (a .pretty), not {json.dumps(library)}")
                if not isinstance(fp, str) or not re.match(r"^[^:]+:[^:/]+$", fp):
                    raise ValueError(f'{_where(el)}: a library footprint is its ref, "Library:Footprint" ("Package_SO:SOIC-8"), not {json.dumps(fp)}')
            elif not isinstance(fp, str) or (fp not in BOARD_FOOTPRINTS and not re.match(r"^[^:]+:[^:/]+$", fp)):
                raise ValueError(f"{_where(el)}: footprint is one of {', '.join(BOARD_FOOTPRINTS)}, or a library footprint by its ref "
                                 f'("Package_SO:SOIC-8") with its library, not {json.dumps(fp)}')
            # A library footprint named with no library is named only: its pads are not on the board yet, so it is not placed.
            named = library is None and fp not in BOARD_FOOTPRINTS
            if named and (el.props.get("pcbX") is not None or el.props.get("pcbY") is not None):
                raise ValueError(f"{_where(el)}: a footprint is placed with its pads: name its library (a .pretty folder)")
            x, y, rot = _num(el, "pcbX"), _num(el, "pcbY"), _num(el, "pcbRotation")
            side = el.props.get("layer")
            if side is not None and side not in ("top", "bottom"):
                raise ValueError(f'{_where(el)}: layer is "top" or "bottom"')
            if (x is None) != (y is None):
                raise ValueError(f"{_where(el)}: give pcbX and pcbY together")
            if x is None and (rot is not None or side is not None):
                raise ValueError(f"{_where(el)}: pcbRotation and layer need pcbX and pcbY")
            chart = _text(el, "chart")
            if chart is not None and surface is None:
                raise ValueError(f"{_where(el)}: chart names a face of the board's surface, and the <board> has no surface")
            if chart is not None and x is None:
                raise ValueError(f"{_where(el)}: chart needs pcbX and pcbY")
            inputs = {"ref": ref}
            if library is not None:
                inputs.update(footprint=fp, library=re.sub(r"/$", "", library))
            elif named:
                inputs["footprint"] = fp
            else:
                inputs["footprint"] = f"Authored:{fp}"
            if x is not None:
                inputs["placement"] = {"x": x, "y": y, "rot": rot if rot is not None else 0, "side": side if side is not None else "top"}
            if chart is not None:
                inputs["surfaceMount"] = {"chart": chart}
            inputs.update(uuid_of(el), **_kicad(el))
            s.add(BOARD_PART, inputs, id=f"fp_{ref}", label=ref, meta=_meta(el))
        elif el.tag in ("trace", "arc"):
            _refuse_unknown(el, ["name", "layer", "width", "points", "from", "to", "net", "uuid", "kicad",
                                 *(["segmentUuids", "surface"] if el.tag == "trace" else [])])
            on_surface = el.props.get("surface")
            if on_surface is not None and on_surface is not True:
                raise ValueError(f"{_where(el)}: surface is true or left out")
            if on_surface and surface is None:
                raise ValueError(f"{_where(el)}: surface runs the trace on the board's surface, and the <board> has no surface")
            pts = _point_list(el, "points", 3, 3) if el.tag == "arc" else _point_list(el, "points", 2)
            layer = el.props.get("layer")
            if not isinstance(layer, str) or not _COPPER.match(layer):
                raise ValueError(f'{_where(el)}: layer is a copper layer ("F.Cu", "In1.Cu", "B.Cu")')
            terminals = ends(el, len(pts))
            segment_uuids = _plain(el, "segmentUuids", lambda v: isinstance(v, (list, tuple)) and all(isinstance(u, str) for u in v),
                                   "a list of uuids, one per segment")
            inputs = {"kind": "arc" if el.tag == "arc" else "run",
                      "points": [{**p, "id": trace_point_id(i, len(pts))} for i, p in enumerate(pts)],
                      "widthMm": _positive(el, "width", True), "layer": layer}
            # The board view routes and re-routes a run under any angle; a KiCad segment says no rule.
            if el.tag == "trace":
                inputs["rule"] = "any"
            if terminals:
                inputs["terminals"] = terminals
            if segment_uuids is not None:
                inputs["segmentUuids"] = segment_uuids
            if on_surface:
                inputs["mount"] = {"kind": "unwrap", "domain": surface["domain"]}
            inputs.update(uuid_of(el), **net_of(el), **_kicad(el))
            s.add(CONDUCTOR, inputs, id=id_of[id(el)], label="Arc" if el.tag == "arc" else "Trace", meta=_meta(el))
        elif el.tag == "via":
            _refuse_unknown(el, ["name", "pcbX", "pcbY", "drill", "diameter", "layers", "pads", "net", "uuid", "kicad"])
            layers_ = _copper_layers(el, ["F.Cu", "B.Cu"])
            if len(layers_) < 2:
                raise ValueError(f"{_where(el)}: layers is two or more copper layers")
            drill, diameter = _positive(el, "drill", True), _positive(el, "diameter", True)
            if diameter <= drill:
                raise ValueError(f"{_where(el)}: the diameter is more than the drill")
            pads = el.props.get("pads")
            if pads is not None and (not isinstance(pads, (list, tuple)) or not pads):
                raise ValueError(f'{_where(el)}: pads is a list of pins (".R1 > .pin2")')
            pad_refs = []
            for p in pads or []:
                t = end(p, el, 0)
                if "ref" not in t:
                    raise ValueError(f'{_where(el)}: a via is plated into a pad (".R1 > .pin2"), not {json.dumps(p)}')
                pad_refs.append({"ref": t["ref"], "number": t["number"]})
            inputs = {"kind": "via", "points": [{"x": _num(el, "pcbX", True), "y": _num(el, "pcbY", True)}], "drillMm": drill,
                      "padDiameterMm": diameter, "layers": layers_}
            if pad_refs:
                inputs["pads"] = pad_refs
            inputs.update(uuid_of(el), **net_of(el), **_kicad(el))
            s.add(CONDUCTOR, inputs, id=id_of[id(el)], label="Via", meta=_meta(el))
        elif el.tag == "pour":
            _refuse_unknown(el, ["name", "layers", "points", "terminals", "net", "uuid", "kicad"])
            pts = _point_list(el, "points", 3)
            raw = el.props.get("terminals")
            if raw is not None and (not isinstance(raw, (list, tuple)) or not all(
                    isinstance(t, (list, tuple)) and len(t) == 2 and isinstance(t[0], int) and not isinstance(t[0], bool)
                    and isinstance(t[1], str) for t in raw)):
                raise ValueError(f'{_where(el)}: terminals is a list of [point, selector] ([[0, ".J1 > .pin2"], …])')
            terminals = []
            for point, sel in raw or []:
                if point < 0 or point >= len(pts):
                    raise ValueError(f"{_where(el)}: the pour has no point {point}")
                terminals.append(end(sel, el, point))
            inputs = {"kind": "pour", "points": pts, "layers": _copper_layers(el)}
            if terminals:
                inputs["terminals"] = terminals
            inputs.update(uuid_of(el), **net_of(el), **_kicad(el))
            s.add(CONDUCTOR, inputs, id=id_of[id(el)], label="Pour", meta=_meta(el))
        elif el.tag == "graphic":
            _refuse_unknown(el, ["kind", "layer", "points", "width", "filled", "id", "kicad"])
            kind = _text(el, "kind", True)
            if kind not in _GRAPHICS:
                raise ValueError(f"{_where(el)}: kind is {', '.join(_GRAPHICS)}")
            filled = el.props.get("filled")
            if filled is not None and not isinstance(filled, bool):
                raise ValueError(f"{_where(el)}: filled is true or false")
            if filled is not None and kind in ("line", "arc"):
                raise ValueError(f"{_where(el)}: a {kind} is not filled")
            inputs = {"fact": "graphic"}
            if el.props.get("id") is not None:
                inputs["id"] = _text(el, "id")
            inputs.update(kind=kind, points=_point_list(el, "points", 2 if kind == "poly" else _GRAPHICS[kind], _GRAPHICS[kind]),
                          widthMm=_num(el, "width", True), layer=_text(el, "layer", True))
            if kind not in ("line", "arc"):
                inputs["filled"] = filled if filled is not None else False
            inputs.update(_kicad(el))
            s.add(BOARD_FACT, inputs, label="Graphic", meta=_meta(el))
        elif el.tag == "text":
            _refuse_unknown(el, ["text", "field", "at", "rotation", "layer", "size", "sizeX", "thickness", "kind", "id", "kicad"])
            t, field = _text(el, "text"), _text(el, "field")
            if (t is None) == (field is None):
                raise ValueError('<text>: give text, or field ("reference" or "value")')
            if field is not None and field not in ("reference", "value"):
                raise ValueError('<text>: field is "reference" or "value"')
            inputs = {"fact": "text"}
            if el.props.get("id") is not None:
                inputs["id"] = _text(el, "id")
            inputs.update({"text": t} if t is not None else {"field": field})
            rotation, size_x, kind = _num(el, "rotation"), _num(el, "sizeX"), _text(el, "kind")
            inputs.update(at=_at(el, "at"), rot=rotation if rotation is not None else 0, layer=_text(el, "layer", True),
                          size=_num(el, "size", True), sizeX=size_x if size_x is not None else _num(el, "size", True),
                          thickness=_num(el, "thickness", True), kind=kind if kind is not None else "text")
            inputs.update(_kicad(el))
            s.add(BOARD_FACT, inputs, label="Text", meta=_meta(el))
        elif el.tag == "dimension":
            _refuse_unknown(el, ["points", "height", "layer", "width", "textSize", "id", "kicad"])
            ident = _text(el, "id")
            inputs = {"fact": "dimension", "id": ident if ident is not None else "", "points": _point_list(el, "points", 2, 2),
                      "height": _num(el, "height", True), "layer": _text(el, "layer", True), "widthMm": _num(el, "width", True),
                      "textSize": _num(el, "textSize", True), **_kicad(el)}
            s.add(BOARD_FACT, inputs, label="Dimension", meta=_meta(el))
        elif el.tag == "kicad":
            _refuse_unknown(el, ["version", "generator", "forms"])
            version, generator = _num(el, "version"), _text(el, "generator")
            inputs = {"fact": "kicad"}
            if version is not None:
                inputs["version"] = version
            if generator is not None:
                inputs["generator"] = generator
            inputs.update(_kicad(el, "forms"))
            s.add(BOARD_FACT, inputs, label="KiCad", meta=_meta(el))
        elif el.tag == "net":
            _refuse_unknown(el, ["name", "code"])
            code = _num(el, "code", True)
            if not float(code).is_integer() or code < 0:
                raise ValueError(f"{_where(el)}: code is a KiCad net code (0 or more)")
            s.add(BOARD_FACT, {"fact": "net", "name": el.props["name"], "code": code}, label="Net", meta=_meta(el))


def _declare(root: Element, stem: str) -> Dict[str, Any]:
    if root.props.get("schematic") is None:
        raise ValueError("<board>: schematic is the schematic file's path, relative to this file (a board in code names its schematic)")
    # The TypeScript SDK reads a board without the file's name (graphOf -> fromTscircuit): its title is its name or "Board".
    return {"graph": declare_board_file(root).ir}


declares("pcb", "board", _declare)
