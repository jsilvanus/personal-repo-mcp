from __future__ import annotations

from collections.abc import Mapping, Sequence
from urllib.parse import quote


REDACTED = "[REDACTED]"


def scrub_text(value: str, secrets: Sequence[str]) -> str:
    """Remove configured secrets from text before it can leave the server."""
    result = value
    for secret in secrets:
        if not secret:
            continue
        result = result.replace(secret, REDACTED)
        # Git URLs and other serialized values may contain percent-encoded
        # credentials. Redact that representation too.
        encoded = quote(secret, safe="")
        if encoded != secret:
            result = result.replace(encoded, REDACTED)
    return result


def scrub_value(value: object, secrets: Sequence[str]) -> object:
    """Recursively scrub configured secrets from MCP result values."""
    if isinstance(value, str):
        return scrub_text(value, secrets)
    if isinstance(value, Mapping):
        return {key: scrub_value(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_value(item, secrets) for item in value)
    return value


def make_secret_scrubber(secrets: Sequence[str]):
    """Create MCP middleware that scrubs secrets from every outbound result."""
    configured = tuple(secret for secret in secrets if secret)

    async def scrub_middleware(ctx, call_next):
        result = await call_next(ctx)
        return scrub_value(result, configured)

    return scrub_middleware
