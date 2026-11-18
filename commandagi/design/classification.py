"""CLASSIFICATION — what kind of business, product or service a thing is, said on purpose by its account
(CommandAGI's docs/formats.md § classification). A ``Company``, a ``Product``, a ``product`` and a storefront's
``Offer`` take two attributes::

    codes=["naics:541511", "unspsc:43232100"]   standard codes as scheme:code
    tags=["robotics", "3d printing"]            free words: lower case, trimmed, single spaces, at most 40 characters

Business schemes classify what a company does (naics, nace, isic, sic, anzsic, jsic); product schemes what is sold
(unspsc, gs1, hs). A shorter code of a scheme is the group of the longer codes it starts (``naics:54`` holds
``naics:541511``). The same grammar as the TypeScript SDK's ``classification.ts``, the Rust SDK's ``classification.rs``
and CommandAGI's ``packages/domain/world/classification.js``.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Sequence

SCHEMES: Dict[str, Dict[str, Any]] = {
    "naics": {"kind": "business", "name": "NAICS", "pattern": r"[0-9]{2,6}", "example": "naics:541511", "grammar": "2 to 6 digits"},
    "nace": {"kind": "business", "name": "NACE", "pattern": r"[A-U]|[0-9]{2}(?:\.[0-9]{1,2})?", "example": "nace:28.41",
             "grammar": "a section letter A-U, or a division, group or class (28, 28.4, 28.41)"},
    "isic": {"kind": "business", "name": "ISIC", "pattern": r"[A-U]|[0-9]{2,4}", "example": "isic:2822", "grammar": "a section letter A-U, or 2 to 4 digits"},
    "sic": {"kind": "business", "name": "SIC", "pattern": r"[0-9]{2,4}", "example": "sic:3569", "grammar": "2 to 4 digits"},
    "anzsic": {"kind": "business", "name": "ANZSIC", "pattern": r"[A-S]|[0-9]{2,4}", "example": "anzsic:2469", "grammar": "a division letter A-S, or 2 to 4 digits"},
    "jsic": {"kind": "business", "name": "JSIC", "pattern": r"[A-T]|[0-9]{2,4}", "example": "jsic:2694", "grammar": "a division letter A-T, or 2 to 4 digits"},
    "unspsc": {"kind": "product", "name": "UNSPSC", "pattern": r"(?:[0-9]{2}){1,4}", "example": "unspsc:43232100", "grammar": "2, 4, 6 or 8 digits"},
    "gs1": {"kind": "product", "name": "GS1 GPC", "pattern": r"[0-9]{8}", "example": "gs1:10001234", "grammar": "8 digits (a GPC brick or a level above it)"},
    "hs": {"kind": "product", "name": "HS", "pattern": r"(?:[0-9]{2}){1,5}", "example": "hs:847989", "grammar": "2, 4, 6, 8 or 10 digits"},
}

SCHEME_NAMES = list(SCHEMES)
BUSINESS_SCHEMES = [s for s in SCHEME_NAMES if SCHEMES[s]["kind"] == "business"]
PRODUCT_SCHEMES = [s for s in SCHEME_NAMES if SCHEMES[s]["kind"] == "product"]
MAX_CODES = 20
MAX_TAGS = 20
MAX_TAG_LENGTH = 40

__all__ = ["SCHEMES", "SCHEME_NAMES", "BUSINESS_SCHEMES", "PRODUCT_SCHEMES", "MAX_CODES", "MAX_TAGS", "MAX_TAG_LENGTH",
           "code_problem", "normalize_tag", "tag_problem", "classification_problem", "matches_prefix"]

_PATTERNS = {k: re.compile(s["pattern"], re.ASCII) for k, s in SCHEMES.items()}
_SPACES = re.compile(r"\s+")


def _said(v: Any) -> str:
    """A value as the TypeScript SDK says it: a text quoted, anything else as JavaScript's ``String(v)``."""
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, tuple)):
        return ",".join("" if x is None else (x if isinstance(x, str) else _said(x)) for x in v)
    if isinstance(v, dict):
        return "[object Object]"
    return str(v)


def code_problem(raw: Any) -> Optional[str]:
    """Why ``raw`` is not a code, or None when it is one."""
    if not isinstance(raw, str):
        return f'a code is a "scheme:code" text, not {_said(raw)}'
    i = raw.find(":")
    if i <= 0:
        return f"{_said(raw)} is not a code: write it as scheme:code ({SCHEMES['naics']['example']})"
    scheme = raw[:i]
    s = SCHEMES.get(scheme)
    if s is None:
        return f'{_said(raw)}: "{scheme}" is not a known scheme ({", ".join(SCHEME_NAMES)})'
    if not _PATTERNS[scheme].fullmatch(raw[i + 1:]):
        return f"{_said(raw)}: a {s['name']} code is {s['grammar']} ({s['example']})"
    return None


def normalize_tag(raw: Any) -> str:
    """A tag as a file writes it: trimmed, lower case, single spaces."""
    return _SPACES.sub(" ", ("" if raw is None else str(raw)).strip()).lower()


def tag_problem(raw: Any) -> Optional[str]:
    """Why ``raw`` is not a tag, or None."""
    if not isinstance(raw, str):
        return f"a tag is a text, not {_said(raw)}"
    norm = normalize_tag(raw)
    if not norm:
        return "a tag is not empty"
    if len(norm) > MAX_TAG_LENGTH:
        return f"{_said(raw)}: a tag is at most {MAX_TAG_LENGTH} characters"
    if norm != raw:
        return f"{_said(raw)}: write the tag as {_said(norm)} (lower case, trimmed, single spaces)"
    return None


def classification_problem(codes: Any = None, tags: Any = None, schemes: Optional[Sequence[str]] = None) -> Optional[str]:
    """The first problem of a thing's ``codes`` and ``tags`` (None is absent), or None; ``schemes`` narrows the schemes allowed."""
    if codes is not None:
        if not isinstance(codes, (list, tuple)):
            return f'codes is a list of "scheme:code" texts, not {_said(codes)}'
        if len(codes) > MAX_CODES:
            return f"codes holds at most {MAX_CODES} codes, not {len(codes)}"
        seen = set()
        for c in codes:
            p = code_problem(c)
            if p:
                return f"codes: {p}"
            scheme = c[:c.find(":")]
            if schemes is not None and scheme not in schemes:
                return f"codes: {_said(c)} is a {SCHEMES[scheme]['kind']} code; here a code is of {', '.join(schemes)}"
            if c in seen:
                return f"codes: {_said(c)} is written twice"
            seen.add(c)
    if tags is not None:
        if not isinstance(tags, (list, tuple)):
            return f"tags is a list of words, not {_said(tags)}"
        if len(tags) > MAX_TAGS:
            return f"tags holds at most {MAX_TAGS} tags, not {len(tags)}"
        seen = set()
        for t in tags:
            p = tag_problem(t)
            if p:
                return f"tags: {p}"
            if t in seen:
                return f"tags: {_said(t)} is written twice"
            seen.add(t)
    return None


def matches_prefix(code: str, prefix: str) -> bool:
    """Whether ``code`` is under ``prefix`` (``naics:54`` holds ``naics:541511``; ``naics`` holds every NAICS code)."""
    if code_problem(code):
        return False
    i = code.find(":")
    scheme, digits = code[:i], code[i + 1:]
    j = prefix.find(":")
    if j < 0 or j == len(prefix) - 1:
        return scheme == (prefix if j < 0 else prefix[:j])
    return scheme == prefix[:j] and digits.startswith(prefix[j + 1:])
