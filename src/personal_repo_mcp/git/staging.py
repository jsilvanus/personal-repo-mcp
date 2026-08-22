from .runner import GitRunner


def add(runner: GitRunner, paths: list[str]) -> dict[str, object]:
    if not paths:
        raise ValueError("At least one path is required")
    runner.run("add", "--", *paths)
    return {"staged": paths}


def unstage(runner: GitRunner, paths: list[str]) -> dict[str, object]:
    if not paths:
        raise ValueError("At least one path is required")
    runner.run("restore", "--staged", "--", *paths)
    return {"unstaged": paths}
