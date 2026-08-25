from mcp.server import MCPServer
from mcp.types import EmbeddedResource, TextContent

from personal_repo_mcp.mcp.prompts import register_prompts


async def _get_prompt_messages(name: str):
    server = MCPServer(name="test")
    register_prompts(server)
    result = await server.get_prompt(name, None)
    return result.messages


def _resource_and_text(messages):
    resource = next(message.content for message in messages if isinstance(message.content, EmbeddedResource))
    text = next(message.content for message in messages if isinstance(message.content, TextContent))
    return resource, text


async def test_setup_prompt_embeds_help_index():
    messages = await _get_prompt_messages("setup")
    resource, text = _resource_and_text(messages)
    assert resource.resource.uri == "mcp://help/index"
    assert resource.resource.mime_type == "text/markdown"
    assert "Personal Repo MCP" in resource.resource.text
    assert "mcp://help/repositories" in text.text


async def test_development_prompt_embeds_help_index():
    messages = await _get_prompt_messages("development")
    resource, text = _resource_and_text(messages)
    assert resource.resource.uri == "mcp://help/index"
    assert resource.resource.mime_type == "text/markdown"
    assert "mcp://help/files" in text.text
    assert "mcp://help/git" in text.text
