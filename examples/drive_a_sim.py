"""Launch a simulated world, look at what it accepts, drive it, and read where its arm is.

    export COMMANDAGI_API_KEY=cagi_...
    python examples/drive_a_sim.py
"""
import time

from commandagi import CommandAGI

cagi = CommandAGI()

with cagi.launch("simulation/arm-cell") as world:
    for channel in world.controls():
        print(channel["channelId"], "→", ", ".join(channel["actions"]))

    world.sim.reset()
    world.sim.run()  # a launched simulation starts paused
    world.sim.ik(target=[0.08, -0.12, 0.86])  # the arm's tool point, in metres

    time.sleep(2)  # an answer is not a state: let it move, then read
    arm = world.describe()["world"]["robots"][0]
    print(arm["id"], "tool point (mm):", arm["sites"][0]["world"])
