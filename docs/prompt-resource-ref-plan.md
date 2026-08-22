# Prompt-Embedded Help Resource Plan

## Goal

Make the `setup` and `development` MCP prompts directly include the small `mcp://help/index` resource instead of only telling the model to fetch it.

## Behavior

- `prompts/list` continues to expose `setup` and `development`.
- `prompts/get` returns the workflow instructions plus an embedded resource containing the current `mcp://help/index` content.
- The help index remains a resource and remains independently readable through `resources/read`.
- Specialized help resources remain progressively discoverable from the index.
- No additional capabilities are granted by the embedded resource.

## Rationale

A prompt selected by an MCP client should carry the entry-point knowledge with it. This removes reliance on the model noticing a URI in prose while preserving the resource architecture and avoiding duplication of the detailed help topics.

## Testing

Verify both prompts contain the expected workflow instructions and an embedded `mcp://help/index` resource. Verify the normal resource listing/reading behavior is unchanged.
