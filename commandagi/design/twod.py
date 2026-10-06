"""2D documents — a drawing, a paint document, a photo and a nest — declared as the nodes the CommandAGI 2D editors
draw and edit. The same elements as the TypeScript SDK's JSX (``commandagi/design`` ``twod.ts``), one call per tag::

    from commandagi.design.twod import drawing, ellipse, group, layer, path, rect

    result = drawing(
        layer(
            rect(x=40, y=40, w=200, h=120, fill="#3b82f6"),
            group(
                ellipse(cx=500, cy=300, rx=60, ry=60, fill="#f59e0b"),
                path(d="M 440 300 L 560 300", stroke_color="#111111", stroke_width=2),
                name="Badge",
            ),
            name="Layer 1",
        ),
        name="Poster", width=800, height=600, background="#ffffff",
    )

The root names the document: ``drawing`` (layers of shapes, ``.draw.py``), ``painting`` (a layer stack of brush
strokes, ``.paint.py``), ``photo`` (pixel layers, adjustments, filters, ``.img.py``) and ``nest`` (flat parts nested on
a sheet, ``.nest.py``).

ONE RULE FOR EVERY TAG: an element is one node, its keywords are the node's inputs (snake_case of the input's name:
``stroke_width`` is ``strokeWidth``), and its positional arguments are the nodes it takes, in order. ``id``, ``label``
and ``disabled`` set the node's own fields. The encodings are the TypeScript SDK's: a top-level group of a drawing is a
``layer``; a path's ``d`` (absolute M L H V C Q Z); a drawn brush stroke's ``[x, y]`` points; a paint stroke's
``[x, y, pressure, t]`` points; a modifier (``blur``, ``transform``, ``fill`` …) wraps the one node it takes; ``clip``
takes its content, then its mask; in a painting or a photo a ``mask`` child of a layer, a stroke or a filter holds the
one layer that masks it. PIXELS ARE NOT CODE: a pixel layer names its image file by relative path (``src``). Each node
carries its element's call in ``meta.source``; a ``mask`` is not a node, so a masked node carries the mask's call in
``meta.sources.mask``. A tag the vocabulary does not have is refused by name.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from .element import Element, child_elements, declares, define
from .ir import NodeRef, Scope, channels, slug, using

_C: Dict[str, Any] = {"holds": "children"}
#: Every tag of the 2D documents: what it holds (absent: a leaf). The TypeScript SDK's ``SIGNATURES.twod``.
SIGNATURES: Dict[str, Dict[str, Any]] = {
    # roots
    "drawing": _C, "painting": _C, "photo": _C, "nest": _C,
    # drawing: groups, shapes, pixels, modifiers
    "layer": _C, "group": _C,
    "rect": {}, "ellipse": {}, "polygon": {}, "path": {}, "text": {}, "brush-stroke": {}, "image": {}, "raster-layer": {},
    "transform": _C, "offset": _C, "array": _C, "mirror": _C, "stroke": _C, "fill": _C, "blur": _C, "levels": _C,
    "threshold": _C, "adjust": _C, "crop": _C, "bucket-fill": _C, "boolean": _C, "clip": _C,
    # painting and photo: layers, masks, adjustments, filters
    "raster": _C, "gradient": _C, "mask": _C,
    "exposure": _C, "curves": _C, "hsl": _C, "vibrance": _C, "colorBalance": _C, "blackWhite": _C, "invert": _C, "posterize": _C, "develop": _C,
    "gaussianBlur": _C, "unsharpMask": _C, "sharpen": _C, "noise": _C,
    # nest
    "sheet": {}, "stock": {}, "options": {}, "part": {},
}

__all__ = ["SIGNATURES", "TWOD_ROOTS", "PHOTO_ADJUSTMENTS", "PHOTO_FILTERS", "subpaths_of", "from_twod",
           *define(globals(), "twod", SIGNATURES)]

#: The roots of a 2D document.
TWOD_ROOTS = ("drawing", "painting", "photo", "nest")


def _meta(el: Element) -> Optional[Dict[str, Any]]:
    return None if el.source is None else {"source": el.source}


def _where(el: Element) -> str:
    name = el.props.get("name")
    return f'<{el.tag} name="{name}">' if isinstance(name, str) else f"<{el.tag}>"


def _plain(v: Any, what: str) -> Any:
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise ValueError(f"{what}: {v} is not a finite number")
        return v
    if isinstance(v, (list, tuple)):
        return [_plain(x, f"{what}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: _plain(x, f"{what}.{k}") for k, x in v.items()}
    raise ValueError(f"{what} is plain data (numbers, strings, arrays, objects)")


def _attrs(el: Element, skip: tuple = ()) -> Dict[str, Any]:
    """An element's attributes as plain data, without ``key`` and the node fields (``id``, ``label``, ``disabled``)."""
    return {k: _plain(v, f"{_where(el)} {k}") for k, v in el.props.items()
            if k not in ("key", "id", "label", "disabled", *skip) and v is not None}


def _add(s: Scope, el: Element, type: str, inputs: Dict[str, Any]) -> NodeRef:
    """Declare ``el`` as one node of ``type``."""
    nid = el.props.get("id")
    if nid is not None and not isinstance(nid, str):
        raise ValueError(f"{_where(el)}: id is a string")
    label = el.props.get("label")
    ref = s.add(type, inputs, id=nid or None, label=label if isinstance(label, str) else None, meta=_meta(el))
    if el.props.get("disabled") is True:
        ref.node["disabled"] = True
    return ref


# ── Drawing ──────────────────────────────────────────────────────────────────────────────────────────────────────

_DRAW_SOURCES = {"rect", "ellipse", "polygon", "path", "text", "brush-stroke"}
#: Modifiers: the one node each takes is its child, on port ``in``.
_DRAW_MODIFIERS = {"transform", "offset", "array", "mirror", "stroke", "fill", "blur", "levels", "threshold", "adjust", "crop", "bucket-fill"}
#: Pixels a drawing places: each names its image file (``src``).
_DRAW_PIXELS = {"image", "raster-layer"}
_DRAW_LATER = {"sketch", "connector", "draw.instance"}
_NUMBER = re.compile(r"[MLHVCQZmlhvcqz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?")


def subpaths_of(d: str, what: str) -> List[Dict[str, Any]]:
    """An SVG path's ``d`` (absolute M L H V C Q Z) as the editor's subpaths."""
    tokens = _NUMBER.findall(d)
    out: List[Dict[str, Any]] = []
    i, cmd, cur = 0, "", {"x": 0, "y": 0}

    def n() -> float:
        nonlocal i
        if i >= len(tokens) or tokens[i].isalpha():
            raise ValueError(f"{what}: d ends where a number is needed")
        v = float(tokens[i])
        i += 1
        return int(v) if v.is_integer() else v

    def pt() -> Dict[str, Any]:
        return {"x": n(), "y": n()}

    def sub() -> Dict[str, Any]:
        if not out:
            raise ValueError(f"{what}: d starts with M")
        return out[-1]

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
        if cmd != cmd.upper():
            raise ValueError(f"{what}: d is written in absolute commands (M L H V C Q Z), not {cmd}")
        if cmd == "M":
            cur = pt()
            out.append({"start": cur, "segs": []})
            cmd = "L"
        elif cmd == "L":
            cur = pt()
            sub()["segs"].append({"to": cur})
        elif cmd == "H":
            cur = {"x": n(), "y": cur["y"]}
            sub()["segs"].append({"to": cur})
        elif cmd == "V":
            cur = {"x": cur["x"], "y": n()}
            sub()["segs"].append({"to": cur})
        elif cmd == "C":
            c1, c2 = pt(), pt()
            cur = pt()
            sub()["segs"].append({"c1": c1, "c2": c2, "to": cur})
        elif cmd == "Q":
            c1 = pt()
            cur = pt()
            sub()["segs"].append({"c1": c1, "to": cur})
        elif cmd == "Z":
            sub()["closed"] = True
            cur = sub()["start"]
        else:
            raise ValueError(f"{what}: d has no command before {tokens[i]}")
    return out


def _pairs(v: Any, what: str) -> List[Dict[str, Any]]:
    if not isinstance(v, list):
        raise ValueError(f"{what} is a list of [x, y] points")
    out = []
    for i, p in enumerate(v):
        if not isinstance(p, list) or len(p) != 2 or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p):
            raise ValueError(f"{what}[{i}] is [x, y]")
        out.append({"x": p[0], "y": p[1]})
    return out


def _drawn(s: Scope, el: Element, top: bool) -> NodeRef:
    t = el.tag
    kids = child_elements(el)
    if t == "layer" and not top:
        raise ValueError(f"{_where(el)}: a <layer> is a child of the <drawing>; inside it, group with <group>")
    if t != "layer" and top:
        raise ValueError(f"<{t}> is inside a <layer> (a drawing's children are its layers)")
    if t in ("layer", "group"):
        children = [_drawn(s, c, False) for c in kids]
        return _add(s, el, "group", {**_attrs(el), **channels("children", children)})
    if t in _DRAW_SOURCES:
        if kids:
            raise ValueError(f"{_where(el)} takes no children")
        a = _attrs(el)
        if t == "path":
            if "subpaths" in a:
                raise ValueError(f"{_where(el)}: a path is written with d (an SVG path), not subpaths")
            if "d" in a:
                if not isinstance(a["d"], str):
                    raise ValueError(f"{_where(el)}: d is an SVG path string")
                a["subpaths"] = subpaths_of(a.pop("d"), _where(el))
        if t == "brush-stroke" and "points" in a:
            a["points"] = _pairs(a["points"], f"{_where(el)} points")
        return _add(s, el, t, a)
    if t in _DRAW_PIXELS:
        if kids:
            raise ValueError(f"{_where(el)} takes no children")
        if el.props.get("src") is None:
            raise ValueError(f'{_where(el)}: src names its image file by relative path ("photo.png")')
        return _add(s, el, t, {**_attrs(el, ("src",)), "__asset": _asset(el.props["src"], el)})
    if t in _DRAW_MODIFIERS:
        if len(kids) != 1:
            raise ValueError(f"{_where(el)} wraps the one node it changes")
        return _add(s, el, t, {**_attrs(el), "in": _drawn(s, kids[0], False)})
    if t == "boolean":
        return _add(s, el, t, {**_attrs(el), **channels("shapes", [_drawn(s, c, False) for c in kids])})
    if t == "clip":
        if len(kids) != 2:
            raise ValueError(f"{_where(el)} takes its content, then its mask")
        content = _drawn(s, kids[0], False)
        masked_by = _drawn(s, kids[1], False)
        return _add(s, el, t, {**_attrs(el), "content": content, "mask": masked_by})
    if t in _DRAW_LATER:
        raise ValueError(f"<{t}> is not declared in code yet (a drawing in code holds shapes, images, groups and modifiers)")
    raise ValueError(f"<{t}> is not read in a drawing (see commandagi.design.twod)")


def _drawing(root: Element, name: str) -> Dict[str, Any]:
    a = _attrs(root, ("name", "width", "height", "background"))
    if a:
        raise ValueError(f"<drawing>: {next(iter(a))} is not read (a drawing has name, width, height, background)")
    # A drawing with no name of its own declares none; the file's name only names the graph.
    own = root.props.get("name") if isinstance(root.props.get("name"), str) else None
    m: Dict[str, Any] = {"name": own} if own is not None else {}
    for k in ("width", "height", "background"):
        if root.props.get(k) is not None:
            m[k] = _plain(root.props[k], f"<drawing> {k}")
    s = Scope(f"draw:{slug(own if own is not None else name)}", m)
    with using(s):
        layers = [_drawn(s, c, True) for c in child_elements(root)]
        comp = s.add("composite", {**({"background": m["background"]} if "background" in m else {}), **channels("layers", layers)},
                     id="composite", label="Output", meta=_meta(root))
        s.output(comp)
    return s.build()


# ── Paint and photo: a layer stack ───────────────────────────────────────────────────────────────────────────────

#: The fields every layer of a stack carries (a chain's top stands in for its layer in the stack).
_COMMON = ("name", "visible", "opacity", "blend", "clip", "locked")
_COMMON_DEFAULTS = {"name": "Layer", "visible": True, "opacity": 1, "blend": "normal"}
PHOTO_ADJUSTMENTS = ("exposure", "levels", "curves", "hsl", "vibrance", "colorBalance", "blackWhite", "invert", "threshold", "posterize", "develop")
PHOTO_FILTERS = ("gaussianBlur", "unsharpMask", "sharpen", "noise")
_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp"}


def _asset(src: Any, el: Element) -> Dict[str, Any]:
    """A pixel layer's ``src``: the image file it names, as the document's own file names it."""
    if not isinstance(src, str) or not src or src.startswith("data:"):
        raise ValueError(f'{_where(el)}: src names an image file by relative path ("scan.png"); pixels are not written in code')
    if src.startswith("/") or re.match(r"^[a-z]+:", src, re.I):
        raise ValueError(f"{_where(el)}: src is a path relative to this file, not {src}")
    ext = src.rsplit(".", 1)[-1].lower()
    return {"kind": "file", "$file": src, **({"mime": _MIME[ext]} if ext in _MIME else {})}


def _stroke_points(v: Any, what: str) -> List[Dict[str, Any]]:
    if not isinstance(v, list):
        raise ValueError(f"{what} is a list of [x, y, pressure, t] points")
    out = []
    for i, p in enumerate(v):
        if not isinstance(p, list) or len(p) not in (4, 6) or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p):
            raise ValueError(f"{what}[{i}] is [x, y, pressure, t] or [x, y, pressure, t, tiltX, tiltY]")
        q = {"x": p[0], "y": p[1], "pressure": p[2], "t": p[3]}
        if len(p) == 6:
            q.update(tiltX=p[4], tiltY=p[5])
        out.append(q)
    return out


def _adjustment_layer(el: Element, node_type: str) -> tuple:
    """An adjustment tag as a layer: the layer's own fields, and the rest as its ``adjustment``."""
    common: Dict[str, Any] = {}
    adjustment: Dict[str, Any] = {"type": el.tag}
    for k, v in _attrs(el).items():
        (common if k in _COMMON else adjustment)[k] = v
    return node_type, {**common, "adjustment": adjustment}


def _paint_layer(el: Element) -> Optional[tuple]:
    if el.tag == "layer":
        a = _attrs(el, ("src",))
        if el.props.get("src") is not None:
            a["__asset"] = _asset(el.props["src"], el)
        return "paint.layer", a
    if el.tag in ("fill", "group"):
        return f"paint.{el.tag}", _attrs(el)
    if el.tag in PHOTO_ADJUSTMENTS:
        return _adjustment_layer(el, "paint.adjust")
    return None


def _paint_chain(el: Element) -> Optional[Dict[str, Any]]:
    if el.tag != "stroke":
        return None
    a = _attrs(el)
    for k in _COMMON:
        if k in a:
            raise ValueError(f"{_where(el)}: {k} is the layer's (write it on the layer the stroke is painted on)")
    if "points" in a:
        a["points"] = _stroke_points(a["points"], f"{_where(el)} points")
    return a


def _photo_layer(el: Element) -> Optional[tuple]:
    if el.tag == "raster":
        a = _attrs(el, ("src",))
        if el.props.get("src") is not None:
            a["__asset"] = _asset(el.props["src"], el)
        return "photo.raster", a
    if el.tag in ("fill", "gradient", "group"):
        return f"photo.{el.tag}", _attrs(el)
    if el.tag in PHOTO_ADJUSTMENTS:
        return _adjustment_layer(el, "photo.adjust")
    return None


def _photo_chain(el: Element) -> Optional[Dict[str, Any]]:
    if el.tag not in PHOTO_FILTERS:
        return None
    a = _attrs(el)
    for k in _COMMON:
        if k in a:
            raise ValueError(f"{_where(el)}: {k} is the layer's (write it on the layer it filters)")
    return {"filter": {"type": el.tag, **a}}


#: Each stack: its root tag, its chain's node type, and how a layer and a chain member read.
_STACKS = {
    "paint": ("painting", "paint.stroke", _paint_layer, _paint_chain),
    "photo": ("photo", "photo.filter", _photo_layer, _photo_chain),
}


def _mask_of(s: Scope, prefix: str, el: Element) -> tuple:
    """A layer's (or a stroke's, or a filter's) ``mask``: the one stack layer it holds, declared outside the stack and
    wired to the node's ``mask`` port, and the mask element's call (the masked node's ``meta.sources.mask``)."""
    masks = [c for c in child_elements(el) if c.tag == "mask"]
    if not masks:
        return {}, None
    if len(masks) > 1:
        raise ValueError(f"{_where(el)} has one <mask>")
    m = masks[0]
    if _attrs(m):
        raise ValueError(f"<mask> in {_where(el)} has no attributes (write them on the layer it holds)")
    held = child_elements(m)
    if len(held) != 1:
        raise ValueError(f"<mask> in {_where(el)} holds one layer")
    return {"mask": _stack(s, prefix, held)[0]}, m.source


def _add_masked(s: Scope, prefix: str, el: Element, type: str, inputs: Dict[str, Any]) -> NodeRef:
    """Declare ``el`` as one node of ``type``, masked by its ``mask`` when it has one."""
    mask_inputs, at = _mask_of(s, prefix, el)
    ref = _add(s, el, type, {**inputs, **mask_inputs})
    if at is not None:
        ref.node["meta"] = {**(ref.node.get("meta") or {}), "sources": {"mask": at}}
    return ref


def _stack(s: Scope, prefix: str, children: List[Element]) -> List[NodeRef]:
    root, chain_type, layer_of, chain_of = _STACKS[prefix]
    slots = []
    for el in children:
        layer = layer_of(el)
        if layer is None:
            if chain_of(el) is not None:
                raise ValueError(f"{_where(el)} is painted on a layer: write it inside one")
            raise ValueError(f"<{el.tag}> is not read in a {root} (see commandagi.design.twod)")
        kind, inputs = layer
        stack: List[Element] = []
        chain: List[Element] = []
        for c in child_elements(el):
            if c.tag != "mask":
                (chain if chain_of(c) is not None else stack).append(c)
        if stack and kind != f"{prefix}.group":
            raise ValueError(f"{_where(el)}: only a <group> holds layers")
        inner = _stack(s, prefix, stack) if kind == f"{prefix}.group" else []
        top = _add_masked(s, prefix, el, kind, {**inputs, **channels("layers", inner)})
        # Each chain member carries the layer's fields: the stack reads them off whichever member is on top.
        carried = dict(_COMMON_DEFAULTS)
        carried.update({k: inputs[k] for k in _COMMON if inputs.get(k) is not None})
        for c in chain:
            top = _add_masked(s, prefix, c, chain_type, {**carried, **chain_of(c), "src": top})
        slots.append(top)
    return slots


def _stack_document(prefix: str, root: Element, name: str) -> Dict[str, Any]:
    a = _attrs(root)
    for k in a:
        if k not in ("name", "width", "height", "background", "dpi"):
            raise ValueError(f"<{root.tag}>: {k} is not read (it has name, width, height, background, dpi)")
    title = a["name"] if isinstance(a.get("name"), str) else name
    s = Scope(f"{prefix}:{slug(title)}", {"domain": prefix, "name": title})
    with using(s):
        layers = _stack(s, prefix, child_elements(root))
        doc = s.add(f"{prefix}.doc", {**a, **channels("layers", layers)}, id="doc", meta=_meta(root))
        s.output(doc)
    return s.build()


# ── Nest ─────────────────────────────────────────────────────────────────────────────────────────────────────────

_NEST_ONE = ("sheet", "stock", "options")


def _nest(root: Element, name: str) -> Dict[str, Any]:
    a = _attrs(root, ("name",))
    for k in a:
        if k not in ("safeZMm", "overrides"):
            raise ValueError(f"<nest>: {k} is not read (it has safeZMm, overrides)")
    title = root.props["name"] if isinstance(root.props.get("name"), str) else name
    s = Scope(f"nest:{slug(title)}", {"domain": "nest", "name": title})
    with using(s):
        one: Dict[str, NodeRef] = {}
        parts: List[NodeRef] = []
        for el in child_elements(root):
            if el.tag in _NEST_ONE:
                if el.tag in one:
                    raise ValueError(f"a nest has one <{el.tag}>")
                one[el.tag] = _add(s, el, f"nest.{el.tag}", _attrs(el))
            elif el.tag == "part":
                if not isinstance(el.props.get("id"), str):
                    raise ValueError(f"{_where(el)}: a part has an id (the name its placements and overrides use)")
                parts.append(_add(s, el, "nest.part", _attrs(el)))
            else:
                raise ValueError(f"<{el.tag}> is not read in a nest (it has <sheet>, <stock>, <options>, <part>)")
        for k in _NEST_ONE:
            if k not in one:
                raise ValueError(f"a nest needs its <{k}>")
        doc = s.add("nest.doc", {**a, **one, **channels("parts", parts)}, id="nest", meta=_meta(root))
        s.output(doc)
    return s.build()


def from_twod(root: Element, name: str = "Drawing") -> Dict[str, Any]:
    """The op graph a 2D document's root element declares."""
    if root.tag == "drawing":
        return _drawing(root, name)
    if root.tag == "painting":
        return _stack_document("paint", root, name)
    if root.tag == "photo":
        return _stack_document("photo", root, name)
    if root.tag == "nest":
        return _nest(root, name)
    raise ValueError(f"<{root.tag}> is not a 2D document ({', '.join(TWOD_ROOTS)})")


for _root in TWOD_ROOTS:
    declares("twod", _root, lambda root, stem: {"graph": from_twod(root, stem)})
