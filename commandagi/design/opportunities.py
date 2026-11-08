"""An opportunity and an experiment, declared in Python: the same documents and the same elements as the TypeScript
SDK's JSX (``commandagi/design`` ``opportunities.ts``), each element a call. ``<name>.opportunity.py`` declares one
``opportunity`` (a collaborator, a partnership or a listing; an application is its folder of ``applications/`` and a
client is a company's ``Deal``), and ``<name>.experiment.py`` one ``experiment`` (keywords are the attributes in
snake_case: ``approved_by`` is ``approvedBy``; ``from_`` is ``from``)::

    from commandagi.design.opportunities import opportunity, contact, action, draft

    result = opportunity(
        contact(ref="../relationships/cards/fetch-ai.vcf", role="marketplace"),
        action(id="approve", title="Approve the listing's text", owner="person:jacob-valdez", decision=True),
        draft(id="listing", channel="agentverse", body="Plans, simulates and runs robots."),
        title="CommandAGI's agent on Agentverse", kind="listing", stage="draft", channel="agentverse",
    )

A stage is one of its kind's (``OPPORTUNITY_STAGES``); the last ``move`` names the stage it is in. A ``draft`` is all
that exists until a principal approves it (``approved_by``, ``approved_at``): a listing is never ``submitted`` or
``live`` without an approved draft. An experiment's objectives are kept apart by kind (quality, distribution, impact);
reach alone is never an objective.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Callable, Dict, List

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

OPPORTUNITY_KINDS = ["collaborator", "partnership", "listing"]
OPPORTUNITY_STAGES = {
    "collaborator": {"open": ["found", "contacted", "talking", "working"], "closed": ["ended", "dropped"]},
    "partnership": {"open": ["found", "contacted", "negotiating", "active"], "closed": ["ended", "declined", "dropped"]},
    "listing": {"open": ["draft", "approved", "submitted", "live"], "closed": ["withdrawn", "refused"]},
}
PUBLIC_STAGES = ["submitted", "live"]
OPPORTUNITY_STATUSES = ["open", "waiting", "blocked", "closed"]
ELIGIBILITIES = ["eligible", "eligible-with-partner", "not-eligible", "unknown"]
OPPORTUNITY_FIELDS = ["title", "kind", "stage", "status", "source", "deadline", "value", "currency", "eligibility", "folder", "owner", "counterparty", "channel", "handle", "about"]
CONTACT_FIELDS = ["ref", "role", "note"]
ACTION_FIELDS = ["id", "title", "due", "owner", "decision", "done"]
EVIDENCE_FIELDS = ["id", "fact", "ref", "source", "way", "by", "at"]
MOVE_FIELDS = ["from", "to", "at", "by", "note"]
DRAFT_FIELDS = ["id", "channel", "to", "subject", "body", "approvedBy", "approvedAt"]

EXPERIMENT_STATUSES = ["draft", "running", "decided", "stopped"]
OBJECTIVE_KINDS = ["quality", "distribution", "impact"]
EXPERIMENT_FIELDS = ["title", "hypothesis", "status", "opportunity", "channel", "started", "ended"]
ARM_FIELDS = ["id", "file", "note"]
OBJECTIVE_FIELDS = ["id", "kind", "metric", "direction", "note"]
DECISION_FIELDS = ["arm", "at", "by", "reason"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "opportunity": {"holds": "children"}, "contact": {}, "action": {}, "evidence": {}, "move": {}, "draft": {},
    "experiment": {"holds": "children"}, "arm": {}, "objective": {}, "decision": {},
}

__all__ = ["OPPORTUNITY_KINDS", "OPPORTUNITY_STAGES", "PUBLIC_STAGES", "OPPORTUNITY_STATUSES", "ELIGIBILITIES",
           "EXPERIMENT_STATUSES", "OBJECTIVE_KINDS", "SIGNATURES", "stages_of", "closes_kind", "opportunity_of",
           "experiment_of", "OPPORTUNITY_VOCABULARY", "EXPERIMENT_VOCABULARY", *define(globals(), "opportunities", SIGNATURES)]

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$")
_PRINCIPAL = re.compile(r"^(?:person|agent|org|role):[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$")
_DECIMAL = re.compile(r"^\d+(?:\.\d+)?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _said(v: Any) -> str:
    return _json(v)


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v.encode("utf-16-le")) // 2 <= mx


def _parses(v: str) -> bool:
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _day(v: Any) -> bool:
    return isinstance(v, str) and bool(_DAY.match(v) or _INSTANT.match(v)) and _parses(v)


def _instant(v: Any) -> bool:
    return isinstance(v, str) and bool(_INSTANT.match(v)) and _parses(v)


def _principal(v: Any) -> bool:
    return isinstance(v, str) and bool(_PRINCIPAL.match(v))


def _id(v: Any) -> bool:
    return isinstance(v, str) and bool(_ID.match(v))


def _keep(out: Dict[str, Any], a: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    for k in fields:
        if k in a and k not in out:
            out[k] = a[k]
    return out


def _stamp(v: str) -> float:
    return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()


def stages_of(kind: str) -> List[str]:
    """The stages of a kind, open then closed (the TypeScript SDK's ``stagesOf``)."""
    s = OPPORTUNITY_STAGES[kind]
    return [*s["open"], *s["closed"]]


def closes_kind(kind: str, stage: str) -> bool:
    return stage in OPPORTUNITY_STAGES[kind]["closed"]


def _contact(a: Dict[str, Any]) -> Dict[str, Any]:
    if not _text(a.get("ref"), 1000):
        raise ValueError(f"<contact> ref names a card (a .vcf, by ref) or a relationship's id, not {_said(a.get('ref'))}")
    at = f'<contact ref="{a["ref"]}">'
    for k in ("role", "note"):
        if k in a and not _text(a[k], 2000 if k == "note" else 80):
            raise ValueError(f"{at} {k} is a short text, not {_said(a[k])}")
    return _keep({"ref": a["ref"]}, a, CONTACT_FIELDS)


def _action(a: Dict[str, Any]) -> Dict[str, Any]:
    if not _id(a.get("id")):
        raise ValueError(f"<action> id is lower-case letters, digits and dashes (at most 64), not {_said(a.get('id'))}")
    at = f'<action id="{a["id"]}">'
    if not _text(a.get("title"), 200):
        raise ValueError(f"{at} title is a short text (at most 200), not {_said(a.get('title'))}")
    if "due" in a and not _day(a["due"]):
        raise ValueError(f"{at} due is an ISO 8601 day or instant, not {_said(a['due'])}")
    if "done" in a and not _day(a["done"]):
        raise ValueError(f"{at} done is the ISO 8601 day or instant it was done, not {_said(a['done'])}")
    if "owner" in a and not _principal(a["owner"]):
        raise ValueError(f"{at} owner is a principal (person:, agent:, org: or role:<id>), not {_said(a['owner'])}")
    if "decision" in a and not isinstance(a["decision"], bool):
        raise ValueError(f"{at} decision is true when only its owner can decide it, not {_said(a['decision'])}")
    return _keep({"id": a["id"], "title": a["title"]}, a, ACTION_FIELDS)


def _evidence(a: Dict[str, Any]) -> Dict[str, Any]:
    if not _id(a.get("id")):
        raise ValueError(f"<evidence> id is lower-case letters, digits and dashes (at most 64), not {_said(a.get('id'))}")
    at = f'<evidence id="{a["id"]}">'
    if not _text(a.get("fact"), 2000):
        raise ValueError(f"{at} fact says what it is evidence of, not {_said(a.get('fact'))}")
    if "ref" not in a and "source" not in a:
        raise ValueError(f"{at} names where the fact was read: a ref (a file) or a source (a URL)")
    for k in ("ref", "source", "way"):
        if k in a and not _text(a[k], 2000):
            raise ValueError(f"{at} {k} is a text, not {_said(a[k])}")
    if "by" in a and not _principal(a["by"]):
        raise ValueError(f"{at} by is the principal that read it, not {_said(a['by'])}")
    if "at" in a and not _instant(a["at"]):
        raise ValueError(f"{at} at is the ISO 8601 instant it was read, not {_said(a['at'])}")
    return _keep({"id": a["id"], "fact": a["fact"]}, a, EVIDENCE_FIELDS)


def _move(a: Dict[str, Any], kind: str) -> Dict[str, Any]:
    stages = stages_of(kind)
    if not _instant(a.get("at")):
        raise ValueError(f"<move> at is an ISO 8601 instant, not {_said(a.get('at'))}")
    at = f'<move at="{a["at"]}">'
    if a.get("to") not in stages:
        raise ValueError(f"{at} to is a stage of a {kind} ({', '.join(stages)}), not {_said(a.get('to'))}")
    if "from" in a and a["from"] not in stages:
        raise ValueError(f"{at} from is a stage of a {kind}, not {_said(a['from'])}")
    if "from" in a and a["from"] == a["to"]:
        raise ValueError(f"{at} moves to the stage it is in ({a['to']})")
    if not _principal(a.get("by")):
        raise ValueError(f"{at} by is the principal who moved it, not {_said(a.get('by'))}")
    if "note" in a and not _text(a["note"], 2000):
        raise ValueError(f"{at} note is a text, not {_said(a['note'])}")
    return _keep({"to": a["to"], "at": a["at"], "by": a["by"]}, a, MOVE_FIELDS)


def _draft(a: Dict[str, Any]) -> Dict[str, Any]:
    if not _id(a.get("id")):
        raise ValueError(f"<draft> id is lower-case letters, digits and dashes (at most 64), not {_said(a.get('id'))}")
    at = f'<draft id="{a["id"]}">'
    if not _text(a.get("body"), 20000):
        raise ValueError(f"{at} body is the text that would be sent or published (at most 20000), not {_said(a.get('body'))}")
    if "channel" in a and not _id(a["channel"]):
        raise ValueError(f"{at} channel is a channel's id, not {_said(a['channel'])}")
    for k in ("to", "subject"):
        if k in a and not _text(a[k], 1000):
            raise ValueError(f"{at} {k} is a short text, not {_said(a[k])}")
    if ("approvedBy" in a) != ("approvedAt" in a):
        raise ValueError(f"{at} approvedBy and approvedAt come together: who approved it, and when")
    if "approvedBy" in a and not _principal(a["approvedBy"]):
        raise ValueError(f"{at} approvedBy is the principal that approved it, not {_said(a['approvedBy'])}")
    if "approvedAt" in a and not _instant(a["approvedAt"]):
        raise ValueError(f"{at} approvedAt is an ISO 8601 instant, not {_said(a['approvedAt'])}")
    return _keep({"id": a["id"], "body": a["body"]}, a, DRAFT_FIELDS)


def _many(t: DocTree, tag: str, key: str, of: Callable[[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out = []
    for c in t["children"]:
        if c["tag"] != tag:
            continue
        k = _said(c["attrs"].get(key))
        if k in seen:
            raise ValueError(f"<{tag} {key}={k}> is declared twice")
        seen.add(k)
        out.append(of(c["attrs"]))
    return out


def opportunity_of(t: DocTree) -> Dict[str, Any]:
    """An opportunity as its tree declares it (the TypeScript SDK's ``opportunityOf``)."""
    a = t["attrs"]
    if not _text(a.get("title"), 160):
        raise ValueError(f"<opportunity> title is a short text (at most 160), not {_said(a.get('title'))}")
    at = f'<opportunity title="{a["title"]}">'
    kind = a.get("kind")
    if kind not in OPPORTUNITY_KINDS:
        home = ": an application is its folder of applications/" if kind == "application" else ": a client is a <Deal> of its company" if kind == "client" else ""
        raise ValueError(f"{at} kind is {', '.join(OPPORTUNITY_KINDS)}, not {_said(kind)}{home}")
    stages = stages_of(kind)
    stage = a.get("stage")
    if stage not in stages:
        raise ValueError(f"{at} stage is a stage of a {kind} ({', '.join(stages)}), not {_said(stage)}")
    status = a.get("status")
    if "status" in a and status not in OPPORTUNITY_STATUSES:
        raise ValueError(f"{at} status is {', '.join(OPPORTUNITY_STATUSES)}, not {_said(status)}")
    if closes_kind(kind, stage) and "status" in a and status != "closed":
        raise ValueError(f"{at} is {stage}, which closes it: its status is closed, not {status}")
    if status == "closed" and not closes_kind(kind, stage):
        raise ValueError(f"{at} is closed, so its stage is one that closes a {kind} ({', '.join(OPPORTUNITY_STAGES[kind]['closed'])}), not {stage}")
    if "source" in a and not _text(a["source"], 2000):
        raise ValueError(f"{at} source is where it was found (a URL or a ref), not {_said(a['source'])}")
    if "deadline" in a and not _day(a["deadline"]):
        raise ValueError(f"{at} deadline is an ISO 8601 day or instant, not {_said(a['deadline'])}")
    out: Dict[str, Any] = {"title": a["title"], "kind": kind, "stage": stage}
    if "value" in a:
        v = a["value"]
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0:
            v = str(int(v)) if float(v).is_integer() else repr(float(v))
        if not isinstance(v, str) or not _DECIMAL.match(v):
            raise ValueError(f"{at} value is a decimal amount (text or a number, not negative), not {_said(a['value'])}")
        if not (isinstance(a.get("currency"), str) and _CURRENCY.match(a["currency"])):
            raise ValueError(f"{at} value needs its currency (three capitals, ISO 4217), not {_said(a.get('currency'))}")
        out["value"] = v
    elif "currency" in a:
        raise ValueError(f"{at} names a currency and no value")
    if "eligibility" in a and a["eligibility"] not in ELIGIBILITIES:
        raise ValueError(f"{at} eligibility is {', '.join(ELIGIBILITIES)}, not {_said(a['eligibility'])}")
    for k in ("folder", "counterparty"):
        if k in a and not _text(a[k], 1000):
            raise ValueError(f"{at} {k} is a ref, not {_said(a[k])}")
    if "owner" in a and not _principal(a["owner"]):
        raise ValueError(f"{at} owner is a principal (person:, agent:, org: or role:<id>), not {_said(a['owner'])}")
    if "channel" in a and not _id(a["channel"]):
        raise ValueError(f"{at} channel is a channel's id, not {_said(a['channel'])}")
    if "handle" in a and not _text(a["handle"], 300):
        raise ValueError(f"{at} handle is its name on its channel (a GitHub org or owner/repo, an agent's address, a domain), not {_said(a['handle'])}")
    if "handle" in a and "channel" not in a:
        raise ValueError(f"{at} names a handle and no channel")
    if "about" in a and not _text(a["about"], 8000):
        raise ValueError(f"{at} about is a text (at most 8000)")
    _keep(out, a, OPPORTUNITY_FIELDS)
    out["contacts"] = _many(t, "contact", "ref", _contact)
    out["actions"] = _many(t, "action", "id", _action)
    out["evidence"] = _many(t, "evidence", "id", _evidence)
    out["moves"] = _many(t, "move", "at", lambda m: _move(m, kind))
    out["drafts"] = _many(t, "draft", "id", _draft)
    if out["moves"]:
        last = sorted(out["moves"], key=lambda m: _stamp(m["at"]))[-1]
        if last["to"] != stage:
            raise ValueError(f"{at} is {stage}, but its last <move> ({last['at']}) went to {last['to']}")
    if kind == "listing" and stage in PUBLIC_STAGES and not any("approvedBy" in d for d in out["drafts"]):
        raise ValueError(f"{at} is {stage}: a listing is public only after a principal approved its <draft> (approvedBy, approvedAt)")
    return out


def _arm(c: Dict[str, Any]) -> Dict[str, Any]:
    if not _id(c.get("id")):
        raise ValueError(f"<arm> id is lower-case letters, digits and dashes (at most 64), not {_said(c.get('id'))}")
    for k in ("file", "note"):
        if k in c and not _text(c[k], 2000):
            raise ValueError(f'<arm id="{c["id"]}"> {k} is a text, not {_said(c[k])}')
    return _keep({"id": c["id"]}, c, ARM_FIELDS)


def _objective(c: Dict[str, Any]) -> Dict[str, Any]:
    if not _id(c.get("id")):
        raise ValueError(f"<objective> id is lower-case letters, digits and dashes (at most 64), not {_said(c.get('id'))}")
    o = f'<objective id="{c["id"]}">'
    if c.get("kind") not in OBJECTIVE_KINDS:
        raise ValueError(f"{o} kind is {', '.join(OBJECTIVE_KINDS)}, not {_said(c.get('kind'))}")
    if not _text(c.get("metric"), 120):
        raise ValueError(f"{o} metric names what is measured, not {_said(c.get('metric'))}")
    if c.get("direction") not in ("up", "down"):
        raise ValueError(f"{o} direction is up or down, not {_said(c.get('direction'))}")
    if "note" in c and not _text(c["note"], 2000):
        raise ValueError(f"{o} note is a text, not {_said(c['note'])}")
    return _keep({"id": c["id"], "kind": c["kind"], "metric": c["metric"], "direction": c["direction"]}, c, OBJECTIVE_FIELDS)


def experiment_of(t: DocTree) -> Dict[str, Any]:
    """An experiment as its tree declares it (the TypeScript SDK's ``experimentOf``)."""
    a = t["attrs"]
    if not _text(a.get("title"), 160):
        raise ValueError(f"<experiment> title is a short text (at most 160), not {_said(a.get('title'))}")
    at = f'<experiment title="{a["title"]}">'
    if "hypothesis" in a and not _text(a["hypothesis"], 2000):
        raise ValueError(f"{at} hypothesis is a text (at most 2000), not {_said(a['hypothesis'])}")
    if "status" in a and a["status"] not in EXPERIMENT_STATUSES:
        raise ValueError(f"{at} status is {', '.join(EXPERIMENT_STATUSES)}, not {_said(a['status'])}")
    if "opportunity" in a and not _text(a["opportunity"], 1000):
        raise ValueError(f"{at} opportunity is a ref to its .opportunity.tsx, not {_said(a['opportunity'])}")
    if "channel" in a and not _id(a["channel"]):
        raise ValueError(f"{at} channel is a channel's id, not {_said(a['channel'])}")
    for k in ("started", "ended"):
        if k in a and not _day(a[k]):
            raise ValueError(f"{at} {k} is an ISO 8601 day or instant, not {_said(a[k])}")
    out = _keep({"title": a["title"]}, a, EXPERIMENT_FIELDS)
    out["arms"] = _many(t, "arm", "id", _arm)
    out["objectives"] = _many(t, "objective", "id", _objective)
    # Reach alone rewards whatever spreads: an experiment that measures only distribution has no objective.
    if out["objectives"] and all(o["kind"] == "distribution" for o in out["objectives"]):
        raise ValueError(f"{at} measures only distribution: name a quality or an impact objective too")
    decisions = [c for c in t["children"] if c["tag"] == "decision"]
    if len(decisions) > 1:
        raise ValueError(f"{at} has one <decision>, not {len(decisions)}")
    if decisions:
        d = decisions[0]["attrs"]
        if not any(x["id"] == d.get("arm") for x in out["arms"]):
            raise ValueError(f"{at} <decision> arm is one of its arms ({', '.join(x['id'] for x in out['arms'])}), not {_said(d.get('arm'))}")
        if not _instant(d.get("at")):
            raise ValueError(f"{at} <decision> at is an ISO 8601 instant, not {_said(d.get('at'))}")
        if not _principal(d.get("by")):
            raise ValueError(f"{at} <decision> by is the principal that decided, not {_said(d.get('by'))}")
        if not _text(d.get("reason"), 2000):
            raise ValueError(f"{at} <decision> reason says why, from the observations, not {_said(d.get('reason'))}")
        out["decision"] = {"arm": d["arm"], "at": d["at"], "by": d["by"], "reason": d["reason"]}
    if out.get("status") == "decided" and "decision" not in out:
        raise ValueError(f"{at} is decided: its <decision> says which arm, who, when and why")
    if "decision" in out and out.get("status") != "decided":
        raise ValueError(f"{at} has a <decision>, so its status is decided, not {_said(out.get('status'))}")
    return out


def _leaves(tag: str, rows: Any, fields: List[str]) -> List[DocTree]:
    return [{"tag": tag, "attrs": {k: r[k] for k in fields if r.get(k) is not None}, "children": []} for r in rows or []]


def _opportunity_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "opportunity", "attrs": {k: d[k] for k in OPPORTUNITY_FIELDS if d.get(k) is not None}, "children": [
        *_leaves("contact", d.get("contacts"), CONTACT_FIELDS), *_leaves("action", d.get("actions"), ACTION_FIELDS),
        *_leaves("evidence", d.get("evidence"), EVIDENCE_FIELDS), *_leaves("move", d.get("moves"), MOVE_FIELDS),
        *_leaves("draft", d.get("drafts"), DRAFT_FIELDS)]}


def _experiment_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "experiment", "attrs": {k: d[k] for k in EXPERIMENT_FIELDS if d.get(k) is not None}, "children": [
        *_leaves("arm", d.get("arms"), ARM_FIELDS), *_leaves("objective", d.get("objectives"), OBJECTIVE_FIELDS),
        *_leaves("decision", [d["decision"]] if d.get("decision") else [], DECISION_FIELDS)]}


OPPORTUNITY_VOCABULARY = Vocabulary("opportunity", "an opportunity", "opportunity", {
    "opportunity": {"parents": [], "required": ["title", "kind", "stage"], "attrs": OPPORTUNITY_FIELDS},
    "contact": {"parents": ["opportunity"], "key": "ref", "required": ["ref"], "attrs": CONTACT_FIELDS},
    "action": {"parents": ["opportunity"], "key": "id", "required": ["id", "title"], "attrs": ACTION_FIELDS},
    "evidence": {"parents": ["opportunity"], "key": "id", "required": ["id", "fact"], "attrs": EVIDENCE_FIELDS},
    "move": {"parents": ["opportunity"], "key": "at", "required": ["to", "at", "by"], "attrs": MOVE_FIELDS},
    "draft": {"parents": ["opportunity"], "key": "id", "required": ["id", "body"], "attrs": DRAFT_FIELDS},
}, opportunity_of, _opportunity_tree, lambda stem: {"title": stem or "Opportunity", "kind": "collaborator", "stage": "found",
                                                   "contacts": [], "actions": [], "evidence": [], "moves": [], "drafts": []})

EXPERIMENT_VOCABULARY = Vocabulary("experiment", "an experiment", "experiment", {
    "experiment": {"parents": [], "required": ["title"], "attrs": EXPERIMENT_FIELDS},
    "arm": {"parents": ["experiment"], "key": "id", "required": ["id"], "attrs": ARM_FIELDS},
    "objective": {"parents": ["experiment"], "key": "id", "required": ["id", "kind", "metric", "direction"], "attrs": OBJECTIVE_FIELDS},
    "decision": {"parents": ["experiment"], "single": True, "required": ["arm", "at", "by", "reason"], "attrs": DECISION_FIELDS},
}, experiment_of, _experiment_tree, lambda stem: {"title": stem or "Experiment", "status": "draft", "arms": [], "objectives": []})

register_vocabulary(OPPORTUNITY_VOCABULARY, "opportunities")
register_vocabulary(EXPERIMENT_VOCABULARY, "opportunities")
