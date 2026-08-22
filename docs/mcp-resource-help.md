# MCP Resource Help

## Goal

Provide modular, MCP-native operational documentation as resources instead of adding another large tool or paginating the tool list.

## Resource namespace

Expose a small help index and focused topics:

- `mcp://help/index` — overview and workflow map.
- `mcp://help/repositories` — discovering, preparing, and cloning repositories.
- `mcp://help/files` — reading, searching, and editing files.
- `mcp://help/git` — status, history, branches, synchronization, and conflicts.
- `mcp://help/chain-command` — safely composing multiple operations in one repository.
- `mcp://help/resources` — resource paths, subscriptions, and change notifications.

The index should be short enough to load first. Topic resources provide progressive disclosure and should link conceptually to the relevant tools/resources without duplicating their full schemas.

## Design rules

1. Do not paginate or replace MCP `tools/list`.
2. Help is read-only and must not grant additional capabilities.
3. Keep examples aligned with the actual registered MCP surface.
4. Prefer workflows and tool-selection guidance over a flat tool catalogue.
5. Keep stable documentation separate from changing repository resources.
6. The help resources themselves do not need subscriptions unless the implementation later supports runtime-generated documentation.
7. Keep Tasks/test execution out of the help until those capabilities are actually implemented.

## Implementation

Register the help resources in the server's resource listing/read handlers. Return Markdown for readability by agents. Add tests for listing and reading each URI and for unknown help paths. Update README with the resource namespace and a short recommendation to read `mcp://help/index` when first connecting.
