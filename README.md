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
