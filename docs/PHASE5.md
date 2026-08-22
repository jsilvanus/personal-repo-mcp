# Phase 5 implementation

Phase 5 establishes the MCP Resource and subscription foundation for the persistent multi-repository workspace.

## Implemented

- `repo://<repository>/file/<path>` persistent file resources
- `repo://<repository>/git/status`
- `repo://<repository>/git/diff`
- `repo://<repository>/git/conflicts`
- reserved `tests/<run-id>` and `artifacts/<id>` namespaces
- standard MCP `subscriptions/listen` through the MCP Python SDK v2
- resource-update publication after filesystem mutations
- file SHA-256 resource metadata and existing `expected_hash` concurrency protection
- repository path and `.git` isolation

## Deliberately deferred

- filesystem watchers for external changes
- test runners and test result producers
- build/artifact producers
- artifact download endpoints
- resource history/replay
- MCP Tasks
- custom notification types

The resource namespace is intentionally established before these producers exist so they can be added without changing the resource URI model.
