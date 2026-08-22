from __future__ import annotations

import fnmatch
from pathlib import Path

from .paths import FileSystemError, relative_path, resolve_repository_path


def search_text(workspace: Path, query: str, path: str = ".", *, max_results: int = 200, case_sensitive: bool = True) -> list[dict[str, object]]:
    if not query:
        raise FileSystemError("Search query must not be empty")
    if max_results < 1:
        raise FileSystemError("max_results must be positive")
    root = workspace.resolve() if path == "." else resolve_repository_path(workspace, path)
    if not root.exists():
        raise FileSystemError(f"Path does not exist: {path}")
    needle = query if case_sensitive else query.lower()
    results: list[dict[str, object]] = []
    files = [root] if root.is_file() else (p for p in root.rglob("*") if p.is_file())
    for file in files:
        if ".git" in file.relative_to(workspace).parts:
            continue
        try:
            if file.stat().st_size > 2_000_000:
                continue
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            haystack = line if case_sensitive else line.lower()
            if needle in haystack:
                results.append({"path": relative_path(workspace, file), "line": number, "text": line})
                if len(results) >= max_results:
                    return results
    return results


def find_files(workspace: Path, pattern: str, path: str = ".", *, max_results: int = 500) -> list[str]:
    if not pattern:
        raise FileSystemError("File pattern must not be empty")
    root = workspace.resolve() if path == "." else resolve_repository_path(workspace, path)
    if not root.exists():
        raise FileSystemError(f"Path does not exist: {path}")
    candidates = [root] if root.is_file() else (p for p in root.rglob("*"))
    result = []
    for candidate in candidates:
        if ".git" in candidate.relative_to(workspace).parts:
            continue
        if fnmatch.fnmatch(candidate.name, pattern):
            result.append(relative_path(workspace, candidate))
            if len(result) >= max_results:
                break
    return result
