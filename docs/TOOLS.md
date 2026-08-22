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

## Phase 4

- `get_workspace_state`
- `chain_command`

`chain_command` is repository-scoped. It takes one repository and an ordered list of existing server tool names and arguments. Nested commands inherit the repository and cannot specify a different one.
