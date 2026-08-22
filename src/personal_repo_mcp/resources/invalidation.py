from __future__ import annotations

from mcp.server.mcpserver import Context

from .model import file_uri, git_uri, system_storage_uri


async def notify_file_changed(ctx: Context, repository: str, path: str) -> None:
    """Publish resource updates for a file and the Git state it affects."""
    await ctx.notify_resource_updated(file_uri(repository, path))
    await ctx.notify_resource_updated(git_uri(repository, "status"))
    await ctx.notify_resource_updated(git_uri(repository, "diff"))
    await ctx.notify_resource_updated(system_storage_uri())


async def notify_git_changed(ctx: Context, repository: str, *, conflicts: bool = False) -> None:
    """Publish Git state invalidations after a successful Git mutation."""
    await ctx.notify_resource_updated(git_uri(repository, "status"))
    await ctx.notify_resource_updated(git_uri(repository, "diff"))
    if conflicts:
        await ctx.notify_resource_updated(git_uri(repository, "conflicts"))
    await ctx.notify_resource_updated(system_storage_uri())


async def notify_repository_set_changed(ctx: Context) -> None:
    """Publish the aggregate repository-list change signal."""
    from .model import system_repositories_uri

    await ctx.notify_resource_updated(system_repositories_uri())
    await ctx.notify_resource_updated(system_storage_uri())
