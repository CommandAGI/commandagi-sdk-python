"""CommandAGI Python SDK.

Launch cloud computers and 3D robot simulations and control them programmatically.

    from commandagi import CommandAGI
    cagi = CommandAGI(api_key="cagi_...")
    with cagi.launch("simulation/warehouse") as world:
        obs = world.observe()
        obs = world.step("move", speed=0.8)
"""
from .bridge import RobotBridge
from .client import COMPUTERS, SIMULATIONS, CommandAGI, CommandAGIError, World

__all__ = ["CommandAGI", "World", "RobotBridge", "CommandAGIError", "SIMULATIONS", "COMPUTERS"]
__version__ = "0.2.0"
