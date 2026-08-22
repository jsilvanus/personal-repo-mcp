# Personal Repo MCP — Plan

## Purpose

Personal Repo MCP is a multi-repository MCP server intended to run on a VPS. It provides AI agents with a persistent Git workspace and uses GitHub (or another Git remote) as upstream rather than treating GitHub's API as the workspace.

The goal is to overcome practical limitations of hosted GitHub MCP access while retaining MCP interoperability.

## Core principles

- **MCP-native:** use the Model Context Protocol as the external protocol; do not create a competing RPC protocol.
- **Streamable HTTP:** the primary transport is Streamable HTTP because the server is remote and persistent on a VPS.
- **Repository-first:** a repository is the primary domain scope. Tools operate against a selected repository/workspace.
- **Persistent workspaces:** repositories remain cloned on the VPS between agent interactions.
- **Git-first:** Git is the local source-of-truth workflow; GitHub is an upstream remote, not the local workspace API.
- **Explicit scope:** repository identity is explicit rather than being hidden mutable session state.
- **Safe writes:** file writes support whole-file and targeted edits, with conflict/concurrency protection where appropriate.
- **Agent-friendly reads:** large files can be read in chunks and searched locally.
- **First-class Git:** status, diff, history, branches, commits, synchronization, merge/rebase and conflict handling are exposed as structured tools.
- **Composable operations:** `chain_command` executes multiple supported server tools sequentially within one repository in a single MCP `tools/call`.
- **Security by default:** repository paths are isolated, destructive Git operations are controlled, credentials are protected, and operations can be audited.

## Repository model

The server manages multiple persistent repository workspaces. A repository has a stable server-side identity and a Git remote, but clients never need to know the VPS filesystem path.

Ordinary tools receive a repository scope. `chain_command` receives the repository once at the top level; nested commands inherit it and must not select or change repositories.

`chain_command` must not recursively invoke itself or invoke workspace-management operations such as adding/removing repositories.

## File operations

Core file capabilities:

- read complete files
- read line ranges/chunks
- list directories
- search text/files
- write/replace complete files
- replace line ranges
- insert lines
- delete lines
- apply standard unified diff / Git-style patches

Writes should support an expected content/hash check where useful so stale agent reads cannot silently overwrite newer changes.

## Git operations

The MCP should expose structured Git operations rather than requiring agents to construct arbitrary shell commands.

Core areas:

- status and changed files
- diff and comparison
- log/show/blame
- add/stage/unstage
- commit
- branch creation/list/deletion
- checkout/switch
- fetch/pull/synchronization
- push
- merge
- rebase
- reset/other destructive operations with explicit safeguards
- tags and remote inspection as appropriate

## Merge conflicts

Merge and rebase conflicts are first-class state.

The API should provide:

- detection of merge/rebase state
- list of conflicted files
- structured conflict-region display containing ours/base/theirs where available
- conflict resolution
- continue merge/rebase
- abort merge/rebase

The agent should not have to rely solely on parsing raw `<<<<<<<` markers.

## `chain_command`

`chain_command` is an ordinary MCP tool. It does not extend the MCP wire protocol.

It accepts:

- one repository/workspace identifier
- an ordered list of supported tool invocations
- an error policy, defaulting to stop on error

Each nested invocation is dispatched through the same server-side tool validation, authorization, execution, result and error machinery as a normal tool invocation. The nested commands do not repeat the repository identifier.

The chain is repository-local and cannot switch repositories or recursively call `chain_command`.

The first implementation should focus on sequential execution and structured per-command results. Result references and richer conditional workflows can be added later if needed.

## Security

The server runs on a VPS and may have substantially more authority than hosted GitHub MCP integrations. Security is therefore a core feature rather than an optional deployment concern.

Initial security requirements:

- HTTPS
- bearer authentication or equivalent authenticated MCP access
- scoped credentials where practical
- repository path canonicalization and traversal protection
- protection against symlink/path escapes
- no accidental access outside repository workspaces
- careful treatment of `.git`, hooks, submodules and remotes
- explicit controls for force-push and destructive Git operations
- no arbitrary shell execution in the initial core API
- audit logging without logging secrets or full file contents

## Protocol

The implementation should track the current MCP specification and use normal MCP server capabilities, especially `tools/list` and `tools/call`, with Streamable HTTP as the transport.

`chain_command` is application-level orchestration implemented as a normal MCP tool. It must not be represented as a second RPC protocol.

Long-running operations and MCP Tasks can be introduced after the basic server is stable.

## Licensing

Use **EUPL-1.2** as the project license unless implementation experience gives a concrete reason to reconsider it.

## Suggested future capabilities

- long-running operations / Tasks
- repository snapshots and workspace state summaries
- dry-run support for risky operations
- structured audit history
- test/build execution in controlled isolation
- multiple worktrees per repository
- more advanced chain result references
- optional Git providers beyond GitHub
