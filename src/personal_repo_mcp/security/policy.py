from __future__ import annotations

from dataclasses import dataclass


class AuthorizationError(PermissionError):
    """Raised when an authenticated caller is not allowed to perform an operation."""


@dataclass(frozen=True, slots=True)
class Policy:
    """Simple repository-aware authorization policy for the personal deployment."""

    read: bool = True
    write: bool = True
    git_read: bool = True
    git_write: bool = True
    push: bool = True
    destructive: bool = False
    shell: bool = False

    def check(self, operation: str) -> None:
        if operation.startswith("read_") and not self.read:
            raise AuthorizationError("Read access is disabled")
        if operation in {"write_file", "replace_lines", "insert_lines", "delete_lines", "apply_patch"} and not self.write:
            raise AuthorizationError("File write access is disabled")
        if operation.startswith("git_"):
            mutating = operation not in {"git_status", "git_diff", "git_changed_files", "git_log", "git_show", "git_blame", "git_branch_list", "git_conflicts", "git_conflict_file", "git_merge_state", "git_remote_list"}
            if mutating and not self.git_write:
                raise AuthorizationError("Git write access is disabled")
            if not mutating and not self.git_read:
                raise AuthorizationError("Git read access is disabled")
        if operation in {"git_push_force", "git_reset_hard", "git_clean", "git_branch_delete_force"} and not self.destructive:
            raise AuthorizationError("Destructive Git operation is disabled")
        if operation == "shell" and not self.shell:
            raise AuthorizationError("Shell execution is disabled")
