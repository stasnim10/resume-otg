"""
Per-session Supabase client factory.

Each Streamlit user session gets its own client instance stored in
st.session_state so auth tokens don't bleed across concurrent users.
"""
from __future__ import annotations

import logging

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def get_supabase() -> Client:
    """Return the per-user-session Supabase client, restoring auth tokens."""
    if "_sb_client" not in st.session_state:
        st.session_state._sb_client = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_ANON_KEY"],
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
