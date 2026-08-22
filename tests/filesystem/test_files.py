from pathlib import Path

import pytest

from personal_repo_mcp.filesystem import FileSystemError, apply_unified_diff, read_file
from personal_repo_mcp.filesystem.writer import content_hash, insert_lines, replace_lines, write_file


def test_chunked_read_reports_range(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    result = read_file(tmp_path, "a.txt", start_line=2, end_line=3)
    assert result.content == "two\nthree\n"
    assert result.start_line == 2
    assert result.end_line == 3
    assert result.total_lines == 4
    assert result.has_more is True


def test_atomic_write_and_expected_hash(tmp_path: Path) -> None:
    write_file(tmp_path, "a.txt", "hello\n")
    old_hash = content_hash("hello\n")
    write_file(tmp_path, "a.txt", "changed\n", expected_hash=old_hash)
    with pytest.raises(FileSystemError):
        write_file(tmp_path, "a.txt", "bad\n", expected_hash=old_hash)


def test_line_edits(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    replace_lines(tmp_path, "a.txt", 2, 2, "TWO\n")
    insert_lines(tmp_path, "a.txt", 2, "inserted\n")
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "one\ninserted\nTWO\nthree\n"


def test_unified_diff(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    patch = """--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n"""
    result = apply_unified_diff(tmp_path, "a.txt", patch)
    assert result["hunks"] == 1
    assert target.read_text(encoding="utf-8") == "one\nTWO\nthree\n"


def test_unified_diff_rejects_stale_context(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("one\ntwo\n", encoding="utf-8")
    patch = """@@ -1,2 +1,2 @@\n one\n-wrong\n+TWO\n"""
    with pytest.raises(FileSystemError):
        apply_unified_diff(tmp_path, "a.txt", patch)
