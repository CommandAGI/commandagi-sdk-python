"""Agents, declared in Python: a ``harness.py`` and an ``agent.py``, the same documents and the same elements as the
TypeScript SDK's JSX (``commandagi/design`` ``agents.ts``; docs/agents.md in the CommandAGI repository), each element a
call::

    from commandagi.design.agents import agent, harness

    # cloud://global/agents/harnesses/claude-code/harness.py — a CLI agent program
    result = harness(kind="cli", label="Claude Code", provider="anthropic", cli="claude", runs=["host", "vm"])

    # cloud://global/agents/harnesses/openai-realtime/harness.py — a model that converses live
    result = harness(kind="api", label="OpenAI Realtime API", provider="openai", runs=["worker", "host"], realtime={
        "in": ["audio", "video", "text"], "out": ["audio", "text", "tools"],
        "audio": {"in": ["g711-ulaw@8000", "pcm16@24000"], "out": ["g711-ulaw@8000", "pcm16@24000"]},
        "fps": 1, "hz": 2, "minutes": 60})

    # agents/secretary/agent.py in an account's Drive — a fork
    result = agent(parent="cloud://global/agents/claude-code", name="Joe's secretary", instructions="Keep Joe's calendar.")

A harness is the program that runs an agent and talks to a model: a CLI agent, an API provider's loop, or a program
with no model. A base instance names its harness and has no parent; every other instance is a fork: it names its parent
and keeps its parent's harness. A file never names itself: a harness's id and an agent's id are their folders' names.

Attributes are snake_case keywords (``voice_mode`` is ``voiceMode``). ``realtime`` and ``persona`` are plain data,
written with the TypeScript names as keys (``"videoMinutes"``). Nothing adds a default: what the file does not say,
the document does not have.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

#: What runs an agent: a CLI program, an API provider's loop, or a program with no model.
HARNESS_KINDS = ["cli", "api", "program"]
#: Where a harness runs: this machine's host, a cloud computer (the thread's VM kernel), or the api worker's loop.
HARNESS_RUNTIMES = ["host", "vm", "worker"]
#: What a single-task model does in one turn.
HARNESS_TASKS = ["classify", "decide", "extract", "summarize", "act"]
#: What a realtime harness's model takes live, and gives live (docs/realtime-agents.md).
REALTIME_IN = ["audio", "video", "text"]
REALTIME_OUT = ["audio", "text", "tools"]
#: G.711 μ-law (a telephone call) and 16-bit little-endian PCM, mono, at a rate.
AUDIO_FORMATS = ["g711-ulaw@8000", "pcm16@8000", "pcm16@16000", "pcm16@24000"]
HARNESS_FIELDS = ["kind", "label", "provider", "cli", "runs", "tasks", "realtime", "family", "experimental", "homepage", "about"]
AGENT_FIELDS = ["harness", "parent", "name", "model", "effort", "instructions", "voice", "voiceMode", "tools", "persona", "color",
                "icon", "gender"]
VOICE_MODES = ["off", "push-to-talk", "open-mic"]
REALTIME_FIELDS = ["in", "out", "audio", "fps", "hz", "minutes", "videoMinutes"]
#: An id: a folder name.
AGENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

#: Every tag and what it holds (the TypeScript SDK's vocabularies: each is a leaf).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "harness": {},
    "agent": {},
}

__all__ = ["HARNESS_KINDS", "HARNESS_RUNTIMES", "HARNESS_TASKS", "REALTIME_IN", "REALTIME_OUT", "AUDIO_FORMATS", "HARNESS_FIELDS",
           "AGENT_FIELDS", "VOICE_MODES", "REALTIME_FIELDS", "AGENT_ID", "SIGNATURES", "HARNESS_VOCABULARY", "AGENT_VOCABULARY",
           *define(globals(), "agents", SIGNATURES)]


def _quoted(values: List[str]) -> str:
    return ", ".join(f'"{x}"' for x in values)


def _word(t: DocTree, k: str) -> None:
    v = t["attrs"].get(k)
    if k in t["attrs"] and (not isinstance(v, str) or not v):
        raise ValueError(f"<{t['tag']}> {k} is a word, not {v!r}")


def _one_of(t: DocTree, k: str, values: List[str]) -> None:
    if k in t["attrs"] and t["attrs"][k] not in values:
        raise ValueError(f"<{t['tag']}> {k} is {_quoted(values)}, not {t['attrs'][k]!r}")


def _list_of(x: Any, allowed: List[str], empty: bool = False) -> bool:
    return isinstance(x, list) and (empty or len(x) > 0) and all(y in allowed for y in x) and len(set(x)) == len(x)


def _positive(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def _check_realtime(v: Any) -> None:
    def no(why: str) -> None:
        raise ValueError(f"<harness> realtime {why}")

    if not isinstance(v, dict):
        no(f'is an object ({{"in": ["audio"], "out": ["audio", "tools"], …}}), not {v!r}')
    for k in v:
        if k not in REALTIME_FIELDS:
            no(f"has no field {k}; its fields are {', '.join(REALTIME_FIELDS)}")
    if not _list_of(v.get("in"), REALTIME_IN):
        no(f"in is a list of {_quoted(REALTIME_IN)}")
    if not _list_of(v.get("out"), REALTIME_OUT):
        no(f"out is a list of {_quoted(REALTIME_OUT)}")
    ins, outs, audio = v["in"], v["out"], v.get("audio")
    if "audio" in ins or "audio" in outs:
        if not isinstance(audio, dict):
            no('audio names the formats it takes and gives: {"in": ["pcm16@24000"], "out": ["pcm16@24000"]}')
        for side, said in (("in", ins), ("out", outs)):
            if "audio" in said and not _list_of(audio.get(side), AUDIO_FORMATS):
                no(f"audio.{side} is a list of {_quoted(AUDIO_FORMATS)}")
    elif audio is not None:
        no("audio is for a harness that takes or gives audio")
    if "video" in ins and not _positive(v.get("fps")):
        no("fps is the most video frames a second it takes (a harness that takes video says it)")
    if "tools" in outs and not _positive(v.get("hz")):
        no("hz is the most tool calls a second it decides (a harness that calls tools says it)")
    for k in ("fps", "hz", "minutes", "videoMinutes"):
        if k in v and not _positive(v[k]):
            no(f"{k} is a positive number, not {v[k]!r}")


def _harness(t: DocTree) -> Dict[str, Any]:
    if t["children"]:
        raise ValueError("<harness> has no children")
    a = t["attrs"]
    for k in ("label", "provider", "cli", "family", "homepage", "about"):
        _word(t, k)
    _one_of(t, "kind", HARNESS_KINDS)
    if "experimental" in a and not isinstance(a["experimental"], bool):
        raise ValueError(f"<harness> experimental is True or False, not {a['experimental']!r}")
    if "runs" in a and not _list_of(a["runs"], HARNESS_RUNTIMES, empty=True):
        raise ValueError(f"<harness> runs is a list of {_quoted(HARNESS_RUNTIMES)}, not {a['runs']!r}")
    if "tasks" in a and not _list_of(a["tasks"], HARNESS_TASKS):
        raise ValueError(f"<harness> tasks is a list of {_quoted(HARNESS_TASKS)}, not {a['tasks']!r}")
    if "tasks" in a and a.get("kind") != "api":
        raise ValueError('<harness> tasks is for kind="api" only: a model that does one task in a turn')
    if a.get("kind") == "cli" and "cli" not in a:
        raise ValueError('<harness kind="cli"> names the program it starts: cli="claude"')
    if a.get("kind") != "cli" and "cli" in a:
        raise ValueError('<harness> cli is for kind="cli" only')
    if a.get("kind") == "api" and "provider" not in a:
        raise ValueError('<harness kind="api"> names its provider in the model catalog: provider="anthropic"')
    if "realtime" in a:
        if a.get("kind") != "api" or "tasks" in a:
            raise ValueError('<harness> realtime is for kind="api" with no tasks: a model that converses live')
        _check_realtime(a["realtime"])
    return {k: a[k] for k in HARNESS_FIELDS if k in a}


def _agent(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("harness", "parent", "name", "model", "effort", "instructions", "voice", "color", "icon", "gender"):
        _word(t, k)
    _one_of(t, "voiceMode", VOICE_MODES)
    base, fork = "harness" in a, "parent" in a
    if base == fork:
        raise ValueError("<agent> names a harness (a base instance) or a parent (a fork), not both: a fork keeps its parent's harness" if base
                         else '<agent> names its harness (a base instance: harness="claude-code") or its parent (a fork: parent="cloud://global/agents/claude-code")')
    if base and not AGENT_ID.match(a["harness"]):
        raise ValueError(f'<agent> harness is a harness\'s id ("claude-code"), not {a["harness"]!r}')
    tools = a.get("tools")
    if "tools" in a and not (isinstance(tools, list) and all(isinstance(x, str) and x for x in tools)):
        raise ValueError(f"<agent> tools is a list of tool names, not {tools!r}")
    if "persona" in a and not isinstance(a["persona"], dict):
        raise ValueError(f'<agent> persona is an object ({{"tone": "warm"}}), not {a["persona"]!r}')
    if t["children"]:
        raise ValueError('<agent> has no children; its instructions are its instructions="…" attribute')
    return {k: a[k] for k in AGENT_FIELDS if k in a}


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


HARNESS_VOCABULARY = Vocabulary("harness", "an agent harness", "harness", {
    "harness": {"parents": [], "required": ["kind", "label"], "attrs": HARNESS_FIELDS},
}, _harness, _never)

AGENT_VOCABULARY = Vocabulary("agent", "an agent", "agent", {
    "agent": {"parents": [], "attrs": AGENT_FIELDS},
}, _agent, _never)

for _v in (HARNESS_VOCABULARY, AGENT_VOCABULARY):
    register_vocabulary(_v, "agents")
