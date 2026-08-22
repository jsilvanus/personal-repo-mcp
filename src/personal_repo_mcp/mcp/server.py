from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..config import Settings
from ..repositories import RepositoryError, RepositoryManager


def create_mcp(settings: Settings, repositories: RepositoryManager) -> FastMCP:
    """Create the MCP server and register Phase 1 tools."""
    mcp = FastMCP(
        name="Personal Repo MCP",
        instructions=(
            "A persistent multi-repository Git workspace for AI agents. "
            "Repositories are server-managed workspaces; GitHub is an upstream remote."
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
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
