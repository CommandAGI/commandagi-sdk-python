"""A video or a song, declared as the media editors' own documents — the same nodes the TypeScript SDK's
``media.ts`` declares from JSX (``.vid.tsx``, ``.mus.tsx``), from elements built in Python::

    from commandagi.design.media import video, track, clip, title, song, synth, note

    result = video(
        track(clip(src="media/sky.png", start=0, duration=3), title(text="Hello", start=0, duration=2), name="V1"),
        track(clip(src="media/tone.wav", start=0, in_=0.5, out=2.5, volume=0.8), name="A1", kind="audio"),
        name="Balcony", width=1280, height=720, fps=30,
    )

    result = song(
        track(synth(wave="triangle"), clip(note(pitch="C4", start=0, duration=1), name="Keys 1", start=0, length=4), name="Keys"),
        name="Loop", tempo=120, timeSignature="4/4", bars=8,
    )

An element's props are the JSX attributes, spelled the same (``in_`` is ``in``, which Python reserves). Media
files are named by path relative to the file, never inlined. Times on a video's timeline are seconds; in a song,
beats. Anything the vocabulary cannot say is refused by name.
"""
from __future__ import annotations

import copy
import json
import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ir import Declaration, slug

MEDIA_ROOTS = ("video", "song")


class Element:
    """One declared element: its tag, its props and its children (what JSX makes)."""

    def __init__(self, type: str, props: Dict[str, Any], children: List[Any]):
        self.type = type
        self.props = props
        self.children = children

    def __repr__(self) -> str:
        return f"<{self.type} {self.props}>"


def _flat(children: Any) -> List[Element]:
    out: List[Element] = []
    for c in children if isinstance(children, (list, tuple)) else [children]:
        if c is None or isinstance(c, bool):
            continue
        if isinstance(c, (list, tuple)):
            out.extend(_flat(c))
        elif isinstance(c, Element):
            out.append(c)
        else:
            raise ValueError("an element's children are elements")
    return out


def _tag(name: str) -> Callable[..., Element]:
    def make(*children: Any, **props: Any) -> Element:
        if "in_" in props:
            props["in"] = props.pop("in_")
        return Element(name, props, _flat(list(children)))

    make.__name__ = name
    return make


video = _tag("video")
track = _tag("track")
clip = _tag("clip")
title = _tag("title")
transition = _tag("transition")
effect = _tag("effect")
keyframe = _tag("keyframe")
marker = _tag("marker")
song = _tag("song")
synth = _tag("synth")
gain = _tag("gain")
filter_ = _tag("filter")
delay = _tag("delay")
reverb = _tag("reverb")
eq = _tag("eq")
note = _tag("note")


def _where(el: Element) -> str:
    for k in ("name", "src", "text"):
        if isinstance(el.props.get(k), str):
            return f'<{el.type} {k}="{el.props[k]}">'
    return f"<{el.type}>"


def _refuse_unknown(el: Element, allowed: List[str]) -> None:
    for k in el.props:
        if k not in allowed:
            raise ValueError(f"{_where(el)}: prop {k} is not read on a <{el.type}>")


def _num(el: Element, prop: str, lo: Optional[float] = None, hi: Optional[float] = None) -> Optional[float]:
    v = el.props.get(prop)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{_where(el)}: {prop} is a number, not {json.dumps(v)}")
    if lo is not None and v < lo:
        raise ValueError(f"{_where(el)}: {prop} is at least {lo}, not {v}")
    if hi is not None and v > hi:
        raise ValueError(f"{_where(el)}: {prop} is at most {hi}, not {v}")
    return v


def _str(el: Element, prop: str, one_of: Optional[Tuple[str, ...]] = None) -> Optional[str]:
    v = el.props.get(prop)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(f"{_where(el)}: {prop} is text, not {json.dumps(v)}")
    if one_of and v not in one_of:
        raise ValueError(f"{_where(el)}: {prop} is one of {', '.join(one_of)}, not \"{v}\"")
    return v


def _bool(el: Element, prop: str) -> Optional[bool]:
    v = el.props.get(prop)
    if v is None:
        return None
    if not isinstance(v, bool):
        raise ValueError(f"{_where(el)}: {prop} is True or False, not {json.dumps(v)}")
    return v


def _or(v: Any, d: Any) -> Any:
    return d if v is None else v


def _ids() -> Callable[[str], str]:
    taken: set = set()

    def make(base: str) -> str:
        b = slug(base)
        i, n = b, 2
        while i in taken:
            i = f"{b}_{n}"
            n += 1
        taken.add(i)
        return i

    return make


def _node(id: str, type: str, inputs: Dict[str, Any], label: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    n: Dict[str, Any] = {"id": id, "type": type}
    if label is not None:
        n["label"] = label
    n["inputs"] = inputs
    if meta:
        n["meta"] = meta
    return n


def _wire(node: str, port: str) -> Dict[str, Any]:
    return {"wire": {"node": node, "port": port}}


# ── Video ────────────────────────────────────────────────────────────────────────────────────────────────────────

_EXT = {**{e: "video" for e in ("mp4", "webm", "mov", "mkv", "m4v", "ogv")},
        **{e: "audio" for e in ("wav", "mp3", "ogg", "oga", "m4a", "flac", "aac", "opus")},
        **{e: "image" for e in ("png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "svg")}}


def media_kind(src: str) -> Optional[str]:
    m = re.search(r"\.([A-Za-z0-9]+)$", src)
    return _EXT.get(m.group(1).lower()) if m else None


BLEND_MODES = ("normal", "add", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light",
               "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity")
EASINGS = ("linear", "easeIn", "easeOut", "easeInOut", "hold")
TRANSITIONS = ("none", "cut", "crossDissolve", "fadeToBlack", "fadeToWhite", "dipToColor", "wipeLeft", "wipeRight", "wipeUp",
               "wipeDown", "diagonalWipe", "barnDoors", "iris", "diamond", "clockWipe", "pixelDissolve", "pushLeft", "pushRight",
               "slideUp", "slideDown", "zoomIn", "zoomBlur", "glitch", "kineticMatte", "shapeWipe")
EFFECT_TYPES = ("brightnessContrast", "saturation", "hueRotate", "gaussianBlur", "sharpen", "pixelate", "chromaKey", "twist", "wave",
                "mirror", "vignette", "glow", "grayscale", "sepia", "invert", "posterize", "edges", "chromaticAberration", "bulge",
                "duotone", "colorWheels", "mask")
ANIMATABLE = ("opacity", "volume", "transform.x", "transform.y", "transform.scaleX", "transform.scaleY", "transform.rotation")
CLIP_TRANSFORM = {"x": 0, "y": 0, "scaleX": 1, "scaleY": 1, "rotation": 0, "anchorX": 0.5, "anchorY": 0.5}
CLIP_COLOR = {"exposure": 0, "contrast": 0, "saturation": 0, "temperature": 0, "brightness": 0, "hue": 0}
TITLE_TEXT = {"text": "Title", "fontFamily": "Inter, system-ui, sans-serif", "fontSize": 96, "color": "#ffffff", "bold": True,
              "italic": False, "align": "center", "background": "transparent", "strokeColor": "#000000", "strokeWidth": 0}
VIDEO_SETTINGS = {"width": 1920, "height": 1080, "fps": 30, "sampleRate": 48000, "background": "#000000"}
_TRACK_HEIGHT = {"video": 64, "audio": 48}
_CLIP_PROPS = ["name", "start", "duration", "in", "out", "speed", "opacity", "volume", "blendMode", "fitMode", *CLIP_TRANSFORM, *CLIP_COLOR]


def _common(c: Element) -> Dict[str, Any]:
    transform = {k: _or(_num(c, k), d) for k, d in CLIP_TRANSFORM.items()}
    color = {k: _or(_num(c, k, -180 if k == "hue" else -1, 180 if k == "hue" else 1), d) for k, d in CLIP_COLOR.items()}
    fit = _str(c, "fitMode", ("fit", "fill", "stretch"))
    out: Dict[str, Any] = {"opacity": _or(_num(c, "opacity", 0, 1), 1), "volume": _or(_num(c, "volume", 0), 1),
                           "blendMode": _or(_str(c, "blendMode", BLEND_MODES), "normal")}
    if fit:
        out["fitMode"] = fit
    out["transform"] = transform
    out["color"] = color
    return out


def _clip_children(c: Element, clip_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    transition_in: Dict[str, Any] = {"kind": "none", "duration": 0}
    effects: List[Dict[str, Any]] = []
    keyframes: List[Dict[str, Any]] = []
    fx_id, kf_id = _ids(), _ids()
    saw = False

    def key(el: Element, prop: str) -> None:
        time, value = _num(el, "time", 0), _num(el, "value")
        if time is None or value is None:
            raise ValueError(f"{_where(el)}: a keyframe has a time and a value")
        track_ = next((k for k in keyframes if k["property"] == prop), None)
        if track_ is None:
            track_ = {"property": prop, "keys": []}
            keyframes.append(track_)
        track_["keys"].append({"id": kf_id(f"kf_{clip_id}"), "time": time, "value": value, "easing": _or(_str(el, "easing", EASINGS), "linear")})
        track_["keys"].sort(key=lambda k: k["time"])

    for el in c.children:
        if el.type == "transition":
            _refuse_unknown(el, ["kind", "duration"])
            if saw:
                raise ValueError(f"{_where(c)}: a clip has one <transition> (into it)")
            saw = True
            transition_in = {"kind": _or(_str(el, "kind", TRANSITIONS), "crossDissolve"), "duration": _or(_num(el, "duration", 0), 0.5)}
        elif el.type == "effect":
            t = _str(el, "type", EFFECT_TYPES)
            if not t:
                raise ValueError(f"{_where(c)}: an <effect> names its type")
            fid = fx_id(f"fx_{t}")
            params = {}
            for k, v in el.props.items():
                if k in ("type", "enabled", "colors"):
                    continue
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(f'<effect type="{t}">: {k} is a number, not {json.dumps(v)}')
                params[k] = v
            fx: Dict[str, Any] = {"id": fid, "type": t, "enabled": _or(_bool(el, "enabled"), True), "params": params}
            colors = el.props.get("colors")
            if colors is not None:
                if not isinstance(colors, dict) or any(not isinstance(x, str) for x in colors.values()):
                    raise ValueError(f'<effect type="{t}">: colors is {{ name: "#rrggbb" }}')
                fx["colors"] = dict(colors)
            effects.append(fx)
            for k in el.children:
                if k.type != "keyframe":
                    raise ValueError(f"<{k.type}> is not read in an <effect> (its keyframes are <keyframe param time value>)")
                _refuse_unknown(k, ["param", "time", "value", "easing"])
                param = _str(k, "param")
                if not param:
                    raise ValueError(f"{_where(k)}: an effect's keyframe names its param")
                key(k, f"effect.{fid}.{param}")
        elif el.type == "keyframe":
            _refuse_unknown(el, ["property", "time", "value", "easing"])
            prop = _str(el, "property", ANIMATABLE)
            if not prop:
                raise ValueError(f"{_where(el)}: a keyframe names its property ({', '.join(ANIMATABLE)})")
            key(el, prop)
        else:
            raise ValueError(f"<{el.type}> is not read in a <{c.type}> (a clip holds <transition>, <effect> and <keyframe>)")
    return transition_in, effects, keyframes


def declare_video(root: Element) -> Declaration:
    """Declare a video (``video(...)`` and its tracks) as the video editor's own op graph."""
    _refuse_unknown(root, ["name", *VIDEO_SETTINGS])
    name = _or(_str(root, "name"), "Video")
    settings = {"width": _or(_num(root, "width", 1), 1920), "height": _or(_num(root, "height", 1), 1080), "fps": _or(_num(root, "fps", 1), 30),
                "sampleRate": _or(_num(root, "sampleRate", 1), 48000), "background": _or(_str(root, "background"), "#000000")}
    nodes: Dict[str, Any] = {}
    new_id = _ids()
    new_id("composite")
    track_wires: List[Any] = []
    markers: List[Dict[str, Any]] = []
    for tr in root.children:
        if tr.type == "marker":
            _refuse_unknown(tr, ["name", "time", "color"])
            t = _num(tr, "time", 0)
            if t is None:
                raise ValueError(f"{_where(tr)}: a marker has a time")
            markers.append({"id": new_id(f"marker_{len(markers) + 1}"), "time": t, "name": _or(_str(tr, "name"), "Marker"), "color": _or(_str(tr, "color"), "#f5c542")})
            continue
        if tr.type != "track":
            raise ValueError(f"<{tr.type}> is not read in a <video> (it holds <track> and <marker>)")
        _refuse_unknown(tr, ["name", "kind", "muted", "hidden", "locked", "volume", "height"])
        kind = _or(_str(tr, "kind", ("video", "audio")), "video")
        track_name = _or(_str(tr, "name"), "A" if kind == "audio" else "V")
        track_id = new_id(f"track_{track_name}")
        clip_wires: List[Any] = []
        for c in tr.children:
            if c.type == "clip":
                _refuse_unknown(c, ["src", *_CLIP_PROPS])
                src = _str(c, "src")
                if not src:
                    raise ValueError('<clip> names its media file (src="media/take-1.mp4", relative to this file)')
                if re.match(r"^[a-z]+:|^/", src, re.I):
                    raise ValueError(f"{_where(c)}: src is a path relative to this file, not {src}")
                mk = media_kind(src)
                if not mk:
                    raise ValueError(f"{_where(c)}: {src} is not a video, audio or image file this editor reads")
                if (mk == "audio") != (kind == "audio"):
                    raise ValueError(f"{_where(c)}: " + ('a sound goes on an audio track (kind="audio")' if mk == "audio" else 'a picture goes on a video track (kind="video")'))
                asset_id = slug(src)
                source_id = f"src_{asset_id}"
                file_name = src.split("/")[-1]
                if source_id not in nodes:
                    nodes[source_id] = _node(source_id, "video.source", {
                        "asset": {"id": asset_id, "kind": mk, "name": file_name, "url": "", "path": src, "duration": 0, "width": 0, "height": 0, "hasAudio": mk != "image"},
                        "__asset": {"kind": "file", "$file": src}}, file_name)
                clip_name = _or(_str(c, "name"), file_name)
                speed = _or(_num(c, "speed", 0.01), 1)
                in_point = _or(_num(c, "in", 0), 0)
                out, duration = _num(c, "out", 0), _num(c, "duration", 0)
                if out is not None and duration is not None:
                    raise ValueError(f"{_where(c)}: give out or duration, not both")
                if out is not None:
                    if mk == "image":
                        raise ValueError(f"{_where(c)}: a picture has no out (give its duration)")
                    if out <= in_point:
                        raise ValueError(f"{_where(c)}: out ({out}) is after in ({in_point})")
                    duration = (out - in_point) / speed
                if duration is None:
                    raise ValueError(f"{_where(c)}: give its " + ("duration" if mk == "image" else "out (or duration)") + " in seconds")
                inputs: Dict[str, Any] = {"kind": mk, "assetId": asset_id, "name": clip_name, "start": _or(_num(c, "start", 0), 0),
                                          "duration": duration, "inPoint": in_point, "speed": speed, **_common(c)}
                source = _wire(source_id, "media")
            elif c.type == "title":
                _refuse_unknown(c, [p for p in _CLIP_PROPS if p not in ("in", "out", "speed", "volume")] + list(TITLE_TEXT) + ["typewriter"])
                if kind != "video":
                    raise ValueError(f"{_where(c)}: a title goes on a video track")
                clip_name = _or(_str(c, "name"), "Title")
                duration = _num(c, "duration", 0)
                if duration is None:
                    raise ValueError(f"{_where(c)}: give its duration in seconds")
                text: Dict[str, Any] = {}
                for k, d in TITLE_TEXT.items():
                    if isinstance(d, bool):
                        v = _bool(c, k)
                    elif isinstance(d, (int, float)):
                        v = _num(c, k, 0)
                    else:
                        v = _str(c, k, ("left", "center", "right") if k == "align" else None)
                    text[k] = _or(v, d)
                tw = _num(c, "typewriter", 0)
                if tw is not None:
                    text["typewriter"] = tw
                inputs = {"kind": "text", "name": clip_name, "start": _or(_num(c, "start", 0), 0), "duration": duration, "inPoint": 0, "speed": 1,
                          **_common(c), "volume": 1, "text": text}
                source = None
            else:
                raise ValueError(f"<{c.type}> is not read on a <track> (it holds <clip> and <title>)")
            clip_id = new_id(f"clip_{clip_name}")
            transition_in, effects, keyframes = _clip_children(c, clip_id)
            inputs["transitionIn"] = transition_in
            inputs["effects"] = effects
            inputs["trackers"] = []
            if keyframes:
                inputs["keyframes"] = keyframes
            inputs["source"] = source
            nodes[clip_id] = _node(clip_id, "video.clip", inputs, clip_name)
            clip_wires.append(_wire(clip_id, "frames"))
        track_inputs: Dict[str, Any] = {"kind": kind, "name": track_name, "muted": _or(_bool(tr, "muted"), False), "hidden": _or(_bool(tr, "hidden"), False),
                                        "locked": _or(_bool(tr, "locked"), False), "height": _or(_num(tr, "height", 16), _TRACK_HEIGHT[kind]),
                                        "volume": _or(_num(tr, "volume", 0), 1)}
        for i, w in enumerate(clip_wires):
            track_inputs[f"clips.{i + 1}"] = w
        nodes[track_id] = _node(track_id, "video.track", track_inputs, track_name)
        track_wires.append(_wire(track_id, "frames"))
    project_id = slug(f"proj_{name}")
    composite: Dict[str, Any] = {"id": project_id, "name": name, "settings": settings}
    if markers:
        composite["markers"] = markers
    composite.update({"createdAt": 0, "updatedAt": 0})
    for i, w in enumerate(track_wires):
        composite[f"tracks.{i + 1}"] = w
    nodes["composite"] = _node("composite", "video.composite", composite, name)
    return Declaration("video", copy.deepcopy({"id": project_id, "nodes": nodes, "outputs": ["composite"], "meta": {"kind": "video"}}))


# ── Song ─────────────────────────────────────────────────────────────────────────────────────────────────────────

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_LETTER = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def pitch_of(v: Any) -> Optional[int]:
    """A pitch as MIDI: a number (60), or a name with its octave ("C4" is 60, "F#3", "Bb2")."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if 0 <= v <= 127 else None
    if isinstance(v, float):
        return int(v) if v.is_integer() and 0 <= v <= 127 else None
    if not isinstance(v, str):
        return None
    m = re.match(r"^([A-Ga-g])(#|b)?(-?\d)$", v.strip())
    if not m:
        return None
    p = _LETTER[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0) + (int(m.group(3)) + 1) * 12
    return p if 0 <= p <= 127 else None


def pitch_name(p: int) -> str:
    return f"{_NAMES[p % 12]}{p // 12 - 1}"


WAVES = ("sine", "square", "sawtooth", "triangle")
SYNTH = {"wave": "sawtooth", "gain": 0.7, "detune": 8, "voices": 1, "transpose": 0}
ENVELOPE = {"attack": 0.01, "decay": 0.15, "sustain": 0.6, "release": 0.25}
SONG_EFFECTS = {
    "gain": ("fx.gain", "Gain", {"gain": 1}),
    "filter": ("fx.filter", "Filter", {"mode": "lowpass", "freq": 1200, "q": 1}),
    "delay": ("fx.delay", "Delay", {"timeBeats": 0.5, "feedback": 0.35, "mix": 0.3}),
    "reverb": ("fx.reverb", "Reverb", {"decay": 1.8, "mix": 0.3}),
    "eq": ("fx.eq", "EQ", {"lowGain": 0, "midGain": 0, "highGain": 0}),
}


def time_signature_of(v: Any) -> Optional[Dict[str, int]]:
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", v) if isinstance(v, str) else None
    if not m:
        return None
    num, den = int(m.group(1)), int(m.group(2))
    return {"num": num, "den": den} if 1 <= num <= 32 and den in (1, 2, 4, 8, 16, 32) else None


def tempo_of(v: Any) -> Optional[List[Dict[str, float]]]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [{"atBeat": 0, "bpm": v}] if v > 0 and math.isfinite(v) else None
    if not isinstance(v, (list, tuple)) or not v:
        return None
    out, prev = [], -math.inf
    for c in v:
        at, bpm = (c or {}).get("atBeat"), (c or {}).get("bpm")
        if not isinstance(at, (int, float)) or not isinstance(bpm, (int, float)) or not bpm > 0 or at < prev:
            return None
        out.append({"atBeat": at, "bpm": bpm})
        prev = at
    return out if out[0]["atBeat"] <= 0 else None


def declare_song(root: Element) -> Declaration:
    """Declare a song (``song(...)`` and its tracks) as the music studio's own op graph."""
    _refuse_unknown(root, ["name", "volumeDb", "tempo", "timeSignature", "bars"])
    name = _or(_str(root, "name"), "Song")
    tempo = [{"atBeat": 0, "bpm": 120}] if root.props.get("tempo") is None else tempo_of(root.props["tempo"])
    if not tempo:
        raise ValueError("<song>: tempo is beats per minute (120), or [{atBeat: 0, bpm: 120}, …] sorted by beat")
    time_sig = time_signature_of(_or(root.props.get("timeSignature"), "4/4"))
    if not time_sig:
        raise ValueError('<song>: timeSignature is "beats/unit" ("4/4", "6/8")')
    nodes: Dict[str, Any] = {}
    new_id = _ids()
    new_id("master")
    master: Dict[str, Any] = {"name": "Master", "volumeDb": _or(_num(root, "volumeDb"), 0), "tempo": tempo, "timeSig": time_sig, "bars": _or(_num(root, "bars", 1), 8)}
    order = 0
    for tr in root.children:
        if tr.type != "track":
            raise ValueError(f"<{tr.type}> is not read in a <song> (it holds <track>)")
        _refuse_unknown(tr, ["name", "colorIndex", "volumeDb", "pan", "mute", "solo"])
        track_name = _or(_str(tr, "name"), f"Track {order + 1}")
        track_id = new_id(f"track_{track_name}")
        upstream: Optional[str] = None
        instrument: Optional[str] = None
        clips: List[str] = []
        for el in tr.children:
            if el.type == "synth":
                if instrument:
                    raise ValueError(f"{_where(tr)}: a track plays one <synth>")
                _refuse_unknown(el, ["name", *SYNTH, *ENVELOPE])
                spec: Dict[str, Any] = {"kind": "synth", "wave": _or(_str(el, "wave", WAVES), SYNTH["wave"])}
                for k in ("gain", "detune", "voices", "transpose"):
                    spec[k] = _or(_num(el, k), SYNTH[k])
                spec["env"] = {k: _or(_num(el, k, 0), d) for k, d in ENVELOPE.items()}
                instrument = new_id(f"inst_{track_name}")
                nodes[instrument] = _node(instrument, "instrument", {"name": _or(_str(el, "name"), track_name), "spec": spec})
                upstream = instrument
            elif el.type in SONG_EFFECTS:
                fx_type, fx_name, defaults = SONG_EFFECTS[el.type]
                if not upstream:
                    raise ValueError(f"<{el.type}> comes after the track's <synth> (the chain runs synth → effects → track)")
                _refuse_unknown(el, ["name", *defaults])
                spec = {"type": el.type}
                for k, d in defaults.items():
                    spec[k] = _or(_num(el, k), d) if isinstance(d, (int, float)) else _or(_str(el, k, ("lowpass", "highpass", "bandpass")), d)
                fid = new_id(f"fx_{track_name}_{el.type}")
                nodes[fid] = _node(fid, fx_type, {"name": _or(_str(el, "name"), fx_name), "spec": spec, "audio": _wire(upstream, "audio")})
                upstream = fid
            elif el.type == "clip":
                _refuse_unknown(el, ["name", "start", "length", "loop"])
                clip_name = _or(_str(el, "name"), f"{track_name} {len(clips) + 1}")
                cid = new_id(f"clip_{clip_name}")
                notes = []
                for n in el.children:
                    if n.type != "note":
                        raise ValueError(f"<{n.type}> is not read in a <clip> (it holds <note>)")
                    _refuse_unknown(n, ["pitch", "start", "duration", "velocity"])
                    p = pitch_of(n.props.get("pitch"))
                    if p is None:
                        raise ValueError(f'<note>: pitch is a MIDI number (0–127) or a name ("C4", "F#3"), not {json.dumps(n.props.get("pitch"))}')
                    notes.append({"id": f"{cid}_n{len(notes) + 1}", "pitch": p, "start": _or(_num(n, "start", 0), 0), "dur": _or(_num(n, "duration", 0), 1),
                                  "vel": _or(_num(n, "velocity", 0, 1), 0.8)})
                nodes[cid] = _node(cid, "midiClip", {"name": clip_name, "start": _or(_num(el, "start", 0), 0), "length": _or(_num(el, "length", 0), 4),
                                                     "notes": notes, "loop": _or(_bool(el, "loop"), False)})
                clips.append(cid)
            else:
                raise ValueError(f"<{el.type}> is not read on a <track> (it holds <synth>, effects ({', '.join(SONG_EFFECTS)}) and <clip>)")
        if clips and not instrument:
            raise ValueError(f"{_where(tr)}: its clips need a <synth> to play them")
        if instrument:
            for i, c in enumerate(clips):
                nodes[instrument]["inputs"][f"midi.{i + 1}"] = _wire(c, "midi")
        track_inputs: Dict[str, Any] = {"name": track_name, "volumeDb": _or(_num(tr, "volumeDb"), 0), "pan": _or(_num(tr, "pan", -1, 1), 0),
                                        "mute": _or(_bool(tr, "mute"), False), "solo": _or(_bool(tr, "solo"), False), "colorIndex": _or(_num(tr, "colorIndex", 0), order)}
        if upstream:
            track_inputs["audio"] = _wire(upstream, "audio")
        nodes[track_id] = _node(track_id, "track", track_inputs, meta={"order": order})
        master[f"audio.{order + 1}"] = _wire(track_id, "audio")
        order += 1
    nodes["master"] = _node("master", "master", master)
    return Declaration("music", copy.deepcopy({"id": slug(f"music_{name}"), "nodes": nodes, "outputs": ["master"], "meta": {"domain": "music", "name": name}}))


def from_media(root: Element) -> Declaration:
    """Declare a media root element: a ``video(...)`` or a ``song(...)``."""
    if root.type == "video":
        return declare_video(root)
    if root.type == "song":
        return declare_song(root)
    raise ValueError(f"<{root.type}> is not a media root (a video or a song)")
