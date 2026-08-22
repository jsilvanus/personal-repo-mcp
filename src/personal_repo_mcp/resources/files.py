from __future__ import annotations

import hashlib
from pathlib import Path

from mcp.server import Context, MCPServer

from ..repositories import RepositoryError, RepositoryManager
from ..repositories.paths import RepositoryPathError, ensure_contained


def _path(workspace: Path, path: str) -> Path:
    try:
        candidate = ensure_contained(workspace, workspace / path)
    except RepositoryPathError as exc:
        raise ValueError(str(exc)) from exc
    if candidate == workspace or candidate.name == ".git" or ".git" in candidate.relative_to(workspace).parts:
        raise ValueError(".git is not exposed as a repository file resource")
    return candidate


def register_file_resources(mcp: MCPServer, repositories: RepositoryManager) -> None:
    """Register the persistent file resource template."""

    @mcp.resource(
        "repo://{repository}/file/{+path}",
        name="repository_file",
        title="Repository file",
        description="A persistent file in a managed repository workspace, including untracked files.",
        mime_type="application/json",
    )
    def repository_file(repository: str, path: str, ctx: Context) -> dict[str, object]:
        try:
            repo = repositories.get(repository)
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc
        target = _path(repo.workspace, path)
        if not target.is_file():
            raise ValueError(f"Repository file does not exist: {path}")
        data = target.read_bytes()
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Repository file is too large for a resource read; use file tools with chunking")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Binary files are not exposed as text file resources yet")
        return {
            "uri": f"repo://{repository}/file/{path.lstrip('/')}",
            "path": path,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content": text,
        }
