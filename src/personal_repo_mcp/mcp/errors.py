from __future__ import annotations


class MCPApplicationError(RuntimeError):
    """Base class for expected application-level MCP errors."""


class AuthenticationError(MCPApplicationError):
    """Raised when HTTP authentication fails."""
