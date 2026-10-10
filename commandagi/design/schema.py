"""THE SCHEMA OF AN ELEMENT'S PROPS, AND ITS CHECK — the Python form of the TypeScript SDK's ``schema.ts``.

A document's elements (``extrude(distance=10, …)``) take fields whose JSON Schema is generated from the types that
declare them (``threed_schema.py``). The reader checks each element against it with ``validate``, and
``describe_issue`` says each issue in the same English sentence as the TypeScript SDK, the CommandAGI op panels and
the agent tools: ``distance: must be greater than 0 (got -1)``.

The subset: type, enum, const, pattern, properties, required, additionalProperties, items, prefixItems, minItems,
maxItems, minimum, maximum, exclusiveMinimum, exclusiveMaximum, anyOf, oneOf, ``$ref`` (to ``#/$defs/<name>``),
``$defs``; the other keywords (default, description, the editors' ``x-*``) are not checked.
"""
from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

__all__ = ["resolve", "ref_name", "validate", "describe_issue", "issue_field", "is_file_ref"]

_REF = "#/$defs/"


def resolve(schema: Mapping[str, Any], defs: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The definition a ``$ref`` names, with the referring schema's own keywords (a description …) over it."""
    defs = schema.get("$defs", {}) if defs is None else defs
    s: Dict[str, Any] = dict(schema)
    guard = 0
    while "$ref" in s:
        if guard > 32:
            raise ValueError(f"{schema.get('$ref')}: a reference cycle")
        guard += 1
        ref = s["$ref"]
        if not ref.startswith(_REF):
            raise ValueError(f"{ref}: only #/$defs/<name> references are read")
        target = defs.get(ref[len(_REF):])
        if target is None:
            raise ValueError(f"{ref}: no such definition")
        own = {k: v for k, v in s.items() if k != "$ref"}
        s = {**target, **own}
    return s


def ref_name(schema: Mapping[str, Any]) -> Optional[str]:
    """The name of the definition a schema refers to, or None."""
    ref = schema.get("$ref")
    return ref[len(_REF):] if isinstance(ref, str) and ref.startswith(_REF) else None


def is_file_ref(v: Any) -> bool:
    """``{"$file": "Part.assets/f3/positions.f64", …}``: data kept in a file beside the document."""
    return isinstance(v, dict) and isinstance(v.get("$file"), str)


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_integer(v: Any) -> bool:
    return _is_number(v) and math.isfinite(v) and float(v).is_integer()


def _kind_of(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, (list, tuple)):
        return "array"
    if isinstance(v, bool):
        return "boolean"
    if _is_number(v):
        return "integer" if _is_integer(v) else "number"
    if isinstance(v, str):
        return "string"
    return "object"


def _type_matches(t: str, v: Any) -> bool:
    if t == "string":
        # Large data (an array, the bytes of a data URL) may be an ordinary file the document names (docs/formats.md).
        return isinstance(v, str) or is_file_ref(v)
    if t == "number":
        return _is_number(v) and math.isfinite(v)
    if t == "integer":
        return _is_integer(v)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "array":
        return isinstance(v, (list, tuple)) or is_file_ref(v)
    if t == "object":
        return isinstance(v, dict)
    if t == "null":
        return v is None
    return False


def _same(a: Any, b: Any) -> bool:
    """JavaScript's ``===`` on plain values: True is not 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return a == b
    if type(a) is not type(b):
        return False
    return isinstance(a, (str, type(None))) and a == b


def _join(path: str, key: Any) -> str:
    return f"{path}/{key}" if path else str(key)


def _issue(path: str, code: str, expected: Any = None, actual: Any = None, has_expected: bool = False, has_actual: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {"path": path, "code": code}
    if has_expected:
        out["expected"] = expected
    if has_actual:
        out["actual"] = actual
    return out


def validate(schema: Mapping[str, Any], value: Any, defs: Optional[Mapping[str, Any]] = None, path: str = "") -> List[Dict[str, Any]]:
    """Every way ``value`` breaks ``schema`` (issues ``{path, code, expected?, actual?}``); empty when it fits."""
    defs = schema.get("$defs", {}) if defs is None else defs
    s = resolve(schema, defs)
    out: List[Dict[str, Any]] = []
    options = s.get("anyOf") if s.get("anyOf") is not None else s.get("oneOf")
    if options is not None:
        results = [validate(o, value, defs, path) for o in options]
        if any(not r for r in results):
            return []
        # A union of objects told apart by a constant field (`type: "datum"`): the option the value names says the most.
        for i, o in enumerate(options):
            r = resolve(o, defs)
            if isinstance(value, dict) and any("const" in p and k in value and _same(value[k], p["const"]) for k, p in (r.get("properties") or {}).items()):
                return results[i]
        return [_issue(path, "anyOf", actual=_kind_of(value), has_actual=True)]
    t = s.get("type")
    types = [] if t is None else list(t) if isinstance(t, (list, tuple)) else [t]
    if types and not any(_type_matches(x, value) for x in types):
        if "integer" in types and _is_number(value):
            return [_issue(path, "integer", actual=value, has_actual=True)]
        return [_issue(path, "type", " | ".join(types), _kind_of(value), True, True)]
    if "const" in s and not _same(value, s["const"]):
        out.append(_issue(path, "const", s["const"], value, True, True))
    if s.get("enum") is not None and not any(_same(e, value) for e in s["enum"]):
        out.append(_issue(path, "enum", s["enum"], value, True, True))
    if isinstance(value, str) and s.get("pattern") is not None and not re.search(s["pattern"], value):
        out.append(_issue(path, "pattern", s["pattern"], value, True, True))
    if _is_number(value):
        for code, broken in (("minimum", lambda b: value < b), ("maximum", lambda b: value > b),
                             ("exclusiveMinimum", lambda b: value <= b), ("exclusiveMaximum", lambda b: value >= b)):
            if s.get(code) is not None and broken(s[code]):
                out.append(_issue(path, code, s[code], value, True, True))
    if isinstance(value, (list, tuple)):
        if s.get("minItems") is not None and len(value) < s["minItems"]:
            out.append(_issue(path, "minItems", s["minItems"], len(value), True, True))
        if s.get("maxItems") is not None and len(value) > s["maxItems"]:
            out.append(_issue(path, "maxItems", s["maxItems"], len(value), True, True))
        prefix = s.get("prefixItems") or []
        for i, item in enumerate(value):
            item_schema = prefix[i] if i < len(prefix) else s.get("items")
            if item_schema is not None:
                out.extend(validate(item_schema, item, defs, _join(path, i)))
    if isinstance(value, dict) and ("properties" in s or "required" in s or "additionalProperties" in s):
        props = s.get("properties") or {}
        extra = s.get("additionalProperties")
        for k in s.get("required") or []:
            if k not in value:
                out.append(_issue(_join(path, k), "required"))
        for k, v in value.items():
            p = props.get(k)
            if p is not None:
                out.extend(validate(p, v, defs, _join(path, k)))
            elif extra is False:
                out.append(_issue(_join(path, k), "additional"))
            elif isinstance(extra, dict):
                out.extend(validate(extra, v, defs, _join(path, k)))
    return out


def _js_number(n: Any) -> str:
    """A number as JavaScript writes it (``String(n)``, ``JSON.stringify(n)``): 1 not 1.0, 1e-7 not 1e-07."""
    if isinstance(n, int):
        return str(n)
    if not math.isfinite(n):
        return "NaN" if math.isnan(n) else ("Infinity" if n > 0 else "-Infinity")
    if n == 0:
        return "0"
    d = Decimal(repr(n))
    if 1e-6 <= abs(n) < 1e21:
        text = format(d, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    sign, digits, exp = d.normalize().as_tuple()
    ds = "".join(map(str, digits))
    e = exp + len(ds) - 1
    mant = ds[0] + ("." + ds[1:] if len(ds) > 1 else "")
    return f"{'-' if sign else ''}{mant}e{'+' if e >= 0 else '-'}{abs(e)}"


def _js_json(v: Any) -> str:
    """``JSON.stringify(v)`` of plain data."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if _is_number(v):
        return _js_number(v) if math.isfinite(v) else "null"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_js_json(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(f"{json.dumps(str(k), ensure_ascii=False)}:{_js_json(x)}" for k, x in v.items()) + "}"
    return json.dumps(str(v), ensure_ascii=False)


def _js_string(v: Any) -> str:
    """``String(v)``."""
    if isinstance(v, str):
        return v
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if _is_number(v):
        return _js_number(v)
    if isinstance(v, (list, tuple)):
        return ",".join("" if x is None else _js_string(x) for x in v)
    return "[object Object]"


def describe_issue(issue: Mapping[str, Any]) -> str:
    """One issue as an English sentence: ``distance: must be greater than 0 (got -1)``. An op panel shows the same
    sentence (its English catalog, without the path and the value it got)."""
    at = f"{issue['path']}: " if issue.get("path") else ""
    got = f" (got {_js_json(issue['actual'])})" if "actual" in issue else ""
    e = issue.get("expected")
    ex = _js_string(e)
    code = issue["code"]
    if code == "required":
        return f"{at}is required"
    if code == "type":
        return f"{at}must be {ex}{got}"
    if code == "integer":
        return f"{at}must be a whole number{got}"
    if code == "enum":
        return f"{at}must be one of {', '.join(_js_string(v) for v in e)}{got}"
    if code == "const":
        return f"{at}must be {_js_json(e)}{got}"
    if code == "minimum":
        return f"{at}must be at least {ex}{got}"
    if code == "maximum":
        return f"{at}must be at most {ex}{got}"
    if code == "exclusiveMinimum":
        return f"{at}must be greater than {ex}{got}"
    if code == "exclusiveMaximum":
        return f"{at}must be less than {ex}{got}"
    if code == "minItems":
        return f"{at}needs at least {ex} items{got}"
    if code == "maxItems":
        return f"{at}takes at most {ex} items{got}"
    if code == "additional":
        return f"{at}is not one of its fields"
    if code == "pattern":
        return f"{at}has the wrong form (it must match {ex}){got}"
    if code == "anyOf":
        return f"{at}does not match an allowed shape{got}"
    raise ValueError(f"no such issue code: {code}")


def issue_field(issue: Mapping[str, Any]) -> str:
    """The field an issue belongs to: the first segment of its path."""
    return str(issue.get("path", "")).split("/")[0]
