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

# The client (and its HTTP and WebSocket dependencies) loads on first use, so `commandagi.design` — which
# declares structure and never touches the network — imports anywhere, Pyodide included.
_CLIENT_NAMES = ("CommandAGI", "CommandAGIError", "Session")
# The 3D kernel's client (observe, export, measure) uses the standard library only; it loads on first use too.
_KERNEL_NAMES = ("Kernel", "KernelError")


def __getattr__(name):
    if name in _CLIENT_NAMES:
        from . import client

        return getattr(client, name)
    if name in _KERNEL_NAMES:
        from . import kernel

        return getattr(kernel, name)
    raise AttributeError(f"module 'commandagi' has no attribute {name!r}")


__all__ = [
    "CommandAGI",
    "CommandAGIError",
    "Session",
    "Kernel",
    "KernelError",
    "DesktopControls",
    "RobotControls",
    "SimControls",
    "SDK_SCHEMA",
    "ENV_API_KEY",
    "ENV_BASE_URL",
    "ENV_THREAD_ID",
    "DEFAULT_BASE_URL",
]
__version__ = "0.6.4"
