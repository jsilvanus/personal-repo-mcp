from __future__ import annotations

from pathlib import Path

import pytest

from personal_repo_mcp.config import ConfigurationError, load_settings


def _base_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "repositories"
    root.mkdir()
    config = tmp_path / "repositories.json"
    config.write_text(
        '{"version": 1, "repositories": []}', encoding="utf-8"
    )
    monkeypatch.setenv("PERSONAL_REPO_MCP_ROOT", str(root))
    monkeypatch.setenv("PERSONAL_REPO_MCP_CONFIG", str(config))
    monkeypatch.setenv("PERSONAL_REPO_MCP_ALLOWED_HOSTS", "example.test")
    monkeypatch.setenv("PERSONAL_REPO_MCP_ALLOWED_ORIGINS", "https://example.test")
    return root


def test_secret_files_take_precedence_over_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base_environment(monkeypatch, tmp_path)
    token_file = tmp_path / "mcp-token"
    pat_file = tmp_path / "github-pat"
    token_file.write_text("file-token\n", encoding="utf-8")
    pat_file.write_text("file-pat\n", encoding="utf-8")

    monkeypatch.setenv("PERSONAL_REPO_MCP_TOKEN", "environment-token")
    monkeypatch.setenv("PERSONAL_REPO_MCP_GITHUB_PAT", "environment-pat")
    monkeypatch.setenv("PERSONAL_REPO_MCP_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("PERSONAL_REPO_MCP_GITHUB_PAT_FILE", str(pat_file))

    settings = load_settings()

    assert settings.token == "file-token"
    assert settings.github_pat == "file-pat"


def test_missing_secret_file_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base_environment(monkeypatch, tmp_path)
    monkeypatch.delenv("PERSONAL_REPO_MCP_TOKEN", raising=False)
    monkeypatch.delenv("PERSONAL_REPO_MCP_GITHUB_PAT", raising=False)
    monkeypatch.setenv(
        "PERSONAL_REPO_MCP_TOKEN_FILE", str(tmp_path / "missing-token")
    )

    with pytest.raises(ConfigurationError, match="Cannot read secret file"):
        load_settings()


def test_secret_files_are_stripped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _base_environment(monkeypatch, tmp_path)
    token_file = tmp_path / "mcp-token"
    pat_file = tmp_path / "github-pat"
    token_file.write_text("token-with-newline\n\n", encoding="utf-8")
    pat_file.write_text("pat-with-newline\n", encoding="utf-8")
    monkeypatch.setenv("PERSONAL_REPO_MCP_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("PERSONAL_REPO_MCP_GITHUB_PAT_FILE", str(pat_file))

    settings = load_settings()

    assert settings.token == "token-with-newline"
    assert settings.github_pat == "pat-with-newline"
