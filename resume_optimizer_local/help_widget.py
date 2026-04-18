"""
Help panel — rendered inside the app sidebar.

Provides step-by-step task guides for common workflows and a direct
contact escape hatch so users who get stuck can reach the app owner.

Usage (inside a `with st.sidebar:` block in streamlit_app.py):
    from help_widget import render_help_section
    render_help_section()
"""
from __future__ import annotations

import streamlit as st

# ── Your contact details — update these before publishing ─────────────────────
CONTACT_LINKEDIN = "https://www.linkedin.com/in/YOUR-PROFILE-HERE"
CONTACT_EMAIL    = "your@email.com"
# ──────────────────────────────────────────────────────────────────────────────

_DIVIDER = '<hr style="border:none;border-top:1px solid var(--line,#e5e5e5);margin:0.9rem 0;">'


def render_help_section() -> None:
    """
    Render the collapsible help guide inside whatever sidebar context the
    caller has already opened.  Does NOT call `with st.sidebar:` itself.
    """
    st.markdown(_DIVIDER, unsafe_allow_html=True)

    with st.expander("Need Help?", expanded=False):

        # ── Getting started ──────────────────────────────────────────────────
        st.markdown("**Getting started**")
        st.markdown(
            """
1. **Onboarding** — when you first open the app you'll see a short 5-step
   setup wizard.  Fill in your name, career stage, and target roles, then
   upload your resume so we can pre-fill your profile.
2. **Verify your profile** — after setup, open **Career Profile** in the
   sidebar and confirm all extracted information looks right.  Use the
   tabs (Personal, Education, Experience, Skills) to fill any gaps.
3. **You're ready** — once your profile has a green bar you'll get the best
   results from every optimisation run.
"""
        )

        st.markdown(_DIVIDER, unsafe_allow_html=True)

        # ── Optimising a resume ──────────────────────────────────────────────
        st.markdown("**How to optimise a resume**")
        st.markdown(
            """
1. From the **Home** screen, choose *Optimize My Resume*.
2. Upload your **.docx or .pdf** resume on the next screen.
3. Paste or fetch the **job description** you want to target.
4. Click **Continue** to choose Standard (API key) or Local AI mode.
5. Run the optimisation — review every suggested change before accepting.
6. Download the updated **.docx** from the final screen.
"""
        )

        st.markdown(_DIVIDER, unsafe_allow_html=True)

        # ── Job tracker ──────────────────────────────────────────────────────
        st.markdown("**Using the Job Tracker**")
        st.markdown(
            """
1. Open **Job Tracker** from the sidebar.
2. Click **Add Job Manually** to log a role you want to apply for.
3. After optimising a resume for a specific job, the run is automatically
   attached to that job entry — no double-entry needed.
4. Update the **status** column as you move through the process
   (Applied → Interview → Offer, etc.).
"""
        )

        st.markdown(_DIVIDER, unsafe_allow_html=True)

        # ── Profile ──────────────────────────────────────────────────────────
        st.markdown("**Managing your profile**")
        st.markdown(
            """
- **Upload a new document** — in *Career Profile → Documents*, use the
  *Add to library* expander to store additional files.
- **Edit a field** — each tab has an *Edit* button.  Changes are saved
  immediately to your local database.
- **Profile completeness bar** — aim for 100%.  The bar shows exactly
  which sections are still missing.
"""
        )

        st.markdown(_DIVIDER, unsafe_allow_html=True)

        # ── Local AI ─────────────────────────────────────────────────────────
        st.markdown("**Local AI (Ollama)**")
        st.markdown(
            """
Local AI runs entirely on your machine — nothing is sent to the cloud.

1. Install [Ollama](https://ollama.com) on your computer.
2. Run `ollama pull gemma3:4b` in a terminal to download the model.
3. Start Ollama, then choose **Local AI** mode inside the app.

*Local AI is not available on the hosted (Streamlit Cloud) version —
use Standard mode with your own API key there.*
"""
        )

        st.markdown(_DIVIDER, unsafe_allow_html=True)

        # ── Contact ──────────────────────────────────────────────────────────
        st.markdown("**Still stuck?**")
        st.markdown(
            "Reach out directly — happy to help."
        )

        col_li, col_mail = st.columns(2)
        with col_li:
            st.link_button(
                "LinkedIn",
                CONTACT_LINKEDIN,
                use_container_width=True,
            )
        with col_mail:
            st.link_button(
                "Email",
                f"mailto:{CONTACT_EMAIL}",
                use_container_width=True,
            )
