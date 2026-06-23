"""
Settings screen — account, AI settings, and help.

Rendered when screen == "settings".
"""
from __future__ import annotations

import streamlit as st

from auth_state import sign_out
from help_widget import DONATE_URL, SUPPORT_FORM_URL
from help_widget import render_help_section
from shell import render_screen_intro, render_shell_end, render_shell_start
from ui_helpers import primary_button, secondary_button


def render_settings_screen() -> None:
    render_shell_start()

    render_screen_intro(
        "settings",
        "Settings",
        "Manage your account and AI setup.",
        "Keep the essentials close, and use advanced provider settings only when you need them.",
    )

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
    render_screen_intro(
        "help",
        "Help",
        "Get unstuck quickly.",
        "Use this page as your guided walkthrough for uploads, optimization modes, downloads, and support.",
    )
    _render_help_tab()
    render_shell_end()


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


def _render_account_tab() -> None:
    st.markdown('<div class="apple-section-title">Account</div>', unsafe_allow_html=True)
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
    from ollama_local_ai import OLLAMA_BASE_URL

    st.markdown('<div class="apple-section-title">AI Settings</div>', unsafe_allow_html=True)

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
        '<p style="font-size:0.9rem;color:var(--muted);margin-bottom:1rem;">'
        "Save hosted API keys, or connect a local Ollama model for private optimization."
        "</p>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs([*providers, "Local AI"])
    for tab, provider in zip(tabs[: len(providers)], providers):
        with tab:
            _render_provider_section(
                provider=provider,
                provider_config=PROVIDER_CONFIG[provider],
                key_info=all_key_info.get(provider, {"last4": "", "valid": False}),
                use_supabase=use_supabase,
            )
    with tabs[-1]:
        _render_local_ai_section(default_base_url=OLLAMA_BASE_URL)


def _ollama_native_base_url(value: str) -> str:
    """Convert an OpenAI-compatible Ollama URL to the native Ollama API URL."""
    base_url = (value or "").strip().rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3].rstrip("/")
    return base_url or "http://localhost:11434"


def _ollama_openai_base_url(value: str) -> str:
    """Convert the native Ollama URL to the OpenAI-compatible /v1 URL."""
    base_url = _ollama_native_base_url(value)
    return f"{base_url}/v1"


def _render_local_ai_section(default_base_url: str) -> None:
    from ollama_local_ai import (
        DEFAULT_LOCAL_AI_MODEL,
        check_ollama_status,
        get_ollama_download_url,
        get_platform_label,
        list_installed_models,
        pull_model_stream,
        run_readiness_check,
    )

    st.markdown('<div class="apple-kicker">Private Mode</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-section-title">Local AI / Ollama</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.9rem;color:var(--muted);margin-bottom:1rem;">'
        "Use a local Ollama model for Full AI Optimization, including Bulk Application. "
        "Resume OTG will use Ollama's OpenAI-compatible endpoint automatically."
        "</p>",
        unsafe_allow_html=True,
    )

    native_base_url = _ollama_native_base_url(
        st.session_state.get("local_ai_base_url")
        or st.session_state.get("bulk_custom_api_base_url")
        or default_base_url
    )
    model_name = (
        st.session_state.get("local_ai_model_name")
        or st.session_state.get("bulk_custom_api_model")
        or DEFAULT_LOCAL_AI_MODEL
    )

    base_url = st.text_input(
        "Ollama Base URL",
        value=native_base_url,
        placeholder="http://localhost:11434",
        help="Use the native Ollama URL here. The app will use /v1 automatically for Full AI Optimization.",
        key="settings-local-ai-base-url",
    )
    model_name = st.text_input(
        "Local Model Name",
        value=model_name,
        placeholder="gpt-oss:20b",
        help="Use the exact model name from Ollama, for example gpt-oss:20b or mistral-small3.2:24b.",
        key="settings-local-ai-model",
    )

    recommended_models = [
        "gpt-oss:20b",
        "mistral-small3.2:24b",
        "qwen3:30b",
        "gemma3:27b",
        "llama3.3:70b",
    ]
    st.caption("Good local candidates: " + ", ".join(recommended_models))

    status = check_ollama_status(base_url=_ollama_native_base_url(base_url))
    status_rows = [
        ("Ollama engine", "Running" if status.get("reachable") else "Not running"),
        ("Native URL", _ollama_native_base_url(base_url)),
        ("Full AI endpoint", _ollama_openai_base_url(base_url)),
        ("Selected model", model_name or "Missing"),
    ]
    try:
        installed_models = list_installed_models(base_url=_ollama_native_base_url(base_url)) if status.get("reachable") else []
    except Exception:
        installed_models = []
    if installed_models:
        status_rows.append(("Installed models", ", ".join(installed_models[:5])))
    st.markdown(_settings_readiness_rows(status_rows), unsafe_allow_html=True)

    if not status.get("reachable"):
        st.info(f"Ollama is not running yet. Install or open Ollama for {get_platform_label()}, then come back and check setup.")
        st.markdown(f"[Download Ollama]({get_ollama_download_url()})")

    c1, c2 = st.columns(2)
    with c1:
        if primary_button("Save Local AI Settings", key="settings-local-ai-save", disabled=not model_name.strip()):
            native = _ollama_native_base_url(base_url)
            openai_compatible = _ollama_openai_base_url(base_url)
            st.session_state.local_ai_base_url = native
            st.session_state.local_ai_model_name = model_name.strip()
            st.session_state.custom_api_base_url = openai_compatible
            st.session_state.custom_api_model = model_name.strip()
            st.session_state.bulk_selected_provider = "Advanced Custom Endpoint"
            st.session_state.bulk_custom_api_base_url = openai_compatible
            st.session_state.bulk_custom_api_model = model_name.strip()
            st.session_state.bulk_custom_api_key = ""
            st.success("Local AI settings saved for Bulk Application Full AI Optimization.")
    with c2:
        if secondary_button("Check Setup", key="settings-local-ai-check", disabled=not model_name.strip()):
            readiness = run_readiness_check(
                model_name=model_name.strip(),
                base_url=_ollama_native_base_url(base_url),
            )
            st.session_state.local_ai_ready = readiness.get("ready", False)
            st.session_state.local_ai_setup_status = readiness
            if readiness.get("ready"):
                st.success(readiness.get("message", "Local AI is ready."))
            else:
                st.warning(readiness.get("message", "Local AI still needs attention."))

    with st.expander("Download a model with Ollama", expanded=False):
        pull_model = st.text_input(
            "Model to download",
            value=model_name or "gpt-oss:20b",
            key="settings-local-ai-pull-model",
        )
        if secondary_button("Download Model", key="settings-local-ai-pull", disabled=not pull_model.strip()):
            progress = st.progress(0)
            status_placeholder = st.empty()
            try:
                last_percent = 0
                for event in pull_model_stream(
                    pull_model.strip(),
                    base_url=_ollama_native_base_url(base_url),
                ):
                    percent = event.get("percent")
                    if isinstance(percent, int):
                        last_percent = percent
                        progress.progress(percent)
                    status_placeholder.info(
                        f"{event.get('status', 'Downloading model')} {f'({last_percent}%)' if last_percent else ''}"
                    )
                progress.progress(100)
                st.session_state.local_ai_model_name = pull_model.strip()
                st.session_state.bulk_custom_api_model = pull_model.strip()
                st.success(f"{pull_model.strip()} is available in Ollama.")
            except Exception as exc:
                st.error(f"Model download failed: {exc}")
            finally:
                progress.empty()
                status_placeholder.empty()


def _settings_readiness_rows(rows: list[tuple[str, str]]) -> str:
    """Render simple settings status rows without importing full shell helpers."""
    row_html = "".join(
        f'<div style="display:flex;justify-content:space-between;gap:1rem;'
        f'padding:0.65rem 0;border-bottom:1px solid rgba(148,163,184,0.22);">'
        f'<span style="font-size:0.86rem;color:var(--muted);">{label}</span>'
        f'<strong style="font-size:0.9rem;text-align:right;color:var(--text);">{value}</strong>'
        f'</div>'
        for label, value in rows
    )
    return f'<div style="margin:1rem 0;">{row_html}</div>'


def _render_provider_section(
    provider: str,
    provider_config: dict,
    key_info: dict,
    use_supabase: bool,
) -> None:
    from ai_gateway import get_provider_models

    last4 = key_info.get("last4", "")
    key_valid = key_info.get("valid", False)

    # ── Saved key status ──────────────────────────────────────────────────
    if last4:
        _dot_color = "#2d9b5a" if key_valid else "#b45309"
        _status_label = "Verified" if key_valid else "Not tested"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0.75rem;'
            f'padding:0.75rem 1rem;background:var(--surface-muted);border:1px solid var(--line);'
            f'border-radius:10px;margin-bottom:1rem;">'
            f'<span style="font-size:0.8rem;color:var(--muted);font-weight:500;">Saved key</span>'
            f'<code style="font-size:0.9rem;font-weight:600;color:var(--text);">····{last4}</code>'
            f'<span style="font-size:0.75rem;color:{_dot_color};font-weight:500;">'
            f'● {_status_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="font-size:0.875rem;color:var(--muted);margin-bottom:1rem;">'
            "No key saved for this provider."
            "</p>",
            unsafe_allow_html=True,
        )

    # ── Model preference ──────────────────────────────────────────────────
    models = provider_config["models"]
    saved_api_key = ""
    if use_supabase and last4:
        try:
            from supabase_settings_store import get_provider_api_key
            saved_api_key = get_provider_api_key(provider)
        except Exception:
            saved_api_key = ""
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
        if new_key.strip():
            models = get_provider_models(provider, new_key.strip())
        elif saved_api_key:
            models = get_provider_models(provider, saved_api_key)
        if saved_model not in models:
            saved_model = models[0]
        model = st.selectbox(
            "Model",
            options=models,
            index=models.index(saved_model),
            key=f"settings_model_sel_{provider}",
        )
        st.session_state[f"settings_model_{provider}"] = model

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

        - Support Form: [Open the support form]({SUPPORT_FORM_URL})
        - Having a great experience? Consider [supporting the project]({DONATE_URL})
        """
    )
