from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ..config import Settings
from ..repositories import RepositoryError, RepositoryManager


def create_mcp(settings: Settings, repositories: RepositoryManager) -> MCPServer:
    """Create the MCP server and register Phase 1 tools."""
    mcp = MCPServer(
        name="Personal Repo MCP",
        instructions=(
            "A persistent multi-repository Git workspace for AI agents. "
            "Repositories are server-managed workspaces; GitHub is an upstream remote."
        ),
    )

    @mcp.tool()
    def get_repositories() -> list[dict[str, object]]:
        """List repositories managed by this Personal Repo MCP server."""
        return [repository.summary() for repository in repositories.list()]

    @mcp.tool()
    def get_repository(repository: str) -> dict[str, object]:
        """Get metadata for one managed repository by its stable id."""
        try:
            return repositories.get(repository).summary()
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    def prepare_repository(repository: str) -> dict[str, object]:
        """Ensure a configured repository has a persistent local Git workspace."""
        try:
            return repositories.prepare(repository).summary()
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    return mcp


def transport_security(settings: Settings) -> TransportSecuritySettings:
    """Build MCP DNS-rebinding protection for the configured deployment host."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(settings.allowed_hosts),
        allowed_origins=list(settings.allowed_origins),
    )
