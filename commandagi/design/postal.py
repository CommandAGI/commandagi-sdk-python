"""Letters and postcards, declared in Python: a ``.letter.py`` and a ``.postcard.py``, the paper mail that CommandAGI's
postal mail prints and mails. The same documents and the same elements as the TypeScript SDK's JSX
(``commandagi/design`` ``postal.ts``)::

    from commandagi.design.postal import from_, letter, paragraph, to

    result = letter(
        to(name="Ada Lovelace", line1="12 St James's Square", city="London", postal_code="SW1Y 4JH", country="GB"),
        from_(name="Northwind Survey", line1="1 Main St", city="Portland", region="OR", postal_code="97201", country="US"),
        paragraph(text="Dear Ada,"),
        paragraph(text="Thank you for your order. It ships on Monday."),
        mail_class="first",
    )

The rule of the ontology's files: a record is an element and its fields are the element's attributes (snake_case
keywords: ``postal_code`` is ``postalCode``). The addresses are one ``to`` and one ``from_`` (``<from>``: ``from`` is a
Python keyword); the body is ``paragraph(text=…)`` children, in order. A postcard has no options and one
``front(image=…)``: a ref to a JPEG or PNG relative to the postcard's folder. Nothing adds a default. A run gives back
``{"format", "document", "sources"}`` beside an empty graph; ``sources`` names each element's call by its path (``""``,
``to``, ``paragraph@0``).
"""
from __future__ import annotations

from typing import Any, Dict

from .documents import DocTree, Vocabulary, register_vocabulary
from .element import define

ADDRESS_FIELDS = ["name", "company", "line1", "line2", "city", "region", "postalCode", "country"]
LETTER_FIELDS = ["color", "doubleSided", "mailClass"]

#: Every tag and what it holds (the TypeScript SDK's ``SIGNATURES``).
SIGNATURES: Dict[str, Dict[str, Any]] = {
    "letter": {"holds": "children"},
    "postcard": {"holds": "children"},
    "to": {},
    "from": {},
    "front": {},
    "paragraph": {},
}

__all__ = ["ADDRESS_FIELDS", "LETTER_FIELDS", "SIGNATURES", "LETTER_VOCABULARY", "POSTCARD_VOCABULARY",
           *define(globals(), "postal", SIGNATURES)]


def _fields(o: Dict[str, Any], keys: Any) -> Dict[str, Any]:
    """The fields a record says: an absent field and an empty text are not said."""
    return {k: o[k] for k in keys if k in o and o[k] != ""}


def _check(t: DocTree) -> None:
    a = t["attrs"]
    for k in ("color", "doubleSided"):
        if k in a and not isinstance(a[k], bool):
            raise ValueError(f"<letter> {k} is True or False")
    if "mailClass" in a and a["mailClass"] not in ("first", "standard"):
        raise ValueError('<letter> mailClass is "first" or "standard"')
    for c in t["children"]:
        if c["tag"] == "paragraph" and not isinstance(c["attrs"].get("text"), str):
            raise ValueError("<paragraph> text is text")
        if c["tag"] in ("to", "from"):
            for k, v in c["attrs"].items():
                if not isinstance(v, str):
                    raise ValueError(f"<{c['tag']}> {k} is text")


def _piece(t: DocTree) -> Dict[str, Any]:
    """What a letter and a postcard share: the addresses and the paragraphs."""
    _check(t)
    one = {c["tag"]: c for c in t["children"]}
    return {
        **({"to": dict(one["to"]["attrs"])} if "to" in one else {}),
        **({"from": dict(one["from"]["attrs"])} if "from" in one else {}),
        **({"front": one["front"]["attrs"]["image"]} if "front" in one else {}),
        "paragraphs": [c["attrs"]["text"] for c in t["children"] if c["tag"] == "paragraph"],
    }


def _letter(t: DocTree) -> Dict[str, Any]:
    piece = _piece(t)
    return {**_fields(t["attrs"], LETTER_FIELDS), **piece}


def _postcard(t: DocTree) -> Dict[str, Any]:
    front = next((c for c in t["children"] if c["tag"] == "front"), None)
    if front is not None and not isinstance(front["attrs"].get("image"), str):
        raise ValueError("<front> image is the ref of a JPEG or PNG")
    return _piece(t)


def _never(_: Any) -> DocTree:
    raise NotImplementedError("the editor makes the tree from a document (the TypeScript SDK's toTree)")


def _tags(root: str, root_attrs: Any, front: bool) -> Dict[str, Dict[str, Any]]:
    tags: Dict[str, Dict[str, Any]] = {
        root: {"parents": [], "attrs": root_attrs},
        "to": {"parents": [root], "single": True, "attrs": ADDRESS_FIELDS},
        "from": {"parents": [root], "single": True, "attrs": ADDRESS_FIELDS},
    }
    if front:
        tags["front"] = {"parents": [root], "single": True, "required": ["image"], "attrs": ["image"]}
    tags["paragraph"] = {"parents": [root], "required": ["text"], "attrs": ["text"]}
    return tags


LETTER_VOCABULARY = Vocabulary("letter", "a letter", "letter", _tags("letter", LETTER_FIELDS, False), _letter, _never)
POSTCARD_VOCABULARY = Vocabulary("postcard", "a postcard", "postcard", _tags("postcard", [], True), _postcard, _never)

for _v in (LETTER_VOCABULARY, POSTCARD_VOCABULARY):
    register_vocabulary(_v, "postal")
