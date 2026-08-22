from pathlib import Path

import pytest

from personal_repo_mcp.config import RepositoryConfig, Settings
from personal_repo_mcp.mcp.server import create_mcp
from personal_repo_mcp.repositories import RepositoryManager


@pytest.mark.asyncio
async def test_phase_one_tools_are_registered() -> None:
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        token="secret",
        allowed_hosts=("127.0.0.1:*",),
        allowed_origins=("http://127.0.0.1:*",),
        repository_root=Path("/tmp"),
        repositories=(
            RepositoryConfig(
                id="demo",
                name="Demo",
                remote="https://example.invalid/demo.git",
                workspace=Path("/tmp/demo"),
            ),
        ),
    )
    mcp = create_mcp(settings, RepositoryManager(settings.repository_root, settings.repositories))
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {"get_repositories", "get_repository", "prepare_repository"} <= names
