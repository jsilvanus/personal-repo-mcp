# Personal Repo MCP — Technical Implementation Plan

This plan deliberately assigns each implementation phase a **non-overlapping file subset**. A file belongs to exactly one phase. Later phases consume interfaces created by earlier phases but do not modify files owned by earlier phases.

The objective is to keep phases independently reviewable and to make parallel development possible where dependencies permit.

## Phase 1 — MCP server foundation and repository model

### Goal

Create a working Streamable HTTP MCP server with repository discovery and safe persistent repository management. No file editing or Git mutation is implemented yet.

### Files owned by this phase

```text
src/main.*
src/config.*
src/mcp/server.*
src/mcp/transport.*
src/mcp/errors.*
src/repositories/manager.*
src/repositories/model.*
src/repositories/paths.*
src/auth/middleware.*
tests/mcp/*
tests/repositories/*
Dockerfile
docker-compose.yml
pyproject.toml / package.json
LICENSE
```

### Work

- Initialize the application/runtime.
- Implement Streamable HTTP MCP endpoint.
- Implement normal MCP server initialization and tool discovery.
- Implement authentication boundary.
- Define repository model and stable repository identifiers.
- Map repository identifiers to server-owned workspace directories.
- Clone/register repositories safely.
- Validate repository paths and prevent traversal/symlink escape.
- Implement `get_repositories` / repository information capability.
- Establish configuration loading and environment handling.
- Add basic health/readiness handling.
- Add protocol-level tests.

### Exit criteria

A client can connect over Streamable HTTP, discover the server, authenticate, and obtain a list of configured repositories. No repository path is exposed to the client.

---

## Phase 2 — File system operations and safe editing

### Goal

Provide complete agent-friendly repository file access, including chunked reads and precise edits.

### Files owned by this phase

```text
src/filesystem/reader.*
src/filesystem/writer.*
src/filesystem/search.*
src/filesystem/patch.*
src/filesystem/paths.*
src/tools/files.*
src/tools/search.*
src/tools/patch.*
tests/filesystem/*
tests/tools/files/*
```

### Work

Implement MCP tools for:

- complete file reads
- line-range/chunk reads
- directory listing
- text/file search
- complete file replacement
- line-range replacement
- line insertion
- line deletion
- standard unified-diff / Git-style patch application

Implement safe-write mechanisms:

- UTF-8 handling and clear binary-file behavior
- maximum request/read limits
- expected content/hash checks where supported
- atomic writes where practical
- path containment checks through the repository abstraction
- clear structured errors for stale writes and invalid ranges

### Exit criteria

An agent can inspect arbitrarily large text files in chunks, search a repository, perform precise edits, apply Git-style unified diffs, and safely detect stale-write conflicts.

---

## Phase 3 — Git engine and conflict management

### Goal

Expose structured Git operations and make normal Git development workflows possible without arbitrary shell access.

### Files owned by this phase

```text
src/git/runner.*
src/git/status.*
src/git/diff.*
src/git/history.*
src/git/branch.*
src/git/staging.*
src/git/commit.*
src/git/remote.*
src/git/sync.*
src/git/merge.*
src/git/conflicts.*
src/tools/git.*
tests/git/*
tests/tools/git/*
```

### Work

Implement structured operations for:

- status
- changed-file listing
- diff / comparison
- log/show/blame
- add/stage/unstage
- commit
- branch list/create/delete
- checkout/switch
- fetch
- pull/synchronization
- push
- remote inspection
- merge
- rebase
- tags where useful

Implement conflict state as first-class information:

- detect merge/rebase in progress
- list conflicted files
- expose structured conflict regions
- expose ours/base/theirs when available
- resolve a conflict safely
- continue merge/rebase
- abort merge/rebase

Implement explicit policy checks around destructive operations such as force-push and hard reset.

Do not introduce arbitrary shell execution. The Git runner should invoke Git through a controlled internal interface with argument construction and repository/workspace containment handled by the server.

### Exit criteria

An agent can perform a normal Git workflow entirely through MCP, including branching, committing, synchronization, merging/rebasing, and resolving conflicts. Merge conflicts can be presented in structured form rather than requiring raw marker parsing.

---

## Phase 4 — Composition, security hardening, auditing and operational features

### Goal

Turn the core server into the complete persistent VPS service, with repository-scoped command chaining and production-grade controls.

### Files owned by this phase

```text
src/chain/model.*
src/chain/executor.*
src/tools/chain.*
src/security/policy.*
src/security/scopes.*
src/audit/logger.*
src/operations/state.*
src/operations/tasks.*
src/tools/workspace.*
tests/chain/*
tests/security/*
tests/audit/*
tests/operations/*
docs/SECURITY.md
docs/PROTOCOL.md
docs/TOOLS.md
```

### Work

#### `chain_command`

Implement `chain_command` as a normal MCP tool.

Input shape:

```text
repository
commands[]
on_error
```

Nested commands:

- are ordinary tools exposed by this server
- omit repository because it is inherited from the chain
- execute sequentially
- stop on error by default
- cannot recursively invoke `chain_command`
- cannot change repository/workspace
- cannot invoke repository-management operations
- use the same validation, authorization, execution and result semantics as ordinary tool calls

Return structured per-command results while preserving success/error distinctions.

Do not create a second RPC protocol inside `chain_command`.

#### Security

Add:

- scoped authorization
- destructive-operation policies
- force-push controls
- repository-level permissions
- credential isolation
- protections for Git hooks, remotes, submodules and special Git paths
- security regression tests

#### Audit

Record:

- timestamp
- authenticated principal/token identifier
- repository
- operation/tool
- relevant path or Git ref where safe
- success/failure
- duration

Never record secrets or full file contents by default.

#### Operational state

Add repository/workspace state summaries and groundwork for long-running operations. MCP Tasks should be used where appropriate for operations that can legitimately outlive a normal request.

Add dry-run support for suitable risky operations if the underlying Git implementation can expose it safely.

### Exit criteria

The complete service supports repository-scoped chained MCP operations, authorization and destructive-operation policy, audit logging, and operational state while remaining a normal MCP server over Streamable HTTP.

---

## File ownership rule

The phase boundaries above are intentional:

> **No file is assigned to more than one phase.**

If a later phase discovers that an earlier phase needs an interface change, prefer introducing a new adapter/interface file owned by the later phase rather than editing an earlier-phase file. If an architectural change genuinely requires modifying an earlier-phase file, stop and revise the phase plan rather than silently violating the boundary.

This allows each phase to be implemented and reviewed as a discrete change set.

## Dependency order

```text
Phase 1
  ↓
Phase 2
  ↓
Phase 3
  ↓
Phase 4
```

Phase 2 depends on the repository model from Phase 1. Phase 3 depends on both repository and filesystem foundations. Phase 4 composes the completed tool surface and adds policy/operational layers.

The implementation should nevertheless keep interfaces narrow so tests and documentation can be developed in parallel within each phase.
