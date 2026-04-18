"""
Help panel — layered in-product coaching, rendered inside the sidebar.

Layer 1: Contextual hints live inline on each screen (via _help_hint in onboarding_screen.py).
Layer 2: Task-based guided help — this module. Short steps for each workflow.
Layer 3: Direct contact — email + LinkedIn at the bottom.

Usage (inside a `with st.sidebar:` block):
    from help_widget import render_help_section
    render_help_section()
"""
from __future__ import annotations

import streamlit as st

# ── Contact details ────────────────────────────────────────────────────────────
CONTACT_EMAIL    = "tasnimsimum@gmail.com"
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
    st.link_button(
        "☕  Buy me a coffee",
        DONATE_URL,
        use_container_width=True,
    )


def render_help_section() -> None:
    """
    Render the collapsible help panel inside whatever sidebar context the
    caller has already opened. Does NOT call `with st.sidebar:` itself.
    """
    st.markdown(_DIV, unsafe_allow_html=True)

    with st.expander("Need help?", expanded=False):

        # ── Getting started ──────────────────────────────────────────────────
        st.markdown("**Getting started**")
        st.markdown(
            "1. Open the app — a setup wizard appears automatically on first use.\n"
            "2. Enter your name and career details (takes ~1 minute).\n"
            "3. Upload your resume so the app can build your profile.\n"
            "4. Review what was extracted — correct anything that looks off.\n"
            "5. You're ready. Your profile is saved and reused on every run."
        )

        st.markdown(_DIV, unsafe_allow_html=True)

        # ── Optimising a resume ──────────────────────────────────────────────
        st.markdown("**How to optimise a resume**")
        st.markdown(
            "1. From **Home**, choose *Optimize My Resume*.\n"
            "2. Upload your **.docx** or **.pdf** resume.\n"
            "3. Paste or fetch the job description you're targeting.\n"
            "4. Click **Continue** and choose a mode (Standard or Local AI).\n"
            "5. Review every suggested change before accepting.\n"
            "6. Download the updated **.docx** from the final screen."
        )

        st.markdown(_DIV, unsafe_allow_html=True)

        # ── Profile ──────────────────────────────────────────────────────────
        st.markdown("**Managing your profile**")
        st.markdown(
            "- Open **Career Profile** from the sidebar at any time.\n"
            "- Use the tabs (Personal · Education · Experience · Skills) "
            "to add or edit information.\n"
            "- The **completeness bar** shows exactly what's still missing.\n"
            "- Upload more documents under **Documents → Add to library**."
        )

        st.markdown(_DIV, unsafe_allow_html=True)

        # ── Common questions ─────────────────────────────────────────────────
        st.markdown("**Common questions**")

        with st.expander("What should I upload during setup?", expanded=False):
            st.caption(
                "Your resume or CV works best (.docx gives the cleanest extraction). "
                "A LinkedIn PDF export is also useful — it adds your headline, "
                "experience, and education automatically."
            )

        with st.expander("Why didn't my LinkedIn parse correctly?", expanded=False):
            st.caption(
                "LinkedIn PDFs sometimes have unusual layouts. If extraction looks wrong, "
                "paste your LinkedIn **About** section text into the text box instead — "
                "that usually gives cleaner results."
            )

        with st.expander("How do I fix something that extracted wrong?", expanded=False):
            st.caption(
                "In the **Review** step during setup: click **Edit** in the relevant section "
                "and correct the value directly. After setup: open **Career Profile** "
                "and use the pencil button on any item."
            )

        with st.expander("What if my profile is incomplete after setup?", expanded=False):
            st.caption(
                "That's fine — you can continue and fill it in later. "
                "Open **Career Profile** from the sidebar and use the tabs "
                "to add education, experience, and skills manually."
            )

        with st.expander("Does Local AI work on the hosted version?", expanded=False):
            st.caption(
                "No — Local AI requires Ollama running on your own machine. "
                "On the hosted version, use **Standard** mode with your own API key "
                "(OpenAI, Anthropic, or Google Gemini)."
            )

        st.markdown(_DIV, unsafe_allow_html=True)

        # ── Contact ──────────────────────────────────────────────────────────
        st.markdown("**Still stuck? Contact support**")
        st.caption("Happy to help — reach out directly.")

        col_mail, col_li = st.columns(2)
        with col_mail:
            st.link_button(
                "Email",
                f"mailto:{CONTACT_EMAIL}",
                use_container_width=True,
            )
        with col_li:
            st.link_button(
                "LinkedIn",
                CONTACT_LINKEDIN,
                use_container_width=True,
            )

        st.markdown(_DIV, unsafe_allow_html=True)

        # ── Support ───────────────────────────────────────────────────────────
        st.markdown("**Support future development**")
        st.caption("If this saved you time, a coffee goes a long way.")
        st.link_button(
            "☕  Buy me a coffee",
            DONATE_URL,
            use_container_width=True,
        )
