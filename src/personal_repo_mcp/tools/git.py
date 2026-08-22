from __future__ import annotations

from mcp.server import MCPServer

from hotgit import Change

from ..git import (
    GitError, GitRunner, abort_merge, abort_rebase, add, blame, changed_files, commit,
    conflict_file, conflicted_files, continue_merge, continue_rebase, create_branch,
    delete_branch, diff, fetch, list_branches, log, merge, pull, push, rebase, remotes,
    resolve_conflict, show, state, status, switch, unstage,
)
from ..git.backend import BackendError
from ..repositories import RepositoryError, RepositoryManager


def register_git_tools(mcp: MCPServer, repositories: RepositoryManager) -> None:
    def runner(repository: str) -> GitRunner:
        try:
            repo = repositories.get(repository)
            if not repo.initialized:
                raise ValueError(f"Repository is not prepared: {repository}")
            return GitRunner(repo.workspace)
        except (RepositoryError, GitError) as exc:
            raise ValueError(str(exc)) from exc

    def guarded_revision(value: str) -> str:
        if not value or value.startswith("-") or "\x00" in value:
            raise ValueError("Invalid Git revision")
        return value

    @mcp.tool(name="git_read_file")
    def git_read_file(repository: str, path: str, revision: str = "refs/heads/main") -> dict[str, object]:
        """Read a file from a repository revision through the configured repository backend."""
        if not path or path.startswith("/") or "\x00" in path:
            raise ValueError("Invalid repository path")
        try:
            data = repositories.backend(repository).read_file(guarded_revision(revision), path)
            return {"path": path, "revision": revision, "content": data.decode("utf-8", errors="replace"), "bytes": len(data)}
        except (BackendError, RepositoryError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_edit")
    def git_edit(
        repository: str,
        changes: list[dict[str, object]],
        message: str,
        ref: str = "refs/heads/main",
        expected_ref: str | None = None,
    ) -> dict[str, object]:
        """Apply a multi-file treeless edit through the configured repository backend."""
        if not changes:
            raise ValueError("changes must not be empty")
        normalized: list[Change] = []
        for item in changes:
            path = str(item.get("path", ""))
            if not path or path.startswith("/") or "\x00" in path:
                raise ValueError(f"Invalid repository path: {path!r}")
            if bool(item.get("delete", False)):
                normalized.append(Change(path, None, str(item.get("mode", "100644"))))
            else:
                content = item.get("content", "")
                if not isinstance(content, str):
                    raise ValueError("change content must be text")
                normalized.append(Change(path, content.encode("utf-8"), str(item.get("mode", "100644"))))
        try:
            result = repositories.backend(repository).edit(
                guarded_revision(ref), normalized, message, expected_ref=expected_ref,
            )
            return {
                "ref": result.ref,
                "base": result.base,
                "commit": result.commit,
                "tree": result.tree,
                "changed_paths": list(result.changed_paths),
            }
        except (BackendError, RepositoryError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_status")
    def git_status(repository: str) -> dict[str, object]:
        try: return status(runner(repository))
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_diff")
    def git_diff(repository: str, staged: bool = False, base: str | None = None, target: str | None = None) -> dict[str, object]:
        try:
            if (base is None) != (target is None): raise ValueError("base and target must be provided together")
            if base: base, target = guarded_revision(base), guarded_revision(target or "")
            return {"diff": diff(runner(repository), staged=staged, base=base, target=target)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_changed_files")
    def git_changed_files(repository: str, staged: bool = False) -> list[str]:
        try: return changed_files(runner(repository), staged=staged)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_log")
    def git_log(repository: str, limit: int = 20) -> list[dict[str, str]]:
        try: return log(runner(repository), limit=limit)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_show")
    def git_show(repository: str, revision: str) -> dict[str, str]:
        try: return {"output": show(runner(repository), guarded_revision(revision))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_blame")
    def git_blame(repository: str, path: str) -> dict[str, str]:
        try: return {"output": blame(runner(repository), path)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_branch_list")
    def git_branch_list(repository: str) -> list[dict[str, object]]:
        try: return list_branches(runner(repository))
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_branch_create")
    def git_branch_create(repository: str, name: str, start_point: str | None = None) -> dict[str, object]:
        try: return create_branch(runner(repository), name, guarded_revision(start_point) if start_point else None)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_branch_delete")
    def git_branch_delete(repository: str, name: str, force: bool = False) -> dict[str, object]:
        if force: raise ValueError("Force branch deletion is disabled by the Phase 3 core API")
        try: return delete_branch(runner(repository), name, force=False)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_switch")
    def git_switch(repository: str, name: str) -> dict[str, object]:
        try: return switch(runner(repository), name)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_add")
    def git_add(repository: str, paths: list[str]) -> dict[str, object]:
        try: return add(runner(repository), paths)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_unstage")
    def git_unstage(repository: str, paths: list[str]) -> dict[str, object]:
        try: return unstage(runner(repository), paths)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_commit")
    def git_commit(repository: str, message: str, paths: list[str] | None = None) -> dict[str, str]:
        try: return commit(runner(repository), message, paths)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_remote_list")
    def git_remote_list(repository: str) -> list[dict[str, str]]:
        try: return remotes(runner(repository))
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_fetch")
    def git_fetch(repository: str, remote: str = "origin") -> dict[str, str]:
        try: return {"output": fetch(runner(repository), remote)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_pull")
    def git_pull(repository: str, remote: str = "origin", branch: str | None = None, rebase: bool = False) -> dict[str, str]:
        try: return {"output": pull(runner(repository), remote, branch, rebase)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_push")
    def git_push(repository: str, remote: str = "origin", branch: str | None = None, force: bool = False, set_upstream: bool = False) -> dict[str, str]:
        try: return {"output": push(runner(repository), remote, branch, force, set_upstream)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_merge")
    def git_merge(repository: str, revision: str, no_edit: bool = False) -> dict[str, str]:
        try: return {"output": merge(runner(repository), guarded_revision(revision), no_edit)}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_rebase")
    def git_rebase(repository: str, revision: str) -> dict[str, str]:
        try: return {"output": rebase(runner(repository), guarded_revision(revision))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_merge_state")
    def git_merge_state(repository: str) -> dict[str, object]:
        try: return state(runner(repository))
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_conflicts")
    def git_conflicts(repository: str) -> list[str]:
        try: return conflicted_files(runner(repository))
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_conflict_file")
    def git_conflict_file(repository: str, path: str) -> dict[str, object]:
        try: return conflict_file(runner(repository), path)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_resolve_conflict")
    def git_resolve_conflict(repository: str, path: str, content: str) -> dict[str, object]:
        try: return resolve_conflict(runner(repository), path, content)
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_abort_merge")
    def git_abort_merge(repository: str) -> dict[str, str]:
        try: return {"output": abort_merge(runner(repository))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_continue_merge")
    def git_continue_merge(repository: str) -> dict[str, str]:
        try: return {"output": continue_merge(runner(repository))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_abort_rebase")
    def git_abort_rebase(repository: str) -> dict[str, str]:
        try: return {"output": abort_rebase(runner(repository))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc

    @mcp.tool(name="git_continue_rebase")
    def git_continue_rebase(repository: str) -> dict[str, str]:
        try: return {"output": continue_rebase(runner(repository))}
        except (GitError, ValueError) as exc: raise ValueError(str(exc)) from exc
