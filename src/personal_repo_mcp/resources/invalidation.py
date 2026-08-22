from __future__ import annotations

from mcp.server import Context

from .model import file_uri, git_uri


async def notify_file_changed(ctx: Context, repository: str, path: str) -> None:
    """Publish the standard resource-updated event for a repository file."""
    await ctx.notify_resource_updated(file_uri(repository, path))
    await ctx.notify_resource_updated(git_uri(repository, "status"))
    await ctx.notify_resource_updated(git_uri(repository, "diff"))


async def notify_git_changed(ctx: Context, repository: str, *, conflicts: bool = False) -> None:
    """Publish Git state invalidations after a successful Git mutation."""
    await ctx.notify_resource_updated(git_uri(repository, "status"))
    await ctx.notify_resource_updated(git_uri(repository, "diff"))
    if conflicts:
        await ctx.notify_resource_updated(git_uri(repository, "conflicts"))
