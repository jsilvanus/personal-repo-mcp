from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import FileSystemError, relative_path, resolve_repository_path


@dataclass(frozen=True, slots=True)
class FileRead:
    path: str
    content: str
    start_line: int
    end_line: int
    total_lines: int
    has_more: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "total_lines": self.total_lines,
            "has_more": self.has_more,
        }


def read_file(
    workspace: Path,
    path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
    max_bytes: int = 2_000_000,
) -> FileRead:
    """Read a UTF-8 text file, optionally selecting a 1-based inclusive line range."""
    target = resolve_repository_path(workspace, path)
    if not target.is_file():
        raise FileSystemError(f"Not a file: {path}")
    if target.stat().st_size > max_bytes and start_line is None and end_line is None:
        raise FileSystemError(
            f"File is larger than the complete-read limit ({max_bytes} bytes); use a line range"
        )

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FileSystemError(f"File is not valid UTF-8 text: {path}") from exc
    except OSError as exc:
        raise FileSystemError(f"Cannot read file: {path}") from exc

    lines = text.splitlines(keepends=True)
    total = len(lines)
    start = 1 if start_line is None else start_line
    finish = total if end_line is None else end_line
    if start < 1 or finish < start:
        raise FileSystemError("Line range must be a positive inclusive range")
    if start > total + 1:
        raise FileSystemError(f"Start line {start} is beyond end of file ({total} lines)")

    selected = lines[start - 1 : finish]
    actual_end = min(finish, total)
    return FileRead(
        path=relative_path(workspace, target),
        content="".join(selected),
        start_line=start,
        end_line=actual_end,
        total_lines=total,
        has_more=finish < total,
    )


def list_directory(workspace: Path, path: str = ".") -> list[dict[str, object]]:
    target = resolve_repository_path(workspace, path) if path != "." else workspace.resolve()
    if not target.is_dir():
        raise FileSystemError(f"Not a directory: {path}")
    entries = []
    for entry in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entries.append(
            {
                "path": relative_path(workspace, entry),
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
            }
        )
    return entries
