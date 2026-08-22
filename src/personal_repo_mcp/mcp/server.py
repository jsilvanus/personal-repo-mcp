from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.context import Context
from mcp.server.transport_security import TransportSecuritySettings

from ..config import Settings
from ..repositories import RepositoryError, RepositoryManager
from ..resources import register_resources
from ..resources.invalidation import notify_repository_set_changed
from ..security.secrets import make_secret_scrubber
from .chain import register_chain_tools
from .files import register_file_tools
from .git import register_git_tools
from .prompts import register_prompts
from .workspace import register_workspace_tools


def create_mcp(settings: Settings, repositories: RepositoryManager) -> MCPServer:
    """Create the MCP server and register the available tools, resources, and prompts."""
    mcp = MCPServer(
        name="Personal Repo MCP",
        instructions=(
            "A persistent multi-repository Git workspace for AI agents. "
            "Repositories are server-managed workspaces; GitHub is an upstream remote. "
            "The administrator allow-list controls which repositories may be cloned. "
            "Read mcp://help/index for operational guidance when first using this MCP."
        ),
        middleware=[
            make_secret_scrubber((settings.token, settings.github_pat)),
        ],
    )

    @mcp.tool()
    def get_repositories() -> list[dict[str, object]]:
        """List repositories currently available as local managed workspaces."""
        return [repository.summary() for repository in repositories.list()]

    @mcp.tool()
    def get_repository(repository: str) -> dict[str, object]:
        """Get metadata for one managed repository by its stable id."""
        try:
            return repositories.get(repository).summary()
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    async def clone_repository(repository: str, ctx: Context) -> dict[str, object]:
        """Clone an allowed GitHub OWNER/REPOSITORY into persistent storage without changing the administrator allow-list."""
        try:
            result = repositories.clone(repository).summary()
            await notify_repository_set_changed(ctx)
            return result
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    def prepare_repository(repository: str) -> dict[str, object]:
        """Ensure a configured repository has a persistent local Git workspace."""
        try:
            return repositories.prepare(repository).summary()
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    def mcp_help() -> str:
        """Give the two-sentence starting point for using Personal Repo MCP; read mcp://help/index for details."""
        return (
            "Personal Repo MCP is a persistent, multi-repository Git workspace for AI agents, "
            "with filesystem and Git operations exposed through MCP. Read mcp://help/index "
            "and its focused help resources before using unfamiliar repository, file, Git, "
            "chaining, or resource workflows."
        )

    register_file_tools(mcp, repositories)
    register_git_tools(mcp, repositories)
    register_workspace_tools(mcp, repositories)
    register_chain_tools(mcp)
    register_prompts(mcp)
    register_resources(mcp, repositories)
    return mcp


def transport_security(settings: Settings) -> TransportSecuritySettings:
    """Build MCP DNS-rebinding protection for the configured deployment host."""
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(settings.allowed_hosts),
        allowed_origins=list(settings.allowed_origins),
    )
