"""MCP prompts for common Personal Repo MCP workflows."""

from mcp.server import MCPServer

from ..resources.help import HELP


def _help_index_message() -> dict[str, object]:
    """Return the canonical help index as an MCP embedded resource message."""
    return {
        "role": "user",
        "content": {
            "type": "resource",
            "resource": {
                "uri": "mcp://help/index",
                "mimeType": "text/markdown",
                "text": HELP["index"],
            },
        },
    }


def register_prompts(mcp: MCPServer) -> None:
    """Register user-selectable workflow prompts."""

    @mcp.prompt(title="Personal Repo MCP setup")
    def setup() -> list[dict[str, object]]:
        """Guide an agent through the Personal Repo MCP setup and repository lifecycle."""
        return [
            _help_index_message(),
            {
                "role": "user",
                "content": (
                    "Use the embedded help index as the starting point. For setup and repository "
                    "lifecycle work, read mcp://help/repositories next. The administrator allow-list "
                    "is outside the MCP agent's control; use only repositories the server reports as allowed."
                ),
            },
        ]

    @mcp.prompt(title="Personal Repo MCP development")
    def development() -> list[dict[str, object]]:
        """Guide an agent through normal repository development with Personal Repo MCP."""
        return [
            _help_index_message(),
            {
                "role": "user",
                "content": (
                    "Use the embedded help index as the starting point, then load the focused help resources "
                    "you need: mcp://help/repositories, mcp://help/files, mcp://help/git, "
                    "mcp://help/chain-command, or mcp://help/resources. Inspect repository and Git state before "
                    "editing, make the smallest safe changes, review the resulting diff, and use the Git tools "
                    "to commit or synchronize when appropriate."
                ),
            },
        ]
