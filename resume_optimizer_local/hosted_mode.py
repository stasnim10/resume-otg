"""
Feature flags for hosted web mode vs local/desktop mode.

When HOSTED_WEB=true in Streamlit secrets:
  - Supabase auth is required
  - Private Mode / Ollama features are hidden
  - All data is stored in Supabase (not SQLite)
"""
from __future__ import annotations


def is_hosted_web() -> bool:
    """Return True when the app is running in hosted (cloud) mode."""
    try:
        import streamlit as st
        return str(st.secrets.get("HOSTED_WEB", "false")).lower() == "true"
    except Exception:
        return False


def show_private_mode() -> bool:
    """Return True when the Private Mode / Ollama UI should be visible."""
    return not is_hosted_web()


def show_ollama_setup() -> bool:
    """Return True when the Ollama setup wizard should be accessible."""
    return not is_hosted_web()


def show_local_ai_cards() -> bool:
    """Return True when Local AI status cards should appear on the landing screen."""
    return not is_hosted_web()
