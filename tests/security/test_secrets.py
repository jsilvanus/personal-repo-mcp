from personal_repo_mcp.security.secrets import scrub_text, scrub_value


def test_scrub_text_removes_configured_secrets() -> None:
    secret = "ghp_super_secret"
    text = f"remote=https://x-access-token:{secret}@github.com/example/repo.git"

    scrubbed = scrub_text(text, (secret,))

    assert secret not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_scrub_text_removes_url_encoded_secret() -> None:
    secret = "secret/with+specials"
    encoded = "secret%2Fwith%2Bspecials"

    scrubbed = scrub_text(f"token={encoded}", (secret,))

    assert encoded not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_scrub_value_recurses_through_mcp_result_shapes() -> None:
    secret = "mcp-secret"
    value = {
        "content": [
            {"text": f"token={secret}"},
            {"nested": {"error": secret}},
        ],
        "structured": {"remote": f"https://example.invalid/{secret}"},
    }

    scrubbed = scrub_value(value, (secret,))

    assert scrubbed == {
        "content": [
            {"text": "token=[REDACTED]"},
            {"nested": {"error": "[REDACTED]"}},
        ],
        "structured": {"remote": "https://example.invalid/[REDACTED]"},
    }


def test_scrub_value_preserves_non_string_values() -> None:
    value = {"count": 3, "enabled": True, "nothing": None}

    assert scrub_value(value, ("secret",)) == value
