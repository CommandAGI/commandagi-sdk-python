"""CommandAGI — the Python SDK.

Drive the whole platform as code: agent threads, memory, integrations — and live embodiments
(computers, robots, simulated worlds) you watch and control.

    from commandagi import CommandAGI

    cagi = CommandAGI()                                   # reads COMMANDAGI_API_KEY
    cagi.threads.create(intent="Summarise this week's robotics news")

    with cagi.launch("simulation/warehouse") as world:    # a world YOU drive (no agent)
        world.sim.ik(target=[0.3, 0.0, 0.4])
        jpeg = world.observe(fresh=True)

The typed surface is generated from the CommandAGI SDK schema (``commandagi-sdk.schema.json``),
identically for every language; ``call(tool, args)`` reaches any tool.
"""
from ._generated import (
    DEFAULT_BASE_URL,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_THREAD_ID,
    SDK_SCHEMA,
    DesktopControls,
    RobotControls,
    SimControls,
)
from .client import CommandAGI, CommandAGIError, Session

__all__ = [
    "CommandAGI",
    "CommandAGIError",
    "Session",
    "DesktopControls",
    "RobotControls",
    "SimControls",
    "SDK_SCHEMA",
    "ENV_API_KEY",
    "ENV_BASE_URL",
    "ENV_THREAD_ID",
    "DEFAULT_BASE_URL",
]
__version__ = "0.4.0"
