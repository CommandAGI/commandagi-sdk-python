"""A PLANT IN A SCENE — the ``operations`` system a design's ``slot(name="scene")`` holds (docs/formats.md § factories,
in the CommandAGI repository): items with their BOMs, locations, stations of machines, routings of ops, work orders,
resources, moves, deliveries and shipments, run by the simulation engine as discrete events whose material is
entities. The same plant as the TypeScript SDK's (``factory-operations.ts``); the scene stays a plain dict, so the
editor writes each edit back into it::

    from commandagi.design.factory import check_operations_system, machines_for

    line = check_operations_system({
        "id": "line", "kind": "operations", "time_scale": 60,
        "items": [{"id": "kit"}, {"id": "motor", "bom": [{"item": "kit", "qty": 1}]}],
        "locations": [{"id": "kits", "kind": "store", "capacity": 500, "stock": [{"item": "kit", "qty": 400}]},
                      {"id": "fg", "kind": "store", "capacity": 500}],
        "stations": [{"id": "wind", "machines": 4, "in": "kits", "out": "fg"}],
        "routings": [{"item": "motor", "to": "fg", "ops": [{"id": "wind", "station": "wind", "cycle_s": 75,
                                                            "consumes": [{"item": "kit", "qty": 1}]}]}],
        "orders": [{"id": "wo", "item": "motor", "qty": 400, "due_s": 57600}],
    })

``check_operations_system`` refuses an unknown field, a missing one, a number that is not a number or a
``"$parameter"``, and a name that points nowhere, in the engine's own words. The engine checks the rest when the
scene runs. ``machines_for`` is the sizing formula the engine's own sizing uses.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List

#: Each part's fields: the ones it needs, then the ones it may have. One table, the same in the three SDKs.
PLANT_FIELDS: Dict[str, Dict[str, list]] = {
    "system": {"needs": ["id", "kind", "items", "locations", "stations", "routings"], "may": ["seed", "time_scale", "window_s", "shifts", "record", "resources", "orders", "inbound", "outbound", "moves"]},
    "item": {"needs": ["id"], "may": ["label", "bom", "body", "ideal_cycle_s"]},
    "location": {"needs": ["id", "kind", "capacity"], "may": ["label", "stock", "zone", "slots", "transit_s", "to", "drive"]},
    "resource": {"needs": ["id", "kind", "skills"], "may": ["label", "members", "count", "physical"]},
    "station": {"needs": ["id", "in", "out"], "may": ["label", "units", "machines", "mtbf_s", "mttr_s", "repair", "maintenance", "tool", "plc", "zone"]},
    "routing": {"needs": ["item", "to", "ops"], "may": []},
    "op": {"needs": ["id", "station", "cycle_s"], "may": ["cycle_cv", "ideal_s", "setup_s", "consumes", "needs", "load_s", "inspect", "rework", "then", "body", "energy_j", "cell"]},
    "order": {"needs": ["id", "item", "qty"], "may": ["label", "release_s", "due_s", "priority"]},
    "inbound": {"needs": ["id", "item", "qty", "to"], "may": ["label", "at_s", "every_s", "first_s"]},
    "outbound": {"needs": ["id", "item", "qty", "from"], "may": ["label", "at_s", "every_s", "first_s"]},
    "move": {"needs": ["id", "from", "to", "lot", "reorder_at", "by", "travel_s"], "may": ["label", "item"]},
    "shifts": {"needs": ["windows"], "may": ["period_s"]},
}
_NUMBERS = {
    "capacity": "a whole number from 1 to 100000", "machines": "a whole number from 1 to 1000", "qty": "a whole number from 1 to 100000",
    "cycle_s": "the seconds one entity takes, more than 0", "setup_s": "seconds, 0 or more", "mtbf_s": "the mean operating seconds between failures, more than 0",
    "mttr_s": "the mean seconds a repair takes, more than 0", "energy_j": "the joules one entity takes, 0 or more", "lot": "a whole number from 1 to 100000",
    "reorder_at": "a whole number from 0 to 100000", "travel_s": "seconds, 0 or more", "transit_s": "the seconds an entity rides it, more than 0",
}
_PARAM = re.compile(r"^\$[A-Za-z_]\w*$")


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return math.isfinite(v)
    return isinstance(v, str) and bool(_PARAM.match(v))


def check_operations_system(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Refuses what the engine would refuse by shape or by name (``ValueError``); returns the spec."""
    def no(why: str):
        raise ValueError(f"system {spec.get('id')}: {why}")

    def fields(o: Dict[str, Any], part: str, at: str):
        needs, may = PLANT_FIELDS[part]["needs"], PLANT_FIELDS[part]["may"]
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
    if spec.get("kind") != "operations":
        no("kind is operations")

    def listed(k: str) -> List[Dict[str, Any]]:
        v = spec.get(k, [])
        if not isinstance(v, list):
            no(f"{k} is a list")
        return v

    items, locations, resources, stations, routings = (listed(k) for k in ("items", "locations", "resources", "stations", "routings"))
    orders, inbound, outbound, moves = (listed(k) for k in ("orders", "inbound", "outbound", "moves"))
    for part, xs in (("item", items), ("location", locations), ("resource", resources), ("station", stations), ("order", orders), ("inbound", inbound), ("outbound", outbound), ("move", moves)):
        for x in xs:
            fields(x, part, f"{part} {x.get('id')}")
    if "shifts" in spec:
        fields(spec["shifts"], "shifts", "shifts")
    item_ids, loc_ids, station_ids = ({x.get("id") for x in xs} for xs in (items, locations, stations))
    skills = {s for r in resources for s in r.get("skills", [])}

    def item(v, at):
        if v not in item_ids:
            no(f"{at}: item {json.dumps(v)} is not one of the items")

    def loc(v, at):
        if v not in loc_ids:
            no(f"{at}: location {json.dumps(v)} is not one of the locations")

    def skill(v, at):
        if v not in skills:
            no(f"{at}: skill {json.dumps(v)} is no resource's")

    def lines(v, at):
        for i, l in enumerate(v or []):
            item(l.get("item"), f"{at} {i + 1}")

    for x in items:
        lines(x.get("bom"), f"item {x.get('id')}: bom")
    for x in locations:
        lines(x.get("stock"), f"location {x.get('id')}: stock")
        if "to" in x:
            loc(x["to"], f"location {x.get('id')}")
    for x in stations:
        loc(x.get("in"), f"station {x.get('id')}: in")
        loc(x.get("out"), f"station {x.get('id')}: out")
        if "repair" in x:
            skill(x["repair"], f"station {x.get('id')}: repair")
    made = set()
    for i, r in enumerate(routings):
        at = f"routing {i + 1}"
        fields(r, "routing", at)
        item(r.get("item"), at)
        made.add(r.get("item"))
        loc(r.get("to"), f"{at}: to")
        for op in r.get("ops", []):
            where = f"{at} op {op.get('id')}"
            fields(op, "op", where)
            if op.get("station") not in station_ids:
                no(f"{where}: station {json.dumps(op.get('station'))} is not one of the stations")
            lines(op.get("consumes"), f"{where}: consumes")
            if "needs" in op:
                skill(op["needs"], where)
    for x in orders:
        if x.get("item") not in made:
            no(f"order {x.get('id')}: no routing makes {json.dumps(x.get('item'))}")
    for x in inbound:
        item(x.get("item"), f"inbound {x.get('id')}")
        loc(x.get("to"), f"inbound {x.get('id')}: to")
    for x in outbound:
        item(x.get("item"), f"outbound {x.get('id')}")
        loc(x.get("from"), f"outbound {x.get('id')}: from")
    for x in moves:
        if "item" in x:
            item(x["item"], f"move {x.get('id')}")
        loc(x.get("from"), f"move {x.get('id')}: from")
        loc(x.get("to"), f"move {x.get('id')}: to")
        skill(x.get("by"), f"move {x.get('id')}")
    return spec


def machines_for(rate: float, cycle_s: float, batch: float = 1, availability: float = 1, load: float = 0.85) -> int:
    """The machines a rate needs: CEIL(rate * cycle / (batch * availability * load)); ``rate`` in entities a second into
    the station, ``load`` the planned share of a machine's time."""
    if not (rate >= 0 and cycle_s > 0 and batch > 0 and 0 < availability <= 1 and 0 < load <= 1):
        raise ValueError("machines_for: rate is 0 or more; cycle_s, batch and load are above 0; availability and load are at most 1")
    return max(0, math.ceil(rate * cycle_s / (batch * availability * load) - 1e-9))
