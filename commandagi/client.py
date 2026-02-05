"""commandAGI API client."""

from __future__ import annotations

from typing import Any

import httpx

from commandagi.types import (
    EvalDetails,
    EvalParams,
    EvalResult,
    ExportFullResult,
    ExportMetadata,
    ExportMinimalResult,
    ExportMinimalSnapshot,
    Profile,
    ProfileCreateParams,
    ProfileUpdateParams,
)

DEFAULT_BASE_URL = "https://commandagi.com"


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result: list[str] = []
    for ch in name:
        if ch.isupper():
            result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


class CommandAGIError(Exception):
    """Error from the commandAGI API."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class _Profiles:
    """Namespace for profile operations."""

    def __init__(self, client: CommandAGI):
        self._client = client

    def create(self, params: ProfileCreateParams) -> Profile:
        """Create a new taste profile."""
        body: dict[str, Any] = {"projectId": params.project_id, "name": params.name}
        if params.seed is not None:
            body["seed"] = params.seed
        data = self._client._request("POST", "/api/v1/profiles", json=body)
        return _parse_profile(data)

    def get(self, id: str) -> Profile:
        """Get a profile by ID. Returns full profile with constraints, exemplars, comparisons."""
        data = self._client._request("GET", f"/api/v1/profiles/{id}")
        return _parse_profile(data)

    def update(self, id: str, params: ProfileUpdateParams) -> Profile:
        """Update a profile. Only provided fields are updated."""
        body: dict[str, Any] = {}
        if params.name is not None:
            body["name"] = params.name
        if params.seed is not None:
            body["seed"] = params.seed
        if params.constraints is not None:
            body["constraints"] = params.constraints
        if params.exemplars is not None:
            body["exemplars"] = params.exemplars
        if params.comparisons is not None:
            body["comparisons"] = params.comparisons
        if params.prompt_summary is not None:
            body["promptSummary"] = params.prompt_summary
        data = self._client._request("PATCH", f"/api/v1/profiles/{id}", json=body)
        return _parse_profile(data)

    def delete(self, id: str) -> None:
        """Delete a profile."""
        self._client._request("DELETE", f"/api/v1/profiles/{id}")

    def list(self, project_id: str | None = None) -> list[Profile]:
        """List all profiles. Optionally filter by project_id."""
        path = "/api/v1/profiles"
        if project_id:
            path += f"?projectId={project_id}"
        data = self._client._request("GET", path)
        return [_parse_profile(p) for p in data["profiles"]]

    def eval(self, id: str, params: EvalParams) -> EvalResult:
        """Evaluate content against a profile."""
        body: dict[str, Any] = {"frameUrl": params.frame_url}
        if params.embedding is not None:
            body["embedding"] = params.embedding
        data = self._client._request("POST", f"/api/v1/profiles/{id}/eval", json=body)
        return EvalResult(
            score=data["score"],
            confidence=data["confidence"],
            details=EvalDetails(
                latent_score=data["details"].get("latentScore"),
                constraint_match=data["details"]["constraintMatch"],
                exemplar_similarity=data["details"].get("exemplarSimilarity"),
            ),
        )

    def export(self, id: str) -> ExportFullResult:
        """Export a profile in full JSON format."""
        data = self._client._request(
            "GET", f"/api/v1/profiles/{id}/export?format=json"
        )
        meta = data["metadata"]
        return ExportFullResult(
            id=data["id"],
            project_id=data["projectId"],
            name=data["name"],
            seed=data.get("seed"),
            version=data["version"],
            constraints=data["constraints"],
            exemplars=data["exemplars"],
            comparisons=data["comparisons"],
            prompt_summary=data.get("promptSummary"),
            metadata=ExportMetadata(
                created_at=meta.get("createdAt"),
                updated_at=meta.get("updatedAt"),
                exported_at=meta["exportedAt"],
                version=meta["version"],
            ),
        )

    def export_minimal(self, id: str) -> ExportMinimalResult:
        """Export a profile in minimal format (for inference)."""
        data = self._client._request(
            "GET", f"/api/v1/profiles/{id}/export?format=minimal"
        )
        snap = data["snapshot"]
        return ExportMinimalResult(
            id=data["id"],
            name=data["name"],
            seed=data.get("seed"),
            snapshot=ExportMinimalSnapshot(
                prompt_summary=snap.get("promptSummary"),
                exemplar_count=snap["exemplarCount"],
                comparison_count=snap["comparisonCount"],
                constraint_count=snap["constraintCount"],
            ),
            exported_at=data["exportedAt"],
        )


class CommandAGI:
    """commandAGI API client.

    Usage::

        from commandagi import CommandAGI

        client = CommandAGI(api_key="cagi_xxx...")

        profile = client.profiles.create(ProfileCreateParams(
            project_id="your-project-id",
            name="my-taste-profile",
        ))
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "commandagi-python/0.1.0",
            },
            timeout=timeout,
        )
        self.profiles = _Profiles(self)

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> CommandAGI:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        response = self._http.request(method, path, json=json)
        if response.status_code >= 400:
            try:
                data = response.json()
                message = data.get("message") or data.get("error") or f"API error: {response.status_code}"
            except Exception:
                message = f"API error: {response.status_code}"
            raise CommandAGIError(message, status=response.status_code)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


def _parse_profile(data: dict[str, Any]) -> Profile:
    """Parse a profile dict from the API into a Profile dataclass."""
    return Profile(
        id=data["id"],
        project_id=data["projectId"],
        name=data["name"],
        seed=data.get("seed"),
        version=data.get("version"),
        constraints=data.get("constraints"),
        exemplars=data.get("exemplars"),
        comparisons=data.get("comparisons"),
        prompt_summary=data.get("promptSummary"),
        created_at=data.get("createdAt"),
        updated_at=data.get("updatedAt"),
    )
