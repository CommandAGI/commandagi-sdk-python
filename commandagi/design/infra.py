"""An account's own machines declared in Python: the same documents and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``infra.ts``), each element a call. One folder is one thing: ``infra/vpn/<name>/exit.py`` one VPN
exit, ``infra/sessions/<name>/session.py`` one logged-in state, ``infra/vantages/<name>/vantage.py`` one observer::

    from commandagi.design.infra import exit

    result = exit(name="fsn-1", provider="hetzner", region="fsn1", country="DE", continent="EU", size="cax11",
                  image="debian-12", max_monthly_usd=6.99)

::

    from commandagi.design.infra import session, uses

    result = session(uses(monitor="../../../social/x/nvidia"),
                     name="x-web", site="https://x.com", kind="browser-profile", profile="x-web", refreshed="2026-10-12")

::

    from commandagi.design.infra import vantage

    result = vantage(name="fsn-1", path="worker", exit="fsn-1", location={"city": "Falkenstein", "country": "DE"},
                     locale="de-DE", timezone="Europe/Berlin")

Nothing adds a default: what the file does not say, the document does not have. ``exit_with_defaults``,
``session_with_defaults`` and ``vantage_with_defaults`` fill it as its reader does. A session's file holds no
credential. A vantage is a device, a place and a session, never a fake person, so the vocabulary has no words for one:
a field it does not list is refused by name.

The CommandAGI platform runs only a TSX file: its monitors read ``vantage.tsx`` and ``session.tsx``, and ``make
infra-plan`` reads ``exit.tsx``. A ``.py`` file runs in the local sandbox.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from .documents import DocTree, Vocabulary, _json, _text, register_vocabulary
from .element import define

EXIT_FIELDS = ["name", "provider", "region", "country", "continent", "size", "image", "protocol", "enabled", "price", "maxMonthlyUsd"]
#: The providers the reconciler can drive.
INFRA_PROVIDERS = ["hetzner", "vultr"]
EXIT_PROTOCOLS = ["wireguard"]
CONTINENTS = ["AF", "AN", "AS", "EU", "NA", "OC", "SA"]

VANTAGE_FIELDS = ["name", "path", "host", "unit", "snapshot", "exit", "location", "locale", "timezone", "session", "device", "clock", "enabled"]
#: Where a vantage observes from: a browser, a VM, an Android VM, a phone, the api worker, or a host.
VANTAGE_PATHS = ["browser", "vm", "android-vm", "phone", "worker", "host"]
LOCATION_FIELDS = ["city", "region", "country", "zip", "lat", "lon", "precision"]
#: How exactly a vantage's location is known: from a point to a whole country.
LOCATION_PRECISIONS = ["point", "zip", "city", "region", "country"]
DEVICE_FIELDS = ["kind", "os", "browser", "model", "carrier"]

SESSION_FIELDS = ["name", "site", "kind", "host", "profile", "snapshot", "refreshed", "note"]
SESSION_KINDS = ["browser-profile", "vm-snapshot", "android-snapshot"]
#: The source path (``via``) that reads through each kind of state.
SESSION_VIA = {"browser-profile": "browser", "vm-snapshot": "vm", "android-snapshot": "android-vm"}

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "exit": {},
    "vantage": {},
    "session": {"holds": "children"},
    "uses": {},
}

__all__ = [
    "EXIT_FIELDS", "INFRA_PROVIDERS", "EXIT_PROTOCOLS", "CONTINENTS", "VANTAGE_FIELDS", "VANTAGE_PATHS", "LOCATION_FIELDS",
    "LOCATION_PRECISIONS", "DEVICE_FIELDS", "SESSION_FIELDS", "SESSION_KINDS", "SESSION_VIA", "SIGNATURES", "INFRA",
    "EXIT_VOCABULARY", "SESSION_VOCABULARY", "VANTAGE_VOCABULARY", "exit_with_defaults", "session_with_defaults",
    "vantage_with_defaults", *define(globals(), "infra", SIGNATURES),
]

# Each pattern is the TypeScript SDK's, read with fullmatch: Python's `$` also matches before a last line break, and its
# `\s` is not JavaScript's, so whitespace is the list JavaScript's `\s` names.
_SPACE = "\\t\\n\\v\\f\\r \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff"
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
_COUNTRY = re.compile(r"[A-Z]{2}")
_EXIT_REF = re.compile(r"[A-Z]{2}|[a-z0-9][a-z0-9-]{2,47}")
_LOCALE = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})*")
_TIMEZONE = re.compile(r"[A-Za-z]+(/[A-Za-z0-9_+-]+)*")
_DAY = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")
_SITE = re.compile(f"https://[^{_SPACE}/]+(/[^{_SPACE}]*)?")


def _where(t: DocTree) -> str:
    name = t["attrs"].get("name")
    return f'<{t["tag"]} name="{name}">' if isinstance(name, str) else f'<{t["tag"]}>'


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_word(v: Any) -> bool:
    return isinstance(v, str) and bool(v)


def _word(t: DocTree, k: str) -> None:
    # A field written None (null) is written, as a JSX attribute written {null} is: only an absent one is not.
    if k in t["attrs"] and not _is_word(t["attrs"][k]):
        raise ValueError(f"{_where(t)} {k} is a word, not {_json(t['attrs'][k])}")


def _one_of(t: DocTree, k: str, values: Sequence[str]) -> None:
    if k in t["attrs"] and not (isinstance(t["attrs"][k], str) and t["attrs"][k] in values):
        raise ValueError(f"{_where(t)} {k} is {', '.join(_json(x) for x in values)}, not {_json(t['attrs'][k])}")


def _enabled(t: DocTree) -> None:
    if "enabled" in t["attrs"] and not isinstance(t["attrs"]["enabled"], bool):
        raise ValueError(f"{_where(t)} enabled is true or false, not {_json(t['attrs']['enabled'])}")


def _no_children(t: DocTree) -> None:
    if t["children"]:
        raise ValueError(f"{_where(t)} has no children")


def _country(v: Any) -> bool:
    # The TypeScript SDK reads String(v), so a list of one word reads as the word.
    return _COUNTRY.fullmatch(_text(v)) is not None


def _said(attrs: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    return {k: attrs[k] for k in fields if k in attrs}


def _written(d: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    return {k: d[k] for k in fields if d.get(k) is not None and d.get(k) != ""}


def _exit(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("name", "region", "size", "image", "price"):
        _word(t, k)
    if not _NAME.fullmatch(a["name"]):
        raise ValueError(f"{_where(t)} name is lower-case letters, digits and -, at most 48")
    _one_of(t, "provider", INFRA_PROVIDERS)
    _one_of(t, "protocol", EXIT_PROTOCOLS)
    _one_of(t, "continent", CONTINENTS)
    if not _country(a["country"]):
        raise ValueError(f'{_where(t)} country is an ISO 3166 code in capitals ("DE"), not {_json(a["country"])}')
    _enabled(t)
    if "maxMonthlyUsd" in a and not (_is_number(a["maxMonthlyUsd"]) and a["maxMonthlyUsd"] > 0):
        raise ValueError(f"{_where(t)} maxMonthlyUsd is a price in USD (6.99), not {_json(a['maxMonthlyUsd'])}")
    _no_children(t)
    return _said(a, EXIT_FIELDS)


def _exit_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "exit", "attrs": _written(d, EXIT_FIELDS), "children": []}


def _only_keys(t: DocTree, k: str, allowed: Sequence[str]) -> Optional[Dict[str, Any]]:
    if k not in t["attrs"]:
        return None
    v = t["attrs"][k]
    if not isinstance(v, dict):
        raise ValueError(f"{_where(t)} {k} is an object, not {_json(v)}")
    for key in v:
        if key not in allowed:
            raise ValueError(f"{_where(t)} {k}.{key} is not read ({k} has {', '.join(allowed)}; a vantage has no fields for a person)")
    return v


def _vantage(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in ("name", "host", "unit", "snapshot", "exit", "locale", "timezone", "session"):
        _word(t, k)
    if not _NAME.fullmatch(a["name"]):
        raise ValueError(f"{_where(t)} name is the folder's word: lower-case letters, digits and -, at most 48")
    _one_of(t, "path", VANTAGE_PATHS)
    path = a["path"]
    if path not in ("worker", "host") and "host" not in a:
        raise ValueError(f'{_where(t)} a {path} is driven by a host: name it (host="laptop-linux")')
    if path == "worker" and "host" in a:
        raise ValueError(f"{_where(t)} the worker's path has no host")
    if "unit" in a and path != "phone":
        raise ValueError(f'{_where(t)} unit names a phone\'s unit in a world, for path="phone" only')
    if "snapshot" in a and path not in ("vm", "android-vm"):
        raise ValueError(f"{_where(t)} snapshot is for a VM")
    if "exit" in a and not _EXIT_REF.fullmatch(a["exit"]):
        raise ValueError(f"{_where(t)} exit is an exit's name (fsn-1) or a country (DE), not {_json(a['exit'])}")
    if "locale" in a and not _LOCALE.fullmatch(a["locale"]):
        raise ValueError(f"{_where(t)} locale is a BCP 47 tag (en-US), not {_json(a['locale'])}")
    if "timezone" in a and not _TIMEZONE.fullmatch(a["timezone"]):
        raise ValueError(f"{_where(t)} timezone is an IANA zone (America/Chicago), not {_json(a['timezone'])}")
    loc = _only_keys(t, "location", LOCATION_FIELDS)
    if loc is not None:
        if "country" in loc and not _country(loc["country"]):
            raise ValueError(f"{_where(t)} location.country is an ISO 3166 code in capitals (US)")
        for k, lo, hi in (("lat", -90, 90), ("lon", -180, 180)):
            if k in loc and not (_is_number(loc[k]) and lo <= loc[k] <= hi):
                raise ValueError(f"{_where(t)} location.{k} is a number from {lo} to {hi}")
        if "precision" in loc and not (isinstance(loc["precision"], str) and loc["precision"] in LOCATION_PRECISIONS):
            raise ValueError(f"{_where(t)} location.precision is {', '.join(LOCATION_PRECISIONS)}")
        for k in ("city", "region", "zip"):
            if k in loc and not _is_word(loc[k]):
                raise ValueError(f"{_where(t)} location.{k} is a word")
    device = _only_keys(t, "device", DEVICE_FIELDS)
    for k, v in (device or {}).items():
        if not _is_word(v):
            raise ValueError(f"{_where(t)} device.{k} is a word")
    clock = a.get("clock")
    if "clock" in a and not (isinstance(clock, dict) and list(clock) == ["sd"] and _is_number(clock["sd"]) and clock["sd"] >= 0):
        raise ValueError(f"{_where(t)} clock is {{ sd }} in ms (the observer's clock: NTP is tens of ms)")
    _enabled(t)
    _no_children(t)
    return _said(a, VANTAGE_FIELDS)


def _vantage_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "vantage", "attrs": _written(d, VANTAGE_FIELDS), "children": []}


def _session(t: DocTree) -> Dict[str, Any]:
    a = t["attrs"]
    for k in SESSION_FIELDS:
        _word(t, k)
    if not _NAME.fullmatch(a["name"]):
        raise ValueError(f"{_where(t)} name is lower-case letters, digits and -, at most 48")
    if not _SITE.fullmatch(a["site"]):
        raise ValueError(f'{_where(t)} site is an https address ("https://x.com"), not {_json(a["site"])}')
    _one_of(t, "kind", SESSION_KINDS)
    browser = a["kind"] == "browser-profile"
    if browser and "profile" not in a:
        raise ValueError(f"{_where(t)} a browser-profile names its profile")
    if not browser and "snapshot" not in a:
        raise ValueError(f"{_where(t)} a {a['kind']} names its snapshot")
    if browser and "snapshot" in a:
        raise ValueError(f"{_where(t)} a browser-profile has a profile, not a snapshot")
    if not browser and "profile" in a:
        raise ValueError(f"{_where(t)} a {a['kind']} has a snapshot, not a profile")
    if "profile" in a and not _NAME.fullmatch(a["profile"]):
        raise ValueError(f"{_where(t)} profile is lower-case letters, digits and -, at most 48")
    if "refreshed" in a and not _DAY.fullmatch(a["refreshed"]):
        raise ValueError(f'{_where(t)} refreshed is a day ("2026-10-12"), not {_json(a["refreshed"])}')
    uses_: List[Dict[str, Any]] = [{"monitor": c["attrs"]["monitor"]} for c in t["children"]]
    return {**_said(a, SESSION_FIELDS), "uses": uses_}


def _session_tree(d: Dict[str, Any]) -> DocTree:
    return {"tag": "session", "attrs": _written(d, SESSION_FIELDS), "children": [
        {"tag": "uses", "attrs": {"monitor": u["monitor"]}, "children": []} for u in d.get("uses") or []]}


EXIT_VOCABULARY = Vocabulary("exit", "a VPN exit", "exit", {
    "exit": {"parents": [], "required": ["name", "provider", "region", "country", "size", "image"], "attrs": EXIT_FIELDS},
}, _exit, _exit_tree)
VANTAGE_VOCABULARY = Vocabulary("vantage", "a vantage", "vantage", {
    "vantage": {"parents": [], "required": ["name", "path"], "attrs": VANTAGE_FIELDS},
}, _vantage, _vantage_tree)
SESSION_VOCABULARY = Vocabulary("session", "a logged-in state", "session", {
    "session": {"parents": [], "required": ["name", "site", "kind"], "attrs": SESSION_FIELDS},
    "uses": {"parents": ["session"], "key": "monitor", "required": ["monitor"], "attrs": ["monitor"]},
}, _session, _session_tree)

register_vocabulary(EXIT_VOCABULARY, "infra")
register_vocabulary(VANTAGE_VOCABULARY, "infra")
register_vocabulary(SESSION_VOCABULARY, "infra")

#: The vocabulary of infrastructure files, by format.
INFRA = {"exit": EXIT_VOCABULARY, "session": SESSION_VOCABULARY, "vantage": VANTAGE_VOCABULARY}


def exit_with_defaults(d: Dict[str, Any]) -> Dict[str, Any]:
    """An exit as the reconciler reads it: what the file does not say, filled."""
    return {
        "name": d["name"], "provider": d["provider"], "region": d["region"], "country": d["country"],
        "continent": d.get("continent"), "size": d["size"], "image": d["image"],
        "protocol": d.get("protocol", "wireguard"), "enabled": d.get("enabled", True), "price": d.get("price"),
        "maxMonthlyUsd": d.get("maxMonthlyUsd"),
    }


def vantage_with_defaults(d: Dict[str, Any]) -> Dict[str, Any]:
    """A vantage as the platform reads it: what the file does not say, filled (``enabled`` True, the rest None)."""
    return {
        **{k: d.get(k) for k in VANTAGE_FIELDS if k != "enabled"},
        "enabled": d.get("enabled", True),
    }


def session_with_defaults(d: Dict[str, Any]) -> Dict[str, Any]:
    """A session as a source reads it: what the file does not say, filled."""
    return {**{k: d.get(k) for k in SESSION_FIELDS}, "uses": [u["monitor"] for u in d.get("uses") or []]}
