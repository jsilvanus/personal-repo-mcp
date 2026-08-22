from .runner import GitRunner


def commit(runner: GitRunner, message: str, paths: list[str] | None = None) -> dict[str, str]:
    if not message.strip():
        raise ValueError("Commit message must not be empty")
    if paths:
        runner.run("add", "--", *paths)
    sha = runner.run("commit", "-m", message).strip()
    return {"output": sha}
