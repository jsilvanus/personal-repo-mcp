from __future__ import annotations

from pathlib import Path

from .runner import GitRunner


def conflicted_files(runner: GitRunner) -> list[str]:
    text = runner.run("diff", "--name-only", "--diff-filter=U")
    return [line for line in text.splitlines() if line]


def _stage(runner: GitRunner, path: str, stage: int) -> str | None:
    result = runner.run("show", f":{stage}:{path}", check=False)
    return result if result else None


def conflict_file(runner: GitRunner, path: str) -> dict[str, object]:
    if path not in conflicted_files(runner):
        raise ValueError(f"File is not conflicted: {path}")
    worktree = (runner.workspace / path).read_text(encoding="utf-8", errors="replace")
    regions: list[dict[str, object]] = []
    lines = worktree.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<<"):
            i += 1
            continue
        start = i + 1
        ours: list[str] = []
        theirs: list[str] = []
        section = ours
        i += 1
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            if lines[i].startswith("======="):
                section = theirs
            else:
                section.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError(f"Malformed conflict markers in {path}")
        regions.append({"start_line": start, "end_line": i + 1, "ours": "".join(ours), "theirs": "".join(theirs)})
        i += 1
    return {
        "path": path,
        "ours": _stage(runner, path, 2),
        "base": _stage(runner, path, 1),
        "theirs": _stage(runner, path, 3),
        "regions": regions,
    }


def resolve_conflict(runner: GitRunner, path: str, content: str) -> dict[str, object]:
    target = runner.workspace / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    runner.run("add", "--", path)
    return {"path": path, "resolved": path not in conflicted_files(runner)}
