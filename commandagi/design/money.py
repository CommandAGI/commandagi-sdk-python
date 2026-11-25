"""A money account, declared in Python: the same document and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``money.ts``; CommandAGI's docs/financial-accounts.md). ``<name>.money.py`` declares one account a
person or a company holds at a financial institution::

    from commandagi.design.money import At, Connection, Counterparty, MoneyAccount, Recurring

    result = MoneyAccount(
        Connection(id="direct", provider="mercury", account="acc_test_operating"),
        Counterparty(At(connection="direct", recipient="rcp_test_landlord"), id="landlord", name="Harbor Properties LLC"),
        Recurring(id="rent", to="landlord", amount="4200.00", rail="ach", every="month", day=1, by="person:jacob",
                  starts="2027-01-01", memo="Rent"),
        name="Operating", kind="checking", institution="Mercury", last4="0000", currency="USD",
        ledger="Assets:Cash:Operating", books="../books/main.journal",
    )

The file holds no bank or card number and no credential: ``last4`` is the most it says of a number, ``account`` and
``recipient`` are the provider's own ids, and the sign-in is a connection of the holder.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from .documents import DocTree, Vocabulary, _json, register_vocabulary
from .element import define

MONEY_KINDS = ["checking", "savings", "money-market", "card", "loan", "credit-line", "brokerage", "payments", "wallet", "other"]
MONEY_RAILS = ["ach", "wire", "book", "rtp", "check"]
MONEY_EVERY = ["week", "month", "quarter", "year"]
MONEY_ACCOUNT_FIELDS = ["name", "kind", "institution", "last4", "currency", "ledger", "books", "statements", "opened", "closed", "holder"]
MONEY_CONNECTION_FIELDS = ["id", "provider", "account", "mode"]
MONEY_COUNTERPARTY_FIELDS = ["id", "name", "kind", "file"]
MONEY_AT_FIELDS = ["connection", "recipient"]
MONEY_RECURRING_FIELDS = ["id", "to", "amount", "rail", "every", "day", "by", "starts", "ends", "memo"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "MoneyAccount": {"holds": "children"},
    "Connection": {},
    "Counterparty": {"holds": "children"},
    "At": {},
    "Recurring": {},
}

__all__ = ["MONEY_KINDS", "MONEY_RAILS", "MONEY_EVERY", "MONEY_ACCOUNT_FIELDS", "MONEY_CONNECTION_FIELDS",
           "MONEY_COUNTERPARTY_FIELDS", "MONEY_AT_FIELDS", "MONEY_RECURRING_FIELDS", "SIGNATURES", "money_account_of",
           "MONEY_VOCABULARY", *define(globals(), "money", SIGNATURES)]

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# A provider is named by its id; the platform's catalog names the providers (docs/financial-accounts.md), so a new one needs no SDK release.
_PROVIDER = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DECIMAL = re.compile(r"^\d{1,15}(\.\d{1,4})?$")
_PRINCIPAL = re.compile(r"^(person|agent):[A-Za-z0-9._@-]{1,64}$")
_MONEY_FILE = re.compile(r"\.money\.(jsx|tsx|py|rs)$", re.I)


def _said(v: Any) -> str:
    return "undefined" if v is None else _json(v)


def _text(v: Any, mx: int) -> bool:
    return isinstance(v, str) and bool(v.strip()) and len(v) <= mx


def _is(v: Any, pattern: "re.Pattern[str]") -> bool:
    return isinstance(v, str) and bool(pattern.match(v))


def _keep(out: Dict[str, Any], a: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    for k in fields:
        if a.get(k) is not None and k not in out:
            out[k] = a[k]
    return out


def _texts(a: Dict[str, Any], at: str, fields: List[str], mx: int) -> None:
    for k in fields:
        if a.get(k) is not None and not _text(a[k], mx):
            raise ValueError(f"{at} {k} is a short text (at most {mx}), not {_said(a[k])}")


def _id_of(a: Dict[str, Any], tag: str) -> str:
    if not _is(a.get("id"), _ID):
        raise ValueError(f"<{tag}> id is letters, digits, . _ - (at most 64), not {_said(a.get('id'))}")
    return f'<{tag} id="{a["id"]}">'


def _connection_of(a: Dict[str, Any]) -> Dict[str, Any]:
    at = _id_of(a, "Connection")
    if not _is(a.get("provider"), _PROVIDER):
        raise ValueError(f"{at} provider is a provider's id (lowercase letters, digits and -, as plaid or increase), not {_said(a.get('provider'))}")
    if not _text(a.get("account"), 200):
        raise ValueError(f"{at} account is the provider's own id of the account (not a bank number), not {_said(a.get('account'))}")
    if a.get("mode") is not None and a["mode"] not in ("live", "sandbox"):
        raise ValueError(f"{at} mode is live or sandbox, not {_said(a['mode'])}")
    return _keep({}, a, MONEY_CONNECTION_FIELDS)


def _counterparty_of(c: DocTree, connections: Set[str]) -> Dict[str, Any]:
    a = c["attrs"]
    at = _id_of(a, "Counterparty")
    if not _text(a.get("name"), 200):
        raise ValueError(f"{at} name is a short text (at most 200), not {_said(a.get('name'))}")
    _texts(a, at, ["kind"], 80)
    if a.get("file") is not None and not (_text(a["file"], 1000) and _MONEY_FILE.search(a["file"])):
        raise ValueError(f"{at} file is a ref to another money account (.money.tsx), not {_said(a['file'])}")
    ways = []
    for x in c["children"]:
        if x["tag"] != "At":
            continue
        w = x["attrs"]
        if w.get("connection") not in connections:
            raise ValueError(f"{at} <At> connection is the id of a <Connection> of the account, not {_said(w.get('connection'))}")
        if not _text(w.get("recipient"), 200):
            raise ValueError(f'{at} <At connection="{w["connection"]}"> recipient is the provider\'s id of the payee, not {_said(w.get("recipient"))}')
        if any(x["connection"] == w["connection"] for x in ways):
            raise ValueError(f"{at} names the connection {w['connection']} in two <At>s")
        ways.append({"connection": w["connection"], "recipient": w["recipient"]})
    if a.get("file") is not None and ways:
        raise ValueError(f"{at} is another money account of the holder (file) or is reached through <At>, not both")
    if a.get("file") is None and not ways:
        raise ValueError(f"{at} needs an <At connection recipient>, or the file of another money account")
    out = _keep({}, a, MONEY_COUNTERPARTY_FIELDS)
    if ways:
        out["at"] = ways
    return out


def _recurring_of(a: Dict[str, Any], parties: Set[str]) -> Dict[str, Any]:
    at = _id_of(a, "Recurring")
    if a.get("to") not in parties:
        raise ValueError(f"{at} to is the id of a <Counterparty> of the account, not {_said(a.get('to'))}")
    if not _is(a.get("amount"), _DECIMAL):
        raise ValueError(f'{at} amount is a decimal text ("4200.00"), not {_said(a.get("amount"))}')
    if a.get("rail") not in MONEY_RAILS:
        raise ValueError(f"{at} rail is {', '.join(MONEY_RAILS)}, not {_said(a.get('rail'))}")
    if a.get("every") not in MONEY_EVERY:
        raise ValueError(f"{at} every is {', '.join(MONEY_EVERY)}, not {_said(a.get('every'))}")
    out = _keep({}, a, MONEY_RECURRING_FIELDS)
    if a.get("day") is not None:
        d = int(a["day"]) if isinstance(a["day"], str) and re.match(r"^\d{1,2}$", a["day"]) else a["day"]
        most = 7 if a["every"] == "week" else 31
        if not (isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= most):
            raise ValueError(f"{at} day is a whole number from 1 to {most}, not {_said(a['day'])}")
        out["day"] = d
    if not _is(a.get("by"), _PRINCIPAL):
        raise ValueError(f"{at} by is the principal whose grant makes each payment (person:<id> or agent:<id>), not {_said(a.get('by'))}")
    for k in ("starts", "ends"):
        if a.get(k) is not None and not _is(a[k], _DAY):
            raise ValueError(f"{at} {k} is a day (YYYY-MM-DD), not {_said(a[k])}")
    if a.get("starts") is None:
        raise ValueError(f"{at} needs starts")
    _texts(a, at, ["memo"], 140)
    return out


def money_account_of(t: DocTree) -> Dict[str, Any]:
    """A money account as its tree declares it (the TypeScript SDK's ``moneyAccountOf``)."""
    a = t["attrs"]
    if not _text(a.get("name"), 120):
        raise ValueError(f"<MoneyAccount> name is a short text (at most 120), not {_said(a.get('name'))}")
    at = f'<MoneyAccount name="{a["name"]}">'
    if a.get("kind") not in MONEY_KINDS:
        raise ValueError(f"{at} kind is {', '.join(MONEY_KINDS)}, not {_said(a.get('kind'))}")
    if a.get("last4") is not None and not _is(a["last4"], re.compile(r"^\d{4}$")):
        raise ValueError(f"{at} last4 is the last four digits and no more, not {_said(a['last4'])}")
    if a.get("currency") is not None and not _is(a["currency"], re.compile(r"^[A-Z]{3}$")):
        raise ValueError(f"{at} currency is three capitals (ISO 4217), not {_said(a['currency'])}")
    for k in ("opened", "closed"):
        if a.get(k) is not None and not _is(a[k], _DAY):
            raise ValueError(f"{at} {k} is a day (YYYY-MM-DD), not {_said(a[k])}")
    _texts(a, at, ["institution", "ledger", "books", "statements", "holder"], 500)
    out = _keep({"name": a["name"], "kind": a["kind"]}, a, MONEY_ACCOUNT_FIELDS)
    out["connections"] = [_connection_of(c["attrs"]) for c in t["children"] if c["tag"] == "Connection"]
    connections = {c["id"] for c in out["connections"]}
    out["counterparties"] = [_counterparty_of(c, connections) for c in t["children"] if c["tag"] == "Counterparty"]
    parties = {c["id"] for c in out["counterparties"]}
    out["recurring"] = [_recurring_of(c["attrs"], parties) for c in t["children"] if c["tag"] == "Recurring"]
    return out


def _attrs(fields: List[str], r: Dict[str, Any]) -> Dict[str, Any]:
    return {k: r[k] for k in fields if r.get(k) is not None}


def _leaf(tag: str, fields: List[str], r: Dict[str, Any]) -> DocTree:
    return {"tag": tag, "attrs": _attrs(fields, r), "children": []}


def _tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "MoneyAccount", "attrs": _attrs(MONEY_ACCOUNT_FIELDS, d), "children": [
        *(_leaf("Connection", MONEY_CONNECTION_FIELDS, c) for c in d.get("connections") or []),
        *({"tag": "Counterparty", "attrs": _attrs(MONEY_COUNTERPARTY_FIELDS, c),
           "children": [_leaf("At", MONEY_AT_FIELDS, w) for w in c.get("at") or []]} for c in d.get("counterparties") or []),
        *(_leaf("Recurring", MONEY_RECURRING_FIELDS, r) for r in d.get("recurring") or []),
    ]}


MONEY_VOCABULARY = Vocabulary("money", "a money account", "MoneyAccount", {
    "MoneyAccount": {"parents": [], "required": ["name", "kind"], "attrs": MONEY_ACCOUNT_FIELDS},
    "Connection": {"parents": ["MoneyAccount"], "key": "id", "required": ["id", "provider", "account"], "attrs": MONEY_CONNECTION_FIELDS},
    "Counterparty": {"parents": ["MoneyAccount"], "key": "id", "required": ["id", "name"], "attrs": MONEY_COUNTERPARTY_FIELDS},
    "At": {"parents": ["Counterparty"], "required": ["connection", "recipient"], "attrs": MONEY_AT_FIELDS},
    "Recurring": {"parents": ["MoneyAccount"], "key": "id", "required": ["id", "to", "amount", "rail", "every", "by", "starts"], "attrs": MONEY_RECURRING_FIELDS},
}, money_account_of, _tree, lambda stem: {"name": stem or "Account", "kind": "checking", "connections": [], "counterparties": [], "recurring": []})

register_vocabulary(MONEY_VOCABULARY, "money")
