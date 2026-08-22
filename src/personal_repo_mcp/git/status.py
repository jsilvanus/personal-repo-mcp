from .runner import GitRunner


def status(runner: GitRunner) -> dict[str, object]:
    branch = runner.run("branch", "--show-current").strip()
    porcelain = runner.run("status", "--porcelain=v1", "-z")
    entries = []
    parts = porcelain.split("\0")
    for item in parts:
        if not item:
            continue
        code = item[:2]
        path = item[3:] if len(item) > 3 else ""
        entries.append({"index": code[0], "worktree": code[1], "path": path})
    return {"branch": branch or None, "clean": not entries, "changes": entries}
