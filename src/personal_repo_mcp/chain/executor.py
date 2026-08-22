from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from .model import ChainCommand, ChainPolicy


FORBIDDEN_TOOLS = {
    "chain_command",
    "get_repositories",
    "get_repository",
    "prepare_repository",
}


class ChainExecutor:
    def __init__(self, mcp: MCPServer) -> None:
        self.mcp = mcp

    async def execute(self, repository: str, commands: list[ChainCommand], policy: ChainPolicy) -> list[dict[str, Any]]:
        policy.validate()
        if len(commands) > policy.max_commands:
            raise ValueError(f"Too many commands; maximum is {policy.max_commands}")

        results: list[dict[str, Any]] = []
        for index, command in enumerate(commands):
            if command.tool in FORBIDDEN_TOOLS:
                raise ValueError(f"Tool cannot be used inside chain_command: {command.tool}")
            if "repository" in command.arguments:
                raise ValueError(f"Nested command {command.tool} must not specify repository")

            arguments = dict(command.arguments)
            arguments["repository"] = repository
            result = await self.mcp.call_tool(command.tool, arguments)
            entry = {
                "index": index,
                "tool": command.tool,
                "is_error": result.is_error,
                "content": [block.model_dump(mode="json") for block in result.content],
                "structured_content": result.structured_content,
            }
            results.append(entry)
            if result.is_error and policy.on_error == "stop":
                break
        return results
