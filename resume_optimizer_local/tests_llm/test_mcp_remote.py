"""Run with the optional remote MCP requirements installed."""
import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
jwt = pytest.importorskip("jwt")
pytest.importorskip("mcp")
pytest.importorskip("supabase")
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from mcp_remote_server import SupabaseVerifier, create_remote_server
from mcp_cloud_store import export_path

RESOURCE = "https://mcp.resumeotg.app/mcp"
ISSUER = "https://example.supabase.co/auth/v1"


def test_verifier_requires_resource_audience_and_oauth_client():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SupabaseVerifier("https://example.supabase.co", RESOURCE)
    verifier.keys = Mock()
    verifier.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    claims = {"iss": ISSUER, "aud": ["authenticated", RESOURCE], "sub": "user-id",
              "exp": int(time.time()) + 300, "role": "authenticated", "client_id": "client-id"}
    token = jwt.encode(claims, key, algorithm="RS256")
    assert asyncio.run(verifier.verify_token(token)).subject == "user-id"
    for changed in ({"aud": "authenticated"}, {"exp": 1}, {"iss": "https://wrong.example"}, {"client_id": ""}):
        invalid = jwt.encode({**claims, **changed}, key, algorithm="RS256")
        assert asyncio.run(verifier.verify_token(invalid)) is None


def test_remote_discovery_and_unauthenticated_challenge(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "placeholder")
    monkeypatch.setenv("MCP_PUBLIC_URL", RESOURCE)
    server = create_remote_server()
    with TestClient(server.streamable_http_app(), base_url="https://mcp.resumeotg.app") as client:
        assert client.get("/health").status_code == 200
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == RESOURCE
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert response.status_code == 401
        assert "resource_metadata" in response.headers["www-authenticate"]


def test_cloud_export_paths_are_user_scoped():
    first = "00000000-0000-0000-0000-000000000001"
    second = "00000000-0000-0000-0000-000000000002"
    export_id = "a" * 32
    assert export_path(first, export_id) != export_path(second, export_id)
    with pytest.raises(ValueError):
        export_path(first, "../../other-user/source")
