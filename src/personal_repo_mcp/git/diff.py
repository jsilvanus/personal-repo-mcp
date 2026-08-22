from .runner import GitRunner


def diff(runner: GitRunner, staged: bool = False, base: str | None = None, target: str | None = None) -> str:
    if base is not None and target is not None:
        return runner.run("diff", base, target, "--")
    return runner.run("diff", "--cached" if staged else "--")


def changed_files(runner: GitRunner, staged: bool = False) -> list[str]:
    if staged:
        args = ["diff", "--cached", "--name-only"]
    else:
        args = ["diff", "--name-only"]
    return [line for line in runner.run(*args).splitlines() if line]
