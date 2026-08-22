from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceChange:
    """A repository resource invalidated by a server-side mutation."""

    uri: str


def file_uri(repository: str, path: str) -> str:
    return f"repo://{repository}/file/{path.lstrip('/')}"


def git_uri(repository: str, name: str) -> str:
    return f"repo://{repository}/git/{name}"


def test_uri(repository: str, run_id: str) -> str:
    return f"repo://{repository}/tests/{run_id}"


def artifact_uri(repository: str, artifact_id: str) -> str:
    return f"repo://{repository}/artifacts/{artifact_id}"
