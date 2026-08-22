from __future__ import annotations

from mcp.server import MCPServer

from ..filesystem import (
    FileSystemError,
    apply_unified_diff,
    delete_lines,
    find_files,
    insert_lines,
    list_directory,
    read_file,
    replace_lines,
    search_text,
    write_file,
)
from ..repositories import RepositoryError, RepositoryManager


def register_file_tools(mcp: MCPServer, repositories: RepositoryManager) -> None:
    """Register Phase 2 filesystem tools on the MCP server."""

    def workspace(repository: str):
        try:
            return repositories.get(repository).workspace
        except RepositoryError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool()
    def read_file_tool(repository: str, path: str, start_line: int | None = None, end_line: int | None = None) -> dict[str, object]:
        """Read a UTF-8 repository file, optionally as a 1-based inclusive line range."""
        try:
            return read_file(workspace(repository), path, start_line=start_line, end_line=end_line).as_dict()
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="list_directory")
    def list_directory_tool(repository: str, path: str = ".") -> list[dict[str, object]]:
        """List files and directories inside a repository workspace."""
        try:
            return list_directory(workspace(repository), path)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="search_text")
    def search_text_tool(repository: str, query: str, path: str = ".", max_results: int = 200, case_sensitive: bool = True) -> list[dict[str, object]]:
        """Search UTF-8 text files in a repository and return matching lines."""
        try:
            return search_text(workspace(repository), query, path, max_results=max_results, case_sensitive=case_sensitive)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="find_files")
    def find_files_tool(repository: str, pattern: str, path: str = ".", max_results: int = 500) -> list[str]:
        """Find repository files by a filename glob such as *.py."""
        try:
            return find_files(workspace(repository), pattern, path, max_results=max_results)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="write_file")
    def write_file_tool(repository: str, path: str, content: str, expected_hash: str | None = None) -> dict[str, object]:
        """Replace a complete UTF-8 text file atomically."""
        try:
            return write_file(workspace(repository), path, content, expected_hash=expected_hash)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="replace_lines")
    def replace_lines_tool(repository: str, path: str, start_line: int, end_line: int, content: str, expected_hash: str | None = None) -> dict[str, object]:
        """Replace an inclusive range of lines in a UTF-8 text file."""
        try:
            return replace_lines(workspace(repository), path, start_line, end_line, content, expected_hash=expected_hash)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="insert_lines")
    def insert_lines_tool(repository: str, path: str, line: int, content: str, expected_hash: str | None = None) -> dict[str, object]:
        """Insert text immediately before the specified 1-based line."""
        try:
            return insert_lines(workspace(repository), path, line, content, expected_hash=expected_hash)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="delete_lines")
    def delete_lines_tool(repository: str, path: str, start_line: int, end_line: int, expected_hash: str | None = None) -> dict[str, object]:
        """Delete an inclusive range of lines from a UTF-8 text file."""
        try:
            return delete_lines(workspace(repository), path, start_line, end_line, expected_hash=expected_hash)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="apply_patch")
    def apply_patch_tool(repository: str, path: str, patch: str, expected_hash: str | None = None) -> dict[str, object]:
        """Apply a standard single-file unified diff with zero fuzz."""
        try:
            return apply_unified_diff(workspace(repository), path, patch, expected_hash=expected_hash)
        except FileSystemError as exc:
            raise ValueError(str(exc)) from exc
