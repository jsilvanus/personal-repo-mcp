from __future__ import annotations

import os
import time
from pathlib import Path

from mcp.server import MCPServer

from ..metrics import Metrics
from ..repositories import RepositoryManager
from .model import repository_statistics_uri, system_statistics_uri


_cpu_sample: tuple[float, float] | None = None


def _memory_bytes() -> int | None:
    try:
        return int(Path("/proc/self/statm").read_text(encoding="utf-8").split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def _memory_limit() -> int | None:
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


def _cpu_percent() -> float | None:
    global _cpu_sample
    try:
        process = os.times()
        now = time.monotonic()
        cpu_time = process.user + process.system
    except OSError:
        return None
    if _cpu_sample is None:
        _cpu_sample = (now, cpu_time)
        return 0.0
    previous_time, previous_cpu = _cpu_sample
    _cpu_sample = (now, cpu_time)
    elapsed = now - previous_time
    if elapsed <= 0:
        return 0.0
    return round(min(100.0, max(0.0, (cpu_time - previous_cpu) / elapsed * 100.0)), 2)


def _directory_stats(root: Path) -> dict[str, int]:
    total = 0
    files = 0
    try:
        for path in root.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
                    files += 1
            except OSError:
                continue
    except OSError:
        pass
    return {"bytes": total, "files": files}


def _repository_stats(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False, "total_bytes": 0, "files": 0, "git_bytes": 0, "workspace_bytes": 0}
    total = _directory_stats(path)
    git = _directory_stats(path / ".git") if (path / ".git").exists() else {"bytes": 0, "files": 0}
    return {
        "exists": True,
        "total_bytes": total["bytes"],
        "files": total["files"],
        "git_bytes": git["bytes"],
        "workspace_bytes": max(0, total["bytes"] - git["bytes"]),
    }


def register_statistics_resources(mcp: MCPServer, repositories: RepositoryManager, metrics: Metrics) -> None:
    @mcp.resource(
        system_statistics_uri(),
        name="system_statistics",
        title="System statistics",
        description="Current container resources and process-lifetime MCP usage counters.",
        mime_type="application/json",
    )
    def system_statistics() -> dict[str, object]:
        snapshot = metrics.snapshot()
        usage = os.statvfs(repositories.root)
        block_size = usage.f_frsize
        storage = {
            "total_bytes": usage.f_blocks * block_size,
            "available_bytes": usage.f_bavail * block_size,
            "used_bytes": (usage.f_blocks - usage.f_bfree) * block_size,
        }
        return {
            "started_at": snapshot.started_at,
            "resources": {
                "cpu_percent": _cpu_percent(),
                "memory_bytes": _memory_bytes(),
                "memory_limit_bytes": _memory_limit(),
                "storage": storage,
                "cpu_count": os.cpu_count(),
            },
            "mcp": {
                "messages": snapshot.messages,
                "tool_calls": snapshot.tool_calls,
                "tool_successes": snapshot.tool_successes,
                "tool_failures": snapshot.tool_failures,
                "resource_reads": snapshot.resource_reads,
                "notifications": snapshot.notifications,
                "total_duration_ms": snapshot.total_duration_ms,
                "max_duration_ms": snapshot.max_duration_ms,
                "bytes_in": snapshot.bytes_in,
                "bytes_out": snapshot.bytes_out,
                "tools": snapshot.tools,
            },
        }

    @mcp.resource(
        "repo://{repository}/statistics",
        name="repository_statistics",
        title="Repository statistics",
        description="Current storage statistics for a managed repository.",
        mime_type="application/json",
    )
    def repository_statistics(repository: str) -> dict[str, object]:
        repo = repositories.get(repository)
        stats = _repository_stats(repo.workspace)
        return {"repository": repo.id, "path": str(repo.workspace), "storage": stats}
