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


class StreamlitSessionStorage:
    """Supabase Auth storage backed by Streamlit session state."""

    _STATE_KEY = "_sb_auth_storage"

    def _storage(self) -> dict[str, str]:
        if self._STATE_KEY not in st.session_state:
            st.session_state[self._STATE_KEY] = {}
        return st.session_state[self._STATE_KEY]

    def get_item(self, key: str) -> str | None:
        return self._storage().get(key)

    def set_item(self, key: str, value: str) -> None:
        self._storage()[key] = value

    def remove_item(self, key: str) -> None:
        self._storage().pop(key, None)


def get_config_value(key: str, default: str = "") -> str:
    """Read config from Streamlit secrets when available, otherwise env vars."""
    try:
        value = st.secrets.get(key)
    except Exception:
        value = None
    if value is None:
        value = os.environ.get(key, default)
    return str(value) if value is not None else default


def get_supabase() -> Client:
    """Return the per-user-session Supabase client, restoring auth tokens."""
    if "_sb_client" not in st.session_state:
        supabase_url = get_config_value("SUPABASE_URL")
        supabase_anon_key = get_config_value("SUPABASE_ANON_KEY")
        if not supabase_url or not supabase_anon_key:
            raise RuntimeError("Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
        client = create_client(
            supabase_url,
            supabase_anon_key,
        )
        client.auth._storage = StreamlitSessionStorage()
        client.auth.initialize_from_storage()
        st.session_state._sb_client = client

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
