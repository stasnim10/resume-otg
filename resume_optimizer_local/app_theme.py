"""Warm editorial and Night workspace themes, shared by every app screen.

The preference is browser-local. Explicit selections travel in the URL; a browser component restores later
visits into session state without rewriting an in-flight OAuth callback URL.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_preference = components.declare_component("appearance_preference", path=str(Path(__file__).parent / "theme_preference"))

PALETTES = {
    "warm": dict(bg="#F7F3EA", surface="#FFFDFA", text="#352F29", muted="#7A7064",
                 line="#E6DED0", accent="#A6472E", tint="#F1E4D4", coffee="#EFC397",
                 coffee_ink="#593122", accent_ink="#FFFFFF", scheme="light"),
    "night": dict(bg="#101A1D", surface="#18272B", text="#ECF4F2", muted="#AAC0BF",
                  line="#2E4246", accent="#9CE0CC", tint="#223A3C", coffee="#F0BD99",
                  coffee_ink="#452C21", accent_ink="#101A1D", scheme="dark"),
}


def current_theme() -> str:
    value = st.query_params.get("theme", st.session_state.get("appearance_mode", "warm"))
    return value if value in PALETTES else "warm"


def _change_theme() -> None:
    mode = st.session_state["appearance_choice"].lower()
    st.session_state.appearance_mode = mode
    st.query_params["theme"] = mode


def render_theme_control() -> None:
    """Expose an accessible, compact switch on every screen, including sign-in."""
    mode = current_theme()
    st.session_state.appearance_choice = mode.title()
    st.radio("Appearance", ["Warm", "Night"], key="appearance_choice", horizontal=True,
             on_change=_change_theme)


def apply_theme() -> None:
    mode = current_theme()
    p = PALETTES[mode]
    tokens = {
        "bg": p["bg"], "surface": p["surface"], "surface-muted": p["tint"], "panel-fill": p["tint"],
        "text": p["text"], "muted": p["muted"], "muted-light": p["muted"], "line": p["line"],
        "line-strong": p["line"], "sidebar-bg": p["surface"], "input-fill": p["surface"],
        "input-fill-focus": p["surface"], "header-bg": p["bg"], "card-border": p["line"],
        "step-active-bg": p["tint"], "alert-bg": p["tint"], "blue": p["accent"],
        "btn-primary-bg": p["accent"], "btn-primary-text": p["accent_ink"],
        "btn-secondary-bg": p["surface"], "btn-secondary-text": p["text"],
        "btn-secondary-border": p["line"], "focus-blue": p["accent"], "focus-blue-halo": p["tint"],
        "disabled-bg": p["tint"], "disabled-text": p["muted"], "disabled-border": p["line"],
        "coffee": p["coffee"], "coffee-ink": p["coffee_ink"],
        "shadow-soft": "0 4px 16px rgba(0,0,0,.04)", "shadow-raised": "0 8px 24px rgba(0,0,0,.08)",
    }
    declarations = ";".join(f"--{key}:{value}" for key, value in tokens.items())
    st.markdown(f"<style>:root {{{declarations};color-scheme:{p['scheme']}}}</style>", unsafe_allow_html=True)
    st.markdown("""<style>
    .stApp {color-scheme:inherit;}
    #root .block-container {padding-top:1.5rem!important;max-width:1280px!important;}
    #root [data-testid="stSidebar"] {background:var(--sidebar-bg);border-right:1px solid var(--line);}
    #root [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.3rem!important;}
    #root [data-testid="stSidebar"] [data-testid="stButton"] button {height:44px!important;min-height:44px!important;
      padding:0 14px!important;line-height:1.3!important;justify-content:flex-start!important;border-radius:9px!important;}
    #root [data-testid="stSidebar"] button[kind="primary"] {background:var(--step-active-bg)!important;}
    #root [data-testid="stSidebar"] [data-testid="stButton"] {margin:0!important;}
    #root [data-testid="stSidebar"] button[kind="primary"],
    #root [data-testid="stSidebar"] button[kind="secondary"] {
      display:flex!important;justify-content:flex-start!important;text-align:left!important;
      min-height:44px!important;height:44px!important;padding:0 14px!important;
      font-size:.875rem!important;border:0!important;box-shadow:none!important;}
    #root [data-testid="stSidebar"] button[kind="primary"] *,
    #root [data-testid="stSidebar"] button[kind="secondary"] * {text-align:left!important;}
    #root button[aria-label="Collapse sidebar"], #root button[aria-label="Expand sidebar"],
    #root [data-testid="collapsedControl"], #root [data-testid="stSidebarCollapseButton"] {display:flex!important;}
    #root [data-testid="stButton"] button, #root [data-testid="stDownloadButton"] button, #root [data-testid="stFormSubmitButton"] button {
      border-radius:9px!important;min-height:44px!important;line-height:1.4!important;
      background:var(--btn-secondary-bg)!important;color:var(--btn-secondary-text)!important;
      border:1px solid var(--line)!important;box-shadow:none!important;}
    #root button[kind="primary"], #root [data-testid="stDownloadButton"] button {
      background:var(--btn-primary-bg)!important;color:var(--btn-primary-text)!important;border-color:var(--btn-primary-bg)!important;}
    #root button[kind="primary"] *, #root [data-testid="stDownloadButton"] button * {color:inherit!important;}
    #root [data-testid="stButton"] button:hover, #root [data-testid="stDownloadButton"] button:hover {filter:brightness(.94);transform:none!important;}
    #root button:disabled {background:var(--disabled-bg)!important;color:var(--disabled-text)!important;border-color:var(--line)!important;filter:none;}
    #root button:focus-visible, #root input:focus-visible, #root textarea:focus-visible {
      outline:2px solid var(--btn-primary-bg)!important;outline-offset:3px;}
    #root [data-baseweb="radio"] input {accent-color:var(--btn-primary-bg);}
    #root [data-baseweb="radio"]:has(input:checked) > div:first-child {background-color:var(--btn-primary-bg)!important;}
    #root [data-testid="stSidebar"] [data-testid="stButton"] button {background:transparent!important;border:0!important;}
    #root [data-testid="stSidebar"] button[kind="primary"] {background:var(--step-active-bg)!important;color:var(--text)!important;}
    #root .apple-hero, #root .apple-hero-dashboard {text-align:left;padding-bottom:1.5rem;}
    #root .apple-hero h1, #root .apple-page-title {font-size:clamp(1.9rem,3.3vw,3rem);line-height:1.12;letter-spacing:-.045em;max-width:22em;margin-left:0;margin-right:0;}
    #root .apple-hero-panel {background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:24px 28px;margin-bottom:24px;}
    #root .apple-hero p {color:var(--muted);max-width:660px;line-height:1.6;margin-left:0;margin-right:0;}
    #root [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .apple-landing-card-title) {
      padding:24px!important;background:var(--surface)!important;border:1px solid var(--line)!important;border-radius:16px!important;}
    #root [data-testid="stVerticalBlockBorderWrapper"], #root [data-testid="stContainer"] {
      border-color:var(--line)!important;border-radius:16px!important;}
    #root [data-testid="stVerticalBlockBorderWrapper"]:has(.apple-landing-card-title):hover {
      transform:none!important;border-color:var(--line-strong)!important;box-shadow:var(--shadow-soft)!important;}
    #root [data-testid="stVerticalBlockBorderWrapper"]:has(.apple-landing-card-title)::before {display:none;}
    #root [data-baseweb="tab"] {color:var(--muted)!important;}
    #root [data-baseweb="tab"][aria-selected="true"] {color:var(--text)!important;border-bottom-color:var(--btn-primary-bg)!important;}
    #root [data-baseweb="tab"]:hover {background:var(--panel-fill)!important;}
    .otg-brand {color:var(--text)!important;font-size:1.12rem;font-weight:700;letter-spacing:-.03em;margin:4px 0 20px;}
    .otg-support {display:flex;align-items:center;justify-content:space-between;gap:16px;
      padding:12px 18px;border:1px solid var(--line);border-radius:12px;background:var(--surface);margin-bottom:22px;}
    .otg-support-copy {font-size:.84rem;color:var(--muted);}
    .otg-support-copy strong {display:block;color:var(--text);font-size:.92rem;margin-bottom:3px;}
    .otg-coffee {display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 16px;
      background:var(--coffee)!important;color:var(--coffee-ink)!important;border-radius:9px;font-size:.88rem;
      font-weight:650;text-decoration:none!important;white-space:nowrap;}
    .otg-coffee:hover {filter:brightness(.95);}
    .otg-coffee:focus-visible {outline:2px solid var(--btn-primary-bg);outline-offset:3px;}
    .otg-sidebar-support {border-top:1px solid var(--line);margin-top:16px;padding-top:16px;}
    .otg-sidebar-support p {color:var(--muted)!important;font-size:.82rem;margin:0 0 10px;}
    .otg-sidebar-support .otg-coffee {display:flex;width:100%;box-sizing:border-box;}
    @media(max-width:640px) {
      .otg-support {align-items:flex-start;flex-direction:column;padding:14px;gap:10px;}
      #root .apple-hero-panel {padding:20px;}
      #root .block-container {padding-left:1rem!important;padding-right:1rem!important;}
    }
    </style>""", unsafe_allow_html=True)
    saved = _preference(selected=mode, explicit=st.query_params.get("theme") in PALETTES,
                        default=mode, key="otg-appearance-preference")
    if st.query_params.get("theme") not in PALETTES and saved in PALETTES and saved != mode:
        # Google sign-in returns tokens in the browser URL fragment. Updating
        # query params here can erase it before the auth bridge consumes it.
        st.session_state.appearance_mode = saved
        st.rerun()


def render_support_banner() -> None:
    from help_widget import DONATE_URL
    st.markdown(f'''<div class="otg-support"><div class="otg-support-copy">
      <strong>A little support goes a long way.</strong>Help keep Resume OTG growing.</div>
      <a class="otg-coffee" href="{DONATE_URL}" target="_blank" rel="noopener noreferrer">☕ Buy me a coffee</a></div>''',
      unsafe_allow_html=True)


def render_sidebar_support() -> None:
    from help_widget import DONATE_URL
    st.markdown(f'''<div class="otg-sidebar-support">
      <p>Help keep Resume OTG growing.</p>
      <a class="otg-coffee" href="{DONATE_URL}" target="_blank" rel="noopener noreferrer">☕ Buy me a coffee</a></div>''',
      unsafe_allow_html=True)
