# Post-MVP Plan: Treeless Git Workers and Chain-Local State

## Status

**Planned, post-MVP.** This document defines the architecture now so the current working-tree MCP and `chain_command` do not accidentally prevent a future object-level Git API.

## Relationship to Aidos

Aidos is an important target consumer/integration context for this design. Its Git architecture distinguishes the human/driver working tree from autonomous workers that operate directly on Git objects using an in-memory index/tree/commit model. The two projects should therefore share **Git semantics**, not necessarily implementation or dependencies.

The intended boundary is:

```text
Aidos agent/session/tool broker
          |
          v
personal-repo-mcp
          |
   repository authorization
          |
   +------+------+
   |             |
working tree   treeless workers
   |             |
   +------+------+
          |
      Git object DB
```

`personal-repo-mcp` should remain an MCP server and persistent VPS workspace service. Aidos may use its repository/worker operations remotely, while retaining ownership of agent sessions, runs, capabilities, audit semantics, and higher-level reconciliation.

This means the post-MVP feature should be designed as a **generic treeless Git worker API**, not as an Aidos-specific API. Aidos-specific metadata should not be embedded into repository or Git primitives.

## Goal

Allow an agent to edit Git history directly, without checking files out or mutating the persistent working tree. The primary use case is safe concurrent work by multiple agents against the same repository object database.

The object-level API should treat a Git commit/ref as the concurrency boundary. Creating Git objects must be independent of moving a branch ref.

## Worker model

The future abstraction should be a **treeless worker**:

```text
base ref/commit
      |
      v
worker state
  base commit
  current tree
      |
   edits/tests
      |
   final commit
      |
worker ref
```

A worker must not require a checkout. Its evolving state can be represented by an in-memory tree/index and, when necessary, newly-created Git objects.

A persistent branch should not be treated as the worker's mutable workspace. A worker ref provides an isolated publication/reconciliation point. A future convention compatible with Aidos may use a namespace such as:

```text
refs/aidos/workers/<worker-id>
```

but the MCP implementation must keep the worker-ref namespace configurable/generic rather than hard-coding Aidos names.

## Why this is separate from the current API

The current MCP is intentionally working-tree oriented:

- file tools read and mutate the persistent workspace;
- existing Git tools inspect or mutate that workspace;
- `chain_command` sequences ordinary MCP operations within one repository.

Object editing is a different mode. It must not silently alter the working tree, and it must not change the meaning of existing file tools.

The two modes should coexist:

```text
repository
├── working-tree operations  -> persistent workspace
└── treeless worker ops     -> Git object database
```

## Core model

A future object-level edit conceptually accepts:

```text
repository
base ref or commit
one or more file changes
commit message
```

The server resolves the base ref to an immutable commit SHA, reads the commit's tree/blob objects, applies the changes in memory, creates new Git objects, and creates a new commit. No checkout is required.

Conceptual flow:

```text
base ref
  -> commit
  -> tree
  -> affected blobs
  -> new blobs
  -> reconstructed trees
  -> new commit
```

Unchanged blobs and trees should be reused by SHA. Only affected tree paths need reconstruction.

## Ref update and publication

Creating a commit and moving a branch are deliberately separate.

A commit-producing operation returns the new commit SHA but does not implicitly move the source branch unless an explicit convenience operation is later defined.

Publication must use compare-and-swap semantics:

```text
update_ref(ref, expected_old_sha, new_sha)
```

If the current ref does not equal `expected_old_sha`, the operation fails with a ref-changed/conflict result and does not overwrite another agent's work.

This is the central concurrency guarantee.

A worker ref may be updated during worker lifetime, but every update must preserve the same optimistic-concurrency rule. The worker's final publication to a shared branch is a separate reconciliation step.

## Chain-local Git state

`chain_command` is the natural transaction boundary for a sequence of treeless operations.

At chain start, the repository's selected base is resolved once:

```text
chain.base_commit = resolved starting commit
chain.current_tree = tree(chain.base_commit)
```

Object-level edit operations inside the chain default to the chain's current state. Each edit updates `chain.current_tree` rather than requiring the agent to provide a new SHA.

For example:

```text
A: resolve HEAD -> commit A
B: edit file 1 -> tree T1
C: edit file 2 -> tree T2
D: edit file 3 -> tree T3
E: create commit from T3 -> commit B
F: CAS-update worker/shared ref -> B
```

The intermediate edits do **not** need to create intermediate commits. The chain can accumulate a tree state and create one final commit.

This solves the original problem where operation A has a known base but B/C/D do not. The chain carries the evolving state; the agent does not have to observe or supply intermediate hashes.

The resulting state should expose at least:

```text
base_commit
final_commit (after commit creation)
selected_ref
worker_ref (if applicable)
ref_updated
```

The current tree is implementation state and should not be serialized unless a future API requires it.

## Chain semantics

1. A chain is scoped to exactly one repository, consistent with current `chain_command` semantics.
2. At chain start, a selected ref is resolved to an immutable base commit.
3. Object-level operations without an explicit base use the chain's evolving state.
4. An explicit alternate ref/base is allowed only where the operation's schema explicitly permits it; it must not silently replace the chain state.
5. Working-tree operations continue to use the actual workspace and do not become object operations merely because they occur inside a chain.
6. Object edits never mutate the working tree.
7. A final commit is created only when explicitly requested, or by a clearly defined atomic convenience operation.
8. Updating a shared ref is explicit and uses expected-old-SHA compare-and-swap.
9. If a ref changed while the chain was executing, final publication fails without losing the created commit.
10. The chain reports its base and final commit SHA so an agent can recover or reconcile after a ref conflict.
11. A chain failure must not leave a partially published shared ref.
12. Intermediate object state should remain private to the chain unless explicitly materialized as Git objects/commits.

## Proposed future operations

Names are provisional and should be finalized during implementation.

### `git_worker_create`

Create a treeless worker state from an explicit ref/commit. Return the immutable base commit and worker identity/ref. The first implementation may keep worker state request-scoped through `chain_command`; a persistent worker abstraction should only be added if Aidos integration needs it.

### `git_edit`

Apply one or more standard unified diffs to the Git tree rooted at an explicit ref or the chain's current state. It produces a new tree state in a chain or a new commit in a standalone atomic form, depending on the final API design.

A multi-file operation should be supported so related changes can become one commit.

### `git_create_commit`

Create a commit from the current object-level tree state, with an explicit commit message. In a chain this consumes the chain's current tree. It should return the new commit SHA.

### `git_update_ref`

Move a branch/worker ref using expected-old-SHA compare-and-swap. It must reject stale expectations rather than overwrite concurrent work.

A higher-level `git_edit_commit` convenience operation may eventually combine edit + commit + optional CAS ref update, but the underlying semantics remain separate.

## Patch format

Use standard unified diff / Git-style patch as the input representation. The implementation must validate that the patch applies against the requested base content.

The server should return enough information for auditing and recovery, including:

```text
base_commit
result_commit (if committed)
changed_paths
ref
ref_updated
```

Patch application must not depend on a checked-out working tree.

## Git plumbing implementation

Prefer Git's existing plumbing/object mechanisms instead of directly implementing the Git object format.

The implementation should use equivalent operations to:

```text
git rev-parse
git cat-file / tree inspection
git hash-object
git mktree
git commit-tree
git update-ref
```

The exact subprocess/API implementation is an implementation detail. The important invariant is that object editing does not require checkout or working-tree mutation.

For a nested path, reconstruct only the affected tree chain. Reuse all unaffected Git objects by SHA.

The implementation should be factored so that the pure Git-object layer is usable independently of MCP transport. This is the main route by which the code could be reused by Aidos: a small generic Git worker/object library can be consumed by an Aidos adapter without importing the MCP server layer.

## Aidos reuse assessment

**Likely reusable, but not as-is.** The most reusable part should be the future treeless Git implementation, not the current MCP transport/server code.

The desired package boundary is:

```text
Git object/worker library
├── ref resolution
├── tree/index manipulation
├── blob creation
├── tree reconstruction
├── commit creation
├── CAS ref updates
├── patch application
└── concurrency/error model

MCP adapter
├── tool schemas
├── chain_command integration
├── authorization
├── resources
└── transport
```

Aidos could consume the first layer directly or through a very thin adapter. It should not need to speak MCP merely to use the Git implementation locally.

Conversely, `personal-repo-mcp` should not depend on Aidos types, worker/session objects, or Aidos-specific persistence.

Before implementation, create a small proof-of-concept API boundary and test it from both projects. If Aidos already has a suitable Git abstraction, prefer extracting/aligning with that abstraction rather than creating a second competing implementation.

## Aidos integration boundary

The MCP should expose repository/Git semantics such as:

```text
create worker from ref
edit worker tree
create commit
read worker/ref state
CAS-update ref
```

Aidos can then map its own concepts onto these operations:

```text
Aidos Session / Run / Attempt
          |
          v
Aidos worker identity
          |
          v
personal-repo-mcp worker/ref
          |
          v
Git commit DAG
```

Do not store Aidos session IDs in Git commit semantics unless explicitly required. If correlation metadata is useful, pass it as optional commit metadata or an external audit record rather than making it part of the generic Git API.

## Concurrent agents

Starting state:

```text
main -> A
```

Agent 1 and Agent 2 both begin from A:

```text
A -> B    Agent 1 worker
A -> C    Agent 2 worker
```

Both commits are valid and coexist in the object database.

If Agent 1 publishes:

```text
update_ref(main, expected=A, new=B)
```

it succeeds if `main` still points to A.

If Agent 2 has already published C, Agent 1 receives:

```text
expected: A
actual: C
new: B
```

Agent 1's B remains available and can be reconciled through normal Git merge/rebase logic. No work is silently lost.

A worker namespace makes this cleaner:

```text
main -> A
          |
          +-> worker/1 -> B
          |
          +-> worker/2 -> C
```

Workers should normally publish to their own isolated refs first. Shared-branch publication is a deliberate reconciliation action.

## Relationship to working-tree resources

Existing resources remain working-tree oriented:

```text
repo://<repo>/file/<path>
repo://<repo>/git/status
repo://<repo>/git/diff
```

Future object resources may expose immutable Git state, for example:

```text
repo://<repo>/git/ref/heads/<branch>
repo://<repo>/git/commit/<sha>
repo://<repo>/git/tree/<sha>
repo://<repo>/git/worker/<id>
```

These should not be introduced until there is a concrete consumer; the object editing API should not require a broad new resource surface initially.

## Submodules

The existing submodule safety rules remain in force. Object-level editing must explicitly define how gitlink entries are handled before implementation. It must never interpret a gitlink as an ordinary file blob or permit modification of a submodule's contents through the parent repository's file-edit path.

For Aidos integration, a submodule worker must either operate on the parent gitlink only or explicitly target a separately authorized submodule repository. It must never implicitly cross repository boundaries.

## Error and recovery semantics

The API should distinguish at least:

- invalid/unresolvable ref;
- patch does not apply to the base;
- path is a submodule/gitlink;
- object creation failure;
- commit creation failure;
- ref changed since expected base;
- unauthorized repository/ref operation;
- worker/chain state expired or unavailable.

A failed ref update must never delete or invalidate a successfully created commit.

## Security considerations

Object-level editing remains inside the same repository authorization boundary as the current MCP.

The server must validate repository identity and ref names and must not allow arbitrary filesystem paths to escape the repository object database. Git commands must use argument-safe invocation; no shell interpolation.

Aidos integration must not bypass the MCP's repository allow-list when the MCP is the remote authorization boundary. If Aidos is linked directly to the reusable Git library, Aidos becomes responsible for applying its own equivalent repository/capability authorization.

## Implementation order

1. **Architecture boundary:** define a transport-independent Git worker/object library interface.
2. **Aidos compatibility spike:** compare this interface with Aidos' existing Git abstraction and determine whether to reuse, adapt, or extract common code.
3. Finalize object-level MCP tool schemas and chain semantics.
4. Implement immutable ref/commit/tree/blob resolution helpers.
5. Implement unified-diff application against blobs in memory.
6. Implement tree reconstruction and object creation.
7. Implement commit creation without checkout.
8. Implement compare-and-swap ref updates.
9. Add chain-local object state and automatic base derivation.
10. Add multi-file commit support.
11. Add worker-ref support if the Aidos integration spike confirms it is needed.
12. Add concurrency/ref-race tests.
13. Add submodule/gitlink tests.
14. Add Aidos integration tests against a real repository object database.
15. Add resource/help documentation and agent workflow guidance.
16. Add optional convenience operations only after the primitives are stable.

## Explicit non-goals for the first implementation

- no automatic merge/rebase after a ref race;
- no automatic working-tree synchronization;
- no implicit branch movement when merely creating a commit;
- no test/build execution as part of the Git object primitive;
- no replacement of the existing working-tree Git tools;
- no Aidos-specific dependencies in the generic Git layer;
- no requirement that Aidos use MCP as its local Git transport.

## MVP boundary

This feature is **post-MVP**. The current MVP remains the persistent working-tree MCP. The plan exists now so future object-level Git support, chain semantics, worker refs, resource naming, and concurrency behavior remain compatible with both the current MCP and potential Aidos integration.
