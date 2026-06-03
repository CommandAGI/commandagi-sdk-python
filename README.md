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

`launch()` provisions a real GCE VM running a PyBullet world, waits until it's streaming, and gives
you a `World`. Built-in scenes: `simulation/warehouse`, `simulation/house-on-fire`,
`simulation/school` (a mobile robot in each).

### The control vocabulary

| World kind | actions |
|------------|---------|
| robot / sim | `move(speed)`, `back(speed)`, `turn(dir, rate)`, `stop`, `reset` |
| computer | `click(x, y)`, `type(text)`, `key(key)`, `move(x, y)`, `scroll(x, y, dy)` |

```python
world.act("move", speed=0.8)        # fire-and-forget
obs = world.step("move", speed=0.8) # act + return the next observation (settles 0.8s)
obs = world.observe(fresh=True)     # wait for a frame newer than now
arr = world.observe_array()         # HxWx3 uint8 numpy (needs commandagi[vision])
for frame in world.stream():        # live generator of frames
    ...
```

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

Full HTTP + WebSocket reference (what the SDK wraps): [`docs/ROBOT_DEVELOPER_API.md`](../../docs/ROBOT_DEVELOPER_API.md).
