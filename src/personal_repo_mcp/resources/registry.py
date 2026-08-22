from __future__ import annotations

from mcp.server import MCPServer

from ..repositories import RepositoryManager
from .files import register_file_resources
from .git import register_git_resources
from .help import register_help_resources
from .system import register_system_resources


def register_resources(mcp: MCPServer, repositories: RepositoryManager) -> None:
    """Register persistent repository, system, and operational help resources."""
    register_help_resources(mcp)
    register_system_resources(mcp, repositories)
    register_file_resources(mcp, repositories)
    register_git_resources(mcp, repositories)
