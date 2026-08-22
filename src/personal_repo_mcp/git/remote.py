from .runner import GitRunner


def remotes(runner: GitRunner) -> list[dict[str, str]]:
    text = runner.run("remote", "-v")
    result = []
    seen: set[tuple[str, str, str]] = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        item = (parts[0], parts[1], parts[2].strip("()"))
        if item not in seen:
            seen.add(item)
            result.append({"name": item[0], "url": item[1], "direction": item[2]})
    return result
