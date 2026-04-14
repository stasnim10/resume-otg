"""
Shared UI helpers, CSS theme, stepper, and display constants.

Extracted from streamlit_app.py so that screen modules can import
these utilities without circular dependencies.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from profile_schema import ProfileItem
from profile_store import list_profile_items


CAREER_STAGES = [
    "Student",
    "Early Career",
    "Mid-Level",
    "Manager",
    "Executive",
    "Career Pivot",
]

INDUSTRIES = [
    "",
    "Technology",
    "Consulting",
    "Finance",
    "Supply Chain / Operations",
    "Healthcare",
    "Marketing",
    "General Business",
]

ROLE_KEYWORDS = [
    "Analyst",
    "Manager",
    "Engineer",
    "Specialist",
    "Consultant",
    "Coordinator",
    "Associate",
    "Intern",
    "Designer",
    "Administrator",
    "Strategist",
    "Recruiter",
    "Marketer",
    "Developer",
    "Scientist",
    "Product Manager",
    "Program Manager",
]

FLOW_STEPS = [
    ("landing", "Start"),
    ("input", "Upload"),
    ("mode", "Run"),
    ("review", "Review"),
    ("complete", "Download"),
]

FLOW_STEP_ALIASES = {
    "builder_input": "input",
    "builder_stub": "mode",
    "builder_review": "review",
    "fit_report": "input",
    "manual": "mode",
    "api": "mode",
    "application_match": "input",
}

PROFILE_ITEM_TYPES = [
    "experience",
    "project",
    "education",
    "certification",
    "leadership",
    "activity",
    "volunteering",
    "business",
    "award",
    "skills",
]

def format_preview_text(text: str, max_len: int = 260) -> str:
    """Trim long paragraph previews so comparison cards stay readable."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len].rstrip()}..."


PROFILE_ITEM_PRIORITY = {
    "experience": 0,
    "project": 1,
    "business": 2,
    "leadership": 3,
    "education": 4,
    "certification": 5,
    "activity": 6,
    "volunteering": 7,
    "award": 8,
    "skills": 9,
}


def sort_profile_items_for_review(items: list[ProfileItem]) -> list[ProfileItem]:
    """Prioritize high-signal evidence items first in the import review flow."""
    return sorted(
        items,
        key=lambda item: (
            PROFILE_ITEM_PRIORITY.get(item.item_type, 99),
            -float(item.confidence_score or 0),
            (item.title or "").lower(),
            (item.organization or "").lower(),
        ),
    )

def apply_apple_theme() -> None:
    """Inject a restrained, editorial Apple-inspired visual system."""
    st.markdown(
        """
        <style>
        :root {
          --bg: #f5f5f7;
          --surface: #ffffff;
          --surface-muted: #fbfbfd;
          --panel-fill: #f7f7f9;
          --text: #1d1d1f;
          --muted: #6e6e73;
          --muted-light: #86868b;
          --line: rgba(0,0,0,0.05);
          --line-strong: rgba(0,0,0,0.08);
          --shadow-soft: 0 6px 18px rgba(0,0,0,0.04);
          --shadow-raised: 0 8px 20px rgba(0,0,0,0.06);
          --blue: #0071e3;
          --green: #1f8f4e;
          --amber: #b7791f;
          --danger: #c9342f;
          --font-main: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
        }

        .stApp {
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-main);
          color-scheme: light dark;
        }

        [data-testid="stSidebar"] {
          background: #fbfbfd;
          border-right: 1px solid var(--line);
        }

        [data-testid="stHeader"] {
          background: rgba(245,245,247,0.94);
          border-bottom: 1px solid rgba(0,0,0,0.03);
        }

        h1, h2, h3, h4, h5, h6, p, label, span, div {
          color: var(--text);
          font-family: var(--font-main);
        }

        .block-container {
          max-width: 1200px !important;
          padding-top: 4rem;
          padding-bottom: 4rem;
        }

        .apple-hero {
          padding: 1rem 0 4rem 0;
          text-align: center;
        }

        .apple-eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          font-size: 0.82rem;
          color: var(--muted-light);
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          margin-bottom: 0.9rem;
          justify-content: center;
        }

        .apple-hero h1, .apple-page-title {
          font-size: clamp(3.5rem, 6vw, 5.5rem);
          line-height: 1.1;
          letter-spacing: -0.022em;
          margin: 0 0 1rem 0;
          font-weight: 700;
          max-width: 11em;
          margin-left: auto;
          margin-right: auto;
        }

        .apple-hero p, .apple-subtitle {
          margin: 0;
          font-size: 1.06rem;
          line-height: 1.68;
          color: var(--muted);
          max-width: 760px;
          margin-left: auto;
          margin-right: auto;
        }

        .apple-trust-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.7rem;
          margin-top: 1.2rem;
        }

        .apple-chip {
          display: inline-flex;
          align-items: center;
          gap: 0.42rem;
          padding: 0.5rem 0.9rem;
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 999px;
          font-size: 0.86rem;
          color: var(--text);
          box-shadow: none;
        }

        .apple-stepper {
          display: flex;
          align-items: center;
          gap: 0.35rem;
          width: fit-content;
          padding: 0.5rem 0.8rem;
          margin: 0 auto 2.2rem auto;
          background: #e8e8ed;
          border-radius: 999px;
        }

        .apple-step {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0.72rem 1.5rem;
          border-radius: 999px;
          border: 1px solid transparent;
          background: transparent;
          text-align: center;
          font-size: 0.83rem;
          color: var(--muted);
          font-weight: 600;
          min-width: 96px;
          text-decoration: none !important;
          white-space: nowrap;
          cursor: pointer;
        }

        .apple-step:hover {
          background: rgba(255,255,255,0.45);
        }

        .apple-step.active {
          background: #ffffff;
          color: var(--text);
          border-color: rgba(0,0,0,0.03);
          box-shadow: var(--shadow-soft);
        }

        .apple-step.done {
          color: var(--muted-light);
        }

        .apple-step.disabled {
          opacity: 0.55;
          cursor: default;
          pointer-events: none;
        }

        .apple-hero-panel,
        .apple-panel,
        .apple-card,
        .apple-choice {
          position: relative;
          overflow: hidden;
          background: var(--surface);
          border: 1px solid var(--line);
          box-shadow: none;
        }

        .apple-hero-panel {
          background: transparent;
          border: none;
          border-radius: 0;
          padding: 0;
          margin-bottom: 0;
        }

        .apple-panel {
          border-radius: 24px;
          padding: 2.5rem;
        }

        .apple-card {
          border-radius: 24px;
          padding: 2.5rem;
          min-height: 100%;
        }

        .apple-choice {
          border-radius: 32px;
          padding: 2rem;
          min-height: 380px;
          transition: background-color 180ms ease, border-color 180ms ease, opacity 180ms ease;
        }

        .apple-choice:hover {
          background: var(--surface-muted);
        }

        .apple-choice-primary {
          background: var(--surface);
        }

        .apple-choice-selected {
          border-color: rgba(0,0,0,0.08);
          box-shadow: var(--shadow-soft);
        }

        .apple-kicker {
          font-size: 0.8rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted-light);
          font-weight: 600;
          margin-bottom: 0.95rem;
        }

        .apple-choice-title {
          font-size: 1.9rem;
          line-height: 1.12;
          letter-spacing: -0.022em;
          font-weight: 700;
          margin-bottom: 0.85rem;
        }

        .apple-choice-copy {
          color: var(--muted);
          font-size: 1rem;
          line-height: 1.7;
          margin-bottom: 1.3rem;
          max-width: 34ch;
        }

        .apple-section-title {
          font-size: 1.45rem;
          font-weight: 680;
          letter-spacing: -0.022em;
          margin-bottom: 0.45rem;
        }

        .apple-section-copy {
          color: var(--muted);
          font-size: 1rem;
          line-height: 1.72;
          margin-bottom: 1.1rem;
        }

        .apple-card-note {
          font-size: 0.88rem;
          color: var(--muted);
        }

        .apple-minor-copy {
          color: var(--muted);
          font-size: 0.92rem;
          line-height: 1.65;
        }

        .apple-stat-line {
          display: flex;
          gap: 0.55rem;
          align-items: center;
          margin-top: 1rem;
          color: var(--muted);
          font-size: 0.92rem;
        }

        .apple-float-space {
          height: 1rem;
        }

        .apple-landing-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 1.5rem;
          margin-top: 0.9rem;
        }

        .apple-landing-card {
          height: 340px;
          padding: 2.75rem;
          border-radius: 30px;
          background: #ffffff;
          border: 1px solid var(--line);
          box-shadow: none;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }

        .apple-landing-card.featured {
          border-color: var(--line-strong);
          box-shadow: var(--shadow-soft);
        }

        .apple-landing-card-title {
          font-size: 2rem;
          line-height: 1.08;
          letter-spacing: -0.022em;
          font-weight: 710;
          margin: 0.2rem 0 0.85rem 0;
        }

        .apple-landing-card-copy {
          color: var(--muted);
          font-size: 1rem;
          line-height: 1.72;
          max-width: 33ch;
          margin-bottom: 1.25rem;
        }

        .apple-landing-actions {
          margin-top: 0.65rem;
        }

        .apple-landing-actions .stButton button {
          min-height: 56px;
        }

        .apple-choice-frame {
          min-height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }

        .apple-choice-meta {
          margin-top: 1rem;
        }

        .apple-choice-actions {
          margin-top: 0.9rem;
        }

        .apple-inline-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.55rem;
          margin-top: 1rem;
        }

        .apple-inline-chip {
          display: inline-flex;
          align-items: center;
          padding: 0.42rem 0.75rem;
          border-radius: 999px;
          border: 1px solid var(--line);
          background: #ffffff;
          font-size: 0.82rem;
          color: var(--muted);
          line-height: 1;
        }

        .instruction-panel {
          margin: 0.65rem 0 1rem 0;
          padding: 1.45rem 1.5rem;
          border-radius: 20px;
          border: 1px solid var(--line);
          background: #f5f5f7;
        }

        .instruction-panel-title {
          font-size: 0.98rem;
          font-weight: 700;
          margin-bottom: 0.9rem;
          color: var(--text);
        }

        .instruction-row {
          display: flex;
          gap: 0.85rem;
          align-items: flex-start;
          margin-bottom: 0.85rem;
        }

        .instruction-row:last-child {
          margin-bottom: 0;
        }

        .instruction-number {
          min-width: 1.55rem;
          color: var(--text);
          font-size: 1rem;
          font-weight: 700;
          line-height: 1.4;
        }

        .instruction-copy {
          color: var(--muted);
          font-size: 0.95rem;
          line-height: 1.6;
        }

        .apple-summary-grid {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 24px;
          padding: 2rem;
          margin: 1rem 0 1.1rem 0;
        }

        .apple-summary-label {
          color: var(--muted-light);
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          margin-bottom: 0.55rem;
        }

        .apple-summary-title {
          font-size: 1.35rem;
          line-height: 1.2;
          letter-spacing: -0.02em;
          font-weight: 700;
          margin-bottom: 1.2rem;
        }

        .apple-stat-card {
          min-height: 100%;
        }

        .apple-stat-value {
          font-size: 2.3rem;
          line-height: 1;
          letter-spacing: -0.03em;
          font-weight: 700;
          margin-top: 0.35rem;
        }

        .apple-readiness-card {
          background: #f5f5f7;
          border: 1px solid var(--line);
          border-radius: 20px;
          padding: 1.25rem 1.35rem;
          margin-top: 0.8rem;
        }

        .apple-readiness-row {
          display: flex;
          justify-content: space-between;
          gap: 1rem;
          padding: 0.5rem 0;
          border-bottom: 1px solid rgba(0,0,0,0.04);
          font-size: 0.94rem;
        }

        .apple-readiness-row:last-child {
          border-bottom: none;
          padding-bottom: 0;
        }

        .apple-readiness-key {
          color: var(--muted);
        }

        .apple-readiness-value {
          color: var(--text);
          font-weight: 600;
          text-align: right;
        }

        div[data-testid="stVerticalBlock"] div[data-testid="stContainer"] {
          border-radius: 32px;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
          background-color: #ffffff !important;
          border: 1px solid rgba(0,0,0,0.06) !important;
          border-radius: 32px !important;
          padding: 1.5rem !important;
          box-shadow: none !important;
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }

        div[data-testid="stFileUploader"] section,
        div[data-testid="stExpander"] details,
        div[data-testid="stForm"],
        .stTextInput > div > div,
        .stSelectbox > div > div,
        .stTextArea textarea,
        .stMultiSelect > div > div {
          border-radius: 20px !important;
        }

        .stTextArea textarea,
        .stTextInput input {
          background: #f2f2f5 !important;
          border: 1px solid transparent !important;
          color: var(--text) !important;
          box-shadow: none !important;
          transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
        }

        .stTextArea textarea:focus,
        .stTextInput input:focus {
          background: #ebebf0 !important;
          border-color: rgba(0,0,0,0.06) !important;
          box-shadow: 0 0 0 3px rgba(0,113,227,0.08) !important;
        }

        .stSelectbox > div > div,
        .stMultiSelect > div > div {
          background: #f2f2f5 !important;
          border: 1px solid transparent !important;
        }

        .stButton button, .stDownloadButton button {
          border-radius: 999px !important;
          min-height: 54px;
          font-weight: 600;
          font-size: 1rem !important;
          border: 1px solid transparent !important;
          box-shadow: none !important;
          transition: opacity 180ms ease, background-color 180ms ease, border-color 180ms ease;
        }

        .stButton button:hover, .stDownloadButton button:hover {
          opacity: 0.82;
        }

        .apple-primary button {
          background: #1d1d1f !important;
          color: #ffffff !important;
          border-color: #1d1d1f !important;
        }

        .apple-primary button *,
        .apple-primary button p,
        .apple-primary button span,
        .apple-primary button div {
          color: #ffffff !important;
          fill: #ffffff !important;
          opacity: 1 !important;
        }

        .apple-secondary button {
          background: transparent !important;
          color: var(--blue) !important;
          box-shadow: none !important;
          border-color: var(--line-strong) !important;
        }

        .apple-secondary button *,
        .apple-secondary button p,
        .apple-secondary button span,
        .apple-secondary button div {
          color: var(--blue) !important;
          fill: var(--blue) !important;
          opacity: 1 !important;
        }

        div[data-testid="stAlert"] {
          border-radius: 20px;
          border: 1px solid rgba(0,0,0,0.04);
          box-shadow: none;
          background: #f6faf7;
        }

        div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
          color: var(--text) !important;
        }

        div[data-baseweb="notification"] {
          border-radius: 20px !important;
          border: 1px solid rgba(0,0,0,0.04) !important;
          box-shadow: none !important;
        }

        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #111214;
            --surface: #1c1c1f;
            --surface-muted: #242428;
            --panel-fill: #202126;
            --text: #f5f5f7;
            --muted: #b1b1b6;
            --muted-light: #8e8e93;
            --line: rgba(255,255,255,0.08);
            --line-strong: rgba(255,255,255,0.14);
            --shadow-soft: 0 6px 18px rgba(0,0,0,0.32);
            --shadow-raised: 0 8px 20px rgba(0,0,0,0.4);
            --blue: #4c9fff;
          }

          .stApp {
            background: var(--bg);
            color: var(--text);
          }

          [data-testid="stSidebar"] {
            background: #16171a;
            border-right: 1px solid var(--line);
          }

          [data-testid="stHeader"] {
            background: rgba(17,18,20,0.94);
            border-bottom: 1px solid rgba(255,255,255,0.06);
          }

          .apple-stepper {
            background: #2a2b31;
          }

          .apple-step.active {
            background: #3a3b42;
            color: var(--text);
            border-color: rgba(255,255,255,0.08);
          }

          .apple-step:hover {
            background: rgba(255,255,255,0.04);
          }

          .apple-chip,
          .apple-landing-card,
          .apple-panel,
          .apple-card,
          .apple-choice,
          [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface) !important;
            border-color: var(--line) !important;
            color: var(--text) !important;
          }

          .apple-readiness-card {
            background: #202126 !important;
            border-color: rgba(255,255,255,0.08) !important;
          }

          .apple-readiness-row {
            border-bottom: 1px solid rgba(255,255,255,0.08);
          }

          .apple-readiness-key {
            color: var(--muted) !important;
          }

          .apple-readiness-value {
            color: var(--text) !important;
          }

          .stTextArea textarea,
          .stTextInput input,
          .stSelectbox > div > div,
          .stMultiSelect > div > div {
            background: #23242a !important;
            color: var(--text) !important;
            border-color: rgba(255,255,255,0.08) !important;
          }

          .stTextArea textarea:focus,
          .stTextInput input:focus {
            background: #2a2b31 !important;
            border-color: rgba(76,159,255,0.45) !important;
            box-shadow: 0 0 0 3px rgba(76,159,255,0.12) !important;
          }

          .apple-primary button,
          .stButton button,
          .stDownloadButton button {
            background: #f5f5f7 !important;
            color: #111214 !important;
            border-color: #f5f5f7 !important;
          }

          .apple-primary button *,
          .apple-primary button p,
          .apple-primary button span,
          .apple-primary button div,
          .stButton button *,
          .stButton button p,
          .stButton button span,
          .stButton button div,
          .stDownloadButton button *,
          .stDownloadButton button p,
          .stDownloadButton button span,
          .stDownloadButton button div {
            color: #111214 !important;
            fill: #111214 !important;
            opacity: 1 !important;
          }

          .apple-secondary button {
            background: transparent !important;
            color: var(--blue) !important;
            border-color: var(--line-strong) !important;
          }

          .apple-secondary button *,
          .apple-secondary button p,
          .apple-secondary button span,
          .apple-secondary button div {
            color: var(--blue) !important;
            fill: var(--blue) !important;
            opacity: 1 !important;
          }

          div[data-testid="stAlert"] {
            background: #1e2521;
            border-color: rgba(255,255,255,0.08);
          }

          div[data-baseweb="notification"] {
            background: var(--surface) !important;
            border-color: var(--line) !important;
          }
        }

        @media (max-width: 900px) {
          .apple-hero h1, .apple-page-title {
            font-size: clamp(2.6rem, 10vw, 3.8rem);
          }

          .apple-hero-panel,
          .apple-panel,
          .apple-card,
          .apple-choice {
            padding: 2rem;
          }

          .apple-stepper {
            width: 100%;
            overflow-x: auto;
          }

          .apple-landing-grid {
            grid-template-columns: 1fr;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_shell_start() -> None:
    """No-op wrapper hook for shared screen layout."""
    return


def render_shell_end() -> None:
    """No-op wrapper hook for shared screen layout."""
    return


def _is_builder_flow_screen(screen_key: str) -> bool:
    """Return whether the current screen belongs to the builder flow."""
    return screen_key in {"builder_input", "builder_stub", "builder_review"}


def _resolve_step_target(step_key: str, current_screen: str) -> str | None:
    """Map a top-level step to the concrete screen for the active flow."""
    if step_key not in {key for key, _label in FLOW_STEPS}:
        return None

    if _is_builder_flow_screen(current_screen):
        builder_targets = {
            "landing": "landing",
            "input": "builder_input",
            "mode": "builder_stub",
            "review": "builder_review",
            "complete": "builder_review",
        }
        return builder_targets.get(step_key)

    default_targets = {
        "landing": "landing",
        "input": "input",
        "mode": "mode",
        "review": "review",
        "complete": "review",
    }
    return default_targets.get(step_key)


def _can_access_step(step_key: str, current_screen: str) -> bool:
    """Guard progress-step navigation so users can move safely through the journey."""
    if step_key == "landing":
        return True
    if step_key == "input":
        return True

    if _is_builder_flow_screen(current_screen):
        if step_key == "mode":
            return bool(st.session_state.builder_prompt)
        if step_key in {"review", "complete"}:
            return bool(st.session_state.builder_payload)
        return False

    if step_key == "mode":
        return bool(st.session_state.resume_text and st.session_state.job_description.strip())
    if step_key in {"review", "complete"}:
        return bool(st.session_state.validated_payload)
    return False


def handle_step_navigation_request() -> None:
    """Read `?nav=` query param and route to the correct step target."""
    requested_step = st.query_params.get("nav")
    if not requested_step:
        return

    requested_step = str(requested_step)
    current_screen = st.session_state.screen
    target_screen = _resolve_step_target(requested_step, current_screen)
    if target_screen and _can_access_step(requested_step, current_screen):
        st.session_state.screen = target_screen

    st.query_params.clear()


def render_progress_stepper(current_key: str) -> None:
    """Render the guided progress stepper."""
    current_key = FLOW_STEP_ALIASES.get(current_key, current_key)
    current_index = next((index for index, (key, _label) in enumerate(FLOW_STEPS) if key == current_key), 0)
    steps_html = []
    for index, (step_key, label) in enumerate(FLOW_STEPS):
        classes = ["apple-step"]
        if index < current_index:
            classes.append("done")
        elif index == current_index:
            classes.append("active")
        if not _can_access_step(step_key, st.session_state.screen):
            classes.append("disabled")
            steps_html.append(f'<span class="{" ".join(classes)}">{index + 1}. {label}</span>')
        else:
            steps_html.append(
                f'<a class="{" ".join(classes)}" href="?nav={step_key}">{index + 1}. {label}</a>'
            )
    st.markdown(f'<div class="apple-stepper">{"".join(steps_html)}</div>', unsafe_allow_html=True)


def render_screen_intro(step_key: str, eyebrow: str, title: str, subtitle: str) -> None:
    """Render a calm screen header with progress."""
    render_progress_stepper(step_key)
    st.markdown(
        f"""
        <div class="apple-hero">
          <div class="apple-eyebrow">{eyebrow}</div>
          <div class="apple-page-title">{title}</div>
          <p class="apple-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_chip_row(items: list[str]) -> None:
    """Render small trust or detected-value chips."""
    if not items:
        return
    html = "".join(f'<div class="apple-chip">{item}</div>' for item in items)
    st.markdown(f'<div class="apple-trust-row">{html}</div>', unsafe_allow_html=True)


def build_inline_chip_row(items: list[str]) -> str:
    """Return compact chip HTML for use inside local card layouts."""
    if not items:
        return ""
    chips = "".join(f'<div class="apple-inline-chip">{item}</div>' for item in items)
    return f'<div class="apple-inline-chip-row">{chips}</div>'


def build_readiness_rows(items: list[tuple[str, str]]) -> str:
    """Return structured readiness rows for setup and summary cards."""
    rows = "".join(
        (
            f'<div class="apple-readiness-row">'
            f'<div class="apple-readiness-key">{label}</div>'
            f'<div class="apple-readiness-value">{value}</div>'
            f"</div>"
        )
        for label, value in items
    )
    return f'<div class="apple-readiness-card">{rows}</div>'


def render_replacement_preview(item: dict, index: int, key_prefix: str, show_status: bool = True) -> None:
    """Render a cleaner before/after preview for one replacement."""
    status = item["status"]
    if show_status:
        if status == "matched":
            st.markdown("**✏️ AI-updated**")
        elif status == "duplicate":
            st.markdown("**⚠️ Needs manual review: multiple paragraphs matched**")
        else:
            st.markdown("**⚠️ Needs manual review: no exact anchor was found**")

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown("**Current Resume Text**")
        st.text_area(
            f"Current Resume Text {index}",
            value=item["match_anchor"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-anchor-{index}",
        )
        st.caption(format_preview_text(item["match_anchor"]))
    with right_col:
        st.markdown("**Proposed Replacement**")
        st.text_area(
            f"Proposed Replacement {index}",
            value=item["replacement_text"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-replacement-{index}",
        )
        st.caption(format_preview_text(item["replacement_text"]))

    if item["suggestions"]:
        suggestion_lines = [
            f"{suggestion['score']}: {format_preview_text(suggestion['text'], 180)}"
            for suggestion in item["suggestions"]
        ]
        st.caption("Closest resume paragraphs:")
        st.code("\n\n".join(suggestion_lines), language="text")


def _section_label(count: int, singular: str, plural: str) -> str:
    """Return a compact count label."""
    return f"{count} {singular if count == 1 else plural}"


def _group_review_results(review_results: list[dict]) -> dict[str, list[dict]]:
    """Group review items into user-facing sections."""
    grouped = {"Summary": [], "Bullet": [], "Skills": []}
    for item in review_results:
        grouped.setdefault(item.get("section", "Other"), []).append(item)
    return grouped


def render_review_section(title: str, items: list[dict], expanded: bool = False) -> None:
    """Render one grouped review section with progressive disclosure."""
    count_label = _section_label(len(items), "change", "changes")
    section_slug = title.lower().replace(" ", "-")
    with st.expander(f"{title} · {count_label}", expanded=expanded):
        if not items:
            st.caption("No changes in this section.")
            return

        if title != "Bullet Points" and len(items) == 1:
            render_replacement_preview(items[0], 1, f"{section_slug}-1", show_status=True)
            return

        for index, item in enumerate(items, start=1):
            status = item["status"]
            if status == "matched":
                status_label = "✏️ AI-updated"
            elif status == "duplicate":
                status_label = "⚠️ Needs manual review"
            else:
                status_label = "⚠️ Needs manual review"

            nested_title = f"{index}. {status_label}"
            if title == "Bullet Points":
                nested_title = f"{index}. {status_label} · {format_preview_text(item['replacement_text'], 72)}"

            with st.expander(nested_title, expanded=(len(items) == 1 and expanded)):
                render_replacement_preview(item, index, f"{section_slug}-{index}", show_status=False)



def render_copy_prompt_button(prompt: str, key: str) -> None:
    """Render a one-click clipboard copy button with feedback."""
    prompt_json = json.dumps(prompt)
    button_id = f"copy-btn-{key}"
    feedback_id = f"copy-feedback-{key}"
    components.html(
        f"""
        <div style="display:flex;flex-direction:column;align-items:flex-end;margin:0.05rem 0 0.15rem 0;">
          <button
            id="{button_id}"
            type="button"
            style="background:#1d1d1f;color:white;border:none;padding:0.65rem 1rem;border-radius:999px;cursor:pointer;font-weight:700;font-size:0.92rem;"
          >
            Copy Prompt
          </button>
          <span id="{feedback_id}" style="min-height:1.15rem;margin-top:0.35rem;font-size:0.88rem;font-weight:700;color:#15803d;"></span>
        </div>
        <script>
          const button = document.getElementById("{button_id}");
          const feedback = document.getElementById("{feedback_id}");
          const promptText = {prompt_json};
          button.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(promptText);
              feedback.textContent = "✓ Copied!";
              feedback.style.color = "#15803d";
              setTimeout(() => {{
                feedback.textContent = "";
              }}, 2000);
            }} catch (err) {{
              feedback.textContent = "Failed to copy. Try Cmd+C instead.";
              feedback.style.color = "#b45309";
              setTimeout(() => {{
                feedback.textContent = "";
              }}, 2000);
            }}
          }});
        </script>
        """,
        height=74,
    )


def render_prompt_block(label: str, prompt: str, height: int, copy_key: str) -> None:
    """Render the prompt with a heading and right-aligned copy button."""
    st.markdown(f"**{label}**")
    render_copy_prompt_button(prompt, copy_key)
    st.text_area(
        label,
        value=prompt,
        height=height,
        key=f"{copy_key}-prompt-display",
        label_visibility="collapsed",
        help="Select the prompt text manually if the browser blocks clipboard access.",
    )


def render_instruction_panel(title: str, steps: list[str]) -> None:
    """Render a restrained instructional card."""
    step_html = "".join(
        [
            f'<div class="instruction-row"><div class="instruction-number">{index}.</div><div class="instruction-copy">{step}</div></div>'
            for index, step in enumerate(steps, start=1)
        ]
    )
    components.html(
        f"""
        <style>
          :root {{
            color-scheme: light dark;
            --instruction-bg: #f5f5f7;
            --instruction-border: rgba(0,0,0,0.05);
            --instruction-title: #1d1d1f;
            --instruction-copy: #6e6e73;
          }}

          body {{
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
            background: transparent;
          }}

          .instruction-panel {{
            background: var(--instruction-bg);
            border: 1px solid var(--instruction-border);
            border-radius: 20px;
            padding: 1.35rem 1.4rem;
            box-sizing: border-box;
          }}

          .instruction-panel-title {{
            color: var(--instruction-title);
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            margin-bottom: 0.9rem;
          }}

          .instruction-row {{
            display: flex;
            align-items: flex-start;
            gap: 0.7rem;
            padding: 0.38rem 0;
          }}

          .instruction-number {{
            min-width: 1.55rem;
            color: var(--instruction-title);
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.4;
          }}

          .instruction-copy {{
            color: var(--instruction-copy);
            font-size: 0.95rem;
            line-height: 1.6;
          }}

          @media (prefers-color-scheme: dark) {{
            :root {{
              --instruction-bg: #202126;
              --instruction-border: rgba(255,255,255,0.08);
              --instruction-title: #f5f5f7;
              --instruction-copy: #b1b1b6;
            }}
          }}
        </style>
        <div class="instruction-panel">
          <div class="instruction-panel-title">{title}</div>
          {step_html}
        </div>
        """,
        height=max(170, 78 + (len(steps) * 48)),
    )

