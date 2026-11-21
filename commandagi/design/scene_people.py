"""A PERSON IN A SCENE — the human avatar (``cloud://global/devices/human-avatar/definition.tsx``) placed in a design's
``slot(name="scene")`` as a ``robots`` entry with a ``look``, the ``humanoid`` policy that drives it, and the ``goal``,
``motors``, ``assist`` and ``face`` commands an agent sends it (docs/formats.md § a person in the scene, in the CommandAGI
repository). The same as the TypeScript SDK's ``scene-people.ts``; the scene stays a plain dict, so the editor writes
into it::

    from commandagi.design.scene_people import check_humanoid_policy, check_look

    look = check_look({"body": "feminine", "height_m": 1.68, "hair_style": "ponytail", "outfit": "blouse_skirt"})
    policy = check_humanoid_policy({"id": "ana-day", "kind": "humanoid", "unit": "ana", "repeat": True, "routine": [
        {"do": "walk", "route": [[0, 0], [1, 2]]}, {"do": "sit", "seat": [1, 2.4, 0.45], "facing": 1.57},
        {"do": "idle", "activity": "type", "seconds": 60}, {"do": "stand"}]})

``check_look``, ``check_goal``, ``check_humanoid_policy``, ``check_motors``, ``check_assist`` and ``check_face`` refuse what the engine
refuses (``ValueError``), in its words. They check the shape only: whether a unit, a body or a constraint is in the
scene is the engine's to say.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

try:
    from typing import Literal, TypedDict
except ImportError:  # pragma: no cover
    from typing_extensions import Literal, TypedDict  # type: ignore

LOOK_BODIES = ("masculine", "feminine")
HAIR_STYLES = ("none", "afro", "bob", "bob_sleek", "braid", "long", "ponytail", "short", "short_swept", "pixie", "crop")
OUTFITS = ("tee_jeans", "crew_tee_jeans", "longsleeve_jeans", "shirt_jeans", "denim_shirt_jeans", "jacket_jeans", "suit_tie",
           "overalls", "fitted_tee_jeans", "tee_shorts", "blouse_skirt", "sport_top_leggings")
FOOTWEAR = ("leather_shoes", "hiking_shoes", "boots", "black_shoes", "white_trainers", "blue_trainers")
#: MakeHuman's ethnic macros. A look's ``ethnicity`` weighs them; absent, an even blend.
ETHNICITIES = ("african", "asian", "caucasian")
#: A look's numbers and their bounds, and its colours. One table, the same in the three SDKs.
LOOK_BOUNDS: Dict[str, Tuple[float, float]] = {"height_m": (1.2, 2.2), "weight": (0, 1), "muscle": (0, 1), "proportions": (0, 1),
                                             "age_years": (25, 90)}
LOOK_COLOURS = ("skin", "hair", "top", "bottom", "shoes")
LOOK_FIELDS = ("body", "height_m", "weight", "muscle", "proportions", "age_years", "ethnicity") + LOOK_COLOURS + ("hair_style", "outfit", "footwear")

Rgb = Tuple[float, float, float]
"""sRGB, each from 0 to 1."""


class Look(TypedDict, total=False):
    """A robots entry's ``look``. ``weight``, ``muscle`` and ``proportions`` are MakeHuman's macros (0 to 1, 0.5
    average or neutral); ``age_years`` is 25 to 90 (MakeHuman's adult ages; absent, 25); ``ethnicity`` weighs
    ``ETHNICITIES`` (each 0 or more, not all 0; absent, an even blend); ``top``, ``bottom`` and ``shoes`` tint the
    outfit's and the footwear's own colours."""
    body: Literal["masculine", "feminine"]
    height_m: float
    weight: float
    muscle: float
    proportions: float
    age_years: float
    ethnicity: Dict[str, float]
    skin: Rgb
    hair: Rgb
    top: Rgb
    bottom: Rgb
    shoes: Rgb
    hair_style: str
    outfit: str
    footwear: str


#: Each goal's own fields, beside ``do``, ``plan`` and ``task``. One table, the same in the three SDKs. ``take`` …
#: ``ride`` are a worker's actions on a factory floor, ``drive`` … ``stop`` a vehicle's (CommandAGI's docs/formats.md §
#: a factory floor).
GOAL_FIELDS: Dict[str, Tuple[str, ...]] = {
    "walk": ("route", "speed"), "step": ("to", "heading"), "turn": ("heading",), "sit": ("seat", "facing"), "stand": (),
    "idle": ("activity", "seconds", "at", "with"), "reach": ("at", "hand", "seconds"),
    "take": ("body", "hands"), "put": ("at",), "push": ("body", "handle"), "jack": ("body", "handle"), "press": ("at",),
    "inspect": ("body", "seconds"), "hand": ("body", "to"), "ride": ("body", "at", "standing"), "get-off": ("to",),
    "drive": ("route", "speed", "reverse"), "dock": ("at", "heading", "speed", "reverse"), "lift": ("height", "load"), "mast": ("out",),
    "couple": ("body", "pin", "axle", "legs"), "uncouple": (), "stop": (), "program": ("program",),
}
BODY_GOALS = ("take", "push", "jack", "inspect", "hand", "ride")
VEHICLE_GOALS = ("drive", "dock", "lift", "mast", "couple", "uncouple", "stop")
WORK_HANDS = ("both", "left", "right")
GOAL_KINDS = tuple(GOAL_FIELDS)
IDLE_ACTIVITIES = ("type", "look", "still", "talk")
REACH_HANDS = ("left", "right", "both")
HUMANOID_POLICY_FIELDS = ("id", "kind", "unit", "hz", "lookahead", "routine", "repeat")

#: A goal: ``{"do": "walk", "route": [[x, y], ...], "speed"?}``, ``step`` (``to``, ``heading``?), ``turn`` (``heading``),
#: ``sit`` (``seat``, ``facing``), ``stand``, ``idle`` (``activity``?, ``seconds``?, ``at``?, ``with``?), ``reach``
#: (``at``, ``hand``?, ``seconds``?); any may carry ``plan``: ``{"policy", "step"}``. A routine's step adds ``wait``.
Goal = Dict[str, Any]


class HumanoidPolicy(TypedDict, total=False):
    id: str
    kind: Literal["humanoid"]
    unit: str
    hz: float
    lookahead: float
    routine: List[Goal]
    repeat: bool


#: The person's joints. Each is the constraint ``humanoid_constraint(unit, joint)`` that a ``motors`` command names.
HUMANOID_JOINTS: Tuple[str, ...] = (
    "spine_lower", "spine_lower_lean", "spine_lower_twist", "spine_upper", "spine_upper_lean", "spine_upper_twist",
    "neck_turn", "neck_nod", "neck_lean",
) + tuple(j for s in ("l", "r") for j in (
    f"shoulder_{s}", f"shoulder_{s}_abduct", f"shoulder_{s}_twist", f"elbow_{s}", f"wrist_{s}", f"wrist_{s}_deviate",
    f"hip_{s}", f"hip_{s}_abduct", f"hip_{s}_twist", f"knee_{s}", f"ankle_{s}", f"ankle_{s}_roll"))


def humanoid_constraint(unit: str, joint: str) -> str:
    """``ana``, ``knee_l`` → ``ana-knee-l``."""
    return f"{unit}-{joint.replace('_', '-')}"


def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _point(x: Any, n: int) -> bool:
    return isinstance(x, list) and len(x) == n and all(_num(c) for c in x)


def _text(x: Any) -> bool:
    return isinstance(x, str) and bool(x)


def _unknown(g: Dict[str, Any], fields, what: str) -> Optional[str]:
    for k in g:
        if k not in fields:
            return f"{what} has no field {k} (it has {', '.join(fields)})"
    return None


def check_look(look: Any, where: str = "robot") -> Any:
    """Refuses what the engine would refuse of a look; returns it. ``where``: the entry, for the words."""
    def no(why: str):
        raise ValueError(f"{where}: {why}")
    if look is None:
        return look
    if not isinstance(look, dict):
        no("look is { " + ", ".join(f"{k}?" for k in LOOK_FIELDS) + " }")
    bad = _unknown(look, LOOK_FIELDS, "look")
    if bad:
        no(bad)
    if "body" in look and look["body"] not in LOOK_BODIES:
        no(f"look.body is {' or '.join(LOOK_BODIES)}")
    for k, (lo, hi) in LOOK_BOUNDS.items():
        if k in look and not (_num(look[k]) and lo <= look[k] <= hi):
            no(f"look.{k} is a number from {lo:g} to {hi:g}")
    for k in LOOK_COLOURS:
        if k in look and not (_point(look[k], 3) and all(0 <= c <= 1 for c in look[k])):
            no(f"look.{k} is [r, g, b], sRGB from 0 to 1")
    if "ethnicity" in look:
        e = look["ethnicity"]
        ok = (isinstance(e, dict) and not _unknown(e, ETHNICITIES, "") and all(_num(w) and w >= 0 for w in e.values())
              and any(w > 0 for w in e.values()))
        if not ok:
            no("look.ethnicity is { " + ", ".join(f"{k}?" for k in ETHNICITIES) + " }, each a number 0 or more, not all 0")
    for k, options in (("hair_style", HAIR_STYLES), ("outfit", OUTFITS), ("footwear", FOOTWEAR)):
        if k in look and look[k] not in options:
            no(f"look.{k} is one of {', '.join(options)}")
    return look


def goal_problem(g: Any) -> Optional[str]:
    """What is wrong with a goal (its fields besides ``verb`` and ``unit``), or None."""
    if not isinstance(g, dict):
        return "a goal is an object"
    kind = g.get("do")
    if kind not in GOAL_FIELDS:
        return f"do is one of {', '.join(GOAL_KINDS)}"
    own = GOAL_FIELDS[kind]
    for k in g:
        if k not in ("do", "plan", "task") and k not in own:
            return f"{kind} has no field {k} (it has {', '.join(own + ('plan', 'task'))})"
    if "task" in g and not _text(g["task"]):
        return "task is a text (the dispatcher's token)"
    if kind in VEHICLE_GOALS:
        return _vehicle_goal_problem(g, kind)
    if kind == "program":
        p = g.get("program")
        ok = isinstance(p, dict) and isinstance(p.get("steps"), list) and len(p["steps"]) > 0 and all(isinstance(s, dict) and _text(s.get("id")) and _num(s.get("dur")) for s in p["steps"])
        return None if ok else "program is a program of steps ({ id, dur, … }: g1-skills.js compilePlan)"
    route = g.get("route")
    if kind == "walk" and not (isinstance(route, list) and 1 <= len(route) <= 64 and all(_point(p, 2) for p in route)):
        return "walk needs a route: 1 to 64 points [x, y] (metres)"
    if "speed" in g and not (_num(g["speed"]) and 0 < g["speed"] <= 1.6):
        return "walk speed is metres a second, above 0 and at most 1.6"
    if kind in BODY_GOALS and not _text(g.get("body")):
        return f"{kind} needs a body (what it takes, pushes, steers, inspects, hands over or rides on)"
    if "hands" in g and g["hands"] not in WORK_HANDS:
        return "hands is both, left or right"
    if kind == "press" and not _point(g.get("at"), 3):
        return "press needs at [x, y, z] (metres): the button"
    if kind == "put" and "at" in g and not _point(g["at"], 3):
        return "at is [x, y, z] (metres)"
    if "handle" in g and not _point(g["handle"], 3):
        return "handle is [x, y, z] (metres): where the hands close on it"
    if kind == "hand" and not _text(g.get("to")):
        return "hand needs to (the unit it hands the body to)"
    if kind == "ride" and "at" in g and not _point(g["at"], 3):
        return "ride at is [x, y, z] (metres): where its hips go on the seat or above the platform"
    if "standing" in g and not isinstance(g["standing"], bool):
        return "ride standing is true or false (on a stand-up platform)"
    if kind == "get-off" and not _point(g.get("to"), 2):
        return "get-off needs to [x, y] (metres): where it steps down to, beside its vehicle"
    if kind == "step" and not _point(g.get("to"), 2):
        return "step needs to [x, y] (the point it steps to, metres)"
    if kind == "turn" and not _num(g.get("heading")):
        return "turn needs a heading (radians about z, from +x)"
    if kind == "step" and "heading" in g and not _num(g["heading"]):
        return "step heading is radians about z, from +x"
    if kind == "sit" and not (_point(g.get("seat"), 3) and _num(g.get("facing"))):
        return "sit needs a seat [x, y, z] (where it sits, metres) and facing (the heading it sits facing, radians)"
    if "activity" in g and g["activity"] not in IDLE_ACTIVITIES:
        return f"idle activity is one of {', '.join(IDLE_ACTIVITIES)}"
    if kind == "idle" and "at" in g and not _point(g["at"], 3):
        return "idle at is a point [x, y, z] (where it types or looks, metres)"
    if "with" in g and not _text(g["with"]):
        return "idle with is the unit it talks with"
    if kind == "reach" and not _point(g.get("at"), 3):
        return "reach needs at [x, y, z] (the point it reaches for, metres)"
    if "hand" in g and g["hand"] not in REACH_HANDS:
        return "reach hand is left, right or both"
    if "seconds" in g and not (_num(g["seconds"]) and g["seconds"] > 0):
        return "seconds is a positive number"
    plan = g.get("plan")
    if "plan" in g and not (isinstance(plan, dict) and isinstance(plan.get("policy"), str)
                            and isinstance(plan.get("step"), int) and not isinstance(plan.get("step"), bool)):
        return "plan is { policy, step }"
    return None


def _vehicle_goal_problem(g: Dict[str, Any], kind: str) -> Optional[str]:
    """A vehicle goal's problem (drive, dock, lift, mast, couple, uncouple, stop), or None."""
    route = g.get("route")
    if kind == "drive" and not (isinstance(route, list) and 1 <= len(route) <= 128 and all(_point(p, 2) for p in route)):
        return "drive needs a route: 1 to 128 points [x, y] (metres)"
    if kind == "dock" and not (_point(g.get("at"), 2) and _num(g.get("heading"))):
        return "dock needs at [x, y] (metres) and heading (radians)"
    if kind == "lift" and not (_num(g.get("height")) and g["height"] >= 0):
        return "lift needs a height (metres, 0 or more)"
    if kind == "mast" and not (_num(g.get("out")) and g["out"] >= 0):
        return "mast needs out (metres, 0 or more: how far the mast reaches out)"
    if kind == "couple" and not (_text(g.get("body")) and _point(g.get("pin"), 3)):
        return "couple needs a body (what it tows) and pin [x, y, z] (metres, that body's frame: its drawbar eye or kingpin)"
    if "axle" in g and not _point(g["axle"], 2):
        return "axle is [x, y] (metres, the towed body's frame: the middle of its axle)"
    if "legs" in g and not _text(g["legs"]):
        return "legs names the towed unit's joint that cranks its landing gear"
    if "speed" in g and not (_num(g["speed"]) and 0 < g["speed"] <= 10):
        return "speed is metres a second, above 0 and at most 10"
    if "reverse" in g and not isinstance(g["reverse"], bool):
        return "reverse is true or false"
    if "load" in g and not isinstance(g["load"], str):
        return "load names a body"
    plan = g.get("plan")
    if "plan" in g and not (isinstance(plan, dict) and isinstance(plan.get("policy"), str)
                            and isinstance(plan.get("step"), int) and not isinstance(plan.get("step"), bool)):
        return "plan is { policy, step }"
    return None


def check_goal(cmd: Any) -> Any:
    """Refuses what the engine would refuse of a ``goal`` command; returns it."""
    if not isinstance(cmd, dict) or cmd.get("verb") != "goal":
        raise ValueError('goal: a goal command is { verb: "goal", unit, do, … }')
    if not _text(cmd.get("unit")):
        raise ValueError("goal: unit is the unit it moves")
    no = goal_problem({k: v for k, v in cmd.items() if k not in ("verb", "unit")})
    if no:
        raise ValueError(f"goal: {no}")
    return cmd


def check_humanoid_policy(policy: Any) -> Any:
    """Refuses what the engine would refuse of a humanoid policy's own fields; returns it."""
    p = policy if isinstance(policy, dict) else {}

    def no(why: str):
        raise ValueError(f"policy {p.get('id', 'undefined')}: {why}")
    if not _text(p.get("id")):
        no("id is a text")
    for k in p:
        if k not in HUMANOID_POLICY_FIELDS:
            no(f"unknown field {k} (it has {', '.join(HUMANOID_POLICY_FIELDS)})")
    if p.get("kind") != "humanoid":
        no("kind is humanoid")
    if not _text(p.get("unit")):
        no("unit is the robot it drives")
    if "hz" in p and not (_num(p["hz"]) and p["hz"] > 0):
        no("hz is a positive number")
    if "lookahead" in p and not (_num(p["lookahead"]) and p["lookahead"] >= 0):
        no("lookahead is seconds, 0 or more")
    if "routine" in p:
        routine = p["routine"]
        if not isinstance(routine, list) or not routine:
            no("routine is a list of goals")
        for i, g in enumerate(routine):
            # A step of the routine is a goal, and how long to wait once it is done (``wait``, seconds).
            if not isinstance(g, dict):
                why = "a goal is an object"
            elif "wait" in g and not (_num(g["wait"]) and g["wait"] >= 0):
                why = "wait is seconds, 0 or more"
            else:
                why = goal_problem({k: v for k, v in g.items() if k != "wait"})
            if why:
                no(f"routine[{i}]: {why}")
    if "repeat" in p and not isinstance(p["repeat"], bool):
        no("repeat is true or false")
    return policy


def check_motors(cmd: Any) -> Any:
    """Refuses what the engine would refuse of a ``motors`` command's shape; returns it."""
    def no(why: str):
        raise ValueError(f"motors {why}")
    if not isinstance(cmd, dict) or cmd.get("verb") != "motors":
        no('is { verb: "motors", set?, path?, since? }')
    bad = _unknown(cmd, ("verb", "set", "path", "since"), "motors")
    if bad:
        raise ValueError(bad)
    motors, path = cmd.get("set", {}), cmd.get("path", [])
    if not isinstance(motors, dict) or not isinstance(path, list) or (not motors and not path):
        no("needs set { <constraint>: { target | velocity, stiffness?, damping? } } or path [{ at, set: { <constraint>: target } }]")
    for cid, m in motors.items():
        if (not isinstance(m, dict) or _unknown(m, ("target", "velocity", "stiffness", "damping"), "")
                or ("target" not in m and "velocity" not in m) or not all(_num(v) for v in m.values())):
            no(f"set: {cid} is {{ target | velocity, stiffness?, damping? }}")
    before = -math.inf
    for pt in path:
        if not isinstance(pt, dict) or not (_num(pt.get("at")) and before < pt["at"] <= 10 and pt["at"] >= 0) or not isinstance(pt.get("set"), dict):
            no("path: each point is { at (seconds from now, increasing, at most 10), set: { <constraint>: target } }")
        before = pt["at"]
        for cid, v in pt["set"].items():
            if not _num(v):
                no(f"path: {cid} target {json.dumps(v)} is not a number")
    if "since" in cmd and not _num(cmd["since"]):
        no("since is the scene time its path starts at, not later than now")
    return cmd


#: ARKit's 52 face units (blendshapes), each from 0 (rest) to 1. A ``face`` command names them.
FACE_UNITS: Tuple[str, ...] = (
    "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight", "cheekPuff", "cheekSquintLeft",
    "cheekSquintRight", "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight",
    "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft",
    "eyeWideRight", "jawForward", "jawLeft", "jawOpen", "jawRight", "mouthClose", "mouthDimpleLeft", "mouthDimpleRight",
    "mouthFrownLeft", "mouthFrownRight", "mouthFunnel", "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft",
    "mouthPressRight", "mouthPucker", "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper",
    "mouthSmileLeft", "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
    "noseSneerLeft", "noseSneerRight", "tongueOut",
)

#: A ``face`` command: ``{"verb": "face", "unit", "set"?: {<face unit>: 0..1}, "path"?: [{"at", "set"}], "since"?}``,
#: ``at`` seconds from ``since`` (increasing, at most 10).
FaceCommand = Dict[str, Any]


def check_face(cmd: Any) -> Any:
    """Refuses what the engine would refuse of a ``face`` command's shape; returns it."""
    def no(why: str):
        raise ValueError(f"face {why}")
    if not isinstance(cmd, dict) or cmd.get("verb") != "face":
        no('is { verb: "face", unit, set?, path?, since? }')
    bad = _unknown(cmd, ("verb", "unit", "set", "path", "since"), "face")
    if bad:
        raise ValueError(bad)
    if not _text(cmd.get("unit")):
        no("needs a unit (the person whose face it moves)")
    weights, path = cmd.get("set", {}), cmd.get("path", [])
    if not isinstance(weights, dict) or not isinstance(path, list) or (not weights and not path):
        no("needs set { <face unit>: 0 to 1 } or path [{ at, set: { <face unit>: 0 to 1 } }]")

    def check(where: str, w: Dict[str, Any]):
        for name, v in w.items():
            if name not in FACE_UNITS:
                no(f"{where}: {name} is not one of ARKit's 52 face units (browDownLeft … tongueOut)")
            if not (_num(v) and 0 <= v <= 1):
                no(f"{where}: {name} is a number from 0 to 1")
    check("set", weights)
    before = -math.inf
    for pt in path:
        if not isinstance(pt, dict) or not (_num(pt.get("at")) and before < pt["at"] <= 10 and pt["at"] >= 0) or not isinstance(pt.get("set"), dict):
            no("path: each point is { at (seconds from now, increasing, at most 10), set: { <face unit>: 0 to 1 } }")
        before = pt["at"]
        check("path", pt["set"])
    if "since" in cmd and not _num(cmd["since"]):
        no("since is the scene time its path starts at, not later than now")
    return cmd


def check_assist(cmd: Any) -> Any:
    """Refuses what the engine would refuse of an ``assist`` command's shape; returns it."""
    if not isinstance(cmd, dict) or cmd.get("verb") != "assist":
        raise ValueError('assist is { verb: "assist", body, heading }')
    bad = _unknown(cmd, ("verb", "body", "heading"), "assist")
    if bad:
        raise ValueError(bad)
    if not _text(cmd.get("body")):
        raise ValueError("assist needs a body (the body whose balance aid it turns)")
    heading = cmd.get("heading", math.nan)
    if heading is not None and not _num(heading):
        raise ValueError("assist needs a heading (radians) or null")
    return cmd


__all__ = [
    "LOOK_BODIES", "HAIR_STYLES", "OUTFITS", "FOOTWEAR", "ETHNICITIES", "LOOK_BOUNDS", "LOOK_COLOURS", "LOOK_FIELDS", "Rgb", "Look",
    "GOAL_FIELDS", "GOAL_KINDS", "BODY_GOALS", "VEHICLE_GOALS", "WORK_HANDS", "IDLE_ACTIVITIES", "REACH_HANDS", "HUMANOID_POLICY_FIELDS", "Goal", "HumanoidPolicy",
    "HUMANOID_JOINTS", "humanoid_constraint", "check_look", "goal_problem", "check_goal", "check_humanoid_policy",
    "check_motors", "check_assist", "FACE_UNITS", "FaceCommand", "check_face",
]
