"""
Authentication screen — sign in / sign up UI.

Rendered by main() when the user has no active session in hosted web mode.
"""
from __future__ import annotations

import streamlit as st

from auth_state import sign_in_with_password, sign_up_with_password


def render_auth_screen() -> None:
    """Full-page login / sign-up form."""
    st.markdown(
        """
        <style>
        .auth-wrap { max-width: 420px; margin: 5rem auto 0 auto; }
        .auth-title { font-size: 1.7rem; font-weight: 700; margin-bottom: 0.25rem; }
        .auth-sub { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
        </style>
        <div class="auth-wrap">
          <div class="auth-title">Resume OTG</div>
          <div class="auth-sub">Sign in to continue to your account.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

            with tab_in:
                _render_sign_in()

            with tab_up:
                _render_sign_up()


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
