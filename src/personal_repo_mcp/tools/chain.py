from __future__ import annotations

from mcp.server import MCPServer

from ..chain.executor import ChainExecutor
from ..chain.model import ChainCommand, ChainPolicy


def register_chain_tools(mcp: MCPServer) -> None:
    executor = ChainExecutor(mcp)

    @mcp.tool(name="chain_command")
    async def chain_command(
        repository: str,
        commands: list[dict[str, object]],
        on_error: str = "stop",
    ) -> dict[str, object]:
        """Execute multiple supported MCP tools sequentially within one repository.

        Nested commands inherit the repository and must not specify one. The
        command may not invoke itself or change repository/workspace selection.
        """
        parsed = []
        for command in commands:
            if not isinstance(command, dict) or not isinstance(command.get("tool"), str):
                raise ValueError("Each command requires a string 'tool'")
            arguments = command.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("Command arguments must be an object")
            parsed.append(ChainCommand(tool=command["tool"], arguments=arguments))

        results = await executor.execute(repository, parsed, ChainPolicy(on_error=on_error))
        return {"repository": repository, "results": results, "completed": len(results) == len(parsed)}
