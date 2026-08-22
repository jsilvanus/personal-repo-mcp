from __future__ import annotations

from pathlib import Path


class FileSystemError(ValueError):
    """Raised when a repository path is invalid or unsafe."""


class NestedRepositoryError(FileSystemError):
    """Raised when a write targets a nested Git repository."""


def resolve_repository_path(workspace: Path, relative_path: str) -> Path:
    """Resolve a client path while guaranteeing containment in the workspace."""
    if not relative_path or "\x00" in relative_path:
        raise FileSystemError("Path must be a non-empty string without NUL bytes")

    candidate = (workspace / relative_path).resolve()
    root = workspace.resolve()
    if candidate == root or root not in candidate.parents:
        raise FileSystemError(f"Path escapes repository workspace: {relative_path!r}")
    return candidate


def nested_repository_root(workspace: Path, path: Path) -> Path | None:
    """Return the nearest nested Git repository containing path, if any.

    Both normal .git directories and submodule-style .git files are detected.
    The configured repository root itself is never considered nested.
    """
    root = workspace.resolve()
    candidate = path.resolve()
    if candidate == root or root not in candidate.parents:
        return None

    current = candidate if candidate.is_dir() else candidate.parent
    while current != root:
        marker = current / ".git"
        if marker.is_dir() or marker.is_file():
            return current
        current = current.parent
    return None


def ensure_writable_repository_path(workspace: Path, path: Path) -> Path:
    """Reject paths that resolve inside a nested Git repository."""
    nested = nested_repository_root(workspace, path)
    if nested is not None:
        nested_relative = nested.relative_to(workspace.resolve()).as_posix()
        raise NestedRepositoryError(
            f"Path is inside nested Git repository {nested_relative!r}; "
            "access the nested repository through its own repository context"
        )
    return path


def relative_path(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()
