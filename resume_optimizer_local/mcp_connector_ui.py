"""Hosted connector setup and Supabase OAuth consent inside the existing app."""
from __future__ import annotations

import io
from uuid import UUID
from urllib.parse import urlsplit

import requests
import streamlit as st
from docx import Document

from mcp_cloud_store import BUCKET, DOCX_MIME, save_source, user_folder
from supabase_client import get_config_value, get_supabase


def auth_request(method: str, path: str, **kwargs) -> dict:
    token = st.session_state.get("_sb_access_token")
    if not token:
        raise ValueError("Sign in to Resume OTG first.")
    response = requests.request(method, get_config_value("SUPABASE_URL").rstrip("/") + "/auth/v1/" + path,
                                headers={"apikey": get_config_value("SUPABASE_ANON_KEY"), "Authorization": f"Bearer {token}"},
                                timeout=15, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else {}


def render_consent(authorization_id: str) -> None:
    st.title("Connect an AI app to Resume OTG")
    try:
        authorization_id = str(UUID(authorization_id))
        details = auth_request("GET", f"oauth/authorizations/{authorization_id}")
        if "authorization_id" not in details and details.get("redirect_url"):
            _return_to_client(details["redirect_url"])
            return
        client = details["client"]
        st.write(f"**{client.get('name') or 'AI app'}** is requesting access to your account.")
        st.write("It can read the resume you saved for MCP, tailor its wording, and create downloadable Word exports. Your provider API keys and other account data are excluded.")
        st.caption("Requested account scopes: " + (details.get("scope") or "None"))
        st.caption("Return address: " + details.get("redirect_uri", ""))
        approve, deny = st.columns(2)
        with approve:
            if st.button("Allow Connection", type="primary", key="mcp-oauth-approve"):
                get_supabase().table("mcp_connections").upsert({"user_id": st.session_state.auth_user_id,
                    "client_id": client["id"], "client_name": client.get("name", "AI app")}).execute()
                response = auth_request("POST", f"oauth/authorizations/{authorization_id}/consent", json={"action": "approve"})
                _return_to_client(response["redirect_url"])
        with deny:
            if st.button("Deny", key="mcp-oauth-deny"):
                response = auth_request("POST", f"oauth/authorizations/{authorization_id}/consent", json={"action": "deny"})
                _return_to_client(response["redirect_url"])
    except (ValueError, KeyError, requests.RequestException):
        st.error("This connection request could not be completed. Check that OAuth is configured, or restart the connection from your AI app.")


def _return_to_client(url: str) -> None:
    if urlsplit(url).scheme not in ("https", "http"):
        st.error("The connector returned an unsupported address.")
        return
    st.success("Your decision was saved.")
    st.link_button("Continue to your AI app", url)


def render_hosted_connector() -> None:
    public_url = get_config_value("MCP_PUBLIC_URL")
    st.markdown("### Connect with a link")
    if not public_url:
        st.info("The remote connector is being prepared. It needs its own Render service and Supabase OAuth setup before a connection link is available.")
        st.caption("Planned server address: https://mcp.resumeotg.app/mcp — not live yet.")
        return
    st.write("In your AI app, add a custom connector named **Resume OTG**, paste this MCP server URL, then sign in and approve access.")
    st.code(public_url, language=None)
    st.caption("Your AI app supplies the model. Save a Word resume once, then paste a job link or description in the connected AI chat.")
    uid = st.session_state.get("auth_user_id")
    if not uid:
        st.info("Sign in to save your resume for the connector.")
        return
    client = get_supabase()
    uploaded = st.file_uploader("Resume for connected AI apps", type=["docx"], key="mcp-cloud-source")
    if uploaded and st.button("Save Resume for Connector", key="mcp-cloud-save", type="primary"):
        try:
            contents = uploaded.getvalue()
            if len(contents) > 10 * 1024 * 1024:
                raise ValueError("Resume is too large.")
            Document(io.BytesIO(contents))
            save_source(client, uid, contents)
            st.success("Resume saved privately to your account.")
        except Exception:
            st.error("Could not save the resume. Use a valid Word document under 10 MB and check the storage setup.")
    st.caption("Sharing applies to the resume saved here. Check exported wording before using it.")
    try:
        connections = client.table("mcp_connections").select("client_id,client_name").eq("user_id", uid).execute().data
        for connection in connections:
            col_name, col_revoke = st.columns([3, 1])
            col_name.write(connection["client_name"] or "Connected AI app")
            if col_revoke.button("Disconnect", key="mcp-revoke-" + connection["client_id"]):
                # Delete approval first: existing MCP tokens immediately lose tool access.
                client.table("mcp_connections").delete().eq("user_id", uid).eq("client_id", connection["client_id"]).execute()
                try:
                    auth_request("DELETE", "user/oauth/grants", params={"client_id": connection["client_id"]})
                except requests.RequestException:
                    pass
                st.rerun()
        files = client.storage.from_(BUCKET).list(f"{user_folder(uid)}/exports", {"limit": 100, "sortBy": {"column": "created_at", "order": "desc"}})
        names = [item["name"] for item in files if item.get("name", "").endswith(".docx")]
        if names:
            selected = st.selectbox("Tailored resume", names, key="mcp-cloud-export")
            if st.button("Prepare Download", key="mcp-cloud-prepare-download"):
                contents = client.storage.from_(BUCKET).download(f"{user_folder(uid)}/exports/{selected}")
                st.download_button("Download Word Resume", contents, file_name=selected, mime=DOCX_MIME)
    except Exception:
        st.info("Connector storage is not available yet. Complete the Supabase migration before using uploads and exports.")
