# Post-MVP Plan: Git Object Editing and Chain-Local State

## Status

**Planned, post-MVP.** This document defines the architecture now so the current working-tree API and `chain_command` do not accidentally prevent a future object-level Git API.

## Goal

Allow an agent to edit Git history directly, without checking files out or mutating the persistent working tree. The primary use case is safe concurrent work by multiple agents against the same repository object database.

The object-level API should treat a Git commit/ref as the concurrency boundary. Creating Git objects must be independent of moving a branch ref.

## Why this is separate from the current API

The current MCP is intentionally working-tree oriented:

- file tools read and mutate the persistent workspace;
- existing Git tools inspect or mutate that workspace;
- `chain_command` currently sequences ordinary MCP operations within one repository.

Object editing is a different mode. It must not silently alter the working tree, and it must not change the meaning of existing file tools.

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

## Ref update must be separate

Creating a commit and moving a branch are deliberately separate operations.

A commit-producing operation returns the new commit SHA but does not implicitly move the source branch unless an explicit convenience operation is later defined.

Branch movement must use compare-and-swap semantics:

```text
update_ref(ref, expected_old_sha, new_sha)
```

If the current ref does not equal `expected_old_sha`, the operation fails with a ref-changed/conflict result and does not overwrite the other agent's work.

This is the central concurrency guarantee.

## Chain-local Git state

`chain_command` solves the problem of intermediate bases not being known to the agent.

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
```

The intermediate edits do **not** need to create intermediate commits. The chain can accumulate a tree state and create one final commit.

The resulting state should expose at least:

```text
base_commit
current_tree (internal; not necessarily exposed)
final_commit (after commit creation)
selected_ref
ref_updated
```

## Chain semantics

Define these rules before implementation:

1. A chain is scoped to exactly one repository, consistent with current `chain_command` semantics.
2. At chain start, a selected ref is resolved to an immutable base commit.
3. Object-level operations without an explicit base use the chain's evolving state.
4. An explicit alternate ref/base is allowed only where the operation's schema explicitly permits it; it must not silently replace the chain state.
5. Working-tree operations continue to use the actual workspace and do not become object operations merely because they occur inside a chain.
6. Object edits never mutate the working tree.
7. A final commit is created only when explicitly requested, or by a clearly defined atomic convenience operation.
8. Updating a branch ref is explicit and uses expected-old-SHA compare-and-swap.
9. If the ref changed while the chain was executing, final publication fails without losing the created commit.
10. The chain must report its base and final commit SHA so an agent can recover or reconcile after a ref conflict.

## Proposed future operations

Names are provisional and should be finalized during implementation.

### `git_edit`

Apply one or more standard unified diffs to the Git tree rooted at an explicit ref or the chain's current state. It produces a new tree state in a chain or a new commit in a standalone atomic form, depending on the final API design.

A multi-file operation should be supported so related changes can become one commit.

### `git_create_commit`

Create a commit from the current object-level tree state, with an explicit commit message. In a chain this consumes the chain's current tree. It should return the new commit SHA.

### `git_update_ref`

Move a branch/tag ref using expected-old-SHA compare-and-swap. It must reject stale expectations rather than overwrite concurrent work.

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

Patch application should not depend on a checked-out working tree.

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

## Concurrency example

Starting state:

```text
main -> A
```

Agent 1 and Agent 2 both begin from A.

```text
A -> B    Agent 1
A -> C    Agent 2
```

Both commits are valid and coexist in the object database.

If Agent 1 publishes:

```text
update_ref(main, expected=A, new=B)
```

it succeeds if `main` still points to A.

If Agent 2 has already published C, Agent 1 receives a ref-changed result:

```text
expected: A
actual: C
new: B
```

Agent 1's B remains available and can be reconciled through normal Git merge/rebase logic. No work is silently lost.

## Relationship to working-tree resources

Existing resources remain working-tree oriented:

```text
repo://<repo>/file/<path>
repo://<repo>/git/status
repo://<repo>/git/diff
```

Future object resources may eventually expose immutable Git state, for example:

```text
repo://<repo>/git/ref/heads/<branch>
repo://<repo>/git/commit/<sha>
repo://<repo>/git/tree/<sha>
```

These should not be introduced until there is a concrete consumer; the object editing API should not require a broad new resource surface initially.

## Submodules

The existing submodule safety rules remain in force. Object-level editing must explicitly define how gitlink entries are handled before implementation. It must never interpret a gitlink as an ordinary file blob or permit modification of a submodule's contents through the parent repository's file-edit path.

## Error and recovery semantics

The API should distinguish at least:

- invalid/unresolvable ref;
- patch does not apply to the base;
- path is a submodule/gitlink;
- object creation failure;
- commit creation failure;
- ref changed since expected base;
- unauthorized repository/ref operation.

A failed ref update must never delete or invalidate a successfully created commit.

## Security considerations

Object-level editing remains inside the same repository authorization boundary as the current MCP.

The server must validate repository identity and ref names and must not allow arbitrary filesystem paths to escape the repository object database. Git commands must use argument-safe invocation; no shell interpolation.

## Implementation order

1. Finalize object-level API names and schemas.
2. Implement immutable ref/commit/tree/blob resolution helpers.
3. Implement unified-diff application against blobs in memory.
4. Implement tree reconstruction and object creation.
5. Implement commit creation without checkout.
6. Implement compare-and-swap ref updates.
7. Add chain-local object state and automatic base derivation.
8. Add multi-file commit support.
9. Add concurrency/ref-race tests.
10. Add submodule/gitlink tests.
11. Add resource/help documentation and agent workflow guidance.
12. Add optional convenience operation only after the primitives are stable.

## Explicit non-goals for the first implementation

- no automatic merge/rebase after a ref race;
- no automatic working-tree synchronization;
- no implicit branch movement when merely creating a commit;
- no test/build execution;
- no replacement of the existing working-tree Git tools.

## MVP boundary

This feature is **post-MVP**. The current MVP remains the persistent working-tree MCP. This plan exists now so that future object-level Git support, chain semantics, resource naming, and concurrency behavior remain compatible with the existing architecture.
