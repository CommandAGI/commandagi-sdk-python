"""A FACTORY IN A SCENE — the ``flow`` system a design's ``slot(name="scene")`` holds (docs/formats.md § simulations,
"A factory", in the CommandAGI repository): products on routes through stations of machines with finite buffers, from
sources to sinks, run by the simulation engine as discrete events. The same factory as the TypeScript SDK's
(``factory-flow.ts``); the scene stays a plain dict, so the editor writes each edit back into it::

    from commandagi.design.factory import check_flow_system, machines_for

    line = check_flow_system({
        "id": "line", "kind": "flow", "time_scale": 60,
        "products": [{"id": "motor", "route": ["wind", "test"], "sink": "dock", "demand_per_period": 2000}],
        "sources": [{"id": "kits", "product": "motor"}], "sinks": [{"id": "dock"}],
        "stations": [{"id": "wind", "machines": 4, "cycle_s": 75, "buffer": 12, "availability": 0.92},
                     {"id": "test", "machines": 2, "cycle_s": 44, "buffer": 8, "yield": 0.975}],
    })

``check_flow_system`` refuses an unknown field, a missing one, a number that is not a number or a ``"$parameter"``,
and a name that points nowhere, in the engine's own words. The engine checks the rest when the scene runs.
``machines_for`` is the sizing formula the engine's own sizing uses.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict

#: Each part's fields: the ones it needs, then the ones it may have. One table, the same in the three SDKs.
FACTORY_FIELDS: Dict[str, Dict[str, list]] = {
    "system": {"needs": ["id", "kind", "products", "stations", "sources", "sinks"], "may": ["seed", "time_scale", "window_s", "shifts", "record"]},
    "station": {"needs": ["id", "machines", "cycle_s", "buffer"], "may": ["label", "at", "cycle_cv", "batch", "setup_s", "availability", "mtbf_s", "mttr_s", "yield"]},
    "product": {"needs": ["id", "route", "sink"], "may": ["label", "demand_per_period", "color"]},
    "source": {"needs": ["id", "product"], "may": ["label", "at", "per_hour", "arrivals"]},
    "sink": {"needs": ["id"], "may": ["label", "at"]},
    "shifts": {"needs": ["windows"], "may": ["period_s"]},
}
_NUMBERS = {
    "machines": "a whole number from 1 to 256", "buffer": "a whole number from 1 to 100000", "batch": "a whole number from 1 to 1024",
    "cycle_s": "the seconds one batch takes, more than 0", "cycle_cv": "the spread of the cycle time over its mean, 0 to 4",
    "setup_s": "the seconds a change of product takes, 0 or more", "yield": "the share of parts that survive, above 0 and at most 1",
    "availability": "the share of time it is not under repair, above 0 and at most 1", "mtbf_s": "the mean operating seconds between failures, more than 0",
    "mttr_s": "the mean seconds a repair takes, more than 0", "per_hour": "the parts it releases in a working hour, more than 0",
    "demand_per_period": "the parts wanted in one shift period, more than 0",
}
_PARAM = re.compile(r"^\$[A-Za-z_]\w*$")


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(v)
    return isinstance(v, str) and bool(_PARAM.match(v))


def check_flow_system(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Refuses what the engine would refuse by shape or by name (``ValueError``); returns the spec."""
    def no(why: str):
        raise ValueError(f"system {spec.get('id')}: {why}")

    def fields(o: Dict[str, Any], part: str, at: str):
        needs, may = FACTORY_FIELDS[part]["needs"], FACTORY_FIELDS[part]["may"]
        for k in o:
            if k not in needs and k not in may:
                no(f"{at}: unknown field {k} (it has {', '.join(needs + may)})")
        for k in needs:
            if o.get(k) is None:
                no(f"{at}: {k} is needed")
        for k, why in _NUMBERS.items():
            if k in o and not _is_number(o[k]):
                no(f"{at}: {k} is {why}")

    fields(spec, "system", "the system")
    if spec.get("kind") != "flow":
        no("kind is flow")
    lists = {}
    for k in ("stations", "products", "sources", "sinks"):
        if not isinstance(spec[k], list):
            no(f"{k} is a list")
        lists[k] = spec[k]
    for part, k in (("station", "stations"), ("product", "products"), ("source", "sources"), ("sink", "sinks")):
        for x in lists[k]:
            fields(x, part, f"{part} {x.get('id')}")
    if "shifts" in spec:
        fields(spec["shifts"], "shifts", "shifts")
    stations, sinks, products = ({x.get("id") for x in lists[k]} for k in ("stations", "sinks", "products"))
    for p in lists["products"]:
        for step in p["route"]:
            sid = step if isinstance(step, str) else step.get("station")
            if sid not in stations:
                no(f"product {p.get('id')}: route names {json.dumps(sid)}, which is not a station")
        if p["sink"] not in sinks:
            no(f"product {p.get('id')}: sink {json.dumps(p['sink'])} is not one of the sinks")
    for x in lists["sources"]:
        if x["product"] not in products:
            no(f"source {x.get('id')}: product {json.dumps(x['product'])} is not one of the products")
    return spec


def machines_for(rate: float, cycle_s: float, batch: float = 1, availability: float = 1, load: float = 0.85) -> int:
    """The machines a rate needs: CEIL(rate * cycle / (batch * availability * load)); ``rate`` in parts a second into
    the station, ``load`` the planned share of a machine's time."""
    if not (rate >= 0 and cycle_s > 0 and batch > 0 and 0 < availability <= 1 and 0 < load <= 1):
        raise ValueError("machines_for: rate is 0 or more; cycle_s, batch and load are above 0; availability and load are at most 1")
    return max(0, math.ceil(rate * cycle_s / (batch * availability * load) - 1e-9))
