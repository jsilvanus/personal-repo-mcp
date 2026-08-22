from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .paths import FileSystemError, relative_path, resolve_repository_path


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _check_expected(target: Path, expected_hash: str | None) -> None:
    if expected_hash is None:
        return
    if not target.exists():
        raise FileSystemError("Expected existing file, but file does not exist")
    try:
        current = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FileSystemError("Cannot read existing file for concurrency check") from exc
    if content_hash(current) != expected_hash:
        raise FileSystemError("File changed since the agent last read it")


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise FileSystemError(f"Cannot write file: {target}") from exc


def write_file(
    workspace: Path,
    path: str,
    content: str,
    *,
    expected_hash: str | None = None,
) -> dict[str, object]:
    target = resolve_repository_path(workspace, path)
    _check_expected(target, expected_hash)
    _atomic_write(target, content)
    return {"path": relative_path(workspace, target), "bytes": len(content.encode("utf-8")), "sha256": content_hash(content)}


def _read_existing(target: Path) -> str:
    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileSystemError(f"File does not exist: {target.name}")
    except UnicodeDecodeError as exc:
        raise FileSystemError("File is not valid UTF-8 text") from exc
    except OSError as exc:
        raise FileSystemError("Cannot read existing file") from exc


def _replace_range(text: str, start_line: int, end_line: int, replacement: str) -> str:
    if start_line < 1 or end_line < start_line:
        raise FileSystemError("Line range must be a positive inclusive range")
    lines = text.splitlines(keepends=True)
    if start_line > len(lines) + 1 or end_line > len(lines):
        raise FileSystemError(f"Line range {start_line}-{end_line} is outside file ({len(lines)} lines)")
    return "".join(lines[: start_line - 1]) + replacement + "".join(lines[end_line:])


def replace_lines(workspace: Path, path: str, start_line: int, end_line: int, content: str, *, expected_hash: str | None = None) -> dict[str, object]:
    target = resolve_repository_path(workspace, path)
    current = _read_existing(target)
    if expected_hash is not None and content_hash(current) != expected_hash:
        raise FileSystemError("File changed since the agent last read it")
    updated = _replace_range(current, start_line, end_line, content)
    _atomic_write(target, updated)
    return {"path": relative_path(workspace, target), "sha256": content_hash(updated), "start_line": start_line, "end_line": end_line}


def insert_lines(workspace: Path, path: str, line: int, content: str, *, expected_hash: str | None = None) -> dict[str, object]:
    target = resolve_repository_path(workspace, path)
    current = _read_existing(target)
    if expected_hash is not None and content_hash(current) != expected_hash:
        raise FileSystemError("File changed since the agent last read it")
    lines = current.splitlines(keepends=True)
    if line < 1 or line > len(lines) + 1:
        raise FileSystemError(f"Insertion line {line} is outside file")
    updated = "".join(lines[: line - 1]) + content + "".join(lines[line - 1 :])
    _atomic_write(target, updated)
    return {"path": relative_path(workspace, target), "sha256": content_hash(updated), "line": line}


def delete_lines(workspace: Path, path: str, start_line: int, end_line: int, *, expected_hash: str | None = None) -> dict[str, object]:
    return replace_lines(workspace, path, start_line, end_line, "", expected_hash=expected_hash)
