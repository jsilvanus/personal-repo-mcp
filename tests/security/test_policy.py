import pytest

from personal_repo_mcp.security.policy import AuthorizationError, Policy


def test_default_policy_allows_normal_git():
    Policy().check("git_commit")


def test_destructive_operations_are_disabled():
    with pytest.raises(AuthorizationError):
        Policy().check("git_reset_hard")


def test_shell_is_disabled():
    with pytest.raises(AuthorizationError):
        Policy().check("shell")
