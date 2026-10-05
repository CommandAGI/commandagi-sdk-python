"""A SCHEMATIC IN PYTHON — the circuit's own schematic sheet, declared as the nodes the CommandAGI circuit editor
draws and edits (``sch.symbol.*``, ``sch.wire``, ``sch.junction``, ``sch.label``). The same declarations, node for
node, as the TypeScript SDK's JSX schematic (``commandagi/design`` ``sheet.ts``); each call is one element:

    from commandagi.design.schematic import group, resistor, voltagesource, ground, trace, netlabel

    with group("Divider"):
        voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3)
        resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9)
        resistor("R2", resistance="1.5k", sch_x=139.7, sch_y=88.9, sch_rotation=90)
        ground("#PWR1", sch_x=139.7, sch_y=114.3)
        trace(".V1 > .pos", ".R1 > .pin1")
        netlabel("OUT", ".R1 > .pin2")

The calls:
    resistor|capacitor|inductor(name, resistance|capacitance|inductance=…)   an ideal two-terminal part
    voltagesource|currentsource(name, voltage|current=…, excitation=…)       an ideal source: pin 1 (``pos``) is +
    ground(name)                                                             a ground symbol (name "#PWR1"): net GND
    … sch_x=, sch_y=, sch_rotation=                                          where its symbol sits on the sheet
    junction(name, sch_x=, sch_y=)                                           a wire vertex
    trace(a, b, …)                                                           wires along the selectors: ".R1 > .pin2",
                                                                             ".J1" (a junction), "net.GND" (a label)
    netlabel(net, connection)                                                a label naming the net of a pin
    part(name, symbol="Lib:Name", library="x.kicad_sym", value=…)            a library part: its symbol named by its
                                                                             library ref in a .kicad_sym, by path
    unit(part, n, sch_x=, sch_y=, sch_rotation=, sch_mirror=)                where unit n (2 or more) of a part sits;
                                                                             the part's own sch_x, sch_y place unit 1
    code(name, source=…, inputs={…})                                         a code part: the parts another file
                                                                             declares (its path relative to this one)

``sch_x`` and ``sch_y`` are the sheet's own coordinates: millimetres, Y DOWN. ``sch_rotation`` is 0, 90, 180 or 270
degrees; ``sch_mirror`` is "x" or "y". A part with neither is declared and not placed. A library part's pins and body
are the library's: the editor reads them from the file, so the schematic holds no pin geometry. Its pin is named by
number (".U1 > .pin5"); the editor binds it to the unit that has it (a pin common to every unit lands on the lowest
unit placed). A wire is a binding between two pins, never a coincidence of
coordinates. The ``with group(...)`` block is the file's result. Each node carries the call it came from in
``meta.source`` (``./source.py``), so the circuit editor writes its edits back into the file. Anything else is refused
by name, never guessed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .eda import circuit, part_type_for
from .ir import Scope, channels, current_scope, slug
from .source import declare, here

SCH_WIRE = "sch.wire"
SCH_JUNCTION = "sch.junction"
SCH_LABEL = "sch.label"
_PART_PORT = "part"
_PART_BODY_PORT = "@part"
_VERTEX_PORT = "v"

__all__ = ["SCH_WIRE", "SCH_JUNCTION", "SCH_LABEL", "SHEET_PARTS", "sch_symbol_type_for", "group", "resistor", "capacitor",
           "inductor", "voltagesource", "currentsource", "ground", "junction", "trace", "netlabel", "part", "unit", "code",
           "LIBRARY_PIN_PORT"]


def sch_symbol_type_for(sockets: List[str]) -> str:
    """A placement's node type: ``sch.symbol.`` + FNV-1a over its pin sockets joined by NUL (part of the format)."""
    signature = "\x00".join(sockets)
    h = 0x811C9DC5
    for ch in signature:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"sch.symbol.{h:08x}"


_TWO = {"pin1": "1", "pin2": "2", "left": "1", "right": "2"}
_SOURCE = {**_TWO, "pos": "1", "neg": "2", "+": "1", "-": "2"}
#: The parts a schematic declares, by call: the circuit editor's ideal symbols.
SHEET_PARTS: Dict[str, Dict[str, Any]] = {
    "resistor": {"symbol": "Ideal:R", "value": "resistance", "pins": 2, "aliases": _TWO},
    "capacitor": {"symbol": "Ideal:C", "value": "capacitance", "pins": 2, "aliases": _TWO},
    "inductor": {"symbol": "Ideal:L", "value": "inductance", "pins": 2, "aliases": _TWO},
    "voltagesource": {"symbol": "Ideal:V", "value": "voltage", "pins": 2, "aliases": _SOURCE, "excitation": True},
    "currentsource": {"symbol": "Ideal:I", "value": "current", "pins": 2, "aliases": _SOURCE, "excitation": True},
    "ground": {"symbol": "Ideal:GND", "value": None, "pins": 1, "aliases": {"pin1": "1", "gnd": "1"}, "power": "GND"},
}
_PLACE = ["sch_x", "sch_y", "sch_rotation", "sch_mirror"]
_MIRRORS = ("x", "y")
#: A library part's wire end before the editor reads its library: the part node, and the pin by number.
LIBRARY_PIN_PORT = "pin:"
#: The node a code part declares (the graph's own ``code`` op): it runs another file.
_CODE_OP = "code"


class _Element:
    def __init__(self, type: str, props: Dict[str, Any], source: Optional[int]):
        self.type = type
        self.props = props
        self.source = source

    def where(self) -> str:
        name = self.props.get("name")
        if isinstance(name, str):
            return f"{self.type}({name!r})"
        part = self.props.get("part")
        return f"{self.type}({part!r})" if isinstance(part, str) else f"{self.type}()"

    def meta(self) -> Optional[Dict[str, Any]]:
        return None if self.source is None else {"source": self.source}


_open: List["group"] = []


def _child(type: str, props: Dict[str, Any]) -> None:
    if not _open:
        raise RuntimeError(f"{type}() declares an element of a schematic and belongs inside `with group(...)`")
    _open[-1].children.append(_Element(type, props, here()))


def _refuse_unknown(el: _Element, allowed: List[str]) -> None:
    for k in el.props:
        if k in allowed:
            continue
        if k in ("footprint", "pcb_x", "pcb_y", "pcb_rotation", "layer"):
            raise ValueError(f"{el.where()}: {k} is not read on a schematic (a schematic part declares no board placement)")
        raise ValueError(f"{el.where()}: {k} is not read on a schematic")


def _num(el: _Element, prop: str) -> Optional[float]:
    v = el.props.get(prop)
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf"):
        return v
    raise ValueError(f"{el.where()}: {prop} is a number (mm or degrees), not {v!r}")


def _part(type: str):
    def declare_part(name: Optional[str] = None, **props: Any) -> None:
        _child(type, {"name": name, **props} if name is not None else props)

    declare_part.__name__ = type
    declare_part.__doc__ = f"Declare a {type} on the sheet (see the module's docstring)."
    return declare_part


resistor = _part("resistor")
capacitor = _part("capacitor")
inductor = _part("inductor")
voltagesource = _part("voltagesource")
currentsource = _part("currentsource")
ground = _part("ground")


def junction(name: Optional[str] = None, **props: Any) -> None:
    """A wire vertex at (sch_x, sch_y)."""
    _child("junction", {"name": name, **props} if name is not None else props)


def part(name: Optional[str] = None, **props: Any) -> None:
    """A library part: ``part("U1", symbol="Amplifier_Operational:LM358", library="opamps.kicad_sym", value="LM358")``."""
    _child("part", {"name": name, **props} if name is not None else props)


def unit(part: Optional[str] = None, unit: Any = None, **props: Any) -> None:
    """Where unit ``unit`` (2 or more) of a part sits: ``unit("U1", 2, sch_x=101.6, sch_y=25.4)``."""
    _child("unit", {**({"part": part} if part is not None else {}), **({"unit": unit} if unit is not None else {}), **props})


def code(name: Optional[str] = None, **props: Any) -> None:
    """A code part: ``code("blinker", source="blinker.circuit.ts", inputs={"resistor": "330"})``."""
    _child("code", {"name": name, **props} if name is not None else props)


def trace(*path: str, **props: Any) -> None:
    """Wires along the selectors: ``trace(".V1 > .pos", ".R1 > .pin1")``."""
    _child("trace", {"path": list(path), **props})


def netlabel(net: Optional[str] = None, connection: Optional[str] = None, **props: Any) -> None:
    """A label naming the net of a pin: ``netlabel("OUT", ".R1 > .pin2")``."""
    _child("netlabel", {**({"net": net} if net is not None else {}), **({"connection": connection} if connection is not None else {}), **props})


class group:
    """``with group("Divider"):`` — the schematic; its block declares the sheet's elements. The finished block is the
    file's result (a ``Declaration``: ``group(...).declaration``)."""

    def __init__(self, name: str, **props: Any):
        if not isinstance(name, str) or not name:
            raise ValueError("group() needs a name")
        if props:
            raise ValueError(f"group({name!r}): {', '.join(props)} is not read on a schematic")
        self.name = name
        self.children: List[_Element] = []
        self.source = here()
        self.declaration: Any = None

    def __enter__(self) -> "group":
        if _open:
            raise ValueError(f"group({self.name!r}) is inside group({_open[-1].name!r}); a schematic is one group")
        _open.append(self)
        return self

    def __exit__(self, kind: Any, *exc: Any) -> bool:
        _open.pop()
        if kind is not None:
            return False
        self.declaration = circuit(self.name, lambda: _declare_sheet(self.children))
        declare(self.declaration)
        return False


def _declare_sheet(children: List[_Element]) -> None:
    s: Scope = current_scope("a schematic")
    parts: Dict[str, Dict[str, Any]] = {}
    junctions: Dict[str, str] = {}
    later: List[_Element] = []
    wires = 0
    for el in children:
        ideal = SHEET_PARTS.get(el.type)
        if ideal:
            _refuse_unknown(el, ["name", *_PLACE, *([ideal["value"]] if ideal["value"] else []), *(["excitation"] if ideal.get("excitation") else [])])
            ref = el.props.get("name")
            if not isinstance(ref, str) or not ref:
                raise ValueError(f"{el.type}() needs a name")
            # The netlist leaves power symbols out by their reference (KiCad's rule), so a ground's says it is one.
            if ideal.get("power") and not ref.startswith("#"):
                raise ValueError(f"{el.where()}: a ground symbol's name starts with # (#PWR1), as KiCad names power symbols")
            if ref in parts:
                raise ValueError(f"two parts are called {ref}")
            pins = [{"id": f"p{i + 1}", "number": str(i + 1)} for i in range(ideal["pins"])]
            raw = el.props.get(ideal["value"]) if ideal["value"] else None
            if raw is not None and (isinstance(raw, bool) or not isinstance(raw, (str, int, float))):
                raise ValueError(f"{el.where()}: {ideal['value']} is a value (\"1k\", 1000), not {raw!r}")
            value = ideal.get("power") or (None if raw is None else _value_text(raw))
            inputs: Dict[str, Any] = {"ref": ref}
            if value is not None:
                inputs["value"] = value
            inputs.update(symbol=ideal["symbol"], pins=pins, units=1)
            if ideal.get("power"):
                inputs["powerSymbol"] = True
            if el.props.get("excitation") is not None:
                inputs["excitation"] = el.props["excitation"]
            node = s.add(part_type_for(pins), inputs, id=ref, label=ref, meta=el.meta())
            placed = {"ref": ref, "id": node.id, "units": {}, "ideal": ideal}
            _place(s, placed, 1, el, [p["id"] for p in pins])
            parts[ref] = placed
            continue
        if el.type == "part":
            _refuse_unknown(el, ["name", "symbol", "library", "value", *_PLACE])
            ref = _str(el, "name", "the part's reference (U1)")
            if ref in parts:
                raise ValueError(f"two parts are called {ref}")
            symbol = _str(el, "symbol", 'its library ref ("Device:R_Small")')
            if not re.match(r"^[^:]+:[^:]+$", symbol):
                raise ValueError(f'{el.where()}: symbol is a library ref, "Library:Symbol" ("Device:R_Small"), not {symbol!r}')
            library = _str(el, "library", "the path of the .kicad_sym that holds the symbol")
            if not library.lower().endswith(".kicad_sym"):
                raise ValueError(f"{el.where()}: library names a .kicad_sym file, not {library!r}")
            raw = el.props.get("value")
            if raw is not None and (isinstance(raw, bool) or not isinstance(raw, (str, int, float))):
                raise ValueError(f"{el.where()}: value is a value (\"LM358\", 1000), not {raw!r}")
            inputs = {"ref": ref}
            if raw is not None:
                inputs["value"] = _value_text(raw)
            # The pins are the library's: the editor reads them (and the part's type) from the library file.
            inputs.update(symbol=symbol, library=library, pins=[])
            node = s.add(part_type_for([]), inputs, id=ref, label=ref, meta=el.meta())
            placed = {"ref": ref, "id": node.id, "units": {}, "ideal": None}
            _place(s, placed, 1, el, [])
            parts[ref] = placed
            continue
        if el.type == "code":
            _refuse_unknown(el, ["name", "source", "inputs"])
            name = _str(el, "name", "the code part's id")
            source = _str(el, "source", "the path of the file it runs, relative to this one")
            inputs = el.props.get("inputs")
            if inputs is None:
                inputs = {}
            if not isinstance(inputs, dict):
                raise ValueError(f"{el.where()}: inputs is an object of the file's parameters")
            if "source" in inputs:
                raise ValueError(f"{el.where()}: source is the file, not one of its inputs")
            if name in s.nodes:
                raise ValueError(f"two nodes are called {name}")
            s.add(_CODE_OP, {"source": source, **inputs}, id=name, label=source.split("/")[-1], meta=el.meta())
            continue
        if el.type == "junction":
            _refuse_unknown(el, ["name", "sch_x", "sch_y"])
            name = el.props.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("junction() needs a name")
            if name in junctions:
                raise ValueError(f"two junctions are called {name}")
            junctions[name] = s.add(SCH_JUNCTION, {"at": {"x": _num(el, "sch_x") or 0, "y": _num(el, "sch_y") or 0}}, id=name, label="Junction", meta=el.meta()).id
        elif el.type in ("unit", "trace", "netlabel"):
            later.append(el)
        else:
            raise ValueError(f"{el.type}() is not read on a schematic (see commandagi.design.schematic)")

    def end(sel: Any, el: _Element) -> Dict[str, str]:
        if not isinstance(sel, str):
            raise ValueError(f"{el.where()}: an end is a selector (\".R1 > .pin1\", \".J1\", \"net.GND\")")
        n = re.match(r"^\s*net\.([A-Za-z0-9_+\-]+)\s*$", sel)
        if n:
            return {"net": n.group(1)}
        j = re.match(r"^\s*\.([A-Za-z0-9_#\-]+)\s*$", sel)
        if j:
            if j.group(1) not in junctions:
                raise ValueError(f"{el.where()}: there is no junction {j.group(1)}")
            return {"node": junctions[j.group(1)], "port": _VERTEX_PORT}
        p = re.match(r"^\s*\.([A-Za-z0-9_#\-]+)\s*>\s*\.([A-Za-z0-9_+\-]+)\s*$", sel)
        if not p:
            raise ValueError(f"{el.where()}: {sel!r} is not \".REF > .pin\", \".JUNCTION\" or \"net.NAME\"")
        part = parts.get(p.group(1))
        if not part:
            raise ValueError(f"{el.where()}: there is no part {p.group(1)}")
        if not part["units"]:
            raise ValueError(f"{el.where()}: {part['ref']} is not on the sheet (give it sch_x and sch_y)")
        if part["ideal"] is None:
            # A library part's pin by number (".pin5" or ".5"); the editor binds it to the unit that has it.
            lib = re.match(r"^pin(.+)$", p.group(2), re.IGNORECASE)
            return {"node": part["id"], "port": LIBRARY_PIN_PORT + (lib.group(1) if lib else p.group(2))}
        key = p.group(2).lower()
        number = part["ideal"]["aliases"].get(key) or (key if key.isdigit() else None)
        if not number or int(number) > part["ideal"]["pins"]:
            raise ValueError(f"{el.where()}: {part['ref']} has no pin {p.group(2)}")
        return {"node": part["units"][1], "port": f"p{number}"}

    def free(base: str) -> str:
        """A free id ``base``, ``base_2``, … (the same file declares the same ids)."""
        i, n = slug(base), 2
        while i in s.nodes:
            i, n = f"{slug(base)}_{n}", n + 1
        return i

    def label(text: str, on: Dict[str, str], el: _Element) -> None:
        s.add(SCH_LABEL, {"text": text, "on": {"wire": on}}, id=free(f"lbl_{text}"), label=text, meta=el.meta())

    # Units first: a wire may land on any unit's pin.
    for el in later:
        if el.type != "unit":
            continue
        _refuse_unknown(el, ["part", "unit", *_PLACE])
        ref = _str(el, "part", "the reference of the part whose unit it places")
        placed = parts.get(ref)
        if not placed:
            raise ValueError(f"{el.where()}: there is no part {ref}")
        n = el.props.get("unit")
        if isinstance(n, bool) or not isinstance(n, int) or n < 2:
            raise ValueError(f"{el.where()}: unit is 2 or more (the part's own sch_x and sch_y place unit 1)")
        if placed["ideal"] is not None:
            raise ValueError(f"{el.where()}: {ref} is an ideal part, which has one unit")
        if n in placed["units"]:
            raise ValueError(f"{el.where()}: unit {n} of {ref} is placed twice")
        _place(s, placed, n, el, [])
    for el in later:
        if el.type == "unit":
            continue
        if el.type == "netlabel":
            _refuse_unknown(el, ["net", "connection"])
            text = el.props.get("net")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("netlabel() needs a net name")
            on = end(el.props.get("connection"), el)
            if "net" in on:
                raise ValueError(f"{el.where()}: a label's connection is a pin or a junction")
            label(text.strip(), on, el)
            continue
        _refuse_unknown(el, ["path"])
        path = el.props["path"]
        if len(path) < 2:
            raise ValueError("trace() takes two selectors or more")
        ends = [end(p, el) for p in path]
        for a, b in zip(ends, ends[1:]):
            if "net" in a and "net" in b:
                raise ValueError(f"trace() joins two nets ({a['net']}, {b['net']})")
            if "net" in a:
                label(a["net"], b, el)
            elif "net" in b:
                label(b["net"], a, el)
            else:
                wires += 1
                s.add(SCH_WIRE, channels("ends", [{"wire": a}, {"wire": b}]), id=free(f"w_{wires}"), label="Wire", meta=el.meta())


def _str(el: _Element, prop: str, what: str) -> str:
    v = el.props.get(prop)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{el.where()}: {prop} is {what}")
    return v


def _place(s: Scope, placed: Dict[str, Any], unit_number: int, el: _Element, pins: List[str]) -> None:
    """Add the placement of ``unit_number`` of a part that ``el`` declares (its sch_x, sch_y, sch_rotation, sch_mirror)."""
    x, y, rot = _num(el, "sch_x"), _num(el, "sch_y"), _num(el, "sch_rotation")
    mirror = el.props.get("sch_mirror")
    if x is None and y is None:
        if rot is not None or mirror is not None:
            raise ValueError(f"{el.where()}: {'sch_rotation' if rot is not None else 'sch_mirror'} needs sch_x and sch_y")
        if el.type == "unit":
            raise ValueError(f"{el.where()}: a unit is placed: give it sch_x and sch_y")
        return
    if rot is not None and rot not in (0, 90, 180, 270):
        raise ValueError(f"{el.where()}: sch_rotation is 0, 90, 180 or 270")
    if mirror is not None and mirror not in _MIRRORS:
        raise ValueError(f'{el.where()}: sch_mirror is "x" or "y"')
    ref = placed["ref"]
    placed["units"][unit_number] = s.add(
        sch_symbol_type_for(pins),
        {"unit": unit_number, "style": 1, "at": {"x": x if x is not None else 0, "y": y if y is not None else 0}, "rot": rot or 0,
         "mirror": mirror or "", _PART_PORT: {"wire": {"node": placed["id"], "port": _PART_BODY_PORT}}},
        id=f"sym_{ref}_{unit_number}", label=ref, meta=el.meta()).id


def _value_text(raw: Any) -> str:
    """A value as the sheet holds it (the TypeScript SDK's ``String(raw)``: 1000 → "1000", 1.5 → "1.5")."""
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw)
