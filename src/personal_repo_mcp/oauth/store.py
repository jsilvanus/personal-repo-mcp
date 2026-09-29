from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


def _hash(value: str) -> str:
    # Codes, refresh tokens and OIDC states are stored only as SHA-256 hashes.
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Identity:
    """The signed-in person: the OIDC issuer + subject pair, plus a display name."""

    issuer: str
    subject: str
    name: str


@dataclass(frozen=True, slots=True)
class AuthorizationCode:
    client_id: str
    redirect_uri: str
    challenge: str
    identity: Identity
    scope: str


@dataclass(frozen=True, slots=True)
class RefreshToken:
    client_id: str
    identity: Identity
    scope: str


@dataclass(frozen=True, slots=True)
class OidcLoginState:
    verifier: str
    nonce: str
    purpose: str
    oauth: str | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
  code_hash TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  challenge TEXT NOT NULL,
  idp TEXT NOT NULL,
  subject TEXT NOT NULL,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,
  expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
  token_hash TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  idp TEXT NOT NULL,
  subject TEXT NOT NULL,
  name TEXT NOT NULL,
  scope TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS oidc_login_states (
  state_hash TEXT PRIMARY KEY,
  verifier TEXT NOT NULL,
  nonce TEXT NOT NULL,
  purpose TEXT NOT NULL,
  oauth TEXT,
  expires INTEGER NOT NULL
);
"""


class OAuthStore:
    """SQLite storage for authorization codes, refresh tokens and pending OIDC sign-ins.

    All statements are parameterised. One connection guarded by a lock is enough for
    this single-process server; every operation is a short local transaction.
    """

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Authorization codes -------------------------------------------------

    def save_authorization_code(self, code: str, record: AuthorizationCode, ttl: int = 60) -> None:
        now = int(time.time())
        with self._lock:
            self._db.execute("DELETE FROM oauth_authorization_codes WHERE expires < ?", (now,))
            self._db.execute(
                "INSERT INTO oauth_authorization_codes (code_hash, client_id, redirect_uri, challenge, idp, subject, name, scope, expires)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _hash(code), record.client_id, record.redirect_uri, record.challenge,
                    record.identity.issuer, record.identity.subject, record.identity.name, record.scope, now + ttl,
                ),
            )

    def consume_authorization_code(self, code: str) -> AuthorizationCode | None:
        """Return the code's record once; the code is deleted whether or not it is still valid."""
        key = _hash(code)
        with self._lock:
            row = self._db.execute(
                "SELECT client_id, redirect_uri, challenge, idp, subject, name, scope, expires"
                " FROM oauth_authorization_codes WHERE code_hash = ?",
                (key,),
            ).fetchone()
            self._db.execute("DELETE FROM oauth_authorization_codes WHERE code_hash = ?", (key,))
        if row is None or row[7] < time.time():
            return None
        return AuthorizationCode(
            client_id=row[0], redirect_uri=row[1], challenge=row[2],
            identity=Identity(issuer=row[3], subject=row[4], name=row[5]), scope=row[6],
        )

    # Refresh tokens ------------------------------------------------------

    def save_refresh_token(self, token: str, record: RefreshToken, ttl: int = 30 * 86_400) -> None:
        now = int(time.time())
        with self._lock:
            self._db.execute("DELETE FROM oauth_refresh_tokens WHERE expires < ?", (now,))
            self._db.execute(
                "INSERT INTO oauth_refresh_tokens (token_hash, client_id, idp, subject, name, scope, created_at, expires)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _hash(token), record.client_id, record.identity.issuer, record.identity.subject,
                    record.identity.name, record.scope, now, now + ttl,
                ),
            )

    def get_refresh_token(self, token: str) -> RefreshToken | None:
        key = _hash(token)
        with self._lock:
            row = self._db.execute(
                "SELECT client_id, idp, subject, name, scope, expires FROM oauth_refresh_tokens WHERE token_hash = ?",
                (key,),
            ).fetchone()
            if row is not None and row[5] < time.time():
                self._db.execute("DELETE FROM oauth_refresh_tokens WHERE token_hash = ?", (key,))
                return None
        if row is None:
            return None
        return RefreshToken(
            client_id=row[0], identity=Identity(issuer=row[1], subject=row[2], name=row[3]), scope=row[4],
        )

    # Pending OIDC sign-ins -----------------------------------------------

    def save_oidc_state(self, state: str, record: OidcLoginState, ttl: int = 600) -> None:
        now = int(time.time())
        with self._lock:
            self._db.execute("DELETE FROM oidc_login_states WHERE expires < ?", (now,))
            self._db.execute(
                "INSERT INTO oidc_login_states (state_hash, verifier, nonce, purpose, oauth, expires) VALUES (?, ?, ?, ?, ?, ?)",
                (_hash(state), record.verifier, record.nonce, record.purpose, record.oauth, now + ttl),
            )

    def consume_oidc_state(self, state: str) -> OidcLoginState | None:
        """Single use: the row is deleted on first lookup."""
        key = _hash(state)
        with self._lock:
            row = self._db.execute(
                "SELECT verifier, nonce, purpose, oauth, expires FROM oidc_login_states WHERE state_hash = ?",
                (key,),
            ).fetchone()
            self._db.execute("DELETE FROM oidc_login_states WHERE state_hash = ?", (key,))
        if row is None or row[4] < time.time():
            return None
        return OidcLoginState(verifier=row[0], nonce=row[1], purpose=row[2], oauth=row[3])
