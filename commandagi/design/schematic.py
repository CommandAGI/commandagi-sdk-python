"""A SCHEMATIC IN PYTHON — the circuit's own schematic sheet, declared as the nodes the CommandAGI circuit editor
draws and edits (``sch.symbol.*``, ``sch.wire``, ``sch.junction``, ``sch.label``). The same elements, node for node,
as the TypeScript SDK's JSX schematic (``commandagi/design`` ``sheet.ts``); each call is one element:

    from commandagi.design.schematic import ground, group, netlabel, resistor, trace, voltagesource

    result = group(
        "Divider",
        voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3),
        resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9),
        resistor("R2", resistance="1.5k", sch_x=139.7, sch_y=88.9, sch_rotation=90),
        ground("#PWR1", sch_x=139.7, sch_y=114.3),
        trace(".V1 > .pos", ".R1 > .pin1"),
        netlabel("OUT", ".R1 > .pin2"),
    )

The calls (the first arguments are positional attributes; everything else is a keyword):
    group(name, *elements)                                                   the schematic: the file's result
    resistor|capacitor|inductor(name, resistance|capacitance|inductance=…)   an ideal two-terminal part
    voltagesource|currentsource(name, voltage|current=…, excitation=…)       an ideal source: pin 1 (``pos``) is +
    ground(name)                                                             a ground symbol (name "#PWR1"): net GND
    … sch_x=, sch_y=, sch_rotation=                                          where its symbol sits on the sheet
    junction(name, sch_x=, sch_y=)                                           a wire vertex
    trace(from, to) or trace(path=[…])                                       wires along the selectors: ".R1 > .pin2",
                                                                             ".J1" (a junction), "net.GND" (a label)
    netlabel(net, connection)                                                a label naming the net of a pin
    part(name, symbol="Lib:Name", library="x.kicad_sym", value=…)            a library part: its symbol named by its
                                                                             library ref in a .kicad_sym, by path
    part(name, value=…, symbol=…, pins=[…])                                  a part of a netlist circuit (no sheet)
    net(name, pins=[".C1 > .pin1", …])                                       a stored net of a netlist circuit
    unit(part, unit, sch_x=, sch_y=, sch_rotation=, sch_mirror=)             where unit n (2 or more) of a part sits;
                                                                             the part's own sch_x, sch_y place unit 1
    code(name, source=…, inputs={…})                                         a code part: the parts another file
                                                                             declares (its path relative to this one)
    attachment(name, role=…, file=…, mime=…)                                 a KiCad file the circuit carries
    … spice=[{"id", "model", "terminals"}]                                   on any part: its SPICE package bindings

``sch_x`` and ``sch_y`` are the sheet's own coordinates: millimetres, Y DOWN. ``sch_rotation`` is 0, 90, 180 or 270
degrees; ``sch_mirror`` is "x" or "y". A part with neither is declared and not placed. A library part's pins and body
are the library's: the editor reads them from the file, so the schematic holds no pin geometry. Its pin is named by
number (".U1 > .pin5"); the editor binds it to the unit that has it (a pin common to every unit lands on the lowest
unit placed). A wire is a binding between two pins, never a coincidence of coordinates. Each node carries the call it
came from in ``meta.source`` (``./source.py``), so the circuit editor writes its edits back into the file. Anything
else is refused by name, never guessed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .eda import circuit, part_type_for
from .element import Element, child_elements, declares, define
from .ir import Scope, channels, current_scope, slug

SCH_WIRE = "sch.wire"
SCH_JUNCTION = "sch.junction"
SCH_LABEL = "sch.label"
#: A stored net (a netlist circuit's): its pins on channel ``pins``.
NET = "eda.net"
#: A file the circuit carries for exchange (the circuit editor reads its text from ``file``).
ATTACHMENT = "eda.source"
_ROLES = ["schematic", "project", "library", "other"]
_PART_PORT = "part"
_PART_BODY_PORT = "@part"
_VERTEX_PORT = "v"

_NAMED: Dict[str, Any] = {"args": ["name"]}
#: Every tag of the schematic: its positional attributes and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "group": {"args": ["name"], "holds": "children"},
    "resistor": _NAMED, "capacitor": _NAMED, "inductor": _NAMED, "voltagesource": _NAMED, "currentsource": _NAMED,
    "ground": _NAMED, "junction": _NAMED, "part": _NAMED, "code": _NAMED, "net": _NAMED, "attachment": _NAMED,
    "trace": {"args": ["from", "to"]},
    "netlabel": {"args": ["net", "connection"]},
    "unit": {"args": ["part", "unit"]},
}

__all__ = ["SCH_WIRE", "SCH_JUNCTION", "SCH_LABEL", "NET", "ATTACHMENT", "SHEET_PARTS", "SIGNATURES", "LIBRARY_PIN_PORT",
           "sch_symbol_type_for", "declare_sheet", *define(globals(), "schematic", SIGNATURES)]


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
#: The parts a schematic declares, by tag: the circuit editor's ideal symbols.
SHEET_PARTS: Dict[str, Dict[str, Any]] = {
    "resistor": {"symbol": "Ideal:R", "value": "resistance", "pins": 2, "aliases": _TWO},
    "capacitor": {"symbol": "Ideal:C", "value": "capacitance", "pins": 2, "aliases": _TWO},
    "inductor": {"symbol": "Ideal:L", "value": "inductance", "pins": 2, "aliases": _TWO},
    "voltagesource": {"symbol": "Ideal:V", "value": "voltage", "pins": 2, "aliases": _SOURCE, "excitation": True},
    "currentsource": {"symbol": "Ideal:I", "value": "current", "pins": 2, "aliases": _SOURCE, "excitation": True},
    "ground": {"symbol": "Ideal:GND", "value": None, "pins": 1, "aliases": {"pin1": "1", "gnd": "1"}, "power": "GND"},
}
_PLACE = ["schX", "schY", "schRotation", "schMirror"]
_MIRRORS = ("x", "y")
#: A library part's wire end before the editor reads its library: the part node, and the pin by number.
LIBRARY_PIN_PORT = "pin:"
#: The node a code part declares (the graph's own ``code`` op): it runs another file.
_CODE_OP = "code"
_PIN = re.compile(r"^\s*\.([A-Za-z0-9_#\-]+)\s*>\s*\.([A-Za-z0-9_+\-]+)\s*$")


def _meta(el: Element) -> Optional[Dict[str, Any]]:
    return None if el.source is None else {"source": el.source}


def _where(el: Element) -> str:
    for k in ("name", "part"):
        if isinstance(el.props.get(k), str):
            return f'<{el.tag} {k}="{el.props[k]}">'
    return f"<{el.tag}>"


def _refuse_unknown(el: Element, allowed: List[str]) -> None:
    for k in el.props:
        if k == "key" or k in allowed:
            continue
        if k in ("footprint", "pcbX", "pcbY", "pcbRotation", "layer"):
            raise ValueError(f"{_where(el)}: {k} is not read on a schematic (a schematic part declares no board placement)")
        raise ValueError(f"{_where(el)}: prop {k} is not read on a schematic")


def _num(el: Element, prop: str) -> Optional[float]:
    v = el.props.get(prop)
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf"):
        return v
    raise ValueError(f"{_where(el)}: {prop} is a number (mm or degrees), not {v!r}")


def _str(el: Element, prop: str, what: str) -> str:
    v = el.props.get(prop)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{_where(el)}: {prop} is {what}")
    return v


def _plain(v: Any, what: str) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{what}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items()}
    raise ValueError(f"{what} is plain data (numbers, strings, objects)")


def _is_value(raw: Any) -> bool:
    return isinstance(raw, (str, int, float)) and not isinstance(raw, bool)


def _value_text(raw: Any) -> str:
    """A value as the sheet holds it (the TypeScript SDK's ``String(raw)``: 1000 -> "1000", 1.5 -> "1.5")."""
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    return str(raw)


def _spice(el: Element) -> Dict[str, Any]:
    """A part's SPICE package bindings (``spice=[{id, model, terminals: {formal: "pin number"}}]``), as written."""
    v = el.props.get("spice")
    if v is None:
        return {}
    ok = isinstance(v, (list, tuple)) and all(
        isinstance(b, dict) and isinstance(b.get("id"), str) and isinstance(b.get("model"), str) and isinstance(b.get("terminals"), dict)
        and b["terminals"] and all(isinstance(n, str) for n in b["terminals"].values()) for b in v)
    if not ok:
        raise ValueError(f'{_where(el)}: spice is a list of {{ id, model, terminals: {{ formal: "pin number" }} }}')
    return {"spice": _plain(v, f"{_where(el)} spice")}


def _pin_number(written: str) -> str:
    m = re.match(r"^pin(.+)$", written, re.IGNORECASE)
    return m.group(1) if m else written


def _place(s: Scope, placed: Dict[str, Any], unit_number: int, el: Element, pins: List[str]) -> None:
    """Add the placement of ``unit_number`` of a part that ``el`` declares (its schX, schY, schRotation, schMirror)."""
    x, y, rot = _num(el, "schX"), _num(el, "schY"), _num(el, "schRotation")
    mirror = el.props.get("schMirror")
    if x is None and y is None:
        if rot is not None or mirror is not None:
            raise ValueError(f"{_where(el)}: {'schRotation' if rot is not None else 'schMirror'} needs schX and schY")
        if el.tag == "unit":
            raise ValueError(f"{_where(el)}: a unit is placed: give it schX and schY")
        return
    if rot is not None and rot not in (0, 90, 180, 270):
        raise ValueError(f"{_where(el)}: schRotation is 0, 90, 180 or 270")
    if mirror is not None and mirror not in _MIRRORS:
        raise ValueError(f'{_where(el)}: schMirror is "x" or "y"')
    ref = placed["ref"]
    placed["units"][unit_number] = s.add(
        sch_symbol_type_for(pins),
        {"unit": unit_number, "style": 1, "at": {"x": x if x is not None else 0, "y": y if y is not None else 0}, "rot": rot or 0,
         "mirror": mirror or "", _PART_PORT: {"wire": {"node": placed["id"], "port": _PART_BODY_PORT}}},
        id=f"sym_{ref}_{unit_number}", label=ref, meta=_meta(el)).id


def _netlist_part(s: Scope, el: Element, ref: str) -> Dict[str, Any]:
    """A part of a netlist circuit: its pins listed (by number, with a name or not), no symbol drawing, no placement."""
    for p in [*_PLACE, "library"]:
        if el.props.get(p) is not None:
            raise ValueError(f"{_where(el)}: a part that lists its pins is a netlist circuit's; it has no "
                             f"{'library' if p == 'library' else 'place on the sheet'}")
    raw = el.props.get("pins")
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(f'{_where(el)}: pins is a list of pin numbers (["1", "2"]) or of {{ number, name }}')
    pins = []
    for i, p in enumerate(raw):
        pin = {"number": p} if isinstance(p, str) else p if isinstance(p, dict) else None
        if (pin is None or not isinstance(pin.get("number"), str) or ("name" in pin and not isinstance(pin["name"], str))
                or any(k not in ("number", "name") for k in pin)):
            raise ValueError(f'{_where(el)}: pin {i} is a number ("1") or {{ number, name }}, not {p!r}')
        # A pin number may repeat (a power pin each unit of a part shares, a mechanical pad with no number).
        pins.append({"id": f"p{i + 1}", "number": pin["number"], **({"name": pin["name"]} if "name" in pin else {})})
    symbol = el.props.get("symbol")
    if symbol is not None and (not isinstance(symbol, str) or not symbol):
        raise ValueError(f'{_where(el)}: symbol is a library ref ("Device:R")')
    value = el.props.get("value")
    if value is not None and not _is_value(value):
        raise ValueError(f'{_where(el)}: value is a value ("LM358", 1000), not {value!r}')
    inputs: Dict[str, Any] = {"ref": ref}
    if value is not None:
        inputs["value"] = _value_text(value)
    if symbol is not None:
        inputs["symbol"] = symbol
    inputs["pins"] = pins
    inputs.update(_spice(el))
    node = s.add(part_type_for(pins), inputs, id=ref, label=ref, meta=_meta(el))
    return {"ref": ref, "id": node.id, "units": {}, "ideal": None, "pins": pins}


def declare_sheet(children: List[Element]) -> None:
    """Declare a schematic's elements (the root's children) into the current circuit scope."""
    s: Scope = current_scope("a schematic")
    parts: Dict[str, Dict[str, Any]] = {}
    junctions: Dict[str, str] = {}
    later: List[Element] = []
    wires = 0
    for el in children:
        ideal = SHEET_PARTS.get(el.tag)
        if ideal:
            _refuse_unknown(el, ["name", "spice", *_PLACE, *([ideal["value"]] if ideal["value"] else []),
                                 *(["excitation"] if ideal.get("excitation") else [])])
            ref = el.props.get("name")
            if not isinstance(ref, str) or not ref:
                raise ValueError(f"<{el.tag}> needs a name")
            # The netlist leaves power symbols out by their reference (KiCad's rule), so a ground's says it is one.
            if ideal.get("power") and not ref.startswith("#"):
                raise ValueError(f"{_where(el)}: a ground symbol's name starts with # (#PWR1), as KiCad names power symbols")
            if ref in parts:
                raise ValueError(f"two parts are called {ref}")
            pins = [{"id": f"p{i + 1}", "number": str(i + 1)} for i in range(ideal["pins"])]
            raw = el.props.get(ideal["value"]) if ideal["value"] else None
            if raw is not None and not _is_value(raw):
                raise ValueError(f"{_where(el)}: {ideal['value']} is a value (\"1k\", 1000), not {raw!r}")
            value = ideal.get("power") or (None if raw is None else _value_text(raw))
            inputs: Dict[str, Any] = {"ref": ref}
            if value is not None:
                inputs["value"] = value
            inputs.update(symbol=ideal["symbol"], pins=pins, units=1)
            if ideal.get("power"):
                inputs["powerSymbol"] = True
            if el.props.get("excitation") is not None:
                inputs["excitation"] = _plain(el.props["excitation"], f"{_where(el)} excitation")
            inputs.update(_spice(el))
            node = s.add(part_type_for(pins), inputs, id=ref, label=ref, meta=_meta(el))
            placed = {"ref": ref, "id": node.id, "units": {}, "ideal": ideal}
            _place(s, placed, 1, el, [p["id"] for p in pins])
            parts[ref] = placed
            continue
        if el.tag == "part":
            _refuse_unknown(el, ["name", "symbol", "library", "value", "pins", "spice", *_PLACE])
            ref = _str(el, "name", "the part's reference (U1)")
            if ref in parts:
                raise ValueError(f"two parts are called {ref}")
            if el.props.get("pins") is not None:
                parts[ref] = _netlist_part(s, el, ref)
                continue
            symbol = _str(el, "symbol", 'its library ref ("Device:R_Small")')
            if not re.match(r"^[^:]+:[^:]+$", symbol):
                raise ValueError(f'{_where(el)}: symbol is a library ref, "Library:Symbol" ("Device:R_Small"), not {symbol!r}')
            library = _str(el, "library", "the path of the .kicad_sym that holds the symbol")
            if not library.lower().endswith(".kicad_sym"):
                raise ValueError(f"{_where(el)}: library names a .kicad_sym file, not {library!r}")
            raw = el.props.get("value")
            if raw is not None and not _is_value(raw):
                raise ValueError(f"{_where(el)}: value is a value (\"LM358\", 1000), not {raw!r}")
            inputs = {"ref": ref}
            if raw is not None:
                inputs["value"] = _value_text(raw)
            # The pins are the library's: the editor reads them (and the part's type) from the library file.
            inputs.update(symbol=symbol, library=library, pins=[])
            inputs.update(_spice(el))
            node = s.add(part_type_for([]), inputs, id=ref, label=ref, meta=_meta(el))
            placed = {"ref": ref, "id": node.id, "units": {}, "ideal": None}
            _place(s, placed, 1, el, [])
            parts[ref] = placed
            continue
        if el.tag == "code":
            _refuse_unknown(el, ["name", "source", "inputs"])
            name = _str(el, "name", "the code part's id")
            source = _str(el, "source", "the path of the file it runs, relative to this one")
            inputs = {} if el.props.get("inputs") is None else _plain(el.props["inputs"], f"{_where(el)} inputs")
            if not isinstance(inputs, dict):
                raise ValueError(f"{_where(el)}: inputs is an object of the file's parameters")
            if "source" in inputs:
                raise ValueError(f"{_where(el)}: source is the file, not one of its inputs")
            if name in s.nodes:
                raise ValueError(f"two nodes are called {name}")
            s.add(_CODE_OP, {"source": source, **inputs}, id=name, label=source.split("/")[-1], meta=_meta(el))
            continue
        if el.tag == "junction":
            _refuse_unknown(el, ["name", "schX", "schY"])
            name = el.props.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("<junction> needs a name")
            if name in junctions:
                raise ValueError(f"two junctions are called {name}")
            junctions[name] = s.add(SCH_JUNCTION, {"at": {"x": _num(el, "schX") or 0, "y": _num(el, "schY") or 0}}, id=name,
                                    label="Junction", meta=_meta(el)).id
        elif el.tag in ("unit", "trace", "netlabel", "net", "attachment"):
            later.append(el)
        else:
            raise ValueError(f"<{el.tag}> is not read on a schematic (see commandagi.design.schematic)")

    def end(sel: Any, el: Element) -> Dict[str, str]:
        if not isinstance(sel, str):
            raise ValueError(f"{_where(el)}: an end is a selector (\".R1 > .pin1\", \".J1\", \"net.GND\")")
        n = re.match(r"^\s*net\.([A-Za-z0-9_+\-]+)\s*$", sel)
        if n:
            return {"net": n.group(1)}
        j = re.match(r"^\s*\.([A-Za-z0-9_#\-]+)\s*$", sel)
        if j:
            if j.group(1) not in junctions:
                raise ValueError(f"{_where(el)}: there is no junction {j.group(1)}")
            return {"node": junctions[j.group(1)], "port": _VERTEX_PORT}
        p = _PIN.match(sel)
        if not p:
            raise ValueError(f"{_where(el)}: {sel!r} is not \".REF > .pin\", \".JUNCTION\" or \"net.NAME\"")
        part = parts.get(p.group(1))
        if not part:
            raise ValueError(f"{_where(el)}: there is no part {p.group(1)}")
        if not part["units"]:
            raise ValueError(f"{_where(el)}: {part['ref']} is not on the sheet (give it schX and schY)")
        if part["ideal"] is None:
            # A library part's pin by number (".pin5" or ".5"); the editor binds it to the unit that has it.
            return {"node": part["id"], "port": LIBRARY_PIN_PORT + _pin_number(p.group(2))}
        key = p.group(2).lower()
        number = part["ideal"]["aliases"].get(key) or (key if key.isdigit() else None)
        if not number or int(number) > part["ideal"]["pins"]:
            raise ValueError(f"{_where(el)}: {part['ref']} has no pin {p.group(2)}")
        return {"node": part["units"][1], "port": f"p{number}"}

    def free(base: str) -> str:
        """A free id ``base``, ``base_2``, … (ids are deterministic: the same file declares the same ids)."""
        i, n = slug(base), 2
        while i in s.nodes:
            i, n = f"{slug(base)}_{n}", n + 1
        return i

    def label(text: str, on: Dict[str, str], el: Element) -> None:
        s.add(SCH_LABEL, {"text": text, "on": {"wire": on}}, id=free(f"lbl_{text}"), label=text, meta=_meta(el))

    # Units first: a wire may land on any unit's pin.
    for el in later:
        if el.tag != "unit":
            continue
        _refuse_unknown(el, ["part", "unit", *_PLACE])
        ref = _str(el, "part", "the reference of the part whose unit it places")
        placed = parts.get(ref)
        if not placed:
            raise ValueError(f"{_where(el)}: there is no part {ref}")
        n = el.props.get("unit")
        if isinstance(n, bool) or not isinstance(n, int) or n < 2:
            raise ValueError(f"{_where(el)}: unit is 2 or more (the part's own schX and schY place unit 1)")
        if placed["ideal"] is not None:
            raise ValueError(f"{_where(el)}: {ref} is an ideal part, which has one unit")
        if n in placed["units"]:
            raise ValueError(f"{_where(el)}: unit {n} of {ref} is placed twice")
        _place(s, placed, n, el, [])
    for el in later:
        if el.tag == "unit":
            continue
        if el.tag == "attachment":
            _refuse_unknown(el, ["name", "role", "file", "mime"])
            name = _str(el, "name", "the attachment's name (schematic.kicad_sch)")
            role = _str(el, "role", f"one of {', '.join(_ROLES)}")
            if role not in _ROLES:
                raise ValueError(f"{_where(el)}: role is one of {', '.join(_ROLES)}")
            file = _str(el, "file", "the path of the file it carries, relative to this one")
            if file.startswith("/"):
                raise ValueError(f"{_where(el)}: file is a path relative to this file")
            mime = el.props.get("mime")
            if mime is not None and not isinstance(mime, str):
                raise ValueError(f"{_where(el)}: mime is a media type")
            s.add(ATTACHMENT, {"name": name, "role": role, **({"mime": mime} if mime is not None else {}), "file": file},
                  id=free(f"source_{name}"), label=name, meta=_meta(el))
            continue
        if el.tag == "net":
            _refuse_unknown(el, ["name", "pins"])
            name = _str(el, "name", "the net's name")
            pins = el.props.get("pins")
            if not isinstance(pins, (list, tuple)) or not pins:
                raise ValueError(f'{_where(el)}: pins is a list of pins (".C1 > .pin1")')
            ends = []
            for sel in pins:
                p = _PIN.match(sel) if isinstance(sel, str) else None
                if not p:
                    raise ValueError(f'{_where(el)}: {sel!r} is not ".REF > .pin1"')
                part = parts.get(p.group(1))
                if not part:
                    raise ValueError(f"{_where(el)}: there is no part {p.group(1)}")
                number = _pin_number(p.group(2))
                if not part.get("pins") and part["ideal"] is None:
                    # A library part's pin by number: the editor reads its pins from the library.
                    ends.append({"wire": {"node": part["id"], "port": LIBRARY_PIN_PORT + number}})
                    continue
                if not part.get("pins"):
                    raise ValueError(f"{_where(el)}: {part['ref']} is an ideal part drawn on the sheet; a net names pins of a netlist circuit's parts")
                pin = next((x for x in part["pins"] if x["number"] == number), None)
                if not pin:
                    raise ValueError(f"{_where(el)}: {part['ref']} has no pin {number}")
                ends.append({"wire": {"node": part["id"], "port": pin["id"]}})
            s.add(NET, channels("pins", ends), id=free(f"net_{name}"), label=name, meta=_meta(el))
            continue
        if el.tag == "netlabel":
            _refuse_unknown(el, ["net", "connection"])
            text = el.props.get("net")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("<netlabel> needs a net name")
            on = end(el.props.get("connection"), el)
            if "net" in on:
                raise ValueError(f"{_where(el)}: a label's connection is a pin or a junction")
            label(text.strip(), on, el)
            continue
        _refuse_unknown(el, ["from", "to", "path"])
        path = list(el.props["path"]) if isinstance(el.props.get("path"), (list, tuple)) else [el.props.get("from"), el.props.get("to")]
        if len(path) < 2:
            raise ValueError("<trace> takes from and to, or a path of selectors")
        ends = [end(p, el) for p in path]
        for a, b in zip(ends, ends[1:]):
            if "net" in a and "net" in b:
                raise ValueError(f"<trace> joins two nets ({a['net']}, {b['net']})")
            if "net" in a:
                label(a["net"], b, el)
            elif "net" in b:
                label(b["net"], a, el)
            else:
                wires += 1
                s.add(SCH_WIRE, channels("ends", [{"wire": a}, {"wire": b}]), id=free(f"w_{wires}"), label="Wire", meta=_meta(el))


def _declare_group(root: Element, stem: str) -> Dict[str, Any]:
    """A ``group(name, …)``: the circuit its elements declare (the TypeScript SDK's ``fromTscircuit`` of a ``<group>``)."""
    name = root.props.get("name")
    return {"graph": circuit(str(name if name is not None else "Circuit"), lambda: declare_sheet(child_elements(root))).ir}


declares("schematic", "group", _declare_group)
