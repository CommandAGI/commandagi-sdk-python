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

## One surface, generated

This SDK, the TypeScript SDK (`npm i commandagi`) and the `commandagi` CLI all come from **one
schema**, `commandagi-sdk.schema.json`, so they can't drift apart:

- **Tools**: `cagi.threads`, `cagi.embodiments`, `cagi.memory`, `cagi.integrations`,
  `cagi.social(platform, account)`, `whoami`, `search`, `run` and `post`. Each one is a typed wrapper
  over `call(tool, args)`. Options are passed as keyword arguments, e.g. `snapshot_id=…`, and sent
  over the wire as camelCase (`snapshotId`).
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
| `commandagi.design.media` | a video, a song |
| `commandagi.design.ontology` | a world, a device definition, a dashboard, a geo project, a node graph |
| `commandagi.design.business` | a company, an RFC, a case |
| `commandagi.design.tasks` | a task, a project |
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
