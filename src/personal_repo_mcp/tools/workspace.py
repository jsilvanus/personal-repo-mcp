from __future__ import annotations

from mcp.server import MCPServer

from ..git import GitError, GitRunner, status
from ..repositories import RepositoryError, RepositoryManager


def register_workspace_tools(mcp: MCPServer, repositories: RepositoryManager) -> None:
    @mcp.tool(name="get_workspace_state")
    def get_workspace_state(repository: str) -> dict[str, object]:
        """Return the current persistent workspace and Git state for a repository."""
        try:
            repo = repositories.get(repository)
            result: dict[str, object] = repo.summary()
            if repo.initialized:
                result["git"] = status(GitRunner(repo.workspace))
            else:
                result["git"] = None
            return result
        except (RepositoryError, GitError) as exc:
            raise ValueError(str(exc)) from exc
