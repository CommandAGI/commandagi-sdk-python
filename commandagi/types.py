"""Type definitions for the commandAGI API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Profile:
    """A taste profile returned by the API."""

    id: str
    project_id: str
    name: str
    seed: str | None = None
    version: int | None = None
    constraints: list[Any] | None = None
    exemplars: list[Any] | None = None
    comparisons: list[Any] | None = None
    prompt_summary: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class ProfileCreateParams:
    """Parameters for creating a new profile."""

    project_id: str
    name: str
    seed: str | None = None


@dataclass
class ProfileUpdateParams:
    """Parameters for updating a profile."""

    name: str | None = None
    seed: str | None = None
    constraints: list[Any] | None = None
    exemplars: list[Any] | None = None
    comparisons: list[Any] | None = None
    prompt_summary: str | None = None


@dataclass
class EvalParams:
    """Parameters for evaluating content against a profile."""

    frame_url: str
    embedding: list[float] | None = None


@dataclass
class EvalDetails:
    """Detailed scoring information from an evaluation."""

    latent_score: float | None
    constraint_match: int
    exemplar_similarity: float | None


@dataclass
class EvalResult:
    """The result of an evaluation."""

    score: float
    confidence: float
    details: EvalDetails


@dataclass
class ExportMetadata:
    """Metadata from a full profile export."""

    created_at: str | None
    updated_at: str | None
    exported_at: str
    version: str


@dataclass
class ExportFullResult:
    """Full profile export format."""

    id: str
    project_id: str
    name: str
    seed: str | None
    version: int
    constraints: list[Any]
    exemplars: list[Any]
    comparisons: list[Any]
    prompt_summary: str | None
    metadata: ExportMetadata


@dataclass
class ExportMinimalSnapshot:
    """Snapshot counts from a minimal export."""

    prompt_summary: str | None
    exemplar_count: int
    comparison_count: int
    constraint_count: int


@dataclass
class ExportMinimalResult:
    """Minimal profile export format (for inference)."""

    id: str
    name: str
    seed: str | None
    snapshot: ExportMinimalSnapshot
    exported_at: str
