"""Minimal HTML pages for the authorization server, with a strict CSP."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from starlette.responses import HTMLResponse

_STYLE = (
    "body{font-family:system-ui,sans-serif;background:#f6f7f9;margin:0;padding:4rem 1rem}"
    "main{max-width:460px;margin:0 auto;background:#fff;padding:2rem;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.08)}"
    "h1{margin-top:0}button,.button{display:inline-block;margin-top:1rem;padding:.7rem 1.1rem;border:0;border-radius:7px;"
    "cursor:pointer;background:#1f5eff;color:#fff;text-decoration:none;font:inherit}.secondary{margin-left:.5rem;background:#eee;color:#222}"
    ".note{color:#555;font-size:.9rem}"
)


def content_security_policy(form_action: list[str] | tuple[str, ...] = ()) -> str:
    # Browsers apply form-action to the redirects a form submission follows, so the consent
    # page must list the OAuth client's redirect origin (see codestash LEARNED.md).
    return (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action "
        + " ".join(["'self'", *form_action])
    )


def redirect_source(uri: str) -> str:
    """CSP source for a redirect URI: its origin, or its scheme for custom schemes (e.g. cursor:)."""
    url = urlparse(uri)
    if url.scheme in {"http", "https"} and url.netloc:
        return f"{url.scheme}://{url.netloc}"
    return f"{url.scheme}:"


def page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head><body><main>{body}</main></body></html>"
    )


def html_response(html: str, *, status: int = 200, form_action: list[str] | tuple[str, ...] = ()) -> HTMLResponse:
    return HTMLResponse(
        html,
        status_code=status,
        headers={
            "Content-Security-Policy": content_security_policy(form_action),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def error_page(message: str, *, status: int, retry_url: str | None = None, retry_label: str | None = None) -> HTMLResponse:
    body = f"<h1>Sign-in failed</h1><p>{escape(message)}</p>"
    if retry_url:
        body += f'<p><a class="button" href="{escape(retry_url)}">{escape(retry_label or "Try again")}</a></p>'
    else:
        body += '<p class="note">Close this window and start the connection again from your MCP client.</p>'
    return html_response(page("Sign-in failed", body), status=status)


def invalid_request_page() -> HTMLResponse:
    return html_response(page("Invalid request", "<h1>Invalid authorization request</h1>"), status=400)


def consent_page(*, oauth: str, ticket: str, user_name: str, client_name: str, client_id: str, redirect_uri: str) -> HTMLResponse:
    client_host = urlparse(client_id).hostname or client_id
    body = (
        "<h1>Authorize MCP client</h1>"
        f"<p><strong>{escape(client_name)}</strong> ({escape(client_host)}) wants to use this Personal Repo MCP server"
        f" as <strong>{escape(user_name)}</strong>.</p>"
        "<p class=\"note\">Approving gives the client the same full access as the server's bearer token:"
        " every repository tool, including writes and pushes.</p>"
        '<form method="post" action="/oauth/authorize">'
        f'<input type="hidden" name="oauth" value="{escape(oauth)}">'
        f'<input type="hidden" name="ticket" value="{escape(ticket)}">'
        '<button type="submit" name="action" value="approve">Approve</button>'
        '<button class="secondary" type="submit" name="action" value="deny">Deny</button></form>'
    )
    return html_response(page("Authorize MCP client", body), form_action=[redirect_source(redirect_uri)])
