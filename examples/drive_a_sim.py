"""Launch a simulated world, look at what it accepts, drive it, and save what it sees.

    export COMMANDAGI_API_KEY=cagi_...
    python examples/drive_a_sim.py
"""
from commandagi import CommandAGI

cagi = CommandAGI()

with cagi.launch("simulation/warehouse") as world:
    for channel in world.controls():
        print(channel["channelId"], "→", ", ".join(channel["actions"]))

    world.sim.reset()
    world.sim.ik(target=[0.3, 0.0, 0.4])

    with open("after-ik.jpg", "wb") as f:
        f.write(world.observe(fresh=True))
    print("saved after-ik.jpg")
