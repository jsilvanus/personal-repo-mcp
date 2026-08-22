from pathlib import Path

import pytest

from personal_repo_mcp.repositories.paths import RepositoryPathError, ensure_contained


def test_ensure_contained_accepts_child(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    child = root / "src" / "main.py"
    assert ensure_contained(root, child) == child.resolve()


def test_ensure_contained_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    with pytest.raises(RepositoryPathError):
        ensure_contained(root, root / ".." / "outside")


def test_ensure_contained_rejects_workspace_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    with pytest.raises(RepositoryPathError):
        ensure_contained(root, root)
