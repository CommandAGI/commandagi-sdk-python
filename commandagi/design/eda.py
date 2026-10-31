"""EDA — components, nets and the board, declared as the circuit op graph (the same nodes the TypeScript SDK
declares: ``eda.part.<signature>``, ``eda.net`` with ``pins.N`` channels, ``eda.board``). Structure only: no
placement optimiser, no router, no DRC; nets are intent, and the ratsnest shows what is unrouted.

    from commandagi.design import circuit, board, component, net, footprints as fp

    def blinker():
        board(width=30, height=20)
        r1 = component(ref="R1", value="330", footprint=fp.chip("0603", "R"), at=(8, 10))
        d1 = component(ref="D1", value="red", footprint=fp.chip("0603", "LED"), at=(16, 10))
        net("LED_A", r1.pin(2), d1.pin("A"))

    result = circuit("Blinker", blinker)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .ir import Declaration, NodeRef, Out, Scope, channels, current_scope, fnv1a, slug, using
from .part_fields import part_field_forms
from .source import here

_SMD = ["F.Cu", "F.Paste", "F.Mask"]
_TH = ["*.Cu", "*.Mask"]


def _smd(number: str, x: float, y: float, w: float, h: float, name: Optional[str] = None) -> Dict[str, Any]:
    p: Dict[str, Any] = {"number": number, "pad": {"type": "smd", "shape": "roundrect", "at": {"x": x, "y": y}, "size": {"w": w, "h": h},
                                                   "layers": _SMD, "roundrectRatio": 0.25}}
    if name:
        p["name"] = name
    return p


_CHIP = {"0402": ("1005", 0.51, 0.54, 0.64), "0603": ("1608", 0.825, 0.8, 0.95), "0805": ("2012", 0.9125, 1.025, 1.4), "1206": ("3216", 1.4625, 1.125, 1.75)}
_CHIP_LIB = {"R": ("Resistor_SMD", "R"), "C": ("Capacitor_SMD", "C"), "L": ("Inductor_SMD", "L"), "LED": ("LED_SMD", "LED"), "D": ("Diode_SMD", "D")}


class footprints:
    """The SDK's copies of common land patterns, named after the KiCad footprints they follow."""

    @staticmethod
    def chip(size: str, kind: str = "R") -> Dict[str, Any]:
        if size not in _CHIP or kind not in _CHIP_LIB:
            raise ValueError(f"no {kind} {size} chip footprint")
        metric, x, w, h = _CHIP[size]
        lib, prefix = _CHIP_LIB[kind]
        polar = kind in ("LED", "D")
        return {"name": f"{lib}:{prefix}_{size}_{metric}Metric",
                "pads": [_smd("1", -x, 0, w, h, "K" if polar else None), _smd("2", x, 0, w, h, "A" if polar else None)], "attr": ["smd"]}

    @staticmethod
    def pin_header(count: int, pitch: float = 2.54) -> Dict[str, Any]:
        if not (1 <= count <= 40):
            raise ValueError("a pin header has 1 to 40 pins")
        p = f"{pitch:.2f}"
        pads = [{"number": str(i + 1), "pad": {"type": "thru_hole", "shape": "rect" if i == 0 else "oval", "at": {"x": 0, "y": round(i * pitch, 6)},
                                               "size": {"w": 1.7, "h": 1.7}, "drill": {"w": 1, "h": 1, "oval": False}, "layers": _TH}} for i in range(count)]
        return {"name": f"Connector_PinHeader_{p}mm:PinHeader_1x{count:02d}_P{p}mm_Vertical", "pads": pads, "attr": ["through_hole"]}

    @staticmethod
    def sot23() -> Dict[str, Any]:
        return {"name": "Package_TO_SOT_SMD:SOT-23", "pads": [_smd("1", -1.1375, -0.95, 1.325, 0.6), _smd("2", -1.1375, 0.95, 1.325, 0.6), _smd("3", 1.1375, 0, 1.325, 0.6)], "attr": ["smd"]}


# What JavaScript's trim takes off: the format's rule. Python's own strip keeps U+FEFF and takes U+001C to U+001F and U+0085.
_JS_SPACE = "\t\n\v\f\r \xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def _pin_label(number: str, name: Optional[str]) -> str:
    t = (name or "").strip(_JS_SPACE)
    return number if not t or t == number or t == "~" else f"{number} {t}"


def part_type_for(pins: Sequence[Dict[str, Any]]) -> str:
    """``eda.part.`` + FNV-1a over each pin's ``id\\0label``, pins joined by ``\\x01`` (the engine's rule)."""
    return "eda.part." + fnv1a("\x01".join(f"{p['id']}\x00{_pin_label(p['number'], p.get('name'))}" for p in pins))


class PartRef(NodeRef):
    def __init__(self, scope: Scope, id: str, ref: str, pins: List[Dict[str, Any]], aliases: Dict[str, str]):
        super().__init__(scope, id)
        self.ref = ref
        self.pins = pins
        self.aliases = aliases

    def pin(self, which: Union[int, str]) -> Out:
        key = str(which)
        alias = self.aliases.get(key.lower())
        for p in self.pins:
            if p["number"] == (alias or key):
                return Out(self.id, p["id"])
        for p in self.pins:
            if p.get("name") and p["name"].lower() == key.lower():
                return Out(self.id, p["id"])
        raise ValueError(f"{self.ref} has no pin {key}")


def _scope(what: str) -> Scope:
    s = current_scope(what)
    if s.meta.get("domain") != "eda":
        raise RuntimeError(f"{what} declares circuit structure and belongs inside circuit()")
    return s


def circuit(name: str, fn: Callable[[], Any], id: Optional[str] = None) -> Declaration:
    s = Scope(id or f"eda:{slug(name)}", {"domain": "eda", "rung": "board", "name": name})
    s.state.update(named={}, links=[], parts={})
    with using(s):
        fn()
        _flush(s)
    ir = s.build()
    if any(n["type"] == "eda.board" for n in ir["nodes"].values()):
        ir["outputs"] = ["board"]
    else:
        ir.pop("outputs", None)
    return Declaration("circuit", ir)


def board(width: float, height: float, origin: Tuple[float, float] = (0, 0), thickness_mm: Optional[float] = None) -> NodeRef:
    s = _scope("board()")
    if "board" in s.nodes:
        raise ValueError("a circuit has one board")
    x0, y0 = origin
    c = [{"x": x0, "y": y0}, {"x": x0 + width, "y": y0}, {"x": x0 + width, "y": y0 + height}, {"x": x0, "y": y0 + height}]
    layers = [(0, "F.Cu", "signal"), (31, "B.Cu", "signal"), (34, "B.Paste", "user"), (35, "F.Paste", "user"), (36, "B.SilkS", "user"),
              (37, "F.SilkS", "user"), (38, "B.Mask", "user"), (39, "F.Mask", "user"), (44, "Edge.Cuts", "user")]
    inputs: Dict[str, Any] = {"layers": [{"ordinal": o, "name": n, "type": t} for o, n, t in layers]}
    if thickness_mm is not None:
        inputs["thicknessMm"] = thickness_mm
    inputs["boardArtwork"] = {"graphics": [{"kind": "line", "id": f"edge-{i + 1}", "points": [a, c[(i + 1) % 4]], "widthMm": 0.1, "layer": "Edge.Cuts"} for i, a in enumerate(c)], "texts": []}
    inputs["stack"] = None
    return s.add("eda.board", inputs, id="board", label="Board")


def component(ref: str, footprint: Dict[str, Any], value: Optional[str] = None, at: Any = None, pin_names: Optional[Dict[str, str]] = None,
              aliases: Optional[Dict[str, str]] = None, symbol: Optional[str] = None, part_number: Optional[str] = None,
              manufacturer: Optional[str] = None, mpn: Optional[str] = None, rating: Optional[str] = None,
              attrs: Optional[Dict[str, str]] = None, suppliers: Optional[List[Dict[str, Any]]] = None,
              alternates: Optional[List[Dict[str, Any]]] = None, datasheet: Optional[str] = None,
              lifecycle: Optional[Dict[str, Any]] = None, compliance: Optional[Dict[str, Any]] = None,
              shipping: Optional[Dict[str, Any]] = None, pinout_verified: Optional[str] = None,
              footprint_verified: Optional[str] = None, package_dimensions: Optional[str] = None) -> PartRef:
    """A part of the circuit. Its engineering data and logistics (``part_number`` … ``package_dimensions``) are KiCad
    property forms, the same as a schematic part's (``part_fields.py``)."""
    s = _scope("component()")
    fields = part_field_forms(f'component(ref="{ref}")', {
        "partNumber": part_number, "manufacturer": manufacturer, "mpn": mpn, "rating": rating, "attrs": attrs,
        "suppliers": suppliers, "alternates": alternates, "datasheet": datasheet, "lifecycle": lifecycle,
        "compliance": compliance, "shipping": shipping, "pinoutVerified": pinout_verified,
        "footprintVerified": footprint_verified, "packageDimensions": package_dimensions})
    pins = []
    for p in footprint["pads"]:
        name = (pin_names or {}).get(p["number"], p.get("name"))
        pin: Dict[str, Any] = {"id": f"p{slug(p['number'])}", "number": p["number"]}
        if name:
            pin["name"] = name
        pin["pad"] = p["pad"]
        pins.append(pin)
    inputs: Dict[str, Any] = {"ref": ref}
    if value is not None:
        inputs["value"] = value
    inputs["footprint"] = footprint["name"]
    if symbol:
        inputs["symbol"] = symbol
    inputs["pins"] = pins
    if at is not None:
        inputs["placement"] = {"x": at[0], "y": at[1], "rot": 0, "side": "top"} if isinstance(at, (tuple, list)) else {"rot": 0, "side": "top", **at}
    if footprint.get("attr"):
        inputs["attr"] = footprint["attr"]
    if fields:
        inputs["foreign"] = fields
    at = here()
    node = s.add(part_type_for(pins), inputs, id=f"part_{ref}", label=ref, meta=None if at is None else {"source": at})
    handle = PartRef(s, node.id, ref, [{k: v for k, v in p.items() if k != "pad"} for p in pins], {k.lower(): v for k, v in (aliases or {}).items()})
    s.state["parts"][ref] = handle
    return handle


def net(name: str, *pins: Out) -> None:
    s = _scope("net()")
    lst = s.state["named"].setdefault(name, [])
    for p in pins:
        if not any(q.node == p.node and q.port == p.port for q in lst):
            lst.append(p)


def connect(a: Out, b: Out) -> None:
    _scope("connect()").state["links"].append((a, b))


def _flush(s: Scope) -> None:
    parent: Dict[str, str] = {}
    pins: Dict[str, Out] = {}

    def key(p: Out) -> str:
        return f"{p.node} {p.port}"

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def add(p: Out) -> None:
        parent.setdefault(key(p), key(p))
        pins[key(p)] = p

    def union(a: Out, b: Out) -> None:
        add(a), add(b)
        ra, rb = find(key(a)), find(key(b))
        if ra != rb:
            parent[rb] = ra

    for lst in s.state["named"].values():
        for p in lst:
            add(p)
        for p in lst[1:]:
            union(lst[0], p)
    for a, b in s.state["links"]:
        union(a, b)
    groups: Dict[str, List[Out]] = {}
    for k in pins:
        groups.setdefault(find(k), []).append(pins[k])
    names: Dict[str, str] = {}
    for name, lst in s.state["named"].items():
        if not lst:
            continue
        r = find(key(lst[0]))
        if r in names and names[r] != name:
            raise ValueError(f"nets {names[r]} and {name} are connected: one net cannot have two names")
        names[r] = name

    def number(p: Out) -> str:
        for x in s.nodes[p.node]["inputs"]["pins"]:
            if x["id"] == p.port:
                return x["number"]
        return p.port

    for r, lst in groups.items():
        first = lst[0]
        name = names.get(r) or f"Net-({s.nodes[first.node]['inputs']['ref']}-Pad{number(first)})"
        s.add("eda.net", channels("pins", lst), id=f"net_{name}", label=name)
