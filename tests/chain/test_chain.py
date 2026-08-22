import pytest

from personal_repo_mcp.chain.executor import ChainExecutor
from personal_repo_mcp.chain.model import ChainCommand, ChainPolicy


class FakeResult:
    def __init__(self, error=False):
        self.is_error = error
        self.content = []
        self.structured_content = {"ok": not error}


class FakeMcp:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return FakeResult()


@pytest.mark.asyncio
async def test_chain_injects_repository_once():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    result = await executor.execute("repo", [ChainCommand("git_status", {})], ChainPolicy())
    assert result[0]["is_error"] is False
    assert mcp.calls == [("git_status", {"repository": "repo"})]


@pytest.mark.asyncio
async def test_chain_rejects_nested_repository():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    with pytest.raises(ValueError, match="must not specify repository"):
        await executor.execute("repo", [ChainCommand("git_status", {"repository": "other"})], ChainPolicy())


@pytest.mark.asyncio
async def test_chain_rejects_recursion():
    mcp = FakeMcp()
    executor = ChainExecutor(mcp)
    with pytest.raises(ValueError, match="cannot be used"):
        await executor.execute("repo", [ChainCommand("chain_command", {})], ChainPolicy())
