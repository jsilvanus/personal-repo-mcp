from pathlib import Path

import pytest

from personal_repo_mcp.config import RepositoryConfig, Settings
from personal_repo_mcp.mcp.server import create_mcp
from personal_repo_mcp.repositories import RepositoryManager


@pytest.mark.asyncio
async def test_phase_two_tools_are_registered(tmp_path: Path) -> None:
    settings = Settings(
        host="127.0.0.1",
        port=8000,
        token="secret",
        allowed_hosts=("127.0.0.1:*",),
        allowed_origins=("http://127.0.0.1:*",),
        repository_root=tmp_path,
        repositories=(
            RepositoryConfig("demo", "Demo", "https://example.invalid/demo.git", tmp_path / "demo"),
        ),
    )
    mcp = create_mcp(settings, RepositoryManager(settings.repositories))
    names = {tool.name for tool in await mcp.list_tools()}
    assert {
        "read_file_tool",
        "list_directory",
        "search_text",
        "find_files",
        "write_file",
        "replace_lines",
        "insert_lines",
        "delete_lines",
        "apply_patch",
    } <= names
