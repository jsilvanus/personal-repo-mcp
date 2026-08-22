from .runner import GitRunner


def fetch(runner: GitRunner, remote: str = "origin") -> str:
    return runner.run("fetch", remote, "--prune")


def pull(runner: GitRunner, remote: str = "origin", branch: str | None = None, rebase: bool = False) -> str:
    args = ["pull"]
    if rebase:
        args.append("--rebase")
    args.append(remote)
    if branch:
        args.append(branch)
    return runner.run(*args)


def push(runner: GitRunner, remote: str = "origin", branch: str | None = None, force: bool = False, set_upstream: bool = False) -> str:
    if force:
        raise ValueError("Force push is disabled by the Phase 3 core API")
    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.append(remote)
    if branch:
        args.append(branch)
    return runner.run(*args)
