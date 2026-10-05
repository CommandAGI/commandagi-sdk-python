"""2D documents — a drawing, a paint document, a photo and a nest — declared as the nodes the CommandAGI 2D editors
draw and edit. The same declarations as the TypeScript SDK's ``commandagi/design`` ``twod.ts`` (its JSX), written as
calls::

    from commandagi.design import twod

    result = twod.drawing(
        twod.layer(
            twod.rect(x=40, y=40, w=200, h=120, fill="#3b82f6"),
            twod.group(twod.ellipse(cx=500, cy=300, rx=60, ry=60, fill="#f59e0b"), name="Badge"),
            name="Layer 1",
        ),
        name="Poster", width=800, height=600, background="#ffffff",
    )

One rule for every element: an element is one node, its keyword arguments are the node's inputs by their own names,
and its positional arguments are the nodes it takes, in order. ``id``, ``label`` and ``disabled`` set the node's own
fields. A keyword that is a Python word takes a trailing underscore (``from_`` for a gradient's ``from``). The
encodings are the TypeScript SDK's: a path's ``d`` (absolute M L H V C Q Z), a drawn brush stroke's ``[x, y]``
points, a paint stroke's ``[x, y, pressure, t]`` points, and a pixel layer's ``src`` (its image file by relative path;
pixels are never declared). ``drawing``, ``painting``, ``photo`` and ``nest`` return the declaration.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .ir import Declaration, NodeRef, Scope, channels, slug, using


class Element:
    """One element of a 2D document: its tag, its attributes and the elements it takes."""

    def __init__(self, tag: str, children: tuple, props: Dict[str, Any]):
        self.tag = tag
        self.children: List[Element] = []
        for c in children:
            if isinstance(c, (list, tuple)):
                self.children.extend(c)
            elif c is not None:
                self.children.append(c)
        for c in self.children:
            if not isinstance(c, Element):
                raise TypeError(f"<{tag}> takes elements, not {type(c).__name__}")
        self.props = {k[:-1] if k.endswith("_") and not k.startswith("_") else k: v for k, v in props.items()}

    def where(self) -> str:
        name = self.props.get("name")
        return f'<{self.tag} name="{name}">' if isinstance(name, str) else f"<{self.tag}>"


def element(tag: str, *children: Any, **props: Any) -> Element:
    """An element of any tag (the named helpers below are this, by tag)."""
    return Element(tag, children, props)


def _tag(tag: str):
    def make(*children: Any, **props: Any) -> Element:
        return Element(tag, children, props)

    make.__name__ = tag.replace("-", "_")
    make.__doc__ = f"A <{tag}> element."
    return make


def _attrs(el: Element, skip: tuple = ()) -> Dict[str, Any]:
    return {k: v for k, v in el.props.items() if k not in ("id", "label", "disabled", *skip) and v is not None}


def _add(s: Scope, el: Element, type: str, inputs: Dict[str, Any]) -> NodeRef:
    ref = s.add(type, inputs, id=el.props.get("id"), label=el.props.get("label"))
    if el.props.get("disabled") is True:
        ref.node["disabled"] = True
    return ref


# ── Drawing ──────────────────────────────────────────────────────────────────────────────────────────────────────

_DRAW_SOURCES = {"rect", "ellipse", "polygon", "path", "text", "brush-stroke"}
_DRAW_MODIFIERS = {"transform", "offset", "array", "mirror", "stroke", "fill", "blur", "levels", "threshold", "adjust", "crop", "bucket-fill"}
# Pixels a drawing places: each names its image file (``src``).
_DRAW_PIXELS = {"image", "raster-layer"}
_DRAW_LATER = {"sketch", "connector", "draw.instance"}


def subpaths_of(d: str, what: str) -> List[Dict[str, Any]]:
    """An SVG path's ``d`` (absolute M L H V C Q Z) as the editor's subpaths."""
    tokens = re.findall(r"[MLHVCQZmlhvcqz]|-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?", d)
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
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{what} is a list of [x, y] points")
    out = []
    for i, p in enumerate(v):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError(f"{what}[{i}] is [x, y]")
        out.append({"x": p[0], "y": p[1]})
    return out


def _drawn(s: Scope, el: Element, top: bool) -> NodeRef:
    t = el.tag
    if t == "layer" and not top:
        raise ValueError(f"{el.where()}: a <layer> is a child of the <drawing>; inside it, group with <group>")
    if t != "layer" and top:
        raise ValueError(f"<{t}> is inside a <layer> (a drawing's children are its layers)")
    if t in ("layer", "group"):
        kids = [_drawn(s, c, False) for c in el.children]
        return _add(s, el, "group", {**_attrs(el), **channels("children", kids)})
    if t in _DRAW_SOURCES:
        if el.children:
            raise ValueError(f"{el.where()} takes no children")
        a = _attrs(el)
        if t == "path":
            if "subpaths" in a:
                raise ValueError(f"{el.where()}: a path is written with d (an SVG path), not subpaths")
            if "d" in a:
                a = {("subpaths" if k == "d" else k): (subpaths_of(v, el.where()) if k == "d" else v) for k, v in a.items()}
        if t == "brush-stroke" and "points" in a:
            a["points"] = _pairs(a["points"], f"{el.where()} points")
        return _add(s, el, t, a)
    if t in _DRAW_PIXELS:
        if el.children:
            raise ValueError(f"{el.where()} takes no children")
        if "src" not in el.props:
            raise ValueError(f'{el.where()}: src names its image file by relative path ("photo.png")')
        return _add(s, el, t, {**_attrs(el, ("src",)), "__asset": _asset(el.props["src"], el)})
    if t in _DRAW_MODIFIERS:
        if len(el.children) != 1:
            raise ValueError(f"{el.where()} wraps the one node it changes")
        return _add(s, el, t, {**_attrs(el), "in": _drawn(s, el.children[0], False)})
    if t == "boolean":
        return _add(s, el, t, {**_attrs(el), **channels("shapes", [_drawn(s, c, False) for c in el.children])})
    if t == "clip":
        if len(el.children) != 2:
            raise ValueError(f"{el.where()} takes its content, then its mask")
        content, mask = (_drawn(s, c, False) for c in el.children)
        return _add(s, el, t, {**_attrs(el), "content": content, "mask": mask})
    if t in _DRAW_LATER:
        raise ValueError(f"<{t}> is not declared in code yet (a drawing in code holds shapes, groups and modifiers)")
    raise ValueError(f"<{t}> is not read in a drawing (see commandagi.design.twod)")


def drawing(*children: Any, name: Optional[str] = None, **props: Any) -> Declaration:
    """A drawing: its layers, each holding shapes, images, groups and modifiers."""
    root = Element("drawing", children, {**props, **({"name": name} if name is not None else {})})
    extra = [k for k in root.props if k not in ("name", "width", "height", "background")]
    if extra:
        raise ValueError(f"<drawing>: {extra[0]} is not read (a drawing has name, width, height, background)")
    # A drawing with no name of its own declares none: the file's name only names the graph.
    meta: Dict[str, Any] = {"name": name} if name is not None else {}
    for k in ("width", "height", "background"):
        if root.props.get(k) is not None:
            meta[k] = root.props[k]
    s = Scope(f"draw:{slug(name or 'Drawing')}", meta)
    with using(s):
        layers = [_drawn(s, c, True) for c in root.children]
        comp = s.add("composite", {**({"background": meta["background"]} if "background" in meta else {}), **channels("layers", layers)},
                     id="composite", label="Output")
        s.output(comp)
    return Declaration("drawing", s.build())


# ── Paint and photo: a layer stack ───────────────────────────────────────────────────────────────────────────────

_COMMON = ("name", "visible", "opacity", "blend", "clip", "locked")
_COMMON_DEFAULTS = {"name": "Layer", "visible": True, "opacity": 1, "blend": "normal"}
PHOTO_ADJUSTMENTS = ("exposure", "levels", "curves", "hsl", "vibrance", "colorBalance", "blackWhite", "invert", "threshold", "posterize")
PHOTO_FILTERS = ("gaussianBlur", "unsharpMask", "sharpen", "noise")
_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp"}


def _asset(src: Any, el: Element) -> Dict[str, Any]:
    if not isinstance(src, str) or not src or src.startswith("data:"):
        raise ValueError(f'{el.where()}: src names an image file by relative path ("scan.png"); pixels are not written in code')
    if src.startswith("/") or re.match(r"^[a-z]+:", src, re.I):
        raise ValueError(f"{el.where()}: src is a path relative to this file, not {src}")
    ext = src.rsplit(".", 1)[-1].lower()
    return {"kind": "file", "$file": src, **({"mime": _MIME[ext]} if ext in _MIME else {})}


def _stroke_points(v: Any, what: str) -> List[Dict[str, Any]]:
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{what} is a list of [x, y, pressure, t] points")
    out = []
    for i, p in enumerate(v):
        if not isinstance(p, (list, tuple)) or len(p) not in (4, 6):
            raise ValueError(f"{what}[{i}] is [x, y, pressure, t] or [x, y, pressure, t, tiltX, tiltY]")
        q = {"x": p[0], "y": p[1], "pressure": p[2], "t": p[3]}
        if len(p) == 6:
            q.update(tiltX=p[4], tiltY=p[5])
        out.append(q)
    return out


def _paint_layer(el: Element):
    if el.tag == "layer":
        a = _attrs(el, ("src",))
        if el.props.get("src") is not None:
            a["__asset"] = _asset(el.props["src"], el)
        return "paint.layer", a
    if el.tag in ("fill", "group"):
        return f"paint.{el.tag}", _attrs(el)
    return None


def _paint_chain(el: Element):
    if el.tag != "stroke":
        return None
    a = _attrs(el)
    for k in _COMMON:
        if k in a:
            raise ValueError(f"{el.where()}: {k} is the layer's (write it on the layer the stroke is painted on)")
    if "points" in a:
        a["points"] = _stroke_points(a["points"], f"{el.where()} points")
    return a


def _photo_layer(el: Element):
    if el.tag == "raster":
        a = _attrs(el, ("src",))
        if el.props.get("src") is not None:
            a["__asset"] = _asset(el.props["src"], el)
        return "photo.raster", a
    if el.tag in ("fill", "gradient", "group"):
        return f"photo.{el.tag}", _attrs(el)
    if el.tag in PHOTO_ADJUSTMENTS:
        common: Dict[str, Any] = {}
        adjustment: Dict[str, Any] = {"type": el.tag}
        for k, v in _attrs(el).items():
            (common if k in _COMMON else adjustment)[k] = v
        return "photo.adjust", {**common, "adjustment": adjustment}
    return None


def _photo_chain(el: Element):
    if el.tag not in PHOTO_FILTERS:
        return None
    a = _attrs(el)
    for k in _COMMON:
        if k in a:
            raise ValueError(f"{el.where()}: {k} is the layer's (write it on the layer it filters)")
    return {"filter": {"type": el.tag, **a}}


_STACKS = {
    "paint": ("painting", "paint.stroke", _paint_layer, _paint_chain),
    "photo": ("photo", "photo.filter", _photo_layer, _photo_chain),
}


def _mask_of(s: Scope, prefix: str, el: Element) -> Dict[str, Any]:
    """A layer's (or a stroke's, or a filter's) ``mask(...)``: the one layer it holds, wired to the node's mask port."""
    masks = [c for c in el.children if c.tag == "mask"]
    if not masks:
        return {}
    if len(masks) > 1:
        raise ValueError(f"{el.where()} has one <mask>")
    m = masks[0]
    if _attrs(m):
        raise ValueError(f"<mask> in {el.where()} has no attributes (write them on the layer it holds)")
    if len(m.children) != 1:
        raise ValueError(f"<mask> in {el.where()} holds one layer")
    return {"mask": _stack(s, prefix, m.children)[0]}


def _stack(s: Scope, prefix: str, children: List[Element]) -> List[NodeRef]:
    root, chain_type, layer_of, chain_of = _STACKS[prefix]
    slots = []
    for el in children:
        layer = layer_of(el)
        if layer is None:
            if chain_of(el) is not None:
                raise ValueError(f"{el.where()} is painted on a layer: write it inside one")
            raise ValueError(f"<{el.tag}> is not read in a {root} (see commandagi.design.twod)")
        type_, inputs = layer
        stack = [c for c in el.children if c.tag != "mask" and chain_of(c) is None]
        chain = [c for c in el.children if c.tag != "mask" and chain_of(c) is not None]
        if stack and type_ != f"{prefix}.group":
            raise ValueError(f"{el.where()}: only a <group> holds layers")
        inner = _stack(s, prefix, stack) if type_ == f"{prefix}.group" else []
        top = _add(s, el, type_, {**inputs, **channels("layers", inner), **_mask_of(s, prefix, el)})
        carried = dict(_COMMON_DEFAULTS)
        carried.update({k: inputs[k] for k in _COMMON if k in inputs})
        for c in chain:
            top = _add(s, c, chain_type, {**carried, **chain_of(c), "src": top, **_mask_of(s, prefix, c)})
        slots.append(top)
    return slots


def _stack_document(prefix: str, children: tuple, name: Optional[str], props: Dict[str, Any]) -> Declaration:
    root = Element(_STACKS[prefix][0], children, {**props, **({"name": name} if name is not None else {})})
    a = _attrs(root)
    for k in a:
        if k not in ("name", "width", "height", "background", "dpi"):
            raise ValueError(f"<{root.tag}>: {k} is not read (it has name, width, height, background, dpi)")
    title = a.get("name") if isinstance(a.get("name"), str) else ("Painting" if prefix == "paint" else "Photo")
    s = Scope(f"{prefix}:{slug(title)}", {"domain": prefix, "name": title})
    with using(s):
        layers = _stack(s, prefix, root.children)
        doc = s.add(f"{prefix}.doc", {**a, **channels("layers", layers)}, id="doc")
        s.output(doc)
    return Declaration(prefix, s.build())


def painting(*children: Any, name: Optional[str] = None, **props: Any) -> Declaration:
    """A paint document: its layer stack, bottom first, each layer's strokes inside it."""
    return _stack_document("paint", children, name, props)


def photo(*children: Any, name: Optional[str] = None, **props: Any) -> Declaration:
    """A photo: pixel layers naming their image files, adjustments, each raster's filters, and masks."""
    return _stack_document("photo", children, name, props)


# ── Nest ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def nest(*children: Any, name: Optional[str] = None, **props: Any) -> Declaration:
    """A nest: its sheet, stock, options and parts."""
    root = Element("nest", children, props)
    a = _attrs(root, ("name",))
    for k in a:
        if k not in ("safeZMm", "overrides"):
            raise ValueError(f"<nest>: {k} is not read (it has safeZMm, overrides)")
    title = name or "Nest"
    s = Scope(f"nest:{slug(title)}", {"domain": "nest", "name": title})
    with using(s):
        one: Dict[str, NodeRef] = {}
        parts: List[NodeRef] = []
        for el in root.children:
            if el.tag in ("sheet", "stock", "options"):
                if el.tag in one:
                    raise ValueError(f"a nest has one <{el.tag}>")
                one[el.tag] = _add(s, el, f"nest.{el.tag}", _attrs(el))
            elif el.tag == "part":
                if not isinstance(el.props.get("id"), str):
                    raise ValueError(f"{el.where()}: a part has an id (the name its placements and overrides use)")
                parts.append(_add(s, el, "nest.part", _attrs(el)))
            else:
                raise ValueError(f"<{el.tag}> is not read in a nest (it has <sheet>, <stock>, <options>, <part>)")
        for k in ("sheet", "stock", "options"):
            if k not in one:
                raise ValueError(f"a nest needs its <{k}>")
        doc = s.add("nest.doc", {**a, **one, **channels("parts", parts)}, id="nest")
        s.output(doc)
    return Declaration("nest", s.build())


# The elements, by tag. Draw and paint share some tags (`fill`, `group`, `layer`): an element is read by the document
# it is in.
layer = _tag("layer")
group = _tag("group")
rect = _tag("rect")
ellipse = _tag("ellipse")
polygon = _tag("polygon")
path = _tag("path")
text = _tag("text")
brush_stroke = _tag("brush-stroke")
image = _tag("image")
raster_layer = _tag("raster-layer")
transform = _tag("transform")
offset = _tag("offset")
array = _tag("array")
mirror = _tag("mirror")
stroke = _tag("stroke")
fill = _tag("fill")
blur = _tag("blur")
crop = _tag("crop")
boolean = _tag("boolean")
clip = _tag("clip")
raster = _tag("raster")
gradient = _tag("gradient")
mask = _tag("mask")
sheet = _tag("sheet")
stock = _tag("stock")
options = _tag("options")
part = _tag("part")
