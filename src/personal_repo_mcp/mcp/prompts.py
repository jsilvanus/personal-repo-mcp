"""MCP prompts for common Personal Repo MCP workflows."""

from mcp.server import MCPServer


def register_prompts(mcp: MCPServer) -> None:
    """Register user-selectable workflow prompts."""

    @mcp.prompt(title="Personal Repo MCP setup")
    def setup() -> str:
        """Guide an agent through the Personal Repo MCP setup and repository lifecycle."""
        return (
            "You are using Personal Repo MCP. Read mcp://help/index first, then read "
            "mcp://help/repositories for repository authorization, discovery, preparation, "
            "and cloning. The administrator allow-list is outside the MCP agent's control; "
            "use only repositories the server reports as allowed."
        )

    @mcp.prompt(title="Personal Repo MCP development")
    def development() -> str:
        """Guide an agent through normal repository development with Personal Repo MCP."""
        return (
            "You are using Personal Repo MCP as the primary persistent development workspace. "
            "Read mcp://help/index first, then load the focused help resources you need "
            "(repositories, files, git, chain-command, or resources). Inspect repository and "
            "Git state before editing, make the smallest safe changes, review the resulting "
            "diff, and use the Git tools to commit or synchronize when appropriate."
        )
