"""
Shared Streamlit UI helper functions.

Centralises the apple-primary / apple-secondary button wrapper pattern so
callers don't need to manually emit matching open/close div tags.
"""
from __future__ import annotations

from typing import Any

import streamlit as st


def primary_button(label: str, key: str, **kwargs: Any) -> bool:
    """Render a primary-styled button. Returns True when clicked."""
    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def secondary_button(label: str, key: str, **kwargs: Any) -> bool:
    """Render a secondary-styled button. Returns True when clicked."""
    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def primary_form_submit(label: str, **kwargs: Any) -> bool:
    """Render a primary-styled form submit button. Must be inside st.form."""
    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
    clicked = st.form_submit_button(label, **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def primary_download_button(label: str, data: bytes | str, file_name: str, mime: str, **kwargs: Any) -> bool:
    """Render a primary-styled download button. Returns True when clicked."""
    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
    clicked = st.download_button(label, data=data, file_name=file_name, mime=mime, **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked
