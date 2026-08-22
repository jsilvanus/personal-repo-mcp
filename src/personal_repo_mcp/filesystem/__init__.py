"""Repository filesystem primitives."""

from .paths import FileSystemError, resolve_repository_path
from .reader import FileRead, list_directory, read_file
from .search import find_files, search_text
from .writer import content_hash, delete_lines, insert_lines, replace_lines, write_file
from .patch import apply_unified_diff

__all__ = [
    "FileRead",
    "FileSystemError",
    "apply_unified_diff",
    "content_hash",
    "delete_lines",
    "find_files",
    "insert_lines",
    "list_directory",
    "read_file",
    "replace_lines",
    "resolve_repository_path",
    "search_text",
    "write_file",
]
