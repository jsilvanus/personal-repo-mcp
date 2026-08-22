# Protocol

Personal Repo MCP is a normal MCP server. The public API is exposed through MCP `tools/list` and `tools/call` over Streamable HTTP.

## Repository scope

Repository is the primary domain scope of the service. Ordinary tools take a repository identifier. `chain_command` takes the repository once and nested tool invocations inherit it.

Repository selection is explicit request data; the server does not keep a mutable "current repository" session state.

## chain_command

`chain_command` is an application-level MCP tool, not a second RPC protocol. The client makes one normal `tools/call`; the server internally calls its registered tools through `MCPServer.call_tool()`.

Each nested operation therefore goes through the MCP SDK's normal tool lookup, argument validation, execution and result conversion. Nested commands:

- execute sequentially
- inherit the chain repository
- must not specify `repository`
- cannot invoke `chain_command`
- cannot invoke repository-management operations
- stop on error by default

This preserves MCP semantics while reducing network round trips.

## Transport

Streamable HTTP is the primary transport because the server is remote and persistent on a VPS. The implementation targets the current MCP SDK v2 / 2026-07-28 protocol line while retaining the SDK's compatibility behavior for older clients.

## Long-running work

Phase 4 adds an internal operation state/task runner as groundwork. It is not a replacement for MCP Tasks. Long-running operations should adopt the standard MCP Tasks mechanism when the operation genuinely needs asynchronous task lifecycle semantics.
