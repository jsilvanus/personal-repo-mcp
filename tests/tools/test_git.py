from pathlib import Path

from personal_repo_mcp.config import RepositoryConfig, Settings
from personal_repo_mcp.mcp.server import create_mcp
from personal_repo_mcp.repositories import RepositoryManager


def test_git_tools_are_registered(tmp_path: Path):
    config = RepositoryConfig(id="repo", name="Repo", remote="https://example.invalid/repo.git", workspace=tmp_path / "repo")
    manager = RepositoryManager(tmp_path, (config,))
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        token="test",
        github_pat="secret",
        git_backend="git",
        allowed_hosts=("127.0.0.1:*",),
        allowed_origins=("http://127.0.0.1:*",),
        repository_root=tmp_path,
        repositories=(config,),
        repository_patterns=(),
    )
    server = create_mcp(settings, manager)
    assert server is not None
