from __future__ import annotations

from pathlib import Path


class RepositoryPathError(ValueError):
    """Raised when a path would escape a repository workspace."""


def ensure_contained(root: Path, candidate: Path) -> Path:
    """Resolve a path and require it to remain below root."""
    root = root.resolve()
    candidate = candidate.resolve()
    if candidate == root or root not in candidate.parents:
        raise RepositoryPathError(f"Path escapes repository workspace: {candidate}")
    return candidate


def workspace_for(root: Path, relative_workspace: str) -> Path:
    """Resolve a configured workspace below the repository root."""
    return ensure_contained(root, root / relative_workspace)
