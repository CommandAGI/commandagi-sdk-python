# CommandAGI Python SDK

Launch real cloud **computers** and **3D robot simulations** and control them from Python — stream
the robot's camera, send actions, run episodes. No agent required: you drive.

```bash
pip install commandagi          # + `pip install commandagi[vision]` for numpy frames
```

## Robot testing in a 3D world

```python
from commandagi import CommandAGI

cagi = CommandAGI(api_key="cagi_...")          # or set COMMANDAGI_API_KEY

with cagi.launch("simulation/warehouse") as world:
    obs = world.observe()                      # JPEG bytes from the robot's head camera
    for _ in range(20):
        obs = world.step("turn", dir="left")   # act, then get the next frame
    world.reset()                              # robot back to the episode start
# leaving the block stops the world and releases the cloud VM
```

`launch()` provisions a real GCE VM running a 3D physics world, waits until it's streaming, and gives
you a `World`. Built-in scenes: `simulation/warehouse`, `simulation/house-on-fire`,
`simulation/school` (a mobile robot in each).

### The control vocabulary

| World kind  | actions                                                                   |
| ----------- | ------------------------------------------------------------------------- |
| robot / sim | `move(speed)`, `back(speed)`, `turn(dir, rate)`, `stop`, `reset`          |
| computer    | `click(x, y)`, `type(text)`, `key(key)`, `move(x, y)`, `scroll(x, y, dy)` |

```python
world.act("move", speed=0.8)        # fire-and-forget
obs = world.step("move", speed=0.8) # act + return the next observation (settles 0.8s)
obs = world.observe(fresh=True)     # wait for a frame newer than now
arr = world.observe_array()         # HxWx3 uint8 numpy (needs commandagi[vision])
for frame in world.stream():        # live generator of frames
    ...
```

## Simulator instances (morphology-agnostic robots)

The simulator is **morphology-agnostic**: a robot is just a set of named actuators and sites, driven
by one small **generic** control vocabulary — no `drive`/`gripper`, just `ctrl` / `actuator` / `ik`
/ `trajectory` / `describe`. Spin up your own instance, choose who can watch or add robots, and
populate it with one or many robots on a single session.

```python
from commandagi import CommandAGI

cagi = CommandAGI(api_key="cagi_...")

sim = cagi.launch_sim(scene="the-matrix", visibility="private", title="demo")
print("instance:", sim.id, "session:", sim.session_id)

# Who can do what:
sim.grant("user_teammate", capability="viewer")    # may watch the stream
sim.grant("user_buddy",    capability="operator")  # may also launch robots into the world

# Add robots (each becomes a embodiment on sim.session_id):
rover = sim.join_robot(kind="rover")   # -> {robotId, embodimentId, sessionId}
arm   = sim.join_robot(kind="arm")

cagi.sims()             # list instances visible to you
cagi.get_sim(sim.id)    # rehydrate a SimInstance
sim.view()              # instance metadata + attached embodiments
sim.stop()              # release it (or use `with cagi.launch_sim(...) as sim:`)
```

### Generic robot control

`World` exposes the morphology-agnostic vocabulary (address a specific robot in a multi-robot embodiment
with `robot_id`):

```python
world = cagi.connect_world(sim.session_id, rover["embodimentId"], kind="robot")

desc = world.describe()                                   # actuators, sites, objects (best-effort)
world.ctrl({"left_wheel": 1.0, "right_wheel": 1.0})       # set actuator targets directly
world.actuator("left_wheel", 0.0)                          # one named actuator
world.ik(target=[0.3, 0.0, 0.4], site="ee", relative=False)  # inverse kinematics to a point
world.trajectory([{"left_wheel": 1.0}, {"left_wheel": 0.0}])  # follow waypoints
frame = world.observe()                                    # camera frame, as before
```

> `describe()` is best-effort: the runtime answers a describe request over the session channel, but
> there is currently no synchronous describe HTTP endpoint — if nothing echoes back it returns `{}`,
> and the autonomous agent also obtains descriptions server-side via `/agent/robot-act`.

## Autonomous agents over many robots

One agent can drive **many** robots in a single session. `RobotAgent` loops perceive → reason → act:
each step it gathers every embodiment's description + a fresh camera frame, calls `/agent/robot-act` with
all embodiments, and applies the returned tool calls (`ctrl`/`actuator`/`ik`/`trajectory`) back to the
addressed embodiment — until a `done` call or `max_steps`.

```python
from commandagi import CommandAGI
from commandagi.agent import RobotAgent, attach_robots

cagi = CommandAGI(api_key="cagi_...")
sim = cagi.launch_sim(scene="warehouse")

embodiments = attach_robots(cagi, sim, kinds=["rover", "arm"])   # two robots, one session

with RobotAgent(cagi, sim.session_id, embodiments, goal="bring the red box to the arm") as agent:
    result = agent.run(max_steps=25)        # blocks; prints reasoning + applied calls each step
print("done:", result["done"], "in", result["steps"], "steps")

sim.stop()
```

A full runnable script lives in [`examples/sim_agent.py`](examples/sim_agent.py).

## Computers too

```python
with cagi.launch("computer/software-engineer") as pc:
    pc.act("type", text="hello")
    pc.act("key", key="Return")
    screenshot = pc.observe()       # PNG bytes of the live Ubuntu desktop
```

## Auth

Create an API key with an `operator` scope (dashboard → API keys, or `POST /me/api-keys`). Pass it to
`CommandAGI(api_key=...)` or set `COMMANDAGI_API_KEY`. Point at another environment with
`COMMANDAGI_BASE_URL` (e.g. `https://api-dev.commandagi.com`).

Full HTTP + WebSocket reference (what the SDK wraps): [`docs/platform/ROBOT_DEVELOPER_API.md`](../../docs/platform/ROBOT_DEVELOPER_API.md).
