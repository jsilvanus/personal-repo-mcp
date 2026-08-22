from .runner import GitRunner


def list_branches(runner: GitRunner) -> list[dict[str, object]]:
    text = runner.run("branch", "--format=%(refname:short)\t%(HEAD)\t%(objectname)\t%(upstream:short)")
    result = []
    for line in text.splitlines():
        name, head, sha, upstream = (line.split("\t", 3) + [""] * 4)[:4]
        result.append({"name": name, "current": head == "*", "sha": sha, "upstream": upstream or None})
    return result


def create_branch(runner: GitRunner, name: str, start_point: str | None = None) -> dict[str, object]:
    args = ["switch", "-c", name]
    if start_point:
        args.append(start_point)
    runner.run(*args)
    return {"branch": name}


def delete_branch(runner: GitRunner, name: str, force: bool = False) -> dict[str, object]:
    runner.run("branch", "-D" if force else "-d", name)
    return {"deleted": name}


def switch(runner: GitRunner, name: str) -> dict[str, object]:
    runner.run("switch", name)
    return {"branch": name}
