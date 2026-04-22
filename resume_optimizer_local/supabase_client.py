"""
Per-session Supabase client factory.

Each Streamlit user session gets its own client instance stored in
st.session_state so auth tokens don't bleed across concurrent users.
"""
from __future__ import annotations

import logging
import os

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def get_supabase() -> Client:
    """Return the per-user-session Supabase client, restoring auth tokens."""
    if "_sb_client" not in st.session_state:
        supabase_url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        supabase_anon_key = st.secrets.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if not supabase_url or not supabase_anon_key:
            raise RuntimeError("Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
        st.session_state._sb_client = create_client(
            supabase_url,
            supabase_anon_key,
        )

    client: Client = st.session_state._sb_client

    # Restore session tokens so RLS policies work on subsequent reruns.
    access = st.session_state.get("_sb_access_token", "")
    refresh = st.session_state.get("_sb_refresh_token", "")
    if access and refresh:
        try:
            client.auth.set_session(access, refresh)
        except Exception as exc:
            logger.debug("Session restore failed (token likely expired): %s", exc)
            st.session_state._sb_access_token = ""
            st.session_state._sb_refresh_token = ""
            st.session_state.is_authenticated = False

    return client
