# Changelog

One entry for each release. A release is the tag `v<version>` in this repository and the same version on PyPI. The
TypeScript and Rust SDKs carry the same version number. A version promises nothing about the next one (README
§ Versions): read this file before you change the version you pin.

## Unreleased

Added

- A board's layout constraints, each a board fact: `netclass()`, `diffpair()`, `group()`, `keepout()`, `thermal()`,
  `objective()` (`commandagi.design.pcb`; CommandAGI's `docs/eda-layout.md`), as the TypeScript SDK's elements.
- `eda.layout`, `eda.layout_score`, `eda.check_layout`, `eda.constrain`, `eda.place_group`, `eda.route_nets`,
  `eda.rip_up`: the layout tools (`pcb_layout`, `pcb_layout_score`, …).

Removed

- `eda.autoroute` (`pcb_autoroute`): the board has one router. `eda.route_nets` routes what is open of the nets from
  the copper they have, on the copper layers given (`layers`), and `ripUp: true` routes them whole.

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
