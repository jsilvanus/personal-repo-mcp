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
        current_commit: str | None = None
        for index, command in enumerate(commands):
            if command.tool in FORBIDDEN_TOOLS:
                raise ValueError(f"Tool cannot be used inside chain_command: {command.tool}")
            if "repository" in command.arguments:
                raise ValueError(f"Nested command {command.tool} must not specify repository")

            arguments = dict(command.arguments)
            if current_commit is not None:
                if command.tool == "git_edit" and "expected_ref" not in arguments:
                    arguments["expected_ref"] = current_commit
                elif command.tool == "git_read_file" and "revision" not in arguments:
                    arguments["revision"] = current_commit
            arguments["repository"] = repository

            result = await self.mcp.call_tool(command.tool, arguments)
            structured = result.structured_content
            entry = {
                "index": index,
                "tool": command.tool,
                "is_error": result.is_error,
                "content": [block.model_dump(mode="json") for block in result.content],
                "structured_content": structured,
            }
            results.append(entry)

            if not result.is_error and command.tool == "git_edit" and isinstance(structured, dict):
                commit = structured.get("commit")
                if isinstance(commit, str) and commit:
                    current_commit = commit

            if result.is_error and policy.on_error == "stop":
                break
        return results
