"""
Supabase authentication helpers for Streamlit.

All public functions read/write st.session_state so they work correctly
across Streamlit reruns without re-authenticating on every page interaction.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import streamlit as st

from supabase_client import get_config_value, get_supabase

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


def get_google_oauth_url() -> str:
    """Build the Supabase OAuth URL for Google sign-in."""
    redirect_to = _get_oauth_redirect_url()
    resp = get_supabase().auth.sign_in_with_oauth(
        {
            "provider": "google",
            "options": {
                "redirect_to": redirect_to,
                "scopes": "email profile",
                "query_params": {"access_type": "offline", "prompt": "select_account"},
            },
        }
    )
    return resp.url


def handle_oauth_callback() -> bool:
    """
    Complete a pending OAuth redirect if the current URL contains auth params.

    Returns True when the callback was handled and triggered a rerun.
    """
    query_params = st.query_params
    auth_code = query_params.get("code")
    error = query_params.get("error")
    error_description = query_params.get("error_description")

    if error:
        message = str(error_description or error).replace("+", " ")
        st.session_state.auth_notice_error = f"Google sign-in failed: {message}"
        _clear_auth_query_params()
        return False

    if not auth_code:
        return False

    try:
        resp = get_supabase().auth.exchange_code_for_session(
            {
                "auth_code": auth_code,
                "redirect_to": _get_oauth_redirect_url(),
            }
        )
        if resp.session and resp.user:
            _store_session(resp.session, resp.user)
            st.session_state.auth_notice_success = "Signed in with Google."
            _clear_auth_query_params()
            st.rerun()
        raise ValueError("Google sign-in returned no session.")
    except Exception as exc:
        logger.warning("OAuth callback failed: %s", exc)
        st.session_state.auth_notice_error = f"Google sign-in failed: {exc}"
        _clear_auth_query_params()
        return False


def send_password_reset_email(email: str) -> None:
    """Send a Supabase password reset email to the user."""
    get_supabase().auth.reset_password_for_email(
        email.strip(),
        {"redirect_to": _get_oauth_redirect_url()},
    )


def handle_password_recovery_callback() -> bool:
    """
    Complete a password recovery redirect and hold the user in reset mode.

    Returns True when a recovery session was established.
    """
    query_params = st.query_params
    token_hash = query_params.get("token_hash")
    recovery_type = query_params.get("type")

    if not token_hash or recovery_type != "recovery":
        return False

    try:
        resp = get_supabase().auth.verify_otp(
            {
                "token_hash": token_hash,
                "type": "recovery",
            }
        )
        if resp.session and resp.user:
            _store_session(resp.session, resp.user)
            st.session_state.auth_recovery_mode = True
            st.session_state.auth_notice_success = "Choose a new password to finish resetting your account."
            _clear_auth_query_params()
            st.rerun()
        raise ValueError("Password reset link did not create a session.")
    except Exception as exc:
        logger.warning("Password recovery failed: %s", exc)
        st.session_state.auth_notice_error = f"Password reset link is invalid or expired: {exc}"
        st.session_state.auth_recovery_mode = False
        _clear_auth_query_params()
        return False


def update_password(new_password: str) -> None:
    """Update the current user's password after a recovery flow."""
    user_resp = get_supabase().auth.update_user({"password": new_password})
    user = getattr(user_resp, "user", None)
    if not user:
        raise ValueError("Password update did not return a user.")
    st.session_state.auth_user_id = user.id
    st.session_state.auth_user_email = user.email
    st.session_state.is_authenticated = True
    st.session_state.auth_recovery_mode = False
    st.session_state.auth_notice_success = "Password updated successfully."


def sign_out() -> None:
    """Sign out and wipe auth tokens from session state."""
    try:
        get_supabase().auth.sign_out()
    except Exception as exc:
        logger.debug("sign_out error (ignored): %s", exc)
    for key in ("_sb_access_token", "_sb_refresh_token", "auth_user_id", "auth_user_email"):
        st.session_state[key] = ""
    st.session_state.is_authenticated = False
    st.session_state.auth_recovery_mode = False


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
        client = get_supabase()

        # First validate the token directly. This is the most reliable path in
        # Streamlit because reruns don't always preserve the SDK's in-memory
        # session shape the same way a browser SPA would.
        user_resp = client.auth.get_user(access)
        user = getattr(user_resp, "user", None)
        if user:
            st.session_state.auth_user_id = user.id
            st.session_state.auth_user_email = user.email
            st.session_state.is_authenticated = True
            st.session_state._sb_access_token = access
            st.session_state._sb_refresh_token = refresh
            return True

        # Fallback: consult the SDK-managed session if present.
        resp = client.auth.get_session()
        session = getattr(resp, "session", None)
        user = getattr(session, "user", None) if session else None
        if session and user:
            st.session_state.auth_user_id = user.id
            st.session_state.auth_user_email = user.email
            st.session_state.is_authenticated = True
            st.session_state._sb_access_token = session.access_token
            st.session_state._sb_refresh_token = session.refresh_token
            return True
    except Exception as exc:
        logger.warning("Session refresh failed: %s", exc)
    for key in ("_sb_access_token", "_sb_refresh_token", "auth_user_id", "auth_user_email"):
        st.session_state[key] = ""
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


def _get_oauth_redirect_url() -> str:
    """
    Resolve the absolute URL Supabase should redirect back to after OAuth.

    `SUPABASE_OAUTH_REDIRECT_TO` can override the detected app URL when the
    deployment sits behind a custom proxy/CDN.
    """
    configured = get_config_value("SUPABASE_OAUTH_REDIRECT_TO")
    if configured:
        return configured

    current_url = getattr(st.context, "url", "") or ""
    if current_url:
        parts = urlsplit(str(current_url))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    headers = getattr(st.context, "headers", {}) or {}
    host = headers.get("host", "")
    proto = headers.get("x-forwarded-proto", "https" if host else "")
    if host and proto:
        return f"{proto}://{host}"

    raise RuntimeError(
        "Unable to determine the app URL for Google sign-in. "
        "Set SUPABASE_OAUTH_REDIRECT_TO in your Streamlit secrets or environment."
    )


def _clear_auth_query_params() -> None:
    for key in (
        "code",
        "error",
        "error_code",
        "error_description",
        "provider_token",
        "provider_refresh_token",
    ):
        try:
            del st.query_params[key]
        except Exception:
            pass
