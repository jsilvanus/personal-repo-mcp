from pathlib import Path

import pytest

from personal_repo_mcp.repositories.manager import RepositoryError, RepositoryManager


def test_pattern_allows_matching_repository(tmp_path: Path):
    manager = RepositoryManager(tmp_path, (), ("jsilvanus/*",))
    assert manager.is_allowed("jsilvanus/example")
    assert not manager.is_allowed("other/example")


def test_clone_rejects_repository_outside_allow_list(tmp_path: Path):
    manager = RepositoryManager(tmp_path, (), ("jsilvanus/*",))
    with pytest.raises(RepositoryError, match="not allowed"):
        manager.clone("other/example")


def test_clone_rejects_invalid_repository_id(tmp_path: Path):
    manager = RepositoryManager(tmp_path, (), ("jsilvanus/*",))
    with pytest.raises(RepositoryError, match="OWNER/REPOSITORY"):
        manager.clone("../example")
