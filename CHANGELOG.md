# Changelog

One entry for each release. A release is the tag `v<version>` in this repository and the same version on PyPI. The
TypeScript and Rust SDKs carry the same version number. A version promises nothing about the next one (README
§ Versions): read this file before you change the version you pin.

## Unreleased

Added

- A part states its steady `draw` (`draw="120 mA"` or `"1.2 W"`, a KiCad property `Draw`). A system's load that states
  no current or power names a circuit part (`part="ee/main.circuit.ts#U1"`), and `commandagi check` reads the part's draw.
- A link budget: `quantity="rf-link"` with `frequency` (Hz) and `range` (m) on the budget, and contributions in `dBm`
  (with `end="tx"`, the power sent, or `end="rx"`, the receiver's sensitivity) and in `dB` (gains +, losses -). The
  check adds the free-space path loss and passes when the margin is at least the limit (dB).
- An interface states its `<channel format dir medium dialect transport>`; `commandagi check` holds a definition or a
  unit side's channel to each field it states.
- A part's features and a circuit's components keep the call that declared them (`cad.py`, `eda.py`), and the source
  map gives each list its entries, so an editor writes an edit into the literals of `box(…)` or `component(…)`.
- A data sheet: `sheet(name=…, source=…, query=…, format=…)` reads a file beside the workbook, an http(s) URL or
  `surface:<id>`, as the TypeScript SDK's `<sheet source>` does; it holds no cells, columns or rows.

- A video's `clip(link=…)`: two clips of one video file with the same `link` are its picture and its sound, patched to
  two tracks at once. A video file on an audio track is its sound (a clip of kind `audio`); a still there is refused.
- A drawing's compound shape is `compound(…, op=…)` (`unite`, `minus`, `intersect` or `exclude`): it holds its shapes
  and draws their Pathfinder result live, so each shape stays editable. It replaces `boolean`, which a drawing no longer
  reads; a file that wrote `boolean(…, op="subtract")` writes `compound(…, op="minus")`.
- A camera unit's calibration takes `camera(channel=…, intrinsics=…, extrinsics=…, residual=…, robot=…, marker=…,
  run=…, reality=…, at=…, by=…)`, one per video channel: the lens, the camera in the world, the residual and the run
  that measured it with its reality (the TypeScript SDK's `<camera>`).
- A board's `<component>` takes `locked` (KiCad's footprint lock, `true` or left out), so a KiCad board's locked footprints keep the
  lock through the code and back to a `.kicad_pcb`.
- A schematic's code part takes `suppressed` (`code(name, source=…, suppressed=True)`): a suppressed part is not run
  and declares nothing (the graph's disabled node).
- A board's `trace(…)` takes `rule`, its routing rule: "45", "90" or "any" (the default). A value off these three is
  refused.
- A market recording (`<name>.market.py`, `commandagi.design.market`): `market(...)` holds one element per record, in
  time order: `note`, `quote`, `trade`, `book` (its `bid` and `ask` levels), `news`, `position`, `order`,
  `order_update`, `cancel`, `cancel_update`, `amend`, `amend_update`, `fill` and `account` (its `holding`,
  `open_order` and `problem` children). Every attribute is text; a price or a quantity is decimal text (`"185.09"`),
  and a number there is refused by name. It declares `{"records": [...]}`.
- A step-response study's `tune(joint=…, kp=[low, high], kv=[low, high])`: the bounds the validation planner may
  search a joint's gains in when the study fails; what it finds is proposed as an edit of the unit's calibration.
- A study of kind `step-response` (`units="rad-s"`, `STEP_RESPONSE_UNITS`): `step(id=…, joint=…, from_=…, to=…)` (each
  solved alone), `gains(joint=…, kp=…, kv=…)` (the gains to try on a joint), `response(duration=…, dt=…, band=…)`; a
  `criterion` names the `step` it reads. Its `part` is a `definition.tsx` or a unit of a world (`world.tsx#<uid>`).
- A unit's calibration (`<name>.calibration.py`, `commandagi.design.records`): `calibration(device=…, serial=…, note=…)`
  with `joint(name=…, zero=…, kp=…, kv=…, run=…)` and `rezero(joint=…, zero=…, at=…, by=…, reason=…)`, the unit's
  re-zeros oldest first. A world unit names it by `calibration`.
- A side places the interface's frame by `rotation` (degrees, counter-clockwise) and `face` (`back`: read from the
  mating part, the frame mirrored through its y axis, so a hole or pin placed on it is mirrored too).
- A painting's or a photo's `mask(of="Name")` names a layer the stack shows, by its `name`, and wires the masked node to it; the element holds no layer of its own.
- `sch_style`: a placement's De Morgan body style (`unit("U1", 2, …, sch_style=2)`), which selects the pins and body the library draws for it. 1 is the default and writes nothing.
- `commandagi.design.scouts`: the scouts' two documents, the same as the TypeScript SDK's `scouts.ts` (docs/scouts.md
  in the CommandAGI repository):
  - `scout(case(...), configuration(...), workload(...), judge(...), budget=…, …)` (`<name>.scout.py`): one comparison
    of configurations on the cases of each workload, scored by a check (`exact`, `oneOf`, `number`, `contains`,
    `regex`, `json`, `letter`, `literal`, `tool`, `program`) or by a judge panel, with the verdict's rules (`budget`,
    `repeats`, `margin`, `relative_margin`, `error_floor`, `min_calls`, `min_cases`, `resamples`, `alpha`, `seed`,
    `max_cases`). A case's `from_` is `public`, `synthetic` or `own-run`; nothing else may be a case.
  - `replacement(layer(capability(evidence(...))), decision(...), product=…, as_of=…)` (`<name>.replacement.py`): what
    replacing a product would cost, by layer and capability, with the decision and the economics.

- A monitor source names the connected account it reads as (`<source connection="gmail@jacobfv123@gmail.com">`); the api worker reads it (`via="worker"` only).
- `<component refRot={90}>`: how far a part's reference text is turned where it sits, in degrees, in the footprint's own frame (the placer turns a text it has no upright place for).

- A world unit declares `tilt_deg`: how far its front is raised above level, in degrees (positive up; absent is
  level). A video channel declares its lens as `fieldOfViewDeg`, `frameAspect` and `lensAtMm`, which the world view and a
  world's coverage test read alike.

Added

- A load states its `duty`: the share of time it draws (`duty={0.25}`, a number in (0, 1]). A power budget takes
  its average draw; a peak budget takes the whole draw at the peak. A load's `inrushCurrent` (A) is its peak at
  switch-on when it is more than its peak draw.
- An agent declares its `supervisor` (`<agent supervisor="agent:lead">`, `agent:<id>` or `person:<id>`): a thread's
  membership takes it at join, and a person's supervise of that member overrides it.
- An interface's `<param>` states a number with its unit, or a text a channel states (a `format`, a `dialect`,
  a `transport`: `<param id="framing" value="8N1" />`) and then no unit. A side's `params` maps such a field
  to it, and the check compares the texts: a definition's channel and a firmware `#define` alike.
- A side states where the interface's frame sits on it with `rotation` (degrees counter-clockwise) and `face`
  (`top`, or `bottom` for the side seen from the mating board, whose frame is mirrored): a 3D deck turned a
  quarter turn, or read from underneath, matches the same hole pattern.

Changed (a document written for 0.6.8 may need an edit)

- `commandagi.design.evals`: a metric's `probe` names a task file (`{"kind": "task", "task": "<ref>"}`, an
  `alignment`'s `reference.task`) or another metric file (a `composite` input's `metric`) by ref; a probe that names
  one by node id (`taskId`, `metricId`) is refused with why, as the platform's routes and reader refuse it.

Fixed

- 3D: a placed file's `<joint>`s come with it, as `<placement id>/<joint id>` at any depth (`dock_a/palletLift`,
  `bay_1/dock_a/palletLift`). Each is placed as the file's bodies are (its anchor, axis and references), with its
  `fixed` chain, so a sweep in any document above moves what the joint moves in its file:
  `sweep={{ joint: "dock_a/palletLift" }}`. No level restates a joint (CORE-58, IC1-20, PCBC-22, ROUTER-02). A joint
  whose `a` or `b` the placement leaves out (`omit`) goes with it; a `moves` entry that moves only its `a` along the
  joint (a latch closed, a lid opened) shifts its `limits` by that value, so the sweep still stops where the file
  says. Needs a host of this version (`commandagi check` links the placed files).

## 0.6.8 (2026-10-23)

Added

- `commandagi.design.monitors`: `discover(of=..., into=..., when=..., slug=..., class_=..., props=..., name=..., max=...)`,
  a monitor's part that gives each thing its records name a folder and a thread of its own; a monitor's `same_as`, a
  source's `vantage` and a follow's `where`. A monitor's document always has `discovers`. The same as the TypeScript
  SDK's `<discover>`, `sameAs`, `vantage` and `where`.
- `commandagi.design.twod`: `engrave(id=..., src="logo.png", x_mm=..., y_mm=..., width_mm=..., height_mm=..., dpi=...,
  dither="ordered")` in a `nest(...)`, an image burned on the first sheet. The same as the TypeScript SDK's
  `<engrave>`.
- `commandagi.design.threed`: `curve(tangents=[{"at": 1, "direction": [...]}], tangent_scale=...)`, a spline's
  direction at an inner point (the spline is C1 there) and how hard every given tangent holds (1 is the natural
  spline). `pathPattern(path={"curve": ...})` places its copies along a curve in space, and `align_to_path` turns each
  by the curve's rotation-minimizing frame. A sweep's `twist` now turns the profile on top of the Frenet and up frames
  too.
- `commandagi.design.threed`: `product(id=, name=, part_number=, compliance=, shipping=)`, the product as it is sold
  (its certifications, tariff heading, packed size and mass; the document's `products`); `make.stock` (the stock a
  made part uses, bought by its own offers); a process chemical's `shutoff`. The same as the TypeScript SDK's
  `<product>`.
- `commandagi.design.evals` (`commandagi::design::evals`): an eval and a metric in code, `<eval>` with `<case>`
  children and `<metric>`, the same documents as the TypeScript SDK's `evals.ts`. A case names its task file (`task`,
  a ref) or says its `instruction`; `metrics` and `acceptanceMetric` are refs; `frozen` is the digest the eval is
  frozen at. In Python the elements are `eval(...)`, `case(...)` and `metric(...)` (importing `eval` hides the builtin
  in that file), and a metric's `pass` is written `pass_`.
- `commandagi.design.pcb`: `group(side="any")` lets the placer turn each part over where that costs less, and
  `group(edge=…, mating=…)` holds the group's parts against a board edge (`"left"`, `"right"`, `"top"`, `"bottom"`),
  their `mating` side (in the footprint's own frame) out; `mating` needs `edge`.
- `commandagi.design.pcb`: `component(ref_at=[x, y])`, where the part's reference text sits (mm, in the footprint's
  own frame); the layout moves each reference off copper and off the others and writes it here.
- `commandagi.design.pcb`: `bus(name, nets, pitch)`, nets that run together: where their tracks run side by side they
  are parallel, `pitch` (mm) apart centre to centre. The same element as the TypeScript SDK's `<bus>` and the Rust
  SDK's `bus()`.
- `commandagi.design.threed`: `fastener(corner=...)`, the direction from the axis to a corner of each hexagon of the
  stack (a hexagon head, a nut). Absent, it is the model's X (its Y when the axis is within 26° of X). An assembly that
  places the file turns it with the placement, so one assembly placed at two turns is one STEP product.
- The materials data has the fastener grades `A2-70`, `A4-70`, `8.8` and `12.9` (each row's source says where its
  numbers were read): a screw whose stack names one of them has a mass.

Changed (a document written for 0.6.7 may need an edit)

- `commandagi.design.evals`: an eval's `objective` and its `scoring` weights name metric files by ref, as `metrics`
  does: `objective={"kind": "metric", "metric": "Lap time.metric.tsx"}`, a linear term's `metric`, and weights keyed
  by ref. An objective that names a metric by node id (`metricId`) is refused with why. The same as the TypeScript
  SDK's.

Fixed

- The T-slot sections have the maker's 45° web again: `cavity_floor_width` is 5.88 (5 Series) and 9.17 (HFS6-3030).
  0.6.6 had it, but 0.6.7's standards data was generated from tables that never took the fix (5.6 and 8.5), so
  HFS5-2080's ix was 5.04 % over MISUMI's again. The repository's tables now hold it: each section's area, ix, iy and
  mass are within 3.1 % of MISUMI's, and the repository's test holds 5 %.

- Silent failures are errors (microfab 0.6.6). The vocabulary's descriptions say so; what reads a document does it:
  - CORE-59: `<externalPart omit moves>` take a placed file's id for everything placed under it (`omit={["pallet"]}`
    is `pallet/*`, its `<item>`s too), and an entry that names nothing of the file is an error that names it.
  - CORE-63: an `<accept check>` or a `<permitted check>` that is no check of the document is an error
    (`accept-unknown-check`, `permitted-unknown-check`); a `<permitted body>` that names no body is one too
    (`permitted-unknown-body`). A circuit's `<accept check>` of no check is an ERC error.
  - CORE-64: a placement's `quaternion` is a unit quaternion: within 1e-5 of unit length (6 decimals) it is read as
    the rotation it rounds; further off it is refused, so a placement never scales a part.
  - LABS-27: `commandagi task approve | decline` is a person's own act: refused from an agent's shell or with an
    agent's key, and typed at a terminal; the record names the person.

## 0.6.7 (2026-10-23)

Added

- `commandagi.design.threed`: `curve(...)`, a curve in space (`kind` `"spline"` through `points` with optional
  `start_tangent` and `end_tangent`, `"polyline"` with `bend_radius`, `"helix"`), and `sweep(...)` along it
  (`path={"curve": "lead"}`) with `frame` (`"minimal"`, `"frenet"`, `"up"` with `up`, `"guide"` with `guide`) and
  `twist`. A curve is also the plane normal to it at its start, under its id (`plane={"type": "datum", "plane": "lead"}`).
  A sweep that would cross itself fails by name (`self_intersection`). Needs a 3D service of this version.

- `commandagi.design.mounts`: a thread's mounted tasks as `mounts.py` in its run folder, `mounts(mount(label=…, …))`,
  the same document as the TypeScript SDK's `mounts.tsx`. A mount names one task (`task`), or a list (`folder`,
  `project`, or a query: `assignee`, `labels`, `status`); a mount that names both, or nothing, is refused.

- `cagi.tasks.mount`, `unmount` and `mounts`: mount a task (`task=…`), a task list (`folder=…`), a project
  (`project=…`) or a query (`assignee="me", status=["todo"]`) to a thread. With no thread named, they act on the
  thread the code runs in, and the agent is prompted with the open tasks until they are done.
- `commandagi.design.systems`: a device definition is a side of an interface (`side(kind="definition", channel=…,
  params=…)`). `load(...)` takes `peak_current` and `peak_power`; `budget(quantity="power", peak=True)` counts each
  load at its peak. `peak` on any other budget is refused.

Fixed

- 3D: each face of the view cube carries the name of its view (Front showed "Back"); a thread cuts its whole groove
  (it removed half a turn); a hole of a sketch (a circle inside a rectangle) is a region of its own, so a profile can
  extrude the disc alone. Needs a 3D service of this version.
- PCB: after Lay out, the board view shows the copper that the layout added, with no reload.

In the host (`@commandagi/host` 0.6.7)

- Agent CLIs as instances: a host runs each CLI (Claude Code, Codex, Gemini CLI) and every fork of one found along the
  search path of the thread's folder (`agents/<folder>/agent.tsx`), each with its own model and a named sign-in.
  `commandagi agents signin <name> --cli claude-code|codex|gemini-cli` runs the CLI's own login into a config folder of
  its own; `--save-to-account` keeps the sign-in in your account, sealed, and `--from-account` brings it to another
  computer. A sign-in at its limit gives its turn only to another provider, never to another sign-in of the same
  provider. `agents.sandbox` (`os` or `off`) replaces `agents.approvals`; `agents.models` is gone (each instance has
  its model).
- A thread with several agent members works a mounted task list in parallel: `commandagi agents start --mount <M>
  --member <A> …`, `agents join|leave` and `agents tasks`. A claim is a compare-and-set write of the task file,
  recorded first in the thread's `tasks` stream. Each task gets its own git worktree and branch, which the host never
  merges. `agents.concurrency` bounds the turns of each sign-in; a dead claim is released. An agent may be a member of
  several threads.
- The task loop on the host: the `mounts.tsx` (or `.py`, `.rs`) in a thread's run folder starts each agent turn with
  the open mounted work, and a write of a mounted task wakes the loop.
- Site hosting: `commandagi sites deploy|list|logs|rollback|domains|env|build`. A push deploys each branch (the
  production branch to `<slug>.commandagi.app`, any other branch to a preview). A framework site (Vite, Astro,
  SvelteKit, Next static export, CRA) is built by `commandagi sites build` on a computer of the account.
- Interfaces: a device definition's channel is a side of an interface; the check holds the channel's fields (baud) to
  the interface's parameters.
- Test plans: each step's `verifies` is read back, and a requirement that it names must name the step.
  `commandagi testplan check|run|history|results`.
- Firmware rollouts refuse a rollback: a release below a unit's `minSecurityVersion` goes to no unit, and the wave
  halts. `commandagi rollout check|start|advance|retry|rollback|status|close`.
- Budgets: a power budget with `peak` counts each load at its `peakCurrent` or `peakPower`; data and data-rate units
  (`bit` … `TB`, `bit/s` … `GB/d`); the contributors of a cost budget are the roll-up's lines. A release refuses a
  pinout or footprint check that names a part from memory.

On the platform

- A thread's mounted tasks: `GET|POST|DELETE /threads/:id/mounts` and the tools `mount_tasks`, `unmount_tasks` and
  `list_mounts`. Each turn carries the open mounted work, and the thread continues with the next task until the work is
  done, bounded by no-progress turns, its budget and its run state. A task is named by its drive and its id: an id
  found in two other drives is refused (`409 ambiguous_task`) with each address.
- Agent sign-ins kept in the account (`agents signin --save-to-account`), sealed outside the Drive; a person's key only.
- Sites deploy from a push, with a preview for each branch, env for each target, rollback and deploy logs
  (`deploy_site { fromFolder, target }`, `site_deploy_log`).
- An API key never mints a key or seats an agent wider than itself, and every Drive write (a git write too) needs the
  key's edit scope.

## 0.6.6 (2026-10-22)

Added

- `client.git`: the folder git operations listed under the host below (`merge(branch=…)`, since `from` is a Python keyword).
- `eda.layout` follows a platform layout job to its end.

Fixed

- The T-slot sections have the maker's 45° web between two slot cavities: 1.5 mm in the 5 Series (MISUMI's drawing
  prints it) and 2.0 mm in HFS6-3030 (measured on its drawing), where 0.6.5 drew 1.7 and 2.5 mm. So
  `cavity_floor_width` is 5.88 (5 Series) and 9.17 (HFS6-3030). 0.6.5 said each section was within 5 % of MISUMI's;
  HFS5-2080's ix was +5.04 %. Now each section's area, ix, iy and mass are within 3.1 % (the straight walls have no
  radii or fillets), and the repository's test holds 5 %.

In the host (`@commandagi/host` 0.6.6)

- The FEA kernel picks its solver for each level from the level's size and the memory it has: PaStiX on every core
  when it fits, SPOOLES on one thread when it does not. The level's line says which ran and why. `COMMANDAGI_FEA_MEMORY`
  (for example `96g`) sets the kernel container's memory. A 2.18-million-node level needs about 73 GB with SPOOLES and
  108 GB with PaStiX.
- The workbench speaks Japanese, Brazilian Portuguese, French, German, Arabic (right to left) and Indonesian, beside
  English, Spanish and Simplified Chinese.
- `commandagi git <op>` works on a folder of this computer or a cloud folder (`cloud://home/<uuid>/…`): status, log,
  diff, commit, checkpoint, branch, switch, checkout (a commit as a detached HEAD), merge, remotes, fetch, pull, push,
  and fork (cloud). A remote's credential names an account of the host's secret store and is given to git for one
  call; it is never written into `.git/config`. A synced folder and its cloud folder share one history.

On the platform

- A cloud file or folder that was renamed or moved is still reached at its old path; the answer names the current one
  (`x-commandagi-moved-to`). A git remote that names an old folder keeps working.
- `pcb_layout` on a board larger than the platform runs in place becomes a job (`pcb_layout_status`); no layout ends in
  a Worker resource error any more.

## 0.6.5 (2026-10-22)

The items still open after 0.6.4 (the microfab team's ids in brackets). `@commandagi/host` 0.6.5 carries the checks.

Changed (a document written for 0.6.4 may need an edit)

- A `<fastener at>` is a point on the screw's axis, on or above the first clamped part: the rebuild seats the stack on
  the face its washer or head bears on (a counterbore's floor, a top face, a countersink), and builds every piece
  there; `grip` is measured from the seat. A stack that finds no seat stays at `at`, and `head-not-seated` says why
  (PCBC-06).

Added

- Board fills read KiCad's thermal spoke angle (45° for a round pad, 90° otherwise), relieve heatsink vias as KiCad
  does, and hold a spoke to the pad's width and the zone's least width: the team's axis node now has KiCad's 5 GND
  pieces (EDA-27).
- `<group near maxDistance>` is a hard rule of the placer; a wide net necks to its class's `minWidth` only where full
  width does not fit, and `pcb_layout` names each neck. The axis node lays out complete: KiCad 0 errors, 0
  unconnected, 0 parity (EDA-20).
- A planar face of many edges is triangulated by the kernel itself: the 1136-hole breadboard's mesh in 2.5 s, not 30 s,
  the same mesh (CORE-23).
- A syntax error in plain code names `file:line:col` and its token in every runner (the command line, the platform, the
  page; Python too).
- The T-slot profiles are drawn as the catalog draws them: each section's area, moments and mass within 5 % of MISUMI's
  (the table also gains `cavity_floor_width`, and HFS6-3030 its corner holes).

## 0.6.4 (2026-10-22)

The fixes for the microfab team's re-test on 0.6.3 (66 open items; the ids in brackets are theirs). The vocabulary below
is the same in the three SDKs, in each language's spelling; `@commandagi/host` 0.6.4 carries the checks.

Changed (a document written for 0.6.3 may need an edit)

- A placed assembly keeps its own `<permitted>`, `<library>`, `<accept>` (`body` and `other`) and names under the
  placement: a dock that passes alone passes where it is placed. A placement's id selects its members in `bodies`,
  `against` and `pair` (`dock`, `dock/MF-SH-VEE-20`) (CORE-51, CORE-52, CORE-54). A placed file of several parts keeps
  each as `<placement>/<id>`.
- Every file resolves its imports from its own folder, in every command; the folder a run reads is `--folder`, else the
  file's git repository (CORE-48, CORE-50). A `<part>` or `<assembly>` inside another document says to place its file.
- `commandagi diff` prints its lines; `--json` or `--out FILE` gives the JSON (CORE-45).
- An accept of a check that ran and covers nothing warns (`accept-unused`); a whole-part finding (`mill.material`) has
  no place, so a body + rule accept covers it (CORE-47). `--only` leaves out the other checks' accepts (IC2-18).
- One finding per hole, cup or region, each with its own size (CORE-46). A washer is what bears on a clamped part
  (IC2-14).
- A bill line of fastener pieces is named by its designation, a roll-up line by its part number (CORE-29).
- `route` says `complete: false` while a net has islands, pours counted (EDA-23); `route`/`layout` `--out` names the
  board written, the input is left (EDA-22); copper too near the edge is an error (EDA-25); a part with no sheet
  position is in ERC (EDA-21).

Added

- `<check sweep={{ joint, samples | step }}>`: interference and clearance over a joint's limits, each finding at its
  joint value with where it starts and ends (PCBC-14); `<accept maxVolume>` (PCBC-18).
- `<externalPart omit moves>`: one placed file with parts left out or moved; a frame placed in every station (IC1-19,
  IC1-14, PCBC-20).
- `engineering.envelope` and `mountingHoles` for a bought part drawn as its envelope (IC2-13); `<library sizes>`, one
  table of sizes, part numbers and prices (CORE-29); a library screw's mass (CORE-44).
- STEP files hold one product per part used N times, nested sub-assemblies, and the library's part numbers (CORE-20,
  CORE-53, IC2-19); `threed observe` names bodies as the checks do (CORE-39).
- `<slice device>`: a resin setup names its printer (CORE-42). A through hole is drilled from both declared setups
  (CORE-40). A run of primitive cuts is one boolean: 473 cut cylinders check in 2.7 s, not 21 s (IC2-15).
- Studies: results are streamed (a 2.18M-node study, 1.2 GB of results, runs to its verdict: CORE-55); a container
  ends with its host; stress beside a converging re-entrant edge is read (CORE-56); `spring` and `pin` supports
  (IC1-15); `--keep field` (PCBC-19); `study check` refuses what `study run` refuses (CORE-41).
- `COMMANDAGI_THREED=cloud` on the command line, and every report says where its kernel ran (CORE-43, IC1-18,
  IC2-16). Times per check and per feature (IC1-09, PCBC-15). A long hole table continues on further sheets
  (IC1-17); a misplaced view is named (IC2-17). A wrong bracket is reported at its token (IC1-16).
- `diff`, `release status --diff` and a task's check read flows, systems, requirements and interfaces (LABS-21); a
  release checks its flows (LABS-22); `make.ratePerHourHigh` (LABS-23); `<visit tool minutes>` in a flow step
  (LABS-24); `commandagi task propose | approve | decline` offline (LABS-13); `live-miss` (LABS-14); `"unknown"` for
  HS code, origin, hazmat, ECCN and datasheet (PCBC-16).
- Boards: pours read KiCad's own fill settings (EDA-27, in part); plane vias from the router (EDA-23); `pins
  --install-hook` (EDA-26); RXD0/TXD0 GPIO numbers (EDA-12); `.3d.py` relative imports (PCBC-17).

## 0.6.3 (2026-10-21)

The fixes for the microfab team's report on 0.6.2 (110 issues; the ids in brackets are theirs). The vocabulary below
is the same in the three SDKs, in each language's spelling; `@commandagi/host` 0.6.3 carries the checks.

Changed (a document written for 0.6.2 may need an edit)

- One face query for 3D documents, checks and studies: a study's `type` is `geometry`, `nearest` is `farthest` with
  the direction reversed, `radius` and `area` take `{ min, max }`; `at` names the face that holds a point (CORE-24,
  PCBC-12, IC2-08).
- A finding names a body by the id the document gives it (`<body id>`, else the feature that made it); the rebuild's
  `body_0` is `rebuildId` (CORE-13). A covered finding's `severity` is `suppressed`, its own in `coveredSeverity`
  (PCBC-03).
- `commandagi check` prints a compact report (verdict, each check, findings grouped by rule); `--json` or `--out FILE`
  gives the whole report (IC2-12, PCBC-04).
- A `bodies` entry that names no body is an `unknown-body` error: a check of nothing never passes (LABS-02).
- Copper joins where it is drawn, and a pour joins the pads and vias of its net it covers; `from`/`to` are optional
  (EDA-03, EDA-06). A part on the bottom flips its pads, paste, mask, silk and courtyard as KiCad does (EDA-04). An
  unrouted net on a board with copper is an error (EDA-05).
- An unknown material is a warning of the process check (CORE-11).

Added

- Placed parts carry what their file states: engineering, mass, part number, fasteners; a placed assembly keeps its
  members as `<placement>/<id>`. Check, `threed bom`, `threed observe`, STEP and `diff` agree (CORE-01 to -04, -09,
  -20, -26, -27). Bill lines and logistics findings are one per part number with a quantity (LABS-16, IC1-11).
- A `.3d.tsx` imports sibling `.ts`, `.tsx` and `.json` files; a `.3d.py` reads its folder and imports sibling modules
  (CORE-05, CORE-06). Syntax errors name the author's line and column (IC1-01); every refused element in one run
  (IC1-02).
- `commandagi --version` with no key; `check --only ID`, `--timeout S` and a timeout that says so; `release --dry-run`
  and `.releaseignore`; a release also holds the folder's requirements, systems and interfaces (SETUP-01, IC1-09,
  LABS-19, LABS-20, CORE-28). `commandagi layout | route | fabricate <board>` run on this computer (EDA-17).
- Faces: a hole on a face split in two, a pick by a point on the face, a pick among the bodies a feature consumes, an
  ambiguous pick that names its faces (CORE-08, IC2-02, IC2-03, LABS-05). A counterbore deeper than its size's
  (CORE-10); `m2.5` threads (IC2-04); a clearance pair the kernel cannot measure is its own finding (CORE-19).
- Every ISO 286 class (IT01 to IT18, A to ZC) to 3150 mm, and ISO 2768-1 (IC2-05, CORE-17, IC1-06); a fit between two
  sizes of different nominals (CORE-16); a fit's `pair` covers its press fit's clash (CORE-18); `against` on
  interference and clearance (CORE-25, LABS-03); `<accept other>` for a part modelled inside another, an accept sized
  to its finding (PCBC-09, IC1-10); `<hole spare>` and `<permitted diameter>` (IC1-04).
- The mill check judges each face from the setup that reaches it (`make.setups`, or the fewest sides), drilled holes as
  drilled, a plate turned on the table, the machine's materials (CORE-07, -12, -14, -15, -21, -34). The resin printer
  prints: SLA printability (drain, cups) and slicing (CORE-32); `commandagi slicer slice X.slice.tsx` (CORE-33).
- Drawing sheets: hole callouts from the hole features (depth, blind, FAR SIDE), a hole table from a datum corner, no
  overlapping callouts, the release's REV (CORE-22, -31, -36, PCBC-10).
- Studies: inverted elements straightened, each level's reason on its line, `<solver timeout>`, `--keep finest`, a
  fixture on a region (CORE-37, IC2-10, PCBC-11, IC1-15).
- Budgets of any quantity and unit (flow, area, volume …), a priced `<item ref>` to a design with its lead-time path,
  a diff that names every logistics change, process flows (`.flow.tsx`), cost ranges, µm and nm, `other` processes,
  `<library>` data for fastener pieces, `<fastener material partNumber>`, a `chemicals` check (LABS-06 to -12, IC1-03,
  IC1-05, IC1-12, IC2-11, PCBC-13). HFS5-2060 and HFS5-2080 in the T-slot table (CORE-35).
- Boards: pinless parts (EDA-02), four-layer net-class rules (EDA-07), KiCad parity on no-connect pins, datasheets and
  back-side text (EDA-08 to -10), interface sides that read a sheet, a board or a `.sch.py` (EDA-14), a fabrication
  BOM by part number (EDA-19), `near` as a hard rule of the placer (EDA-20).
- Speed: a 1136-hole plate checks in about 5 s (was 4 min 54 s); a 206-body assembly in 45 s (was 4 min 41 s)
  (LABS-04, IC2-06).

In this SDK

- `netclass(...)` states the rules a four-layer board needs: `min_width` (the narrowest track; `width` is what the
  router lays), `edge_clearance` and `hole_clearance` (the least gaps to the board edge and to a hole),
  `inner={"clearance": …, "width": …, "minWidth": …}` (the rules on inner copper layers) and `min_spokes` (the fewest
  thermal spokes a pad needs to a pour). `commandagi check` holds the board to them and `commandagi export kicad`
  writes them into the project and its `.kicad_dru` (microfab EDA-07).
- Every request (the client, a session's frames and its WebSocket, the 3D kernel's cloud and local calls) sends
  `User-Agent: commandagi-python/<version>`. The platform's CDN refused the kernel's standard-library requests with
  `error code: 1010` (microfab CORE-30).

## 0.6.2 (2026-10-16)

No change in this SDK's code. The release carries `@commandagi/host` 0.6.2, which `commandagi check` and the local 3D
service run:

- A STEP export writes a body's part number: `<body engineering={{ partNumber: "PN-1001" }}>` is the id of the
  body's `PRODUCT` (`PRODUCT('PN-1001','Plate',…)`, as AP242 and AP214 hold it), and the export's `products` list it.
- The `sourcing` check reports `part-number-collision`: two parts under one part number that differ in process,
  material, finish, description, designation, manufacturer or MPN. Before, the cost roll-up merged them silently and
  priced the second as the first. Shape is not compared.

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
