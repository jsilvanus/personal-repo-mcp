from .runner import GitRunner


def log(runner: GitRunner, limit: int = 20) -> list[dict[str, str]]:
    limit = max(1, min(limit, 200))
    text = runner.run("log", f"-{limit}", "--date=iso-strict", "--format=%H%x1f%P%x1f%an%x1f%aI%x1f%s")
    result = []
    for line in text.splitlines():
        sha, parents, author, date, subject = line.split("\x1f", 4)
        result.append({"sha": sha, "parents": parents, "author": author, "date": date, "subject": subject})
    return result


def show(runner: GitRunner, revision: str) -> str:
    return runner.run("show", "--no-ext-diff", "--format=fuller", revision, "--")


def blame(runner: GitRunner, path: str) -> str:
    return runner.run("blame", "--", path)
