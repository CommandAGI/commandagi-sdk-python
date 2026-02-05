"""Official Python SDK for commandAGI — Command the AGI with taste."""

from commandagi.client import CommandAGI
from commandagi.types import (
    Profile,
    ProfileCreateParams,
    ProfileUpdateParams,
    EvalParams,
    EvalResult,
    ExportFullResult,
    ExportMinimalResult,
)

__all__ = [
    "CommandAGI",
    "Profile",
    "ProfileCreateParams",
    "ProfileUpdateParams",
    "EvalParams",
    "EvalResult",
    "ExportFullResult",
    "ExportMinimalResult",
]

__version__ = "0.1.0"
