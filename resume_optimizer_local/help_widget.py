"""
Help panel — layered in-product coaching, rendered inside the sidebar.

Layer 1: Contextual hints live inline on each screen (via _help_hint in onboarding_screen.py).
Layer 2: Task-based guided help — this module. Short steps for each workflow.
Layer 3: Direct contact — support form + LinkedIn at the bottom.

Usage (inside a `with st.sidebar:` block):
    from help_widget import render_help_section
    render_help_section()
"""
from __future__ import annotations

import streamlit as st

# ── Contact details ────────────────────────────────────────────────────────────
SUPPORT_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSf6mVr-SiJGt25xf-IqyigH1tP7gLDUqKALsL0s7LkVuf-vhw/viewform?usp=sharing&ouid=102555120417784611033"
CONTACT_LINKEDIN = "https://www.linkedin.com/in/simum-tasnim/"
DONATE_URL       = "https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01"
# ──────────────────────────────────────────────────────────────────────────────

_DIV = '<hr style="border:none;border-top:1px solid var(--line,#e5e5e5);margin:0.65rem 0;">'


def render_support_button() -> None:
    """Render a standalone 'Buy me a coffee' button in the sidebar."""
    st.markdown(_DIV, unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.78rem;color:#888;margin-bottom:0.35rem;'>Like the app? Support future development.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        .coffee-cta-link {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            min-height: 36px !important;
            height: 36px !important;
            background: #d97757 !important;
            color: #111111 !important;
            border: 1px solid #d97757 !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 0.875rem !important;
            text-decoration: none !important;
            box-shadow: 0 8px 20px rgba(217, 119, 87, 0.18) !important;
            transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease !important;
            box-sizing: border-box !important;
        }

        .coffee-cta-link:hover {
            background: #c9683f !important;
            border-color: #c9683f !important;
            color: #111111 !important;
            transform: translateY(-1px);
        }

        .coffee-cta-link * {
            color: #111111 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'''
        <a class="coffee-cta-link" href="{DONATE_URL}" target="_blank" rel="noopener noreferrer">
            ☕&nbsp;&nbsp;Buy me a coffee
        </a>
        ''',
        unsafe_allow_html=True,
    )


def render_help_section() -> None:
    """
    Render help content inline. Caller is responsible for any expander wrapper.
    Does NOT call `with st.sidebar:` itself.
    """
    st.markdown("**Getting started**")
    st.markdown(
        "1. Complete the setup wizard on first use.\n"
        "2. Upload your resume to build your profile.\n"
        "3. Review extracted data and correct anything off.\n"
        "4. Pick a job, choose a mode, optimize."
    )

    st.markdown(_DIV, unsafe_allow_html=True)

    st.markdown("**How to optimize a resume**")
    st.markdown(
        "1. From **Home**, choose *Optimize My Resume*.\n"
        "2. Upload your **.docx** resume.\n"
        "3. Paste the job description you're targeting.\n"
        "4. Choose **Full AI Optimization** and enter your API key.\n"
        "5. Review every change before accepting.\n"
        "6. Download the updated **.docx**."
    )

    st.markdown(_DIV, unsafe_allow_html=True)

    st.markdown("**Common questions**")

    with st.expander("What should I upload during setup?", expanded=False):
        st.caption(
            "Your resume (.docx works best for resume optimization) or a LinkedIn PDF export for profile extraction. "
            "LinkedIn adds your headline, experience, and education automatically."
        )

    with st.expander("Why didn't my LinkedIn parse correctly?", expanded=False):
        st.caption(
            "LinkedIn PDFs can have unusual layouts. Paste your LinkedIn "
            "About section text directly for cleaner results."
        )

    with st.expander("How do I fix something extracted wrong?", expanded=False):
        st.caption(
            "During setup: click Edit in the relevant section. "
            "After setup: open Career Profile and use the pencil icon."
        )

    st.markdown(_DIV, unsafe_allow_html=True)

    st.markdown("**Contact support**")
    col_support, col_li = st.columns(2)
    with col_support:
        st.link_button("Support Form", SUPPORT_FORM_URL, use_container_width=True)
    with col_li:
        st.link_button("LinkedIn", CONTACT_LINKEDIN, use_container_width=True)
