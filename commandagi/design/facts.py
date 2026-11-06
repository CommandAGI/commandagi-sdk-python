"""A fact the file does not know, or knows only about (the TypeScript SDK's ``facts.ts``). Any attribute of a company, a
brand and their children may hold, instead of its value, one of two plain dicts::

    Entity(name="Exocortex Labs", jurisdiction=unknown("whether Exocortex Labs is a legal entity at all is open"))
    Domain(name="my-exocortex.com", transfer_lock=about("2026-12-30"))

``{"unknown": "<why>"}`` says the fact exists and its value is not known, and why. It is not an absent attribute:
absent says nothing. A required attribute may be unknown. ``{"about": <value>}`` is a value known only roughly, of the
attribute's own kind. A reader shows each as written and lists every unknown as an open fact; nothing puts a default or
a placeholder code in its place.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

__all__ = ["unknown", "about", "is_unknown", "is_about", "fact_marker"]


def unknown(why: str) -> Dict[str, str]:
    """An unknown fact, and why it is unknown (what is open, what would settle it)."""
    return {"unknown": why}


def about(value: Any) -> Dict[str, Any]:
    """A value known only roughly."""
    return {"about": value}


def is_unknown(v: Any) -> bool:
    return isinstance(v, dict) and list(v) == ["unknown"] and isinstance(v["unknown"], str) and v["unknown"].strip() != ""


def is_about(v: Any) -> bool:
    return isinstance(v, dict) and list(v) == ["about"] and v["about"] is not None


def fact_marker(v: Any, what: str, check: Callable[[Any], Any] = lambda x: x) -> Optional[Dict[str, Any]]:
    """``v`` as a fact marker, or None for a plain value; a malformed marker is refused by name."""
    if not isinstance(v, dict) or not ("unknown" in v or "about" in v):
        return None
    if is_unknown(v):
        return {"unknown": v["unknown"].strip()}
    if is_about(v):
        return {"about": check(v["about"])}
    raise ValueError(f'{what}: an unknown fact is {{"unknown": "<why>"}} and an approximate one {{"about": <value>}}, each alone, not {v!r}')
