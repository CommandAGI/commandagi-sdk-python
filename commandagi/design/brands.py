"""A brand, declared in Python: a ``<Name>.brand.py``, one brand of a company — the names it goes by, its tagline and
voice, its logos, the design system it is drawn with, its domains, its sites, its social handles and the marks that
protect it. The same document and the same elements as the TypeScript SDK's JSX (``commandagi/design`` ``brands.ts``)::

    from commandagi.design.brands import Alias, BrandSurface, Domain, Handle, Logo, Mark, Site

    result = BrandSurface(
        Alias(name="Northwind Survey", kind="legal"),
        Logo(file="../design/logo.svg", kind="mark", background="light"),
        Domain(name="northwind.example", registrar="Porkbun LLC", expires="2027-05-18", auto_renew=True, mail=True),
        Site(folder="../site/"),
        Handle(platform="x", handle="northwindsurvey"),
        Mark(title="NORTHWIND", jurisdiction="US", number="99123456"),
        name="Northwind",
        voice=["plain", "warm"],
        design_system="../design/brand-book.json",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``auto_renew`` is ``autoRenew``). Every path is a ref from the brand file's folder: the brand holds no logo,
design system or site of its own, and a ``Mark`` refs a trademark the company records as an IP asset. Nothing adds a
default. A company names each brand file with ``Brand(file=…)``. A run gives back ``{"format", "document",
"sources"}`` beside an empty graph; ``sources`` names each element's call by its path (``""``,
``Domain#northwind.example``, ``Handle@0``).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

BRAND_FIELDS = ["name", "tagline", "about", "voice", "designSystem"]
ALIAS_FIELDS = ["name", "kind", "locale"]
LOGO_FIELDS = ["file", "kind", "background"]
DOMAIN_FIELDS = ["name", "registrar", "expires", "autoRenew", "site", "mail"]
SITE_FIELDS = ["folder"]
HANDLE_FIELDS = ["platform", "handle", "url", "connection"]
MARK_FIELDS = ["title", "jurisdiction", "number"]

#: Each list of the document, the tag of its elements and the fields they take (the TypeScript SDK's ``BRAND_LISTS``).
BRAND_LISTS = [
    ("aliases", "Alias", ALIAS_FIELDS),
    ("logos", "Logo", LOGO_FIELDS),
    ("domains", "Domain", DOMAIN_FIELDS),
    ("sites", "Site", SITE_FIELDS),
    ("handles", "Handle", HANDLE_FIELDS),
    ("marks", "Mark", MARK_FIELDS),
]
_FLAGS = {"autoRenew", "mail"}

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {"BrandSurface": {"holds": "children"}, **{tag: {} for _, tag, _ in BRAND_LISTS}}

__all__ = ["BRAND_FIELDS", "ALIAS_FIELDS", "LOGO_FIELDS", "DOMAIN_FIELDS", "SITE_FIELDS", "HANDLE_FIELDS", "MARK_FIELDS", "BRAND_LISTS",
           "SIGNATURES", "BRAND_VOCABULARY", *define(globals(), "brands", SIGNATURES)]


def _fields(o: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """The fields a record says: an absent field and an empty text are not said."""
    return {k: o[k] for k in keys if k in o and o[k] != ""}


def _check(t: DocTree) -> None:
    for node in [t, *t["children"]]:
        for k, v in node["attrs"].items():
            if k in _FLAGS:
                if not isinstance(v, bool):
                    raise ValueError(f"<{node['tag']}> {k} is true or false")
            elif k == "voice":
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    raise ValueError(f"<{node['tag']}> voice is a list of words")
            elif not isinstance(v, str):
                raise ValueError(f"<{node['tag']}> {k} is text")


def _brand(t: DocTree) -> Dict[str, Any]:
    _check(t)
    doc = _fields(t["attrs"], BRAND_FIELDS)
    for field, tag, keys in BRAND_LISTS:
        doc[field] = [_fields(c["attrs"], keys) for c in t["children"] if c["tag"] == tag]
    return doc


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


_ROOT = "BrandSurface"
_TAGS: Dict[str, Dict[str, Any]] = {
    _ROOT: {"parents": [], "required": ["name"], "attrs": BRAND_FIELDS},
    "Alias": {"parents": [_ROOT], "required": ["name"], "attrs": ALIAS_FIELDS},
    "Logo": {"parents": [_ROOT], "key": "file", "required": ["file"], "attrs": LOGO_FIELDS},
    "Domain": {"parents": [_ROOT], "key": "name", "required": ["name"], "attrs": DOMAIN_FIELDS},
    "Site": {"parents": [_ROOT], "key": "folder", "required": ["folder"], "attrs": SITE_FIELDS},
    "Handle": {"parents": [_ROOT], "required": ["platform", "handle"], "attrs": HANDLE_FIELDS},
    "Mark": {"parents": [_ROOT], "required": ["title"], "attrs": MARK_FIELDS},
}

BRAND_VOCABULARY = Vocabulary("brand", "a brand", _ROOT, _TAGS, _brand, _never)
register_vocabulary(BRAND_VOCABULARY, "brands")
