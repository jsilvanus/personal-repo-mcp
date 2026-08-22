from __future__ import annotations

import re
from pathlib import Path

from .paths import FileSystemError
from .writer import content_hash, _atomic_write
from .paths import relative_path, resolve_repository_path

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_unified_diff(workspace: Path, path: str, patch: str, *, expected_hash: str | None = None) -> dict[str, object]:
    """Apply a standard single-file unified diff with zero fuzz."""
    target = resolve_repository_path(workspace, path)
    try:
        original = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FileSystemError(f"Cannot read patch target: {path}") from exc
    if expected_hash is not None and content_hash(original) != expected_hash:
        raise FileSystemError("File changed since the agent last read it")

    lines = original.splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)
    hunks = []
    i = 0
    while i < len(patch_lines):
        line = patch_lines[i].rstrip("\r\n")
        match = _HUNK.match(line)
        if match:
            old_start = int(match.group(1))
            old_count = int(match.group(2) or 1)
            new_start = int(match.group(3))
            new_count = int(match.group(4) or 1)
            body = []
            i += 1
            while i < len(patch_lines) and not patch_lines[i].startswith("@@ "):
                current = patch_lines[i]
                if current.startswith((" ", "+", "-")):
                    body.append(current)
                elif current.startswith("\\ No newline at end of file"):
                    i += 1
                    continue
                else:
                    raise FileSystemError("Invalid unified diff hunk")
                i += 1
            old_lines = [x[1:] for x in body if x.startswith((" ", "-"))]
            new_lines = [x[1:] for x in body if x.startswith((" ", "+"))]
            if len(old_lines) != old_count or len(new_lines) != new_count:
                raise FileSystemError("Unified diff hunk line counts do not match")
            hunks.append((old_start, old_lines, new_lines))
            continue
        i += 1

    if not hunks:
        raise FileSystemError("Patch contains no unified diff hunks")

    output = []
    cursor = 0
    for old_start, old_lines, new_lines in hunks:
        index = old_start - 1
        if index < cursor or index > len(lines):
            raise FileSystemError("Unified diff hunk is out of order or outside the file")
        if lines[cursor:index] != lines[cursor:index]:
            raise FileSystemError("Invalid unified diff")
        output.extend(lines[cursor:index])
        if lines[index:index + len(old_lines)] != old_lines:
            raise FileSystemError(f"Unified diff context does not match at line {old_start}")
        output.extend(new_lines)
        cursor = index + len(old_lines)
    output.extend(lines[cursor:])
    updated = "".join(output)
    _atomic_write(target, updated)
    return {"path": relative_path(workspace, target), "sha256": content_hash(updated), "hunks": len(hunks)}
