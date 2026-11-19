"""AGENTS IN A SCENE — the ``agents`` a design's ``slot(name="scene")`` holds (docs/formats.md § simulations, "Agents in
a scene", in the CommandAGI repository): a model agent attached to robots of the scene, or to some joints of one (its
actuators). Each acts as ``agent:<id>`` through the simulation's own commands, and only on its ``units``: that list is
its grant in the simulation, and it grants nothing on hardware. The same as the TypeScript SDK's ``scene-agents.ts``;
the scene stays a plain dict, so the editor writes into it::

    from commandagi.design.scene_agents import check_scene_agents

    scene = check_scene_agents({
        "hz": 240, "robots": [{"id": "left", ...}, {"id": "right", ...}],
        "agents": [{"id": "pilot", "units": ["left"], "instructions": "Keep the left arm clear of the cube."},
                   {"id": "wrist", "units": ["right.wrist_flex"]}],
    })

An agent's ``model`` is ``<route>/<model>`` on a route of the agent runtime (openrouter, deepinfra, deepseek, dashscope);
absent, ``deepseek/deepseek-flash``.

``check_scene_agents`` refuses what the engine refuses, in its words: an unknown field, a malformed or repeated id, an
id that is a policy's principal, a unit that is no robot of the scene nor a joint of one, an empty text.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

#: An entry's fields: the ones it needs, then the ones it may have. One table, the same in the three SDKs.
SCENE_AGENT_FIELDS: Dict[str, list] = {"needs": ["id", "units"], "may": ["model", "instructions", "label"]}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


def check_scene_agents(scene: Dict[str, Any]) -> Dict[str, Any]:
    """Refuses what the engine would refuse (``ValueError``); returns the scene. It reads ``robots``, ``policies`` and ``agents``."""
    agents = scene.get("agents")
    if agents is None:
        return scene
    if not isinstance(agents, list):
        raise ValueError("simulation: agents is a list")
    robots = {r.get("id") for r in scene.get("robots") or []}
    policies = {f"agent:policy-{p.get('id')}" for p in scene.get("policies") or []}
    fields = SCENE_AGENT_FIELDS["needs"] + SCENE_AGENT_FIELDS["may"]
    ids = set()
    for a in agents:
        aid = a.get("id") if isinstance(a, dict) else None
        if not isinstance(aid, str) or not _ID.match(aid) or aid in ids:
            raise ValueError(f"agent {aid if aid is not None else 'undefined'}: missing, malformed or duplicate id (lower case letters, digits and -)")
        ids.add(aid)
        where = f"agent {aid}"
        for k in a:
            if k not in fields:
                raise ValueError(f"{where}: unknown field {k} (it has {', '.join(fields)})")
        if f"agent:{aid}" in policies:
            raise ValueError(f"{where}: agent:{aid} is the principal of a policy of this scene")
        units = a.get("units")
        if not isinstance(units, list) or not units:
            raise ValueError(f'{where}: units is a list of the robots it drives ("arm") or their joints ("arm.j1")')
        for u in units:
            robot = u.split(".")[0] if isinstance(u, str) else None
            if not robot or robot not in robots or ("." in u and not u.split(".")[1]):
                raise ValueError(f"{where}: unit {json.dumps(u)} is not a robot of this scene or a joint of one")
        for k in ("model", "instructions", "label"):
            if k in a and (not isinstance(a[k], str) or not a[k]):
                raise ValueError(f"{where}: {k} is a text")
    return scene
