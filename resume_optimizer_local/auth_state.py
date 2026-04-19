"""
Supabase authentication helpers for Streamlit.

All public functions read/write st.session_state so they work correctly
across Streamlit reruns without re-authenticating on every page interaction.
"""
from __future__ import annotations

import logging

import streamlit as st

from supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sign-in / sign-up
# ---------------------------------------------------------------------------


def sign_in_with_password(email: str, password: str) -> None:
    """Sign in with email + password. Raises on failure."""
    resp = get_supabase().auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    if resp.session and resp.user:
        _store_session(resp.session, resp.user)
    else:
        raise ValueError("Sign-in returned no session. Check your credentials.")


def sign_up_with_password(email: str, password: str) -> bool:
    """
    Create a new account with email + password.

    Returns True if a session was established immediately (email confirmation
    disabled), False if the user must confirm their email first.
    """
    resp = get_supabase().auth.sign_up(
        {"email": email.strip(), "password": password}
    )
    if resp.session and resp.user:
        _store_session(resp.session, resp.user)
        return True
    # Supabase returns a user but no session when email confirmation is required.
    return False


def sign_out() -> None:
    """Sign out and wipe auth tokens from session state."""
    try:
        get_supabase().auth.sign_out()
    except Exception as exc:
        logger.debug("sign_out error (ignored): %s", exc)
    for key in ("_sb_access_token", "_sb_refresh_token", "auth_user_id", "auth_user_email"):
        st.session_state[key] = ""
    st.session_state.is_authenticated = False


# ---------------------------------------------------------------------------
# Session hydration (called on every page load)
# ---------------------------------------------------------------------------


def load_auth_into_session() -> bool:
    """
    Re-hydrate auth state from stored tokens.

    Called at the top of main() on every Streamlit rerun.
    Returns True if the user is (still) authenticated.
    """
    access = st.session_state.get("_sb_access_token", "")
    refresh = st.session_state.get("_sb_refresh_token", "")
    if not (access and refresh):
        return False
    try:
        # get_session() refreshes the access token automatically if expired.
        resp = get_supabase().auth.get_session()
        if resp and resp.user:
            st.session_state.auth_user_id = resp.user.id
            st.session_state.auth_user_email = resp.user.email
            st.session_state.is_authenticated = True
            # Persist any refreshed tokens
            if resp.session:
                st.session_state._sb_access_token = resp.session.access_token
                st.session_state._sb_refresh_token = resp.session.refresh_token
            return True
    except Exception as exc:
        logger.debug("Session refresh failed: %s", exc)
    st.session_state.is_authenticated = False
    return False


def is_authenticated() -> bool:
    """Return True if the current Streamlit session has a valid auth user."""
    return bool(st.session_state.get("is_authenticated", False))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _store_session(session, user) -> None:
    st.session_state._sb_access_token = session.access_token
    st.session_state._sb_refresh_token = session.refresh_token
    st.session_state.auth_user_id = user.id
    st.session_state.auth_user_email = user.email
    st.session_state.is_authenticated = True
