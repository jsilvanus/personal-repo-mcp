from __future__ import annotations

import json

import pytest

from personal_repo_mcp.oauth.cimd import CimdError, _private_address, is_cimd_client_id, parse_cimd_document


@pytest.mark.parametrize(
    ("client_id", "ok"),
    [
        ("https://chatgpt.com/oauth/client.json", True),
        ("http://chatgpt.com/oauth/client.json", False),
        ("https://chatgpt.com/", False),
        ("https://user:pw@chatgpt.com/c.json", False),
        ("https://chatgpt.com/c.json?x=1", False),
        ("https://chatgpt.com/c.json#frag", False),
        ("https://chatgpt.com/a/../c.json", False),
        ("not a url", False),
    ],
)
def test_is_cimd_client_id(client_id: str, ok: bool) -> None:
    assert is_cimd_client_id(client_id) is ok


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "192.168.0.1", "172.16.0.1", "169.254.1.1", "::1", "fd00::1", "::ffff:127.0.0.1", "0.0.0.0"])
def test_private_addresses(address: str) -> None:
    assert _private_address(address)


def test_public_address() -> None:
    assert not _private_address("93.184.215.14")


def test_parse_document() -> None:
    cid = "https://client.example/c.json"
    doc = parse_cimd_document(cid, json.dumps({"client_id": cid, "client_name": "C", "redirect_uris": ["https://client.example/cb"]}))
    assert doc.redirect_uris == ("https://client.example/cb",)
    with pytest.raises(CimdError):
        parse_cimd_document(cid, json.dumps({"client_id": "https://other.example/c.json", "client_name": "C", "redirect_uris": []}))
    with pytest.raises(CimdError):
        parse_cimd_document(cid, b"{")
