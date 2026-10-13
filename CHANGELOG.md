# Changelog

One entry for each release. A release is the tag `v<version>` in this repository and the same version on PyPI. The
TypeScript and Rust SDKs carry the same version number. A version promises nothing about the next one (README
§ Versions): read this file before you change the version you pin.

## Unreleased

Added

- 3D documents: a hole's `positions` and `sketch`; faces and edges chosen by a query, `{"kind", "select": {…}}`,
  beside the pick; a part is built in the order of its elements (a feature that names no `consumes` follows every
  body-making feature written before it).
- `Kernel.interference`, `Kernel.measure_all`, `linked_parts`; `parts=` on every call (an assembly's files);
  `KernelError.failures`.

Changed

- `Kernel.measure(doc, quantity, a, b)` works with the platform too (the service takes `measures`).
- `Kernel.export`, `measure`, `drawing` and `tessellate` refuse a build in which a feature failed. `tessellate`
  answers each body's triangles, not only their count.
- The call form (`part`, `subtract`, `hole`, `fillet` …) wires a feature to the heads of its body and to its last
  feature: about two wires a feature, where a plate of 129 holes was 566 kB. `Body.state` is gone; `Body.heads` and
  `Body.acts_on()` are what it has.
- A union's refusal names the field at fault (`edges/0/select/vertical: is not one of its fields`).

## 0.5.0 (2026-10-13)

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
