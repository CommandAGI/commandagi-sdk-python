"""End-to-end example: launch a simulator, share it, add robots, run an autonomous agent.

    COMMANDAGI_API_KEY=cagi_... python examples/sim_agent.py

This drives the real API (the /sims and /agent/robot-act routes), so it provisions and bills a
hosted simulator. It always stops the instance on exit.
"""
from commandagi import CommandAGI
from commandagi.agent import RobotAgent, attach_robots


def main() -> None:
    cagi = CommandAGI()  # reads COMMANDAGI_API_KEY

    # 1. Launch a private simulator instance for a scene.
    sim = cagi.launch_sim(scene="the-matrix", visibility="private", title="demo")
    print("launched sim:", sim.id, "session:", sim.session_id)
    try:
        # 2. Decide who can see it / launch robots into it.
        sim.grant("user_teammate", capability="viewer")    # may watch
        sim.grant("user_buddy", capability="operator")     # may also add robots

        # 3. Add several robots to the one session (one agent will drive them all).
        devices = attach_robots(cagi, sim, kinds=["rover", "arm"])
        print("robots:", devices)

        # 4. Run an autonomous agent over every robot toward a goal.
        with RobotAgent(cagi, sim.session_id, devices, goal="bring the red box to the arm") as agent:
            result = agent.run(max_steps=25)
        print("finished:", result["done"], "in", result["steps"], "steps")

        # 5. Or drive a single robot by hand with the generic vocabulary:
        world = cagi.connect_world(sim.session_id, devices[0]["deviceId"], kind="robot")
        print("world description:", world.describe())
        world.ctrl({"left_wheel": 1.0, "right_wheel": 1.0})       # raw actuator targets
        world.actuator("left_wheel", 0.0)                          # one actuator
        world.ik(target=[0.3, 0.0, 0.4], site="ee", relative=False)  # end-effector IK
        world.trajectory([{"left_wheel": 1.0}, {"left_wheel": 0.0}])  # waypoints
    finally:
        sim.stop()


if __name__ == "__main__":
    main()
