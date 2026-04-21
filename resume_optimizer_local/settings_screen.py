"""
Settings screen — account, AI settings, and help.

Rendered when screen == "settings".
"""
from __future__ import annotations

import streamlit as st

from auth_state import sign_out
from help_widget import CONTACT_EMAIL, DONATE_URL
from help_widget import render_help_section
from shell import render_shell_end, render_shell_start
from ui_helpers import primary_button, secondary_button


def render_settings_screen() -> None:
    render_shell_start()

    st.markdown("## Settings")

    if st.session_state.get("settings_open_help"):
        st.info("You can find guided help and contact options in the Help tab below.")

    tab_account, tab_ai, tab_help = st.tabs(["Account", "AI Settings", "Help"])

    with tab_account:
        _render_account_tab()

    with tab_ai:
        _render_ai_tab()

    with tab_help:
        _render_help_tab()

    render_shell_end()


def render_help_screen() -> None:
    """Standalone help destination for the sidebar."""
    render_shell_start()
    st.markdown("## Help")
    st.markdown(
        '<p style="font-size:0.96rem;color:var(--muted);max-width:760px;">'
        "Use this page as your guided walkthrough. Each section explains what the app does, what to upload, and what to do if something looks off."
        "</p>",
        unsafe_allow_html=True,
    )
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

    use_supabase = is_hosted_web()
    all_key_info: dict[str, dict] = {}
    if use_supabase:
        try:
            from supabase_settings_store import get_all_provider_key_info
            all_key_info = get_all_provider_key_info()
        except Exception:
            pass

    providers = [p for p in PROVIDER_CONFIG if p != "Advanced Custom Endpoint"]

    st.markdown(
        '<p style="font-size:0.9rem;color:#6b7280;margin-bottom:1rem;">'
        "Save your API keys once — they'll be auto-filled every time you optimize."
        "</p>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(providers)
    for tab, provider in zip(tabs, providers):
        with tab:
            _render_provider_section(
                provider=provider,
                provider_config=PROVIDER_CONFIG[provider],
                key_info=all_key_info.get(provider, {"last4": "", "valid": False}),
                use_supabase=use_supabase,
            )


def _render_provider_section(
    provider: str,
    provider_config: dict,
    key_info: dict,
    use_supabase: bool,
) -> None:
    from ai_gateway import PROVIDER_CONFIG

    last4 = key_info.get("last4", "")
    key_valid = key_info.get("valid", False)

    # ── Saved key status ──────────────────────────────────────────────────
    if last4:
        _dot_color = "#2d9b5a" if key_valid else "#b45309"
        _status_label = "Verified" if key_valid else "Not tested"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0.75rem;'
            f'padding:0.75rem 1rem;background:#f9fafb;border:1px solid #e5e7eb;'
            f'border-radius:10px;margin-bottom:1rem;">'
            f'<span style="font-size:0.8rem;color:#6b7280;font-weight:500;">Saved key</span>'
            f'<code style="font-size:0.9rem;font-weight:600;color:#111827;">····{last4}</code>'
            f'<span style="font-size:0.75rem;color:{_dot_color};font-weight:500;">'
            f'● {_status_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="font-size:0.875rem;color:#9ca3af;margin-bottom:1rem;">'
            "No key saved for this provider."
            "</p>",
            unsafe_allow_html=True,
        )

    # ── Model preference ──────────────────────────────────────────────────
    models = provider_config["models"]
    _chg_state = f"settings_chg_{provider}"
    if _chg_state not in st.session_state:
        st.session_state[_chg_state] = False

    with st.expander("Update Key" if last4 else "Add Key", expanded=not last4):
        cfg = provider_config
        new_key = st.text_input(
            cfg["key_label"],
            placeholder=cfg["placeholder"],
            type="password",
            key=f"settings_key_{provider}",
        )

        saved_model = st.session_state.get(f"settings_model_{provider}", models[0])
        if saved_model not in models:
            saved_model = models[0]
        model = st.selectbox(
            "Model",
            options=models,
            index=models.index(saved_model),
            key=f"settings_model_sel_{provider}",
        )

        c1, c2 = st.columns(2)
        with c1:
            if primary_button(
                "Save Key",
                key=f"settings-save-{provider}",
                disabled=not new_key.strip(),
            ):
                if use_supabase and new_key.strip():
                    from supabase_settings_store import save_provider_api_key
                    save_provider_api_key(provider, model, new_key.strip())
                st.session_state.selected_provider = provider
                st.session_state.api_key = new_key.strip()
                st.success("Key saved.")
                st.rerun()
        with c2:
            if secondary_button(
                "Test Connection",
                key=f"settings-test-new-{provider}",
                disabled=not new_key.strip(),
            ):
                _test_key(provider, model, new_key.strip(), use_supabase)

    # ── Actions for existing key ──────────────────────────────────────────
    if last4:
        c_a, c_b = st.columns(2)
        with c_a:
            if secondary_button("Test Saved Key", key=f"settings-test-saved-{provider}"):
                if use_supabase:
                    try:
                        from supabase_settings_store import get_provider_api_key
                        saved_key = get_provider_api_key(provider)
                        if saved_key:
                            _test_key(provider, models[0], saved_key, use_supabase)
                        else:
                            st.error("Could not retrieve saved key.")
                    except Exception as exc:
                        st.error(f"Error: {exc}")
        with c_b:
            if secondary_button("Remove Key", key=f"settings-remove-{provider}"):
                if use_supabase:
                    from supabase_settings_store import clear_provider_api_key
                    clear_provider_api_key(provider)
                if st.session_state.get("selected_provider") == provider:
                    st.session_state.api_key = ""
                st.success("Key removed.")
                st.rerun()


def _test_key(provider: str, model: str, api_key: str, persist: bool) -> None:
    with st.spinner("Testing connection..."):
        try:
            _validate_key(provider, model, api_key)
            if persist:
                from supabase_settings_store import mark_provider_key_valid
                mark_provider_key_valid(provider, True)
            st.success(f"Connected to {provider} successfully.")
        except Exception as exc:
            if persist:
                from supabase_settings_store import mark_provider_key_valid
                mark_provider_key_valid(provider, False)
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
    st.markdown("### Guided Help")
    render_help_section()
    st.markdown("---")
    st.markdown("### Direct Support")
    st.markdown(
        f"""
        If you still feel stuck after trying the guided steps above, reach out directly.

        - Email: [{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})
        - Having a great experience? Consider [supporting the project]({DONATE_URL})
        """
    )
