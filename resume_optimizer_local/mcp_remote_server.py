"""OAuth-protected Streamable HTTP service; deploy separately from Streamlit."""
from __future__ import annotations

import asyncio
import os
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
from jwt import PyJWKClient
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from supabase import ClientOptions, create_client

from mcp_cloud_store import BUCKET, export_path, read_source, save_export
from mcp_resume_service import build_export, prepare_resume


class SupabaseVerifier(TokenVerifier):
    def __init__(self, supabase_url: str, resource_url: str):
        self.issuer = supabase_url.rstrip("/") + "/auth/v1"
        self.resource_url = resource_url
        self.keys = PyJWKClient(self.issuer + "/.well-known/jwks.json")

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(token, key.key, algorithms=["RS256", "ES256"],
                                issuer=self.issuer, audience=self.resource_url,
                                options={"require": ["exp", "iss", "aud", "sub", "client_id"]})
            if claims.get("role") != "authenticated" or not claims.get("client_id"):
                return None
            return AccessToken(token=token, client_id=claims["client_id"], subject=claims["sub"],
                               scopes=claims.get("scope", "").split(), expires_at=claims["exp"],
                               resource=self.resource_url)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None


def create_remote_server() -> FastMCP:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    resource = os.environ["MCP_PUBLIC_URL"].rstrip("/")
    parsed = urlsplit(resource)
    if parsed.scheme != "https" or parsed.path != "/mcp" or parsed.query or parsed.fragment:
        raise ValueError("MCP_PUBLIC_URL must be the public HTTPS /mcp URL.")
    verifier = SupabaseVerifier(supabase_url, resource)
    server = FastMCP(
        "Resume OTG", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
        stateless_http=True, json_response=True, token_verifier=verifier,
        auth=AuthSettings(issuer_url=verifier.issuer, resource_server_url=resource, validate_token_resource=True),
        transport_security=TransportSecuritySettings(
            allowed_hosts=[parsed.netloc, "127.0.0.1:*", "localhost:*"],
            allowed_origins=[f"https://{parsed.netloc}"],
        ),
    )

    def scoped_client():
        token = get_access_token()
        if token is None or not token.subject:
            raise ValueError("Sign in to Resume OTG to use this connector.")
        # New client per request: never share auth state across accounts.
        client = create_client(supabase_url, anon_key, options=ClientOptions(headers={"Authorization": f"Bearer {token.token}"}))
        approvals = client.table("mcp_connections").select("client_id").eq("user_id", token.subject).eq("client_id", token.client_id).execute()
        if not approvals.data:
            raise ValueError("This connector was revoked or has not been approved in Resume OTG.")
        return client, token.subject

    @server.tool()
    def prepare_resume_for_job(job: str) -> dict:
        """Read your saved resume and a job URL or description; follow the returned instructions, then export."""
        client, uid = scoped_client()
        return prepare_resume(job, source=read_source(client, uid))

    @server.tool()
    def export_tailored_resume(payload: dict, resume_sha256: str) -> dict:
        """Apply truthful paragraph replacements and return a Word download link valid for 10 minutes."""
        client, uid = scoped_client()
        _, source = read_source(client, uid)
        contents, count = build_export(payload, resume_sha256, source)
        export_id = uuid4().hex
        url = save_export(client, uid, export_id, contents)
        return {"export_id": export_id, "download_url": url,
                "resource_uri": f"resume-otg://exports/{export_id}", "replaced_paragraphs": count,
                "download_expires_in_seconds": 600}

    @server.resource("resume-otg://exports/{export_id}", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    def download_resume(export_id: str) -> bytes:
        client, uid = scoped_client()
        return client.storage.from_(BUCKET).download(export_path(uid, export_id))

    @server.custom_route("/health", methods=["GET"])
    async def health(request):
        return JSONResponse({"status": "ok"})

    return server


if __name__ == "__main__":
    create_remote_server().run(transport="streamable-http")
