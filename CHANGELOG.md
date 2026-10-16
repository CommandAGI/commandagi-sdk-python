# Changelog

One entry for each release. A release is the tag `v<version>` in this repository and the same version on PyPI. The
TypeScript and Rust SDKs carry the same version number. A version promises nothing about the next one (README
§ Versions): read this file before you change the version you pin.

## 0.6.1 (2026-10-15)

Added

- Agents (`commandagi.design.agents`): a harness (`harness.py`: `harness(kind=…, label=…, provider=…, runs=[…])`) and an
  agent (`agent.py`: a base names its `harness`, a fork its `parent`), the same elements as the TypeScript SDK's
  `agents.ts`. A realtime harness says what its model takes and gives live: `realtime={"in": […], "out": […], "audio":
  {"in": […], "out": […]}, "fps": …, "hz": …, "minutes": …, "videoMinutes": …}`.
- Test plans (`commandagi.design.testplans`): a `<name>.testplan.py` holds the steps that test one serial-numbered
  unit, never the results: `testplan(title=…, device=…)` with `condition`, `fixture` and `step`, the same elements as
  the TypeScript SDK's `testplans.ts`.
- Firmware (`commandagi.design.firmware`): a release (`<name>.firmware.py`: `firmware(version=…, image=…, sha256=…,
  sbom=…, device=…)` with `supports(revision=…)`) and a rollout (`<name>.rollout.py`: `rollout(firmware=…, world=…,
  channel=…, canary=…, waves=[…])` with `health` and `target`), as the TypeScript SDK's `firmware.ts`. A `sha256` that
  is not 64 lowercase hex digits is refused.
- A world's unit states its `serial` and its hardware `revision`.
- Tolerances. `parameter(tolerance=…)` and `hole(tolerance=…)` take `{"upper", "lower"}` (mm), `{"class": "H7"}` (an
  ISO 286 class or `ISO 492 bore|outside|width`) or `{"basic": True}`; a tolerance given two ways is refused.
  `commandagi.design.tolerances`: `tolerance_limits(nominal, tol)` and `fit_of(hole, shaft)`, the classes read from
  the shipped tables (`TOLERANCE_TABLES`). `check(kind="fit", hole=, shaft=, intent=)` and `check(kind="stackup",
  chain=, limit=, method=, samples=, seed=)` are checks of a 3D document (`kernel.check`).
- A hardware release and a change (`release()`, `change()`): the record of what a release of a design holds, a change
  proposal's change, and the release a unit or an instance was built from. A definition names its firmware and
  revision; `firmware()` also declares the channels a firmware gives.
- Logistics (`part_fields.py`): a schematic part's `suppliers`, `alternates`, `datasheet`, `lifecycle`, `compliance`
  and `shipping`, each KiCad properties of the part, on schematic parts and `component()`; `check(options=)`; a
  board's `fab()`; a 3D document's `item()` and `assemble()`. A body with `process="reference"` (a fit proxy) is out
  of the BOM and the logistics checks.
- Systems (`commandagi.design.systems`): requirements, a system's budgets (a cost budget names the design whose
  logistics roll-up it reads, `design=`) and an interface, as the TypeScript SDK's.
- A flow study (`study(kind="flow")`: `fluid`, `inlet`, `outlet`, `flow_mesh`; units m-kg-s).
- `kernel.dfm`: the manufacturability checks of a part; `kernel.check` takes devices. The slicer kernel (places:
  local, then cloud).
- `eda.export_kicad` (`pcb_export_kicad`): the board as a KiCad project.
- Drawing sheets: section and detail views in the schema; a sheet with a section view and no section, or a bad
  detail, is refused.
- A part's pinout and pads are checked: `pinout_verified`, `footprint_verified` and `package_dimensions` are part
  fields. A material grade states its Poisson's ratio where its source states one.

## 0.6.0 (2026-10-15)

Read **Removed** first: a script that calls `eda.autoroute` stops with `unknown tool` on the platform today, with 0.5.1
too.

Added

- A schematic part states its engineering data: `part_number=`, `manufacturer=`, `mpn=`, `rating=` and `attrs={…}` on
  any part but a ground. Each is one KiCad property of the part (`CommandAGI IPN`, `Manufacturer`, `MPN`, `Rating`,
  and each `attrs` entry by its own name), so the BOM, the `.kicad_pcb` and a board edit carry it. `attrs` refuses a
  name that has its own argument and the part's own `Reference`, `Value` and `Footprint`. `part_fields(inputs)` and
  `PART_FIELDS` read them back.
- Declared checks. A 3D document holds the checks it must pass and what it accepts: `check(id=…, kind=…)`
  (`interference`, `clearance`, `holes`, `fasteners`, `edges`, `symmetry`), `accept(…)` (one finding that is right on
  purpose, with its `reason`) and `permitted(…)` (the findings that a process or a purpose permits, such as the square
  edges of a laser-cut sheet). A circuit (`.sch.py`, `.pcb.py`) holds `check(kind="erc" | "drc")` and `accept(…)`.
  Each is checked against the schema when the document is read.
- `Kernel.check(doc)`: the checks a 3D document declares, run on one build, with its `accept` and `permitted` entries
  applied. Each finding names its check, rule, severity, body (id, name, part number) and location; a check that
  could not run is `skipped` with its reason, never `passed`. A document that declares no check gets the interference
  check.
- Fasteners: `fastener(id=…, part="iso-4762-m6", length=…, at=…, clamped=[…], receiver=…, washer=…, nut=…, grip=…,
  fit=…)` places a screw from the fastener library with its washer and nut, and records what it clamps into what. The
  `fasteners` check reads that record: each clamped part's clearance hole for its `fit` (ISO 273), and the thread a
  tapped receiver engages (`min_engagement`).
- Studies (`commandagi.design.study`): a `<name>.study.py` holds the question of an analysis of a part, never the
  answer: `study(kind="structural", part=…, units="mm-N-MPa-t")` with `material`, `fixture`, `loadCase`, `force`,
  `pressure`, `mesh`, `solver`, `criterion` and `revise`, the same elements as the TypeScript SDK. A solve is a run of
  the `fea` kernel, a new kernel name beside `3d`.
- A board's layout constraints, each a board fact: `netclass()`, `diffpair()`, `group()`, `keepout()`, `thermal()`,
  `objective()` (`commandagi.design.pcb`; CommandAGI's `docs/eda-layout.md`), as the TypeScript SDK's elements. The
  circuit editor's placer, router, layout score and layout checks read them.
- The layout tools: `eda.layout` (`pcb_layout`), `eda.layout_score`, `eda.check_layout`, `eda.constrain`,
  `eda.place_group` (`pcb_place_group`), `eda.route_nets` (`pcb_route_nets`) and `eda.rip_up`.

Changed

- The 3D kernel has a third place, `page`: the workbench page's own kernel. `COMMANDAGI_THREED` accepts `page`, `local`
  and `cloud`. Python has no transport to a page, so it passes `page` over and the default order on this computer stays
  `local`, then `cloud`. The `fea` kernel has no page.
- An example of a task proposal names a simulated run of the world it asks for (`worlds/shop/runs/…`), not a run of
  a second world.

Removed

- `eda.autoroute` (`pcb_autoroute`). The board has one router: `eda.route_nets` routes what is open of the nets from
  the copper they have, on the copper layers given (`layers`); `rip_up=True` routes them whole.
- The platform tools `pcb_optimize_routing` and `pcb_optimize_placement` (no SDK method called them; `call()` with
  their names now gets `unknown tool`). Use `eda.route_nets`, `eda.place_group` and `eda.layout`.

## 0.5.1 (2026-10-15)

Fixed

- `Kernel`'s message when no place can run it names the right install: `npm install -g @commandagi/host`, then
  `commandagi threed install`. 0.5.0 said `npm install -g commandagi`, a package with no command.
- `call()` no longer stops every call after a fixed 120 s. `CommandAGI(timeout=…)` sets how long a call waits (None:
  no limit; default 120 s), and `call(tool, args, timeout=…)` sets it for one call. A call with no answer in time
  raises `CommandAGIError` that says so (`pcb_autoroute: no answer within 120 s`); the platform may still finish the
  operation.

Added

- `commandagi.design.to_tsx(element)`: a Python document's root element as the TypeScript SDK's code file
  (`export default () => (<group …>…</group>);`), for a place that reads only TSX. It declares the same document as
  the Python (checked on the shipped examples: a 3D part, a schematic, a board, a drawing, a letter, a company, a
  project).

## 0.5.0 (2026-10-14)

The first release with the design layer. 0.5.0 was prepared on 2026-10-13 and not published; this entry holds all of it.

Changed

- `Kernel` speaks the kernel contract (`POST <kernel>/v1/<op>`, `GET <kernel>/v1/health`) and is placed by
  `COMMANDAGI_THREED`: `local`, `cloud`, both apart by `,` in the order to try (default `local,cloud`), or a running
  service's URL. `platform` is not a value now: write `cloud`. A place where the kernel is not installed is passed
  over; a refusal of the op is the answer. `Kernel.last_ran` says where each answer ran (`local` is never a cloud
  result), and `Kernel.call(op, doc, params)` gives a whole answer. `observe` takes no `doc_id`.

Added

- A 3D document's engineering vocabulary (`commandagi.design.threed`, checked against the one schema, as in the
  TypeScript SDK): `body(engineering={…})` (material grade, process, finish, vendor, cost, part number, mass),
  `joint(…)` (`fixed`, `revolute`, `prismatic`, `cylindrical`, `planar`, `screw`, `spherical`, `universal`),
  `mate(…)`, `sheet(…)` (an engineering drawing sheet), and `hole(size="M4 close fit")` (a hole by its standard name).
- `commandagi.design.standards`: `material`, `mass_grams`, `hole_size`, `sized_hole`, `standard_row`, `MATERIALS`,
  `HOLE_SIZES`, `STANDARD_TABLES`, `STANDARD_SOURCES`: the same tables as the TypeScript SDK, each with where its
  rows were read.
- `hole(body, at=…, size="M4 close fit", depth=…)` in the code-part primitives (`commandagi.design.cad`).
- `Kernel.sheet`, `Kernel.bom`, and `Kernel.observe(doc, materials=…)`: a body's `mass["grams"]`.
- 3D documents: a hole's `positions` and `sketch`; faces and edges chosen by a query, `{"kind", "select": {…}}`,
  beside the pick; a part is built in the order of its elements (a feature that names no `consumes` follows every
  body-making feature written before it).
- `Kernel.interference`, `Kernel.measure_all`, `linked_parts`; `parts=` on every call (an assembly's files);
  `KernelError.failures`.

Changed

- A joint's kinds: `hinge` is `revolute`, `slider` is `prismatic`, `ball` is `spherical`. Joints and mates are
  `joint(…)` and `mate(…)` elements: the reader refuses them inside `slot(name="dynamics")` and
  `slot(name="assembly")`.
- `Kernel.measure(doc, quantity, a, b)` works with the platform too (the service takes `measures`).
- `Kernel.export`, `measure`, `drawing` and `tessellate` refuse a build in which a feature failed. `tessellate`
  answers each body's triangles, not only their count.
- The call form (`part`, `subtract`, `hole`, `fillet` …) wires a feature to the heads of its body and to its last
  feature: about two wires a feature, where a plate of 129 holes was 566 kB. `Body.state` is gone; `Body.heads` and
  `Body.acts_on()` are what it has.
- A union's refusal names the field at fault (`edges/0/select/vertical: is not one of its fields`).


The first release that contains `commandagi.design`. PyPI 0.4.0 was built on 2026-09-23, before the design layer was
written; the version in the source stayed at 0.4.0 for the 106 commits after it, so the source and the package had
one number and different contents.

Added

- `commandagi.design`: documents declared in code, with the standard library only.
  - The code-part primitives: CAD (`part`, `box`, `cylinder`, `sketch`, `extrude`, `subtract`, `hole`,
    `linear_pattern` …), EDA (`circuit`, `board`, `component`, `net`, `connect`, `footprints`), any graph (`graph`,
    `node`, `input_`, `code`), and `run_module`.
  - One module for each document vocabulary: `schematic`, `pcb`, `threed`, `fab`, `office`, `twod`, `media`,
    `ontology`, `business`, `tasks`, `monitors`, `records`, `postal`, `pdf`.
  - `commandagi.design.cadquery`: a CadQuery-style importer.
  - `commandagi.design.source`: the map from each element to the call that made it, for the editors' write-back.
- `commandagi.kernel.Kernel` (also `commandagi.Kernel`): `observe`, `export`, `measure`, `drawing` and `tessellate` of
  a 3D document, by the CommandAGI 3D design service (OpenCascade). `COMMANDAGI_THREED` chooses the service:
  `platform` (the default, with an API key), `local` (this computer, offline, no account: the `commandagi` npm
  package's `commandagi threed serve`) or the URL of a running one.
- Client namespaces: `computer`, `billing`, `web`, `postal`, `social`, `phone`, `vpn`; agent constraints.
- `LICENSE` (MIT, as `pyproject.toml` states), this file, and § Versions in the README.

Changed

- The desktop control vocabulary has `mouse_down` and `mouse_up`.

Known limits

- `Kernel.measure` works with a local service only: the platform's route cannot be told which measurement.
- The hosted platform does not run a `.py` document's kernel calls for you; `Kernel` sends the graph that
  `run_module` made.

## 0.4.0 (2026-09-23)

The generated client (`CommandAGI`, `Session` over the thread WebSocket) replaced `RobotBridge`.

## 0.3.0 (2026-09-05)

The first release by trusted publishing.
