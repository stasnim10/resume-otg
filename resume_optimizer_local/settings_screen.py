"""
Settings screen — account, AI settings, and help.

Rendered when screen == "settings".
"""
from __future__ import annotations

import streamlit as st

from auth_state import sign_out
from shell import render_shell_end, render_shell_start
from ui_helpers import primary_button, secondary_button


def render_settings_screen() -> None:
    render_shell_start(show_progress=False)

    st.markdown("## Settings")

    tab_account, tab_ai, tab_help = st.tabs(["Account", "AI Settings", "Help"])

    with tab_account:
        _render_account_tab()

    with tab_ai:
        _render_ai_tab()

    with tab_help:
        _render_help_tab()

    render_shell_end()


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


def _render_account_tab() -> None:
    st.markdown("### Account")
    email = st.session_state.get("auth_user_email", "")
    if email:
        st.markdown(f"**Signed in as:** {email}")
    else:
        st.caption("No account information available.")

    st.markdown("---")
    if secondary_button("Sign Out", key="settings-sign-out"):
        sign_out()
        st.rerun()


# ---------------------------------------------------------------------------
# AI Settings
# ---------------------------------------------------------------------------


def _render_ai_tab() -> None:
    from ai_gateway import PROVIDER_CONFIG
    from hosted_mode import is_hosted_web

    st.markdown("### AI Settings")

    try:
        from supabase_settings_store import (
            get_decrypted_api_key,
            get_user_settings,
            mark_api_key_valid,
            save_api_key,
        )
        settings = get_user_settings()
        use_supabase = is_hosted_web()
    except Exception:
        settings = {}
        use_supabase = False

    providers = [p for p in PROVIDER_CONFIG if p != "Advanced Custom Endpoint"]
    saved_provider = settings.get("preferred_provider", "OpenAI")
    if saved_provider not in providers:
        saved_provider = providers[0]

    provider = st.selectbox(
        "AI Provider",
        options=providers,
        index=providers.index(saved_provider),
        key="settings_provider",
    )

    models = PROVIDER_CONFIG[provider]["models"]
    saved_model = settings.get("default_model", models[0])
    if saved_model not in models:
        saved_model = models[0]

    model = st.selectbox(
        "Model",
        options=models,
        index=models.index(saved_model),
        key="settings_model",
    )

    st.markdown("---")
    st.markdown("#### API Key")

    key_last4 = settings.get("api_key_last4", "")
    key_valid = settings.get("api_key_valid", False)

    if key_last4:
        status_color = "#2d9b5a" if key_valid else "#c65347"
        status_label = "Valid" if key_valid else "Needs attention"
        st.markdown(
            f'<span style="font-weight:600;">Saved key:</span> '
            f'<code>****{key_last4}</code> '
            f'<span style="color:{status_color};font-size:0.85rem;">● {status_label}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No API key saved for this provider yet.")

    with st.expander("Update API Key" if key_last4 else "Add API Key"):
        cfg = PROVIDER_CONFIG[provider]
        new_key = st.text_input(
            cfg["key_label"],
            placeholder=cfg["placeholder"],
            type="password",
            key="settings_new_api_key",
        )
        col1, col2 = st.columns(2)
        with col1:
            if primary_button("Save Key", key="settings-save-key", disabled=not new_key.strip()):
                if use_supabase:
                    save_api_key(provider, model, new_key.strip())
                st.session_state.selected_provider = provider
                st.session_state.api_key = new_key.strip()
                st.success("API key saved.")
                st.rerun()
        with col2:
            if secondary_button("Test Connection", key="settings-test-key", disabled=not new_key.strip()):
                _test_key(provider, model, new_key.strip(), use_supabase)

    if key_last4:
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if secondary_button("Test Saved Key", key="settings-test-saved"):
                if use_supabase:
                    saved_key = get_decrypted_api_key()
                    if saved_key:
                        _test_key(provider, model, saved_key, use_supabase)
                    else:
                        st.error("Could not retrieve saved key.")
        with col_b:
            if secondary_button("Remove Key", key="settings-remove-key"):
                if use_supabase:
                    from supabase_settings_store import clear_api_key
                    clear_api_key()
                st.session_state.api_key = ""
                st.success("API key removed.")
                st.rerun()

    # Save provider/model preference even without a new key
    st.markdown("---")
    if primary_button("Save Provider & Model", key="settings-save-provider"):
        if use_supabase and key_last4:
            from supabase_settings_store import save_provider_model
            save_provider_model(provider, model)
        st.session_state.selected_provider = provider
        st.success("Preferences saved.")


def _test_key(provider: str, model: str, api_key: str, persist: bool) -> None:
    from ai_gateway import PROVIDER_CONFIG

    with st.spinner("Testing connection..."):
        try:
            _validate_key(provider, model, api_key)
            if persist:
                from supabase_settings_store import mark_api_key_valid, save_api_key
                save_api_key(provider, model, api_key)
                mark_api_key_valid(True, "Connection successful")
            st.success(f"Connected to {provider} successfully.")
        except Exception as exc:
            if persist:
                from supabase_settings_store import mark_api_key_valid
                mark_api_key_valid(False, str(exc))
            st.error(f"Connection failed: {exc}")


def _validate_key(provider: str, model: str, api_key: str) -> None:
    """Run a minimal test call to verify the key works."""
    if provider == "OpenAI":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        client.models.list()
    elif provider == "Anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        client.models.list()
    elif provider == "Gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
        list(client.models.list())
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def _render_help_tab() -> None:
    st.markdown("### Help & Support")
    st.markdown(
        """
        **Need help?**

        If you run into any issues, reach out and we'll help you out.

        - Email: [support@resumebuilderotg.com](mailto:support@resumebuilderotg.com)
        - Having a great experience? Consider [supporting the project](https://buymeacoffee.com/).
        """
    )
