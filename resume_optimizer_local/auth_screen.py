"""
Authentication screen — sign in / sign up UI.

Rendered by main() when the user has no active session in hosted web mode.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from auth_state import (
    get_google_implicit_oauth_url,
    send_password_reset_email,
    sign_in_with_password,
    sign_up_with_password,
    update_password,
)


def render_auth_screen() -> None:
    """Full-page login / sign-up form."""
    logo_path = Path(__file__).resolve().parent / "assets" / "Resume_Optimizer_Logo.png"
    st.markdown(
        """
        <style>
        .auth-wrap { max-width: 520px; margin: 2.5rem auto 0 auto; text-align: center; }
        .auth-logo-wrap { display: flex; justify-content: center; margin: 0 auto 1rem auto; width: 100%; }
        .auth-logo-image { display: block; width: 118px; height: auto; margin: 0 auto; }
        .auth-title { font-size: 2.65rem; font-weight: 800; letter-spacing: -0.03em; margin-bottom: 0.35rem; line-height: 1.05; }
        .auth-sub { color: var(--muted); font-size: 1rem; margin-bottom: 2.25rem; }
        .auth-panel { max-width: 680px; margin: 0 auto; }
        .st-key-forgot_password_email input {
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          background: var(--input-fill) !important;
        }
        .st-key-forgot_password_email input::placeholder {
          color: var(--muted) !important;
          -webkit-text-fill-color: var(--muted) !important;
          opacity: 1 !important;
        }
        .st-key-forgot-password-button button {
          background: var(--surface) !important;
          color: var(--text) !important;
          border: 1px solid var(--line-strong) !important;
        }
        .st-key-forgot-password-button button * {
          color: var(--text) !important;
          fill: var(--text) !important;
          opacity: 1 !important;
        }
        .auth-panel [data-testid="stHorizontalBlock"] {
          align-items: flex-start !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    logo_markup = ""
    if logo_path.exists():
        logo_bytes = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        logo_markup = (
            '<div class="auth-logo-wrap">'
            f'<img class="auth-logo-image" src="data:image/png;base64,{logo_bytes}" alt="Resume OTG logo" />'
            "</div>"
        )
    st.markdown(
        f"""
        <div class="auth-wrap">
          {logo_markup}
          <div class="auth-title">Resume OTG</div>
          <div class="auth-sub">Sign in to continue to your account.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="auth-panel">', unsafe_allow_html=True)
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            _render_auth_notices()
            if st.session_state.get("auth_recovery_mode", False):
                _render_password_reset()
            else:
                _render_google_sign_in()
                tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

                with tab_in:
                    _render_sign_in()

                with tab_up:
                    _render_sign_up()
        st.markdown("</div>", unsafe_allow_html=True)


def _render_auth_notices() -> None:
    success_message = st.session_state.pop("auth_notice_success", "")
    error_message = st.session_state.pop("auth_notice_error", "")
    if success_message:
        st.success(success_message)
    if error_message:
        st.error(error_message)


def _render_google_sign_in() -> None:
    st.markdown("#### Continue with Google")
    st.caption("Use your Google account for a faster sign-in.")
    components.html(
        """
        <script>
          (function() {
            const topWindow = window.top || window.parent || window;
            const currentUrl = new URL(topWindow.location.href);
            const hash = (topWindow.location.hash || "").replace(/^#/, "");
            if (!hash) {
              return;
            }

            const hashParams = new URLSearchParams(hash);
            const accessToken = hashParams.get("access_token");
            const refreshToken = hashParams.get("refresh_token");
            const hashError = hashParams.get("error_description") || hashParams.get("error");

            if (hashError) {
              currentUrl.hash = "";
              currentUrl.searchParams.set("oauth_error", hashError);
              topWindow.location.replace(currentUrl.toString());
              return;
            }

            if (accessToken && refreshToken) {
              currentUrl.hash = "";
              currentUrl.searchParams.set("sb_access_token", accessToken);
              currentUrl.searchParams.set("sb_refresh_token", refreshToken);
              topWindow.location.replace(currentUrl.toString());
            }
          })();
        </script>
        """,
        height=0,
    )
    try:
        oauth_url = get_google_implicit_oauth_url()
    except Exception as exc:
        st.info(f"Google sign-in is unavailable right now: {exc}")
        return

    st.markdown(
        f"""
        <div style="width:100%; margin: 0.35rem 0 0.85rem 0;">
          <a
            href="{oauth_url}"
            target="_self"
            style="
              display:flex;
              align-items:center;
              justify-content:center;
              width:100%;
              min-height:54px;
              border-radius:999px;
              border:1px solid rgba(127,127,127,0.22);
              background:#ffffff;
              color:#111111;
              font-weight:600;
              font-size:1rem;
              text-decoration:none;
            "
          >
            Continue with Google
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align:center; color:#777; font-size:0.9rem; margin:0.6rem 0 1.1rem 0;'>or use email</div>",
        unsafe_allow_html=True,
    )


def _render_sign_in() -> None:
    with st.form("auth_sign_in_form", clear_on_submit=False):
        st.markdown("#### Sign In")
        email = st.text_input("Email", placeholder="you@example.com", key="signin_email")
        password = st.text_input("Password", type="password", key="signin_password")
        submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

    if submitted:
        if not email.strip() or not password:
            st.error("Enter your email and password.")
            return
        try:
            sign_in_with_password(email, password)
            st.rerun()
        except Exception as exc:
            msg = str(exc)
            if "invalid" in msg.lower() or "credentials" in msg.lower():
                st.error("Incorrect email or password.")
            else:
                st.error(f"Sign-in failed: {msg}")

    forgot_email = st.text_input(
        "Forgot your password?",
        placeholder="Enter your email to receive a reset link",
        key="forgot_password_email",
        label_visibility="visible",
    )
    if st.button("Send password reset email", use_container_width=True, key="forgot-password-button"):
        if not forgot_email.strip():
            st.error("Enter your email address so we know where to send the reset link.")
            return
        try:
            send_password_reset_email(forgot_email)
            st.success("Password reset email sent. Check your inbox and follow the link to choose a new password.")
        except Exception as exc:
            st.error(f"Could not send password reset email: {exc}")


def _render_sign_up() -> None:
    with st.form("auth_sign_up_form", clear_on_submit=False):
        st.markdown("#### Create Account")
        email = st.text_input("Email", placeholder="you@example.com", key="signup_email")
        password = st.text_input(
            "Password",
            type="password",
            key="signup_password",
            help="Minimum 6 characters.",
        )
        password2 = st.text_input("Confirm Password", type="password", key="signup_password2")
        submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

    if submitted:
        if not email.strip():
            st.error("Enter an email address.")
            return
        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return
        if password != password2:
            st.error("Passwords do not match.")
            return
        try:
            session_ready = sign_up_with_password(email, password)
            if session_ready:
                st.rerun()
            else:
                st.success(
                    "Account created! Check your email for a confirmation link, "
                    "then return here to sign in."
                )
        except Exception as exc:
            msg = str(exc)
            if "already registered" in msg.lower() or "already exists" in msg.lower():
                st.error("An account with this email already exists. Try signing in.")
            else:
                st.error(f"Sign-up failed: {msg}")


def _render_password_reset() -> None:
    with st.form("auth_password_reset_form", clear_on_submit=False):
        st.markdown("#### Reset Password")
        password = st.text_input(
            "New Password",
            type="password",
            key="reset_password",
            help="Minimum 6 characters.",
        )
        password2 = st.text_input(
            "Confirm New Password",
            type="password",
            key="reset_password_confirm",
        )
        submitted = st.form_submit_button("Update Password", use_container_width=True, type="primary")

    if submitted:
        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return
        if password != password2:
            st.error("Passwords do not match.")
            return
        try:
            update_password(password)
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update password: {exc}")
