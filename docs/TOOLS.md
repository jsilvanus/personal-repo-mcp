# Tool surface

## Repository

- `get_repositories`
- `get_repository`
- `prepare_repository`

## Files

- `read_file`
- `list_directory`
- `search_text`
- `find_files`
- `write_file`
- `replace_lines`
- `insert_lines`
- `delete_lines`
- `apply_patch`

## Git

- `git_status`
- `git_diff`
- `git_changed_files`
- `git_log`
- `git_show`
- `git_blame`
- `git_branch_list`
- `git_branch_create`
- `git_branch_delete`
- `git_switch`
- `git_add`
- `git_unstage`
- `git_commit`
- `git_remote_list`
- `git_fetch`
- `git_pull`
- `git_push`
- `git_merge`
- `git_rebase`
- `git_merge_state`
- `git_abort_merge`
- `git_continue_merge`
- `git_abort_rebase`
- `git_continue_rebase`
- `git_conflicts`
- `git_conflict_file`
- `git_resolve_conflict`

## Hot-git backend

- `git_read_file`
- `git_edit`

When `PERSONAL_REPO_MCP_GIT_BACKEND=hot-git`, these tools use the persistent, treeless hot-git backend. `git_edit` returns the resulting commit, tree, ref and changed paths.

## Phase 4

- `get_workspace_state`
- `chain_command`

`chain_command` is repository-scoped. It takes one repository and an ordered list of existing server tool names and arguments. Nested commands inherit the repository and cannot specify a different one.

When a chain performs `git_edit`, the successful result's `commit` becomes the chain's current commit. A following `git_edit` automatically receives that commit as `expected_ref` unless the caller explicitly supplied one. A following `git_read_file` automatically reads from that commit unless the caller explicitly supplied a revision.

This gives hot-git chains optimistic concurrency semantics:

```text
A(base=X) -> commit A
B(expected_ref=A) -> commit B
C(expected_ref=B) -> commit C
```

An explicit `expected_ref` or `revision` always wins over the automatically carried value.
