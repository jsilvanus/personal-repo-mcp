from pathlib import Path

from personal_repo_mcp.config import RepositoryConfig, Settings
from personal_repo_mcp.mcp.server import create_mcp
from personal_repo_mcp.repositories import RepositoryManager


def test_phase_one_tools_are_registered() -> None:
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        token="secret",
        repositories=(
            RepositoryConfig(
                id="demo",
                name="Demo",
                remote="https://example.invalid/demo.git",
                workspace=Path("/tmp/demo"),
            ),
        ),
    )
    mcp = create_mcp(settings, RepositoryManager(settings.repositories))
    tools = mcp._tool_manager._tools
    assert "get_repositories" in tools
    assert "get_repository" in tools
    assert "prepare_repository" in tools
