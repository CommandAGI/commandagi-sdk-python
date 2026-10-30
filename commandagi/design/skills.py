"""A symbolic agent's skill, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``skills.ts``), each element a call. ``skills/<name>/skill.py`` declares one ``skill``; its name is
its folder's name, so the file never names itself::

    from commandagi.design.skills import phrase, reply, skill, step

    result = skill(
        phrase(match="count [the] errors in {file:path}"),
        step(tool="read_file", args={"path": "{file}"}, as_="read"),
        step(script="./count.py", args={"text": "{read.text}", "word": "error"}, as_="n"),
        reply(text="{file} has {n} lines that say error."),
        about="How many lines of a file say error.",
    )

A literal script beside it reads its step's ``args`` as ``inputs`` and sets ``result`` to a ``result``::

    # skills/count-errors/count.py
    from commandagi.design.skills import result

    result = result(value=len([l for l in inputs["text"].split("\\n") if inputs["word"] in l]))

What a skill holds, each a child call in the order written: ``phrase(match=…)``, ``step(…)`` (exactly one of ``expr``,
``tool``, ``script``, ``skill`` or ``see``; ``args``; ``as_`` binds its value; ``always``), ``reply(text=…)``,
``rule(if_=…, then=…)``, ``fact(is_=…)`` and ``example(say=…, reply=…)``; on ``skill`` itself ``about``, ``needs``,
``gives``, ``removes`` and ``origin``. Structure only: the phrases, expressions and facts are read, and a skill is
admitted or rejected, by the agent's runtime (``packages/domain/world/symbolic`` in the CommandAGI repository).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

SKILL_FIELDS = ["about", "needs", "gives", "removes", "origin"]
PHRASE_FIELDS = ["match"]
STEP_KINDS = ["expr", "tool", "script", "skill", "see"]
STEP_FIELDS = [*STEP_KINDS, "args", "as", "always", "image", "template", "against"]
RULE_FIELDS = ["if", "then", "name"]
EXAMPLE_FIELDS = ["say", "reply"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "skill": {"holds": "children"},
    "phrase": {},
    "step": {},
    "reply": {},
    "rule": {},
    "fact": {},
    "example": {},
    "result": {},
}

__all__ = ["SKILL_FIELDS", "STEP_KINDS", "STEP_FIELDS", "RULE_FIELDS", "SIGNATURES", "SKILL_VOCABULARY",
           "RESULT_VOCABULARY", *define(globals(), "skills", SIGNATURES)]


def _said(attrs: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in keys if k in attrs and attrs[k] is not None}


def _nothing(v: Any) -> bool:
    return v is None or v == "" or (isinstance(v, list) and not v)


def _text(t: DocTree, k: str) -> None:
    v = t["attrs"].get(k)
    if k in t["attrs"] and (not isinstance(v, str) or not v):
        raise ValueError(f"<{t['tag']}> {k} is text, not {_json(v)}")


def _texts(t: DocTree, k: str) -> None:
    v = t["attrs"].get(k)
    if k in t["attrs"] and not (isinstance(v, list) and all(isinstance(x, str) and x for x in v)):
        raise ValueError(f"<{t['tag']}> {k} is a list of facts ([\"at(?unit, home)\"]), not {_json(v)}")


def _skill(t: DocTree) -> Dict[str, Any]:
    """A skill as its elements declare it; raises with why it does not read (the TypeScript SDK's ``skillOf``)."""
    for k in ("about", "origin"):
        _text(t, k)
    for k in ("needs", "gives", "removes"):
        _texts(t, k)

    def parts(tag: str) -> List[DocTree]:
        return [c for c in t["children"] if c["tag"] == tag]

    steps = []
    for i, s in enumerate(parts("step")):
        kinds = [k for k in STEP_KINDS if k in s["attrs"]]
        if len(kinds) != 1:
            has = f" (it has {' and '.join(kinds)})" if kinds else ""
            raise ValueError(f"<step> {i + 1} is exactly one of {', '.join(STEP_KINDS)}{has}")
        for k in (*STEP_KINDS, "as", "image", "template", "against"):
            _text(s, k)
        if "always" in s["attrs"] and not isinstance(s["attrs"]["always"], bool):
            raise ValueError(f"<step> {i + 1}: always is true or false, not {_json(s['attrs']['always'])}")
        if "args" in s["attrs"] and not isinstance(s["attrs"]["args"], dict):
            raise ValueError(f"<step> {i + 1}: args is an object ({{ path: \"{{file}}\" }}), not {_json(s['attrs']['args'])}")
        steps.append(_said(s["attrs"], STEP_FIELDS))
    rules = []
    for r in parts("rule"):
        cond = r["attrs"].get("if")
        if not ((isinstance(cond, str) and cond) or (isinstance(cond, list) and cond and all(isinstance(x, str) and x for x in cond))):
            raise ValueError(f"<rule> if is a fact or a list of facts, not {_json(cond)}")
        _text(r, "then")
        _text(r, "name")
        rules.append(_said(r["attrs"], RULE_FIELDS))
    replies = parts("reply")
    if replies:
        _text(replies[0], "text")
    phrases = []
    for p in parts("phrase"):
        _text(p, "match")
        phrases.append({"match": p["attrs"]["match"]})
    facts = []
    for f in parts("fact"):
        _text(f, "is")
        facts.append(f["attrs"]["is"])
    examples = []
    for e in parts("example"):
        say, rep = e["attrs"].get("say"), e["attrs"].get("reply")
        if not isinstance(say, str) or not say or not isinstance(rep, str):
            raise ValueError('<example> is say="…" reply="…"')
        examples.append({"say": say, "reply": rep})
    out: Dict[str, Any] = {**_said(t["attrs"], SKILL_FIELDS), "phrases": phrases, "steps": steps}
    if replies:
        out["reply"] = replies[0]["attrs"]["text"]
    out.update({"rules": rules, "facts": facts, "examples": examples})
    return out


def _leaf(tag: str, attrs: Dict[str, Any]) -> DocTree:
    return {"tag": tag, "attrs": attrs, "children": []}


def _attrs(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {k: o[k] for k in keys if not _nothing(o.get(k))}


def _skill_tree(s: Dict[str, Any]) -> DocTree:
    return {"tag": "skill", "attrs": _attrs(s, SKILL_FIELDS), "children": [
        *[_leaf("phrase", {"match": p["match"]}) for p in s.get("phrases") or []],
        *[_leaf("step", _attrs(x, STEP_FIELDS)) for x in s.get("steps") or []],
        *([_leaf("reply", {"text": s["reply"]})] if s.get("reply") else []),
        *[_leaf("rule", _attrs(r, RULE_FIELDS)) for r in s.get("rules") or []],
        *[_leaf("fact", {"is": f}) for f in s.get("facts") or []],
        # An example's reply may be empty text, which is still a reply.
        *[_leaf("example", {"say": e["say"], "reply": e["reply"]}) for e in s.get("examples") or []],
    ]}


def _result(t: DocTree) -> Dict[str, Any]:
    if t["children"]:
        raise ValueError("<result> has no children; its value is its value= attribute")
    return {"value": t["attrs"].get("value")}


SKILL_VOCABULARY = Vocabulary("skill", "a skill", "skill", {
    "skill": {"parents": [], "attrs": SKILL_FIELDS},
    "phrase": {"parents": ["skill"], "key": "match", "required": ["match"], "attrs": PHRASE_FIELDS},
    "step": {"parents": ["skill"], "attrs": STEP_FIELDS},
    "reply": {"parents": ["skill"], "single": True, "required": ["text"], "attrs": ["text"]},
    "rule": {"parents": ["skill"], "required": ["if", "then"], "attrs": RULE_FIELDS},
    "fact": {"parents": ["skill"], "key": "is", "required": ["is"], "attrs": ["is"]},
    "example": {"parents": ["skill"], "key": "say", "required": ["say", "reply"], "attrs": EXAMPLE_FIELDS},
}, _skill, _skill_tree, lambda _stem: {"phrases": [], "steps": [], "rules": [], "facts": [], "examples": []})

RESULT_VOCABULARY = Vocabulary("result", "a script's result", "result", {
    "result": {"parents": [], "required": ["value"], "attrs": ["value"]},
}, _result, lambda r: _leaf("result", {"value": r.get("value")}))

register_vocabulary(SKILL_VOCABULARY, "skills")
register_vocabulary(RESULT_VOCABULARY, "skills")
