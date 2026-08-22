from __future__ import annotations

import os
import shutil
from pathlib import Path

from mcp.server.mcpserver import Context
from mcp.server import MCPServer

from ..repositories import RepositoryManager
from .model import system_info_uri, system_repositories_uri, system_storage_uri


def _memory_limit() -> int | None:
    """Return the effective cgroup memory limit when one is configured."""
    for path in (Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value and value != "max":
            try:
                return int(value)
            except ValueError:
                continue
    return None


def _repositories(repositories: RepositoryManager) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    concrete = {repo.id: repo for repo in repositories.list()}
    for repo in repositories.list():
        result.append({
            "id": repo.id,
            "name": repo.name,
            "remote": repo.remote,
            "status": "cloned" if repo.initialized else "allowed",
            "path": str(repo.workspace),
        })
    for pattern in repositories.allowed_patterns():
        result.append({
            "id": pattern,
            "pattern": pattern,
            "status": "allowed",
            "cloned": False,
        })
    return sorted(result, key=lambda item: str(item["id"]))


def register_system_resources(mcp: MCPServer, repositories: RepositoryManager) -> None:
    @mcp.resource(
        system_info_uri(),
        name="system_info",
        title="System information",
        description="Stable MCP server and effective container capability information.",
        mime_type="application/json",
    )
    def system_info(ctx: Context) -> dict[str, object]:
        return {
            "version": "1.0.0",
            "transport": "streamable-http",
            "cpu_count": os.cpu_count(),
            "memory_limit_bytes": _memory_limit(),
            "repository_root": str(repositories.root),
        }

    @mcp.resource(
        system_storage_uri(),
        name="system_storage",
        title="System storage",
        description="Current storage usage for the persistent repository workspace.",
        mime_type="application/json",
    )
    def system_storage(ctx: Context) -> dict[str, object]:
        usage = shutil.disk_usage(repositories.root)
        return {
            "path": str(repositories.root),
            "total_bytes": usage.total,
            "used_bytes": usage.total - usage.free,
            "available_bytes": usage.free,
        }

    @mcp.resource(
        system_repositories_uri(),
        name="system_repositories",
        title="Repositories",
        description="Allowed repository selectors and currently cloned repository workspaces.",
        mime_type="application/json",
    )
    def system_repositories(ctx: Context) -> dict[str, object]:
        return {"repositories": _repositories(repositories)}
