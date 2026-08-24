from __future__ import annotations

from mcp.server import MCPServer

from ..metrics import Metrics
from ..repositories import RepositoryManager
from .files import register_file_resources
from .git import register_git_resources
from .help import register_help_resources
from .statistics import register_statistics_resources
from .system import register_system_resources


def register_resources(mcp: MCPServer, repositories: RepositoryManager, metrics: Metrics) -> None:
    """Register persistent repository, system, statistics, and operational help resources."""
    register_help_resources(mcp)
    register_system_resources(mcp, repositories)
    register_statistics_resources(mcp, repositories, metrics)
    register_file_resources(mcp, repositories)
    register_git_resources(mcp, repositories)
