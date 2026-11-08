"""An opportunity and an experiment declared in Python give what the TypeScript vocabulary's JSX gives
(opportunities.ts in the CommandAGI repository): a listing with an approved draft, an experiment with its decision, and
each refusal with why. Run: python -m unittest discover -s tests"""
import re
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.opportunities import (action, arm, contact, decision, draft, evidence, experiment, move, objective,
                                             opportunity, stages_of)

LISTING = {
    "title": "CommandAGI's agent on Agentverse", "kind": "listing", "stage": "submitted", "status": "waiting",
    "source": "https://agentverse.ai", "deadline": "2026-12-01", "value": "0", "currency": "USD", "eligibility": "eligible",
    "owner": "agent:market-manager", "channel": "agentverse",
    "contacts": [{"ref": "../relationships/cards/fetch-ai.vcf", "role": "marketplace"}],
    "actions": [{"id": "check-listing", "title": "Read the listing back", "due": "2026-11-10", "owner": "agent:market-manager"}],
    "evidence": [{"id": "api", "fact": "Agentverse registers agents through its API", "source": "https://docs.agentverse.ai",
                  "way": "read the page", "by": "agent:claude-code", "at": "2026-11-08T10:00:00Z"}],
    "moves": [
        {"from": "draft", "to": "approved", "at": "2026-11-08T11:00:00Z", "by": "person:jacob-valdez"},
        {"from": "approved", "to": "submitted", "at": "2026-11-08T12:00:00Z", "by": "agent:market-manager"},
    ],
    "drafts": [{"id": "listing", "channel": "agentverse", "subject": "CommandAGI", "body": "Plans, simulates and runs robots.",
                "approvedBy": "person:jacob-valdez", "approvedAt": "2026-11-08T11:00:00Z"}],
}
EXPERIMENT = {
    "title": "Which first line keeps a reader", "hypothesis": "A concrete number beats a question", "status": "decided",
    "channel": "linkedin",
    "arms": [{"id": "number", "file": "hooks/number.txt"}, {"id": "question", "file": "hooks/question.txt"}],
    "objectives": [{"id": "read", "kind": "quality", "metric": "read-through", "direction": "up"},
                   {"id": "reach", "kind": "distribution", "metric": "impressions", "direction": "up"}],
    "decision": {"arm": "number", "at": "2026-11-20T09:00:00Z", "by": "agent:optimizer", "reason": "read-through 41% against 22%, reach equal"},
}


def kw(v):
    """A record's attributes as its call's keywords."""
    out = {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): x for k, x in v.items()}
    if "from" in out:
        out["from_"] = out.pop("from")
    return out


def listing():
    top = {k: v for k, v in LISTING.items() if not isinstance(v, list)}
    return opportunity(*[contact(**kw(r)) for r in LISTING["contacts"]], *[action(**kw(r)) for r in LISTING["actions"]],
                       *[evidence(**kw(r)) for r in LISTING["evidence"]], *[move(**kw(r)) for r in LISTING["moves"]],
                       *[draft(**kw(r)) for r in LISTING["drafts"]], **top)


class OpportunityTests(unittest.TestCase):
    def test_the_examples_are_their_documents(self):
        self.assertEqual(declare_document(listing()), {"format": "opportunity", "sources": {}, "document": LISTING})
        top = {k: v for k, v in EXPERIMENT.items() if k not in ("arms", "objectives", "decision")}
        d = declare_document(experiment(*[arm(**r) for r in EXPERIMENT["arms"]], *[objective(**r) for r in EXPERIMENT["objectives"]],
                                        decision(**EXPERIMENT["decision"]), **top))
        self.assertEqual(d["format"], "experiment")
        self.assertEqual(d["document"], EXPERIMENT)
        self.assertEqual(stages_of("listing"), ["draft", "approved", "submitted", "live", "withdrawn", "refused"])

    def test_a_bad_opportunity_or_experiment_is_refused(self):
        base = {"title": "x", "kind": "collaborator", "stage": "found"}
        at = "2026-11-08T10:00:00Z"
        bad = {
            r"an application is its folder of applications/": ({**base, "kind": "application"}, []),
            r"a client is a <Deal> of its company": ({**base, "kind": "client"}, []),
            r"stage is a stage of a collaborator \(found, contacted, talking, working, ended, dropped\)": ({**base, "stage": "won"}, []),
            r"is ended, which closes it: its status is closed": ({**base, "stage": "ended", "status": "open"}, []),
            r"is closed, so its stage is one that closes a collaborator": ({**base, "status": "closed"}, []),
            r"value needs its currency": ({**base, "value": "100"}, []),
            r"value is a decimal amount": ({**base, "value": "-1", "currency": "USD"}, []),
            r"names a currency and no value": ({**base, "currency": "USD"}, []),
            r"owner is a principal": ({**base, "owner": "jacob"}, []),
            r"deadline is an ISO 8601 day": ({**base, "deadline": "next week"}, []),
            r"eligibility is eligible, eligible-with-partner, not-eligible, unknown": ({**base, "eligibility": "maybe"}, []),
            r"is found, but its last <move> \(2026-11-08T10:00:00Z\) went to talking": (base, [move(from_="found", to="talking", at=at, by="person:ada")]),
            r"by is the principal who moved it": (base, [move(to="found", at=at, by="ada")]),
            r"names where the fact was read: a ref \(a file\) or a source": (base, [evidence(id="e", fact="f")]),
            r"approvedBy and approvedAt come together": (base, [draft(id="d", body="b", approved_by="person:ada")]),
            r"decision is true when only its owner can decide it": (base, [action(id="a", title="t", decision="yes")]),
            r"is live: a listing is public only after a principal approved its <draft>": ({"title": "x", "kind": "listing", "stage": "live"}, [draft(id="d", body="b")]),
            r"names a handle and no channel": ({**base, "handle": "CommandAGI"}, []),
            r"colour": ({**base, "colour": "red"}, []),
        }
        for why, (attrs, kids) in bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(opportunity(*kids, **attrs))
        reach = objective(id="r", kind="distribution", metric="impressions", direction="up")
        d = dict(at=at, by="agent:o", reason="r")
        exp_bad = {
            r"measures only distribution: name a quality or an impact objective too": ({"title": "x"}, [reach]),
            r"kind is quality, distribution, impact": ({"title": "x"}, [objective(id="q", kind="virality", metric="m", direction="up")]),
            r"is decided: its <decision> says which arm": ({"title": "x", "status": "decided"}, [arm(id="a")]),
            r"<decision> arm is one of its arms \(a\)": ({"title": "x", "status": "decided"}, [arm(id="a"), decision(arm="b", **d)]),
            r"has a <decision>, so its status is decided": ({"title": "x", "status": "running"}, [arm(id="a"), decision(arm="a", **d)]),
        }
        for why, (attrs, kids) in exp_bad.items():
            with self.assertRaisesRegex(ValueError, why, msg=why):
                declare_document(experiment(*kids, **attrs))

    def test_a_run_names_each_child_by_its_key(self):
        out = run_module(
            "from commandagi.design.opportunities import opportunity, contact\n"
            "result = opportunity(contact(ref=\"people/ada.vcf\"), title=\"x\", kind=\"collaborator\", stage=\"found\")\n",
            "market/Ada.opportunity.py")
        self.assertEqual(out["document"]["format"], "opportunity")
        self.assertEqual(sorted(out["document"]["sources"]), ["", "contact#people/ada.vcf"])


if __name__ == "__main__":
    unittest.main()
