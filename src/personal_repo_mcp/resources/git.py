from __future__ import annotations

from mcp.server import MCPServer

from ..git.conflicts import conflicted_files, conflict_file
from ..git.diff import diff
from ..git.runner import GitError, GitRunner
from ..git.status import status
from ..repositories import RepositoryError, RepositoryManager


def _runner(repositories: RepositoryManager, repository: str) -> GitRunner:
    try:
        return GitRunner(repositories.get(repository).workspace)
    except (RepositoryError, GitError) as exc:
        raise ValueError(str(exc)) from exc


def register_git_resources(mcp: MCPServer, repositories: RepositoryManager) -> None:
    """Register read-only repository Git state resources."""

    @mcp.resource(
        "repo://{repository}/git/status",
        name="git_status_resource",
        title="Git status",
        description="Current branch and working-tree/index status for a repository.",
        mime_type="application/json",
    )
    def git_status_resource(repository: str) -> dict[str, object]:
        return status(_runner(repositories, repository))

    @mcp.resource(
        "repo://{repository}/git/diff",
        name="git_diff_resource",
        title="Git diff",
        description="Current unstaged working-tree diff for a repository.",
        mime_type="text/x-diff",
    )
    def git_diff_resource(repository: str) -> str:
        return diff(_runner(repositories, repository))

    @mcp.resource(
        "repo://{repository}/git/conflicts",
        name="git_conflicts_resource",
        title="Git conflicts",
        description="Current structured merge/rebase conflict information.",
        mime_type="application/json",
    )
    def git_conflicts_resource(repository: str) -> dict[str, object]:
        runner = _runner(repositories, repository)
        files = conflicted_files(runner)
        details = []
        for path in files:
            try:
                details.append(conflict_file(runner, path))
            except (OSError, ValueError):
                details.append({"path": path})
        return {"conflicted": bool(files), "files": details}
