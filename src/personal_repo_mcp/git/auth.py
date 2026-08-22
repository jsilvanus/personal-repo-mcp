from __future__ import annotations

import os


GIT_ASKPASS = "/usr/local/bin/personal-repo-mcp-git-askpass"


def git_environment() -> dict[str, str]:
    """Return the environment used for authenticated GitHub HTTPS operations."""
    environment = os.environ.copy()
    environment["GIT_ASKPASS"] = GIT_ASKPASS
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment
