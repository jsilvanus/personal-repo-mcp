from __future__ import annotations

from pathlib import Path


class FileSystemError(ValueError):
    """Raised when a repository path is invalid or unsafe."""


def resolve_repository_path(workspace: Path, relative_path: str) -> Path:
    """Resolve a client path while guaranteeing containment in the workspace."""
    if not relative_path or "\x00" in relative_path:
        raise FileSystemError("Path must be a non-empty string without NUL bytes")

    candidate = (workspace / relative_path).resolve()
    root = workspace.resolve()
    if candidate == root or root not in candidate.parents:
        raise FileSystemError(f"Path escapes repository workspace: {relative_path!r}")
    return candidate


def relative_path(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()
