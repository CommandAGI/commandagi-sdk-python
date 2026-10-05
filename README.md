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

The same structure-declaring primitives as the TypeScript SDK's `commandagi/design`, producing the same op
graph (plain JSON). They cover CAD (`part`, `box`, `cylinder`, `sketch`, `extrude`, `subtract`, `hole`,
`linear_pattern` and the rest), EDA (`circuit`, `board`, `component`, `net`, `connect`, `footprints`) and
any graph (`graph`, `node`, `input_`, `code`). There is no kernel, solver, router or renderer; importing
`commandagi.design` needs nothing but the standard library.

`commandagi.design.twod` declares 2D documents the way the TypeScript SDK's JSX does: `twod.drawing(twod.layer(
twod.rect(x=…, …), name="Layer 1"), name="Poster", width=800, height=600)`, and `twod.painting`, `twod.photo` and
`twod.nest` alike. A call is one node, its keywords the node's inputs (`from_` for a Python word), its positional
arguments the nodes it takes. Tests: `python -m unittest tests.test_twod`.

Office documents are declared as calls with the same shapes as the TypeScript SDK's office JSX: `workbook(sheet(…,
cell("A1", "Item", bold=True), cell("B2", formula="=B1*12")))`, `page(h1("Notes"), p("Text with ", b("bold"), "."))`
and `deck(slide(shape("ellipse", x=160, y=160, w=400, h=400), layout="Blank"))`. A workbook and a page leave
`run_module` as its `document` (the sheets and docs editors' own JSON); a deck is the deck's op graph.

`commandagi.design.cadquery` is a CadQuery-style importer: `Workplane("XY").box(…).faces(">Z").workplane()
.rarray(…).hole(…)` records the same features the primitives declare. It refuses, by name, what needs real
topology (fillets, edge selectors).

`commandagi.design.threed` declares a whole 3D document element by element, as the TypeScript SDK's JSX
does in a `.3d.tsx`: `h(tag, *children, **fields)` makes an element, and a `part` (or `assembly`) element
with `parameter`, `plane`, one element per feature named by its type (`sketch` with its `point`, `line`,
`circle` and `constraint` children, `extrude`, `fillet`, `hole` …), `body` and `slot` declares the `.3dx`
body itself, node for node. Tests: `python -m unittest tests.test_threed`.

A `.py` code part is a script. Its result is `main(**inputs)` if it defines `main`; otherwise what it passed
to `show_object`; otherwise its `result` variable. `param(name, default, unit=…)` declares an input and
reads its value. In a CommandAGI editor, a `.py` code node runs under Pyodide in a sandboxed worker, where
`import cadquery as cq` is this importer (OCCT does not run there). `run_module(source, path, inputs)` is
what the sandbox calls. Tests: `python -m unittest tests.test_design tests.test_schematic tests.test_office`.

`commandagi.design.schematic` is a schematic in Python (a `<name>.sch.py` the CommandAGI circuit editor opens and
edits), the same nodes as the TypeScript SDK's JSX schematic:

```python
from commandagi.design.schematic import ground, group, resistor, trace, voltagesource

with group("Divider"):
    voltagesource("V1", voltage="9", sch_x=114.3, sch_y=114.3)
    resistor("R1", resistance="3k", sch_x=114.3, sch_y=88.9, sch_rotation=90)
    ground("#PWR1", sch_x=139.7, sch_y=114.3)
    trace(".V1 > .pos", ".R1 > .pin1")
```

The `with group(...)` block is the file's result. `run_module` maps the file's calls with Python's `ast`
(`commandagi.design.source`): each node a call declares carries `meta.source` (the call's span, each keyword's span
and literal value or expression, how many times it ran), so the editor writes each edit back into the file as the
smallest text edit. A keyword that is an expression is never replaced with a literal (the edit is refused with its
line).

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
