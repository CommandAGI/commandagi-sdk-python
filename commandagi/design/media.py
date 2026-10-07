"""A VIDEO OR A SONG IN PYTHON — the media editors' own documents, declared as the nodes the CommandAGI video editor
(``.vid.py``: ``video.source``, ``video.clip``, ``video.track``, ``video.composite``) and music studio (``.mus.py``:
``midiClip``, ``instrument``, ``fx.*``, ``track``, ``master``) store and edit. The same elements, node for node, as the
TypeScript SDK's ``media.ts`` (``.vid.tsx``, ``.mus.tsx``)::

    from commandagi.design.media import clip, note, song, synth, title, track, video

    result = video(
        track(clip(src="media/sky.png", start=0, duration=3), title(text="Hello", start=0, duration=2), name="V1"),
        track(clip(src="media/tone.wav", start=0, in_=0.5, out=2.5, volume=0.8), name="A1", kind="audio"),
        name="Balcony", width=1280, height=720, fps=30,
    )

    result = song(
        track(synth(wave="triangle"), clip(note(pitch="C4", start=0, duration=1), name="Keys 1", start=0, length=4), name="Keys"),
        track(clip(src="media/tone.wav", start=4, length=2, in_=0.25, volume=0.8), name="Tone"),
        track(sampler(src="media/tone.wav", root="A4"), clip(name="Bells 1", start=0, length=4), name="Bells"),
        name="Loop", tempo=120, time_signature="4/4", bars=8, cycle_start=0, cycle_end=16,
    )

One call per tag (``commandagi.design.element``): children positional, attributes as snake_case keywords (``font_size``
is ``fontSize``; ``in_`` is ``in``). Media files are named by path relative to the file, never inlined. Times on a
video's timeline are seconds; in a song, beats (an audio clip's ``in``, where it starts in its file, is seconds, as on a
video). Each node carries the call that declared it in ``meta.source``; what a
node holds that is not a node (a clip's effects, transition, intro, outro and keyframes; a midi clip's notes; a video's
markers) carries its call in ``meta.sources``, by key. Anything the vocabulary cannot say is refused by name.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .element import Element, child_elements, declares, define
from .ir import slug

MEDIA_ROOTS = ("video", "song")

_HOLDS: Dict[str, Any] = {"holds": "children"}
#: Every tag of a video and a song: what it holds (the TypeScript SDK's ``SIGNATURES``; absent: a leaf).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "video": _HOLDS, "song": _HOLDS, "track": _HOLDS, "clip": _HOLDS, "title": _HOLDS, "shape": _HOLDS, "adjustment": _HOLDS,
    "midi": _HOLDS, "effect": _HOLDS,
    "marker": {}, "transition": {}, "intro": {}, "outro": {}, "keyframe": {}, "note": {},
    "synth": {}, "sampler": {}, "gain": {}, "filter": {}, "delay": {}, "reverb": {}, "eq": {}, "compressor": {}, "distortion": {},
}

__all__ = ["MEDIA_ROOTS", "SIGNATURES", "declare_video", "declare_song", "media_kind", "pitch_of", "pitch_name", "tempo_of",
           "time_signature_of", *define(globals(), "media", SIGNATURES)]


def _where(el: Element) -> str:
    for k in ("name", "src", "text"):
        if isinstance(el.props.get(k), str):
            return f'<{el.type} {k}="{el.props[k]}">'
    return f"<{el.type}>"


def _refuse_unknown(el: Element, allowed: List[str]) -> None:
    for k in el.props:
        if k != "key" and k not in allowed:
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


def _meta_of(el: Element, sources: Optional[Dict[str, Any]] = None, extra: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """A node's meta: the call it came from, and the calls of what it holds, by key."""
    meta: Dict[str, Any] = dict(extra or {})
    if el.source is not None:
        meta["source"] = el.source
    if sources:
        meta["sources"] = sources
    return meta or None


# ── Video ────────────────────────────────────────────────────────────────────────────────────────────────────────

_EXT = {**{e: "video" for e in ("mp4", "webm", "mov", "mkv", "m4v", "ogv")},
        **{e: "audio" for e in ("wav", "mp3", "ogg", "oga", "m4a", "flac", "aac", "opus")},
        **{e: "image" for e in ("png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "svg")}}


def media_kind(src: str) -> Optional[str]:
    m = re.search(r"\.([A-Za-z0-9]+)$", src)
    return _EXT.get(m.group(1).lower()) if m else None


EASINGS = ("linear", "easeIn", "easeOut", "easeInOut", "hold", "bezier")
TRANSITIONS = ("none", "cut", "crossDissolve", "fadeToBlack", "fadeToWhite", "dipToColor", "wipeLeft", "wipeRight", "wipeUp",
               "wipeDown", "diagonalWipe", "barnDoors", "iris", "diamond", "clockWipe", "pixelDissolve", "pushLeft", "pushRight",
               "slideUp", "slideDown", "zoomIn", "zoomBlur", "glitch", "kineticMatte", "shapeWipe")
EFFECT_TYPES = ("brightnessContrast", "saturation", "hueRotate", "gaussianBlur", "sharpen", "pixelate", "chromaKey", "twist", "wave",
                "mirror", "vignette", "glow", "grayscale", "sepia", "invert", "posterize", "edges", "chromaticAberration", "bulge",
                "duotone", "colorWheels", "mask", "lut")
#: A transition's alignment on the cut.
TRANSITION_ALIGN = ("start", "center", "end")
#: A video's audio effects (a clip's, a track's or the master's chain), by tag: each prop and its default.
VIDEO_AUDIO_EFFECTS: Dict[str, Dict[str, Any]] = {
    "gain": {"gain": 1},
    "eq": {"lowGain": 0, "midGain": 0, "highGain": 0},
    "filter": {"mode": "lowpass", "freq": 1200, "q": 1},
    "delay": {"time": 0.3, "feedback": 0.4, "mix": 0.35},
    "reverb": {"decay": 2, "mix": 0.35},
    "compressor": {"threshold": -24, "ratio": 4, "attack": 0.003, "release": 0.25},
    "distortion": {"amount": 0.4, "mix": 1},
}
FILTER_MODES = ("lowpass", "highpass", "bandpass")
FILTER_DEFAULTS = {"lowpass": {"frequency": 1200, "q": 1}, "highpass": {"frequency": 300, "q": 1}, "bandpass": {"frequency": 1500, "q": 2}}
_AUDIO_BOUNDS = {"gain": (0, 16), "lowGain": (-40, 40), "midGain": (-40, 40), "highGain": (-40, 40), "freq": (10, 24000), "q": (0.0001, 100),
                 "time": (0, 2), "feedback": (0, 0.95), "mix": (0, 1), "decay": (0.01, 20), "threshold": (-100, 0), "ratio": (1, 20),
                 "attack": (0, 1), "release": (0, 1), "amount": (0, 1)}


def _audio_effect(el: Element, make_id: Callable[[str], str]) -> Dict[str, Any]:
    """One audio effect element as the editor's effect: the tag's engine type (a filter is its mode) and its params."""
    spec = VIDEO_AUDIO_EFFECTS[el.type]
    _refuse_unknown(el, [*spec, "enabled"])
    params: Dict[str, Any] = {}
    t = el.type
    if t == "filter":
        t = _or(_str(el, "mode", FILTER_MODES), "lowpass")
        d = FILTER_DEFAULTS[t]
        params["frequency"] = _or(_num(el, "freq", *_AUDIO_BOUNDS["freq"]), d["frequency"])
        params["q"] = _or(_num(el, "q", *_AUDIO_BOUNDS["q"]), d["q"])
    else:
        for k, d in spec.items():
            params[k] = _or(_num(el, k, *_AUDIO_BOUNDS[k]), d)
    return {"id": make_id(f"afx_{t}"), "type": t, "enabled": _or(_bool(el, "enabled"), True), "params": params}
ANIM_PRESETS = ("fade", "slideL", "slideR", "slideU", "slideD", "pop", "rise", "spin")
ANIMATABLE = ("opacity", "volume", "transform.x", "transform.y", "transform.scaleX", "transform.scaleY", "transform.rotation")
CLIP_TRANSFORM = {"x": 0, "y": 0, "scaleX": 1, "scaleY": 1, "rotation": 0, "anchorX": 0.5, "anchorY": 0.5}
CLIP_COLOR = {"exposure": 0, "contrast": 0, "saturation": 0, "temperature": 0, "brightness": 0, "hue": 0}
TITLE_TEXT = {"text": "Title", "fontFamily": "Inter, system-ui, sans-serif", "fontSize": 96, "color": "#ffffff", "bold": True,
              "italic": False, "align": "center", "background": "transparent", "strokeColor": "#000000", "strokeWidth": 0}
VIDEO_SETTINGS = {"width": 1920, "height": 1080, "fps": 30, "sampleRate": 48000, "background": "#000000"}
_TRACK_HEIGHT = {"video": 64, "audio": 48, "midi": 56}
VIDEO_TRACK_KINDS = ("video", "audio", "midi")
SHAPE_KINDS = ("emoji", "rect", "ellipse", "triangle", "star", "arrow", "heart", "speech", "svg")
SHAPE_LOOK = {"fill": "#ffd166", "stroke": "#00000000", "strokeWidth": 0}
MIDI_INSTRUMENTS = ("grandPiano", "electricPiano", "synthLead", "synthPad", "strings", "organ", "bass", "pluck", "bell", "sawLead", "squareLead",
                    "superSaw", "reeseBass", "subBass", "fmBell", "musicBox", "marimba", "vibraphone", "kalimba", "harp", "clav", "brass", "flute",
                    "choir", "glass", "sineLead", "pwmPad", "pluckSynth", "eightBit", "drumKit")
MIDI_CLIP = {"instrument": "grandPiano", "gain": 0.8}


def shape_content(kind: str) -> str:
    """A shape's content when not given: the star's glyph, else none."""
    return "\u2b50" if kind == "star" else ""
#: A clip's crop: the fraction of its picture hidden at each edge.
CLIP_CROP = {"cropTop": "top", "cropRight": "right", "cropBottom": "bottom", "cropLeft": "left"}
_CLIP_PROPS = ["name", "start", "duration", "in", "out", "speed", "opacity", "volume", "blendMode", "fitMode", *CLIP_TRANSFORM, *CLIP_COLOR, *CLIP_CROP]


def _common(c: Element) -> Dict[str, Any]:
    transform = {k: _or(_num(c, k), d) for k, d in CLIP_TRANSFORM.items()}
    color = {k: _or(_num(c, k, -180 if k == "hue" else -1, 180 if k == "hue" else 1), d) for k, d in CLIP_COLOR.items()}
    fit = _str(c, "fitMode", ("fit", "fill", "stretch"))
    out: Dict[str, Any] = {"opacity": _or(_num(c, "opacity", 0, 1), 1), "volume": _or(_num(c, "volume", 0), 1),
                           "blendMode": _or(_str(c, "blendMode"), "normal")}
    if fit:
        out["fitMode"] = fit
    out["transform"] = transform
    out["color"] = color
    if any(k in c.props for k in CLIP_CROP):
        out["crop"] = {edge: _or(_num(c, k, 0, 0.49), 0) for k, edge in CLIP_CROP.items()}
    return out


def _clip_children(c: Element, clip_id: str, sources: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    transition_in: Dict[str, Any] = {"kind": "none", "duration": 0}
    anims: Dict[str, Any] = {}
    notes: List[Dict[str, Any]] = []
    note_id = _ids()
    effects: List[Dict[str, Any]] = []
    audio: List[Dict[str, Any]] = []
    keyframes: List[Dict[str, Any]] = []
    fx_id, kf_id, afx_id = _ids(), _ids(), _ids()
    saw = False

    def key(el: Element, prop: str) -> None:
        time, value = _num(el, "time", 0), _num(el, "value")
        if time is None or value is None:
            raise ValueError(f"{_where(el)}: a keyframe has a time and a value")
        track_ = next((k for k in keyframes if k["property"] == prop), None)
        if track_ is None:
            track_ = {"property": prop, "keys": []}
            keyframes.append(track_)
        kid = kf_id(f"kf_{clip_id}")
        easing = _or(_str(el, "easing", EASINGS), "linear")
        bezier = el.props.get("bezier")
        if bezier is not None and easing != "bezier":
            raise ValueError(f'{_where(el)}: bezier is read with easing="bezier"')
        k = {"id": kid, "time": time, "value": value, "easing": easing}
        if easing == "bezier":
            ok = isinstance(bezier, (list, tuple)) and len(bezier) == 4 and all(
                not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) for v in bezier) and 0 <= bezier[0] <= 1 and 0 <= bezier[2] <= 1
            if not ok:
                raise ValueError(f'{_where(el)}: an easing "bezier" names its curve: bezier=[x1, y1, x2, y2] (x1 and x2 from 0 to 1)')
            k["bezier"] = list(bezier)
        track_["keys"].append(k)
        track_["keys"].sort(key=lambda k: k["time"])
        sources[f"keyframe:{kid}"] = el.source

    for el in child_elements(c):
        if el.type == "transition":
            _refuse_unknown(el, ["kind", "duration", "align", "color", "shape"])
            if saw:
                raise ValueError(f"{_where(c)}: a clip has one <transition> (into it)")
            saw = True
            transition_in = {"kind": _or(_str(el, "kind", TRANSITIONS), "crossDissolve"), "duration": _or(_num(el, "duration", 0), 0.5)}
            tparams: Dict[str, Any] = {}
            for k, v in (("align", _str(el, "align", TRANSITION_ALIGN)), ("color", _str(el, "color")), ("shape", _num(el, "shape", 0))):
                if v is not None:
                    tparams[k] = v
            if tparams:
                transition_in["params"] = tparams
            sources["transition"] = el.source
        elif el.type == "note":
            if c.type != "midi":
                raise ValueError(f"<note> is read in a <midi> clip, not a <{c.type}>")
            _refuse_unknown(el, ["pitch", "start", "duration", "velocity"])
            pitch = pitch_of(el.props.get("pitch"))
            if pitch is None:
                raise ValueError(f'<note>: pitch is a MIDI number 0–127 or a name like "C4", not {json.dumps(el.props.get("pitch"))}')
            start, dur = _num(el, "start", 0), _num(el, "duration", 0)
            if start is None or dur is None:
                raise ValueError("<note>: a note has a start and a duration (seconds in the clip)")
            nid = note_id(f"note_{clip_id}")
            notes.append({"id": nid, "pitch": pitch, "start": start, "duration": dur, "velocity": _or(_num(el, "velocity", 0, 1), 0.8)})
            sources[f"note:{nid}"] = el.source
        elif el.type in ("intro", "outro"):
            _refuse_unknown(el, ["preset", "duration"])
            k = "animIn" if el.type == "intro" else "animOut"
            if k in anims:
                raise ValueError(f"{_where(c)}: a clip has one <{el.type}>")
            preset = _str(el, "preset", ANIM_PRESETS)
            if not preset:
                raise ValueError(f"<{el.type}> names its preset ({', '.join(ANIM_PRESETS)})")
            anims[k] = {"preset": preset, "duration": _or(_num(el, "duration", 0), 1)}
            sources[el.type] = el.source
        elif el.type == "effect":
            t = _str(el, "type", EFFECT_TYPES)
            if not t:
                raise ValueError(f"{_where(c)}: an <effect> names its type")
            fid = fx_id(f"fx_{t}")
            src = None
            if t == "lut":
                src = _str(el, "src")
                if not src:
                    raise ValueError('<effect type="lut">: a LUT names its .cube file (src="looks/film.cube", relative to this file)')
                if re.match(r"^[a-z]+:|^/", src, re.I):
                    raise ValueError(f'<effect type="lut">: src is a path relative to this file, not {src}')
            elif el.props.get("src") is not None:
                raise ValueError(f'<effect type="{t}">: src is read on a LUT (type="lut")')
            params = {}
            for k, v in el.props.items():
                if k in ("key", "type", "enabled", "colors", "src"):
                    continue
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise ValueError(f'<effect type="{t}">: {k} is a number, not {json.dumps(v)}')
                params[k] = v
            fx: Dict[str, Any] = {"id": fid, "type": t, "enabled": _or(_bool(el, "enabled"), True), "params": params}
            colors = el.props.get("colors")
            if colors is not None:
                if not isinstance(colors, dict) or any(not isinstance(x, str) for x in colors.values()):
                    raise ValueError(f'<effect type="{t}">: colors is {{ name: "#rrggbb" }}')
                fx["colors"] = dict(colors)
            if src is not None:
                fx["src"] = src
            effects.append(fx)
            sources[f"effect:{fid}"] = el.source
            for k in child_elements(el):
                if k.type != "keyframe":
                    raise ValueError(f"<{k.type}> is not read in an <effect> (its keyframes are <keyframe param time value>)")
                _refuse_unknown(k, ["param", "time", "value", "easing", "bezier"])
                param = _str(k, "param")
                if not param:
                    raise ValueError(f"{_where(k)}: an effect's keyframe names its param")
                key(k, f"effect.{fid}.{param}")
        elif el.type == "keyframe":
            _refuse_unknown(el, ["property", "time", "value", "easing", "bezier"])
            prop = _str(el, "property", ANIMATABLE)
            if not prop:
                raise ValueError(f"{_where(el)}: a keyframe names its property ({', '.join(ANIMATABLE)})")
            key(el, prop)
        elif el.type in VIDEO_AUDIO_EFFECTS:
            if (c.type != "clip" and c.type != "midi") or (c.type == "clip" and media_kind(str(c.props.get("src") or "")) == "image"):
                raise ValueError(f"<{el.type}> is an audio effect: {_where(c)} has no sound")
            fx = _audio_effect(el, afx_id)
            audio.append(fx)
            sources[f"audio:{fx['id']}"] = el.source
        else:
            raise ValueError(f"<{el.type}> is not read in a <{c.type}> (a clip holds <transition>, <intro>, <outro>, <effect>, <keyframe> and audio effects ({', '.join(VIDEO_AUDIO_EFFECTS)}); a <midi> clip its <note>s)")
    return transition_in, anims, effects, audio, keyframes, notes


def declare_video(root: Element) -> Dict[str, Any]:
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
    composite_sources: Dict[str, Any] = {}
    master: List[Dict[str, Any]] = []
    master_id = _ids()
    for tr in child_elements(root):
        if tr.type in VIDEO_AUDIO_EFFECTS:
            fx = _audio_effect(tr, master_id)
            master.append(fx)
            composite_sources[f"audio:{fx['id']}"] = tr.source
            continue
        if tr.type == "marker":
            _refuse_unknown(tr, ["name", "time", "color"])
            t = _num(tr, "time", 0)
            if t is None:
                raise ValueError(f"{_where(tr)}: a marker has a time")
            mid = new_id(f"marker_{len(markers) + 1}")
            markers.append({"id": mid, "time": t, "name": _or(_str(tr, "name"), "Marker"), "color": _or(_str(tr, "color"), "#f5c542")})
            composite_sources[f"marker:{mid}"] = tr.source
            continue
        if tr.type != "track":
            raise ValueError(f"<{tr.type}> is not read in a <video> (it holds <track>, <marker> and the master's audio effects)")
        _refuse_unknown(tr, ["name", "kind", "muted", "hidden", "locked", "volume", "height"])
        kind = _or(_str(tr, "kind", VIDEO_TRACK_KINDS), "video")
        track_name = _or(_str(tr, "name"), "A" if kind == "audio" else "M" if kind == "midi" else "V")
        track_id = new_id(f"track_{track_name}")
        clip_wires: List[Any] = []
        track_fx: List[Dict[str, Any]] = []
        track_sources: Dict[str, Any] = {}
        track_fx_id = _ids()
        for c in child_elements(tr):
            if c.type in VIDEO_AUDIO_EFFECTS:
                fx = _audio_effect(c, track_fx_id)
                track_fx.append(fx)
                track_sources[f"audio:{fx['id']}"] = c.source
                continue
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
            elif c.type in ("shape", "adjustment"):
                # A shape and an adjustment layer are synthetic: no media, no in/out, speed 1, no sound.
                own = ["kind", "content", *SHAPE_LOOK] if c.type == "shape" else []
                _refuse_unknown(c, [p for p in _CLIP_PROPS if p not in ("in", "out", "speed", "volume")] + own)
                if kind != "video":
                    raise ValueError(f"{_where(c)}: a <{c.type}> goes on a video track")
                clip_name = _or(_str(c, "name"), "Sticker" if c.type == "shape" else "Adjustment")
                duration = _num(c, "duration", 0)
                if duration is None:
                    raise ValueError(f"{_where(c)}: give its duration in seconds")
                inputs = {"kind": c.type, "name": clip_name, "start": _or(_num(c, "start", 0), 0), "duration": duration, "inPoint": 0, "speed": 1,
                          **_common(c), "volume": 1}
                if c.type == "shape":
                    sk = _str(c, "kind", SHAPE_KINDS)
                    if not sk:
                        raise ValueError(f"{_where(c)}: a <shape> names its kind ({', '.join(SHAPE_KINDS)})")
                    inputs["sticker"] = {"kind": sk, "content": _or(_str(c, "content"), shape_content(sk)), "fill": _or(_str(c, "fill"), SHAPE_LOOK["fill"]),
                                         "stroke": _or(_str(c, "stroke"), SHAPE_LOOK["stroke"]), "strokeWidth": _or(_num(c, "strokeWidth", 0), SHAPE_LOOK["strokeWidth"])}
                source = None
            elif c.type == "midi":
                _refuse_unknown(c, [p for p in _CLIP_PROPS if p not in ("in", "out", "speed") and p not in CLIP_CROP] + list(MIDI_CLIP))
                if kind != "midi":
                    raise ValueError(f'{_where(c)}: a <midi> clip goes on a midi track (kind="midi")')
                clip_name = _or(_str(c, "name"), "MIDI")
                duration = _num(c, "duration", 0)
                if duration is None:
                    raise ValueError(f"{_where(c)}: give its duration in seconds")
                inputs = {"kind": "midi", "name": clip_name, "start": _or(_num(c, "start", 0), 0), "duration": duration, "inPoint": 0, "speed": 1, **_common(c)}
                source = None
            else:
                raise ValueError(f"<{c.type}> is not read on a <track> (it holds <clip>, <title>, <shape>, <adjustment>, <midi> and audio effects)")
            if kind == "midi" and c.type != "midi":
                raise ValueError(f"{_where(c)}: a midi track holds <midi> clips")
            clip_id = new_id(f"clip_{clip_name}")
            sources: Dict[str, Any] = {}
            transition_in, anims, effects, audio, keyframes, notes = _clip_children(c, clip_id, sources)
            inputs["transitionIn"] = transition_in
            inputs.update(anims)
            inputs["effects"] = effects
            if audio:
                inputs["audioEffects"] = audio
            inputs["trackers"] = []
            if keyframes:
                inputs["keyframes"] = keyframes
            if c.type == "midi":
                inputs["midi"] = {"notes": notes, "instrument": _or(_str(c, "instrument", MIDI_INSTRUMENTS), MIDI_CLIP["instrument"]),
                                  "gain": _or(_num(c, "gain", 0), MIDI_CLIP["gain"])}
            inputs["source"] = source
            nodes[clip_id] = _node(clip_id, "video.clip", inputs, clip_name, _meta_of(c, sources))
            clip_wires.append(_wire(clip_id, "frames"))
        track_inputs: Dict[str, Any] = {"kind": kind, "name": track_name, "muted": _or(_bool(tr, "muted"), False), "hidden": _or(_bool(tr, "hidden"), False),
                                        "locked": _or(_bool(tr, "locked"), False), "height": _or(_num(tr, "height", 16), _TRACK_HEIGHT[kind]),
                                        "volume": _or(_num(tr, "volume", 0), 1)}
        if track_fx:
            track_inputs["audioEffects"] = track_fx
        for i, w in enumerate(clip_wires):
            track_inputs[f"clips.{i + 1}"] = w
        nodes[track_id] = _node(track_id, "video.track", track_inputs, track_name, _meta_of(tr, track_sources))
        track_wires.append(_wire(track_id, "frames"))
    project_id = slug(f"proj_{name}")
    composite: Dict[str, Any] = {"id": project_id, "name": name, "settings": settings}
    if markers:
        composite["markers"] = markers
    if master:
        composite["masterEffects"] = master
    composite.update({"createdAt": 0, "updatedAt": 0})
    for i, w in enumerate(track_wires):
        composite[f"tracks.{i + 1}"] = w
    nodes["composite"] = _node("composite", "video.composite", composite, name, _meta_of(root, composite_sources))
    return {"id": project_id, "nodes": nodes, "outputs": ["composite"], "meta": {"kind": "video"}}


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


SAMPLER = {"root": 69, "gain": 1}
AUDIO_CLIP = {"in": 0, "volume": 1, "loop": False}


def _sound_src(el: Element) -> str:
    src = _str(el, "src")
    if not src:
        raise ValueError(f'<{el.type}> names its sound file (src="media/tone.wav", relative to this file)')
    if re.match(r"^[a-z]+:|^/", src, re.I):
        raise ValueError(f"{_where(el)}: src is a path relative to this file, not {src}")
    if media_kind(src) != "audio":
        raise ValueError(f"{_where(el)}: {src} is not a sound file this studio reads")
    return src


def _stem(src: str) -> str:
    return re.sub(r"\.[^.]+$", "", re.sub(r"^.*/", "", src))


def declare_song(root: Element) -> Dict[str, Any]:
    """Declare a song (``song(...)`` and its tracks) as the music studio's own op graph. A track plays a ``synth`` or a
    ``sampler`` (an instrument: its clips hold notes), or holds audio clips (``clip(src=...)``: a sound file placed on
    the song, played by the track's player); effects follow the instrument or the player."""
    _refuse_unknown(root, ["name", "volumeDb", "tempo", "timeSignature", "bars", "cycleStart", "cycleEnd"])
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
    cycle_start, cycle_end = _num(root, "cycleStart", 0), _num(root, "cycleEnd", 0)
    if (cycle_start is None) != (cycle_end is None):
        raise ValueError("<song>: a cycle names both its cycleStart and its cycleEnd (beats)")
    if cycle_start is not None and cycle_end is not None:
        if not cycle_end > cycle_start:
            raise ValueError(f"<song>: cycleEnd ({json.dumps(cycle_end)}) comes after cycleStart ({json.dumps(cycle_start)})")
        master["cycle"] = {"start": cycle_start, "end": cycle_end}
    order = 0
    for tr in child_elements(root):
        if tr.type != "track":
            raise ValueError(f"<{tr.type}> is not read in a <song> (it holds <track>)")
        _refuse_unknown(tr, ["name", "colorIndex", "volumeDb", "pan", "mute", "solo"])
        track_name = _or(_str(tr, "name"), f"Track {order + 1}")
        track_id = new_id(f"track_{track_name}")
        children = list(child_elements(tr))
        audio_track = bool(children) and not any(el.type in ("synth", "sampler") for el in children)
        upstream: Optional[str] = None
        instrument: Optional[str] = None
        player: Optional[str] = None
        clips: List[str] = []
        if audio_track:
            player = new_id(f"player_{track_name}")
            nodes[player] = _node(player, "player", {"name": track_name})
            upstream = player
        for el in children:
            if el.type in ("synth", "sampler"):
                if instrument:
                    raise ValueError(f"{_where(tr)}: a track plays one instrument (a <synth> or a <sampler>)")
                if el.type == "synth":
                    _refuse_unknown(el, ["name", *SYNTH, *ENVELOPE])
                    spec: Dict[str, Any] = {"kind": "synth", "wave": _or(_str(el, "wave", WAVES), SYNTH["wave"])}
                    for k in ("gain", "detune", "voices", "transpose"):
                        spec[k] = _or(_num(el, k), SYNTH[k])
                else:
                    _refuse_unknown(el, ["name", "src", "root", "gain", *ENVELOPE])
                    base = SAMPLER["root"] if el.props.get("root") is None else pitch_of(el.props.get("root"))
                    if base is None:
                        raise ValueError(f'<sampler>: root is the pitch the file sounds at, a MIDI number (0–127) or a name ("A4"), not {json.dumps(el.props.get("root"))}')
                    spec = {"kind": "sampler", "src": _sound_src(el), "baseNote": base, "gain": _or(_num(el, "gain", 0), SAMPLER["gain"])}
                spec["env"] = {k: _or(_num(el, k, 0), d) for k, d in ENVELOPE.items()}
                instrument = new_id(f"inst_{track_name}")
                nodes[instrument] = _node(instrument, "instrument", {"name": _or(_str(el, "name"), track_name), "spec": spec}, meta=_meta_of(el))
                upstream = instrument
            elif el.type in SONG_EFFECTS:
                fx_type, fx_name, defaults = SONG_EFFECTS[el.type]
                if not upstream:
                    raise ValueError(f"<{el.type}> comes after the track's instrument (the chain runs instrument → effects → track)")
                _refuse_unknown(el, ["name", *defaults])
                spec = {"type": el.type}
                for k, d in defaults.items():
                    spec[k] = _or(_num(el, k), d) if isinstance(d, (int, float)) else _or(_str(el, k, ("lowpass", "highpass", "bandpass")), d)
                fid = new_id(f"fx_{track_name}_{el.type}")
                nodes[fid] = _node(fid, fx_type, {"name": _or(_str(el, "name"), fx_name), "spec": spec, "audio": _wire(upstream, "audio")},
                                 meta=_meta_of(el))
                upstream = fid
            elif el.type == "clip" and player and el.props.get("src") is not None:
                _refuse_unknown(el, ["name", "src", "start", "length", "in", "volume", "loop"])
                if list(child_elements(el)):
                    raise ValueError(f"{_where(el)}: an audio clip holds no notes (notes go in a clip on a track with a <synth> or a <sampler>)")
                src = _sound_src(el)
                clip_name = _or(_str(el, "name"), _stem(src))
                cid = new_id(f"clip_{clip_name}")
                nodes[cid] = _node(cid, "sample", {"name": clip_name, "src": src, "start": _or(_num(el, "start", 0), 0), "length": _or(_num(el, "length", 0), 4),
                                                   "offsetSeconds": _or(_num(el, "in", 0), AUDIO_CLIP["in"]), "gain": _or(_num(el, "volume", 0), AUDIO_CLIP["volume"]),
                                                   "loop": _or(_bool(el, "loop"), AUDIO_CLIP["loop"])}, meta=_meta_of(el))
                clips.append(cid)
            elif el.type == "clip":
                if el.props.get("src") is not None:
                    raise ValueError(f"{_where(tr)}: a track that plays an instrument holds clips of notes; an audio clip (src) goes on a track without one")
                _refuse_unknown(el, ["name", "start", "length", "loop"])
                clip_name = _or(_str(el, "name"), f"{track_name} {len(clips) + 1}")
                cid = new_id(f"clip_{clip_name}")
                notes = []
                sources: Dict[str, Any] = {}
                for n in child_elements(el):
                    if n.type != "note":
                        raise ValueError(f"<{n.type}> is not read in a <clip> (it holds <note>)")
                    _refuse_unknown(n, ["pitch", "start", "duration", "velocity"])
                    p = pitch_of(n.props.get("pitch"))
                    if p is None:
                        raise ValueError(f'<note>: pitch is a MIDI number (0–127) or a name ("C4", "F#3"), not {json.dumps(n.props.get("pitch"))}')
                    nid = f"{cid}_n{len(notes) + 1}"
                    notes.append({"id": nid, "pitch": p, "start": _or(_num(n, "start", 0), 0), "dur": _or(_num(n, "duration", 0), 1),
                                  "vel": _or(_num(n, "velocity", 0, 1), 0.8)})
                    sources[f"note:{nid}"] = n.source
                nodes[cid] = _node(cid, "midiClip", {"name": clip_name, "start": _or(_num(el, "start", 0), 0), "length": _or(_num(el, "length", 0), 4),
                                                     "notes": notes, "loop": _or(_bool(el, "loop"), False)}, meta=_meta_of(el, sources))
                clips.append(cid)
            else:
                raise ValueError(f"<{el.type}> is not read on a <track> (it holds a <synth> or a <sampler>, effects ({', '.join(SONG_EFFECTS)}) and <clip>)")
        if instrument:
            for i, c in enumerate(clips):
                nodes[instrument]["inputs"][f"midi.{i + 1}"] = _wire(c, "midi")
        if player:
            if any(nodes[c]["type"] == "midiClip" for c in clips):
                raise ValueError(f"{_where(tr)}: its clips need a <synth> or a <sampler> to play them")
            for i, c in enumerate(clips):
                nodes[player]["inputs"][f"audio.{i + 1}"] = _wire(c, "audio")
        track_inputs: Dict[str, Any] = {"name": track_name, "volumeDb": _or(_num(tr, "volumeDb"), 0), "pan": _or(_num(tr, "pan", -1, 1), 0),
                                        "mute": _or(_bool(tr, "mute"), False), "solo": _or(_bool(tr, "solo"), False), "colorIndex": _or(_num(tr, "colorIndex", 0), order)}
        if upstream:
            track_inputs["audio"] = _wire(upstream, "audio")
        nodes[track_id] = _node(track_id, "track", track_inputs, meta=_meta_of(tr, None, {"order": order}))
        master[f"audio.{order + 1}"] = _wire(track_id, "audio")
        order += 1
    nodes["master"] = _node("master", "master", master, meta=_meta_of(root))
    return {"id": slug(f"music_{name}"), "nodes": nodes, "outputs": ["master"], "meta": {"domain": "music", "name": name}}


def _declare(root: Element, stem: str) -> Dict[str, Any]:
    return {"graph": declare_video(root) if root.tag == "video" else declare_song(root)}


declares("media", "video", _declare)
declares("media", "song", _declare)
