# commandagi — the CommandAGI Python SDK

Drive the whole CommandAGI platform as code: agent threads, memory and integrations, and live
**embodiments** (cloud computers, robots, simulated worlds) that you watch and control.

```bash
pip install commandagi
export COMMANDAGI_API_KEY=cagi_...     # Settings → API keys
```

```python
from commandagi import CommandAGI

cagi = CommandAGI()                                   # reads COMMANDAGI_API_KEY

# Agents: start one on a goal and follow along.
t = cagi.threads.create(intent="Summarise this week's robotics news in five bullets")
cagi.threads.send(t["threadId"], "Add a link for each one.")

# Embodiments: launch a world YOU drive (no agent in it), watch it, control it.
with cagi.launch("simulation/warehouse") as world:
    print(world.controls())                           # what it accepts right now, with payload schemas
    world.sim.ik(target=[0.3, 0.0, 0.4])              # typed robot/sim control
    jpeg = world.observe(fresh=True)                  # the next frame, after the move
# leaving the block stops the world and releases the machine

# Anything else: every platform tool by name.
cagi.call("list_snapshots")
```

A call waits 120 s for its answer. `CommandAGI(timeout=600)` sets it for every call (None: no limit), and
`cagi.call("pcb_autoroute", {...}, timeout=900)` for one call. A call with no answer in time raises
`CommandAGIError`; the platform may still finish the operation.

A Python document can go where only TSX is read: `commandagi.design.to_tsx(result)` writes its root element as the
TypeScript SDK's code file, which declares the same document.

## One surface, generated

This SDK, the TypeScript SDK (`npm i commandagi`) and the `commandagi` CLI all come from **one
schema**, `commandagi-sdk.schema.json`, so they can't drift apart:

- **Tools**: `cagi.threads`, `cagi.embodiments`, `cagi.memory`, `cagi.integrations`,
  `cagi.social(platform, account)`, `whoami`, `search`, `run` and `post`. Each one is a typed wrapper
  over `call(tool, args)`. Options are passed as keyword arguments, e.g. `snapshot_id=…`, and sent
  over the wire as camelCase (`snapshotId`). Where the schema names the options, they are typed
  keyword-only arguments: `cagi.postal.send("Letters/Ada.letter.tsx", provider="click2mail")` (the
  provider is `"lob"`, the default, or `"click2mail"`, US only; omitted, the account's
  `postal.providers` order picks it).
- **Control vocabularies** on a live `Session`:
  - `session.desktop` for computers: `click`, `double_click`, `move`, `scroll`, `type`, `key`, `wait`
  - `session.robot` for physical robots: `joint`, `gripper`, `move`, `turn`, `home`, `stop`, …
  - `session.sim` for simulated worlds: `reset`, `sim_mode`, `ctrl`, `actuator`, `ik`,
    `trajectory`, `grab`, `force`, `add_robot`, …

  Every method sends one action to that embodiment. The platform checks it against the controls the
  embodiment is currently declaring, which `session.controls()` lists along with their payload
  schemas. For anything a runtime declares that no vocabulary covers, use `session.act(action,
  payload)`.

The generated part is `commandagi/_generated.py`. Don't edit it: it is regenerated from the schema in
the CommandAGI monorepo.

## Sessions

| | |
| --- | --- |
| `cagi.launch(snapshot_id, title=, wait=True, timeout=600)` | a new agentless thread running that snapshot; waits until it declares controls |
| `cagi.session(thread_id, embodiment_id)` | attach to an embodiment that already exists |
| `session.frame(fresh=False)` / `observe()` / `observe_array()` / `frames()` | the latest frame, as `{url, channel_id, at}`, image bytes, or a numpy array (`pip install "commandagi[vision]"`); `frames()` yields each new one |
| `session.describe()` | the live world a sim or robot runtime reports |
| `session.close()` / `stop()` | stop watching / also stop a world this session launched |

Snapshot ids come from `cagi.call("list_snapshots")`, e.g. `simulation/warehouse` or
`computer/software-engineer`.

## Design in code: `commandagi.design`

The same structure-declaring primitives as the TypeScript SDK's `commandagi/design`, producing the same op graph
(plain JSON). `commandagi.design` itself holds the code-part primitives: CAD (`part`, `box`, `cylinder`, `sketch`,
`extrude`, `subtract`, `hole`, `linear_pattern` and the rest), EDA (`circuit`, `board`, `component`, `net`, `connect`,
`footprints`), any graph (`graph`, `node`, `input_`, `code`) and `run_module`. There is no kernel, solver, router or
renderer; importing `commandagi.design` needs nothing but the standard library.

### Documents: one module per vocabulary

Every document a TypeScript file writes in JSX, a Python file writes as calls, element for element. One module per
vocabulary, one function per tag, named by the tag:

| module | documents |
| --- | --- |
| `commandagi.design.schematic` | a schematic (`group`) |
| `commandagi.design.pcb` | a board in code (`board`) |
| `commandagi.design.threed` | a 3D part or assembly |
| `commandagi.design.fab` | a machining setup (`cam`), a slicing setup (`slicing`) |
| `commandagi.design.office` | a workbook, a page, a deck |
| `commandagi.design.twod` | a drawing, a painting, a photo, a nest |
| `commandagi.design.media` | a video (clips, `composition(src="Intro.vid.py")`: another video drawn live from its own code, `artboard(src="Poster.draw.py")`: a drawing's page drawn live), a song |
| `commandagi.design.ontology` | a world, a device definition, a dashboard, a geo project, a node graph |
| `commandagi.design.business` | a company, an RFC, a case |
| `commandagi.design.tasks` | a task, a project |
| `commandagi.design.monitors` | a monitor (`monitor.py`, in the folder of the thing it follows) |
| `commandagi.design.records` | a contract, a product instance |
| `commandagi.design.postal` | a letter, a postcard |
| `commandagi.design.pdf` | a PDF assembled from pages, comments, stamps, signatures, redactions, fields and bookmarks |

The rules of a call, the same in every module:

- `tag(*children, **attributes)`. The function's name is the tag: `-` becomes `_` (`brush_stroke`), a Python keyword
  gets a trailing `_` (`from_`), the case is kept (`Company`).
- Children are positional, in order. A tag that holds text takes texts and inline elements:
  `p("The run ", b("passed"), ".")`. A loop is a starred argument: `layer(*[rect(x=i * 10) for i in range(3)])`.
  A leaf takes no children.
- Attributes are keywords in snake_case of the TypeScript name: `frozen_rows=1` is `frozenRows`, `sch_x=114.3` is
  `schX`. A keyword with an uppercase letter is refused by name.
- Only the schematic has positional attributes: `resistor("R1", …)`, `group("Divider", …)`, `trace(from, to)`,
  `netlabel(net, connection)`, `unit(part, unit)`.
- The file's result is `result = <root>(…)` (or `main()`, or `show_object`).

```python
from commandagi.design.twod import drawing, ellipse, group, layer, rect

result = drawing(
    layer(
        rect(x=40, y=40, w=200, h=120, fill="#3b82f6"),
        group(ellipse(cx=500, cy=300, rx=60, ry=60, fill="#f59e0b"), name="Badge"),
        name="Layer 1",
    ),
    name="Poster", width=800, height=600, background="#ffffff",
)
```

```python
from commandagi.design.schematic import ground, group, netlabel, resistor, trace, voltagesource

result = group(
    "Divider",
    voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3),
    resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9, sch_rotation=90),
    ground("#PWR1", sch_x=139.7, sch_y=114.3),
    trace(".V1 > .pos", ".R1 > .pin1"),
    netlabel("OUT", ".R1 > .pin2"),
)
```

A graph document (a schematic, a board, a 3D part, a drawing, a deck, a video, a node graph) leaves `run_module` as
its graph. Any other document (a workbook, a world, a company, a task …) leaves as `document` (`{format, document,
sources}`) beside an empty graph.

### Where each element is written

`run_module` maps the file's calls with Python's `ast` (`commandagi.design.source`). Each element records the call
that made it. A declaration puts that call where the TypeScript SDK puts a JSX element's source: a node's
`meta.source`, a node's `meta.sources` by key, a document's `sources` by key. Each one holds the call's span, each
keyword's span with its literal value or its expression, and how many times the call ran. The whole map rides on the
graph as `meta.sourceMap`: every call with its arguments, its parent element, its slot among its parent's children,
and whether it runs in a loop. The editor writes each edit back into the file as the smallest text edit. A keyword
that is an expression is never replaced with a literal: the edit is refused with its line.

### Code parts and CadQuery

`commandagi.design.cadquery` is a CadQuery-style importer: `Workplane("XY").box(…).faces(">Z").workplane()
.rarray(…).hole(…)` records the same features the primitives declare. It refuses, by name, what needs real topology
(fillets, edge selectors).

A `.py` code part is a script. Its result is `main(**inputs)` if it defines `main`; otherwise what it passed to
`show_object`; otherwise its `result` variable. `param(name, default, unit=…)` declares an input and reads its value.
In a CommandAGI editor, a `.py` code node runs under Pyodide in a sandboxed worker, where `import cadquery as cq` is
this importer (OCCT does not run there). `run_module(source, path, inputs)` is what the sandbox calls. Tests:
`python -m unittest discover -s tests`.

## The 3D kernel: `commandagi.kernel`

`commandagi.design.threed` declares a part and builds nothing. `Kernel` asks the CommandAGI 3D design service
(OpenCascade) to build it. It uses the standard library only.

```python
from commandagi.design.threed import box, cylinder, part
from commandagi.kernel import Kernel

plate = part(
    box(id="plate", center=[0, 0, 4], size=[60, 40, 8], operation="new"),
    cylinder(id="hole", center=[0, 0, -1], axis=[0, 0, 1], radius=3, height=10, operation="cut"),
    name="Plate",
)
kernel = Kernel()                                  # reads COMMANDAGI_THREED
seen = kernel.observe(plate)["observation"]        # bodies, faces, edges, mass properties; status and failures
assert seen["status"] == "built", seen["failures"] # "failed": the bodies are built from the features that did not fail
open("plate.step", "w").write(kernel.export(plate, "step"))   # refused (KernelError.failures) when a feature failed
```

A part is built in the order of its elements: the cut above follows the plate because it is written after it.
`consumes=[…]` names the features a feature follows instead.

One setting says where it runs: `COMMANDAGI_THREED`, the places to try in order, apart by `,` (default `local,cloud`).
A place where the kernel is not installed is passed over. A refusal of the op itself (a build that is not whole) is
the answer: it is not asked of the next place. `kernel.last_ran` says where each answer ran (`{"kernel", "build",
"place"}`); `place` is where the SDK sent the request, so a result made on this computer says `local` and is never a
cloud result.

| place | the kernel | needs |
| --- | --- | --- |
| `local` | this computer, offline, no account. `Kernel` starts it and stops it when Python exits; `COMMANDAGI_THREED_URL` names one that runs already (`commandagi threed serve --port 8091`) | Node 22 and, once: `npm install -g @commandagi/host` then `commandagi threed install` (it downloads OpenCascade as WebAssembly, about 130 MB); for a running one, `COMMANDAGI_THREED_TOKEN`, the bearer you started it with |
| `cloud` | the platform's kernel door (`/kernels/3d/v1/<op>`) | the network and `COMMANDAGI_API_KEY` |

A URL in `COMMANDAGI_THREED` is that running service only. Both places speak one contract (`POST <kernel>/v1/<op>`,
`GET <kernel>/v1/health`), and `kernel.call(op, doc, params)` gives a whole answer (`outputs`, `result`, `ran`).

`observe(doc)`, `export(doc, "step" | "iges", bodies=)`, `measure(doc, "distance" | "angle" | "radius" | "closest", a,
b)`, `measure_all(doc, [{"quantity", "a", "b"}, …])` (many on one build), `interference(doc, clearance=, bodies=)`,
`drawing(doc, direction=, up=, section=)`, `tessellate(doc, deflection)`. `doc` is what a file declares, its
graph (`run_module(...)["graph"]`) or the graph's JSON text. An entity is `{"body": "body_0", "kind": "face" | "edge" |
"vertex" | "body", "index": n}`, with the index as `observe` lists it.

- **A build in which a feature failed is not whole.** `observe` answers it with `status: "failed"` and `failures`.
  Every other call refuses it: `KernelError` with `status` 422 and `failures` (each failed feature, with why).
- **`interference`** compares every pair of bodies: `clashes` (shared volume), `engagements` (shared volume that all
  lies in a declared `thread`: a screw in a tapped hole) and, with `clearance`, `close` (nearer than it). Each body
  has its part's name.
- **An assembly's files** go with the call: `parts=linked_parts({"bolt.3d.py": bolt, "bracket.step": text})`, each
  under the name its `externalPart` gives.
- **A STEP file names its parts**: each body is a product of its part's name, an assembly the product they are
  components of.

## Reinforcement learning

`commandagi.gym_env.CommandAGIEnv` wraps a sim session as a Gymnasium env (`pip install
"commandagi[gym]"`), and `commandagi.lerobot` records rollouts as LeRobot datasets (`pip install
"commandagi[lerobot]"`).

## Environment

| variable | meaning |
| --- | --- |
| `COMMANDAGI_API_KEY` | your `cagi_…` key. Its scopes decide what every call may do |
| `COMMANDAGI_BASE_URL` | API origin (default `https://api.commandagi.com`) |
| `COMMANDAGI_THREAD_ID` | default thread for self-thread methods. Set automatically when your code runs inside the platform |
| `COMMANDAGI_THREED` | where `Kernel` runs: `local`, `cloud`, both apart by `,` in the order to try (default `local,cloud`), or a running service's URL |
| `COMMANDAGI_THREED_URL`, `COMMANDAGI_THREED_TOKEN` | a 3D design service that runs already, and its bearer |

## Versions

- A release is the tag `v<version>` in this repository and the same version on PyPI. Pin an exact version:
  `commandagi==0.5.1`. A range (`^`, `~=`, `>=`) takes the next release without asking you.
- The three SDKs (Python, TypeScript, Rust) carry one version number. A vocabulary at version X in one language is
  the vocabulary at version X in the others.
- A version promises nothing about the next one. CommandAGI keeps no compatibility layers: a release may rename or
  remove a function, an element or an attribute, with no alias and no migration. `CHANGELOG.md` says what changed.
- So a document belongs with the version that reads it. Keep the pin in the project that holds the documents, and
  change both together. A document you open in a CommandAGI editor is read by the SDK that editor ships.

## Licence

MIT (`LICENSE`).
