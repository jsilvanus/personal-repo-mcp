"""Client ID Metadata Documents (CIMD): the OAuth client_id is an HTTPS URL of its metadata."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx2

MAX_BYTES = 64 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 5.0


class CimdError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CimdMetadata:
    client_id: str
    client_name: str
    redirect_uris: tuple[str, ...]
    extra: dict = field(default_factory=dict)


def is_cimd_client_id(client_id: str) -> bool:
    try:
        url = urlparse(client_id)
    except ValueError:
        return False
    return (
        url.scheme == "https"
        and bool(url.hostname)
        and url.path not in {"", "/"}
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment
        and ".." not in url.path.split("/")
    )


def _private_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not ip.is_global


async def _assert_public_host(hostname: str) -> None:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise CimdError("CIMD host cannot be resolved") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or any(_private_address(address) for address in addresses):
        raise CimdError("CIMD host resolves to a private address")


async def fetch_cimd_metadata(client_id: str) -> CimdMetadata:
    """Fetch and validate a client's metadata document with SSRF-oriented limits."""
    if not is_cimd_client_id(client_id):
        raise CimdError("Invalid CIMD client_id")
    current = client_id
    async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        for attempt in range(MAX_REDIRECTS + 1):
            await _assert_public_host(urlparse(current).hostname or "")
            async with client.stream("GET", current, headers={"accept": "application/json"}) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location or attempt == MAX_REDIRECTS:
                        raise CimdError("Invalid CIMD redirect")
                    current = urljoin(current, location)
                    if not is_cimd_client_id(current):
                        raise CimdError("Invalid CIMD redirect")
                    continue
                if response.status_code != 200:
                    raise CimdError("Unable to fetch CIMD document")
                length = response.headers.get("content-length")
                if length and length.isdigit() and int(length) > MAX_BYTES:
                    raise CimdError("CIMD document is too large")
                body = b""
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise CimdError("CIMD document is too large")
                return parse_cimd_document(client_id, body)
    raise CimdError("Unable to fetch CIMD document")


def parse_cimd_document(client_id: str, body: bytes | str) -> CimdMetadata:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CimdError("Invalid CIMD document") from exc
    if not isinstance(value, dict):
        raise CimdError("Invalid CIMD document")
    redirect_uris = value.get("redirect_uris")
    if (
        value.get("client_id") != client_id
        or not isinstance(value.get("client_name"), str)
        or not isinstance(redirect_uris, list)
        or not all(isinstance(uri, str) for uri in redirect_uris)
    ):
        raise CimdError("Invalid CIMD document")
    extra = {key: value[key] for key in ("grant_types", "response_types", "token_endpoint_auth_method") if key in value}
    return CimdMetadata(client_id=client_id, client_name=value["client_name"], redirect_uris=tuple(redirect_uris), extra=extra)
