"""
Streamlit prototype for the Resume Optimizer MVP.
"""
from __future__ import annotations

import io
import json
import re
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ai_gateway import PROVIDER_CONFIG, optimize_with_provider
from docx_handler import apply_replacements, build_resume_from_scratch, extract_text
from jd_cleaning import clean_job_description
from jd_fetcher import fetch_job_description_from_url, looks_like_url
from json_parser import (
    build_builder_validation_summary,
    build_validation_summary,
    parse_builder_payload,
    parse_replacement_payload,
)
from prompt_engine import build_builder_prompt, build_optimizer_prompt
from review_engine import analyze_payload_against_document


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
    "manual": "mode",
    "api": "mode",
}


def format_preview_text(text: str, max_len: int = 260) -> str:
    """Trim long paragraph previews so comparison cards stay readable."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len].rstrip()}..."


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
          padding: 0.72rem 1.5rem;
          border-radius: 999px;
          border: 1px solid transparent;
          background: transparent;
          text-align: center;
          font-size: 0.83rem;
          color: var(--muted);
          font-weight: 600;
          min-width: 96px;
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


def render_progress_stepper(current_key: str) -> None:
    """Render the guided progress stepper."""
    current_key = FLOW_STEP_ALIASES.get(current_key, current_key)
    current_index = next((index for index, (key, _label) in enumerate(FLOW_STEPS) if key == current_key), 0)
    steps_html = []
    for index, (_key, label) in enumerate(FLOW_STEPS):
        classes = ["apple-step"]
        if index < current_index:
            classes.append("done")
        elif index == current_index:
            classes.append("active")
        steps_html.append(f'<div class="{" ".join(classes)}">{index + 1}. {label}</div>')
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


def detect_role_title(job_description: str) -> str:
    """Infer a role title from the pasted job description."""
    if not job_description.strip():
        return ""

    top_section = job_description[:700]
    role_suffixes = "|".join(
        [
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
        ]
    )
    ignore_markers = [
        "requirements",
        "education",
        "years of experience",
        "skills",
        "physical requirements",
        "safety",
        "salary",
        "benefits",
        "preferred",
    ]
    patterns = [
        r"(?im)^\s*(?:job title|title|role|position)\s*[:\-]\s*(.+)$",
        rf"(?im)^\s*([A-Z][A-Za-z/&,\-\s]{{2,80}}(?:{role_suffixes}))\s*$",
        rf"(?i)\bthe\s+([A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes}))\s+(?:plays|is|will|works|supports|leads)\b",
        rf"\b((?:Senior|Lead|Principal|Staff|Junior|Associate|Assistant)\s+[A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes})|[A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes}))\b",
    ]
    for pattern in patterns:
        for text_block in [top_section, job_description]:
            matches = re.findall(pattern, text_block)
            if not matches:
                continue
            for raw_match in matches:
                cleaned_match = " ".join(raw_match.split())
                cleaned_match = re.sub(
                    r"^(?:about the job|job description|job)\s+",
                    "",
                    cleaned_match,
                    flags=re.IGNORECASE,
                ).strip()
                cleaned_match = re.sub(r"^the\s+", "", cleaned_match, flags=re.IGNORECASE).strip()
                cleaned_match = re.sub(r"\s+-\s+remote$", "", cleaned_match, flags=re.IGNORECASE).strip()
                lowered = cleaned_match.lower()
                if any(marker in lowered for marker in ignore_markers):
                    continue
                if len(cleaned_match) > 90:
                    continue
                return cleaned_match

    for line in job_description.splitlines()[:12]:
        cleaned = " ".join(line.split())
        if not cleaned or len(cleaned) > 90:
            continue
        lowered = cleaned.lower()
        if any(marker in lowered for marker in ignore_markers):
            continue
        if any(keyword.lower() in cleaned.lower() for keyword in ROLE_KEYWORDS):
            return cleaned

    return ""


def detect_industry(job_description: str) -> str:
    """Infer an industry bucket from the pasted job description."""
    text = job_description.lower()
    if not text:
        return ""

    keyword_map = {
        "Supply Chain / Operations": [
            "supply chain",
            "logistics",
            "transportation",
            "warehouse",
            "inventory",
            "distribution",
            "carrier",
            "routing",
            "fulfillment",
            "delivery network",
        ],
        "Finance": ["finance", "financial", "fp&a", "banking", "investment", "accounting", "budget", "forecasting"],
        "Consulting": ["consulting", "client engagement", "advisory", "strategy projects"],
        "Technology": ["software", "saas", "cloud", "developer", "product", "tech", "automation platform"],
        "Healthcare": ["healthcare", "clinical", "patient", "medical", "hospital", "pharma"],
        "Marketing": ["marketing", "brand", "campaign", "growth", "content", "seo"],
    }
    scores = {
        industry: sum(text.count(keyword) for keyword in keywords)
        for industry, keywords in keyword_map.items()
    }
    best_industry = max(scores, key=scores.get)
    if scores[best_industry] > 0:
        return best_industry
    return "General Business"


def get_effective_target_role(job_description: str) -> str:
    """Use the manual override when present, otherwise JD detection."""
    return (
        st.session_state.target_role.strip()
        or (st.session_state.jd_role_hint.strip() if st.session_state.jd_source_url else "")
        or detect_role_title(job_description)
        or "the target role"
    )


def get_effective_industry(job_description: str) -> str:
    """Use the manual override when present, otherwise JD detection."""
    return st.session_state.target_industry.strip() or detect_industry(job_description)


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


def init_session_state() -> None:
    """Initialize expected session keys."""
    defaults = {
        "screen": "landing",
        "resume_name": None,
        "resume_bytes": None,
        "resume_text": None,
        "resume_paragraphs": [],
        "job_description": "",
        "career_stage": CAREER_STAGES[0],
        "target_role": "",
        "target_industry": "",
        "execution_mode": None,
        "selected_provider": "OpenAI",
        "generated_prompt": None,
        "api_prompt_customized": False,
        "api_prompt_override": "",
        "validated_payload": None,
        "validation_summary": None,
        "output_docx_bytes": None,
        "output_filename": None,
        "last_error": None,
        "review_details": None,
        "builder_full_name": "",
        "builder_contact_info": "",
        "builder_education": "",
        "builder_experience_dump": "",
        "builder_activities": "",
        "builder_skills": "",
        "builder_job_description": "",
        "builder_prompt": "",
        "builder_payload": None,
        "builder_validation_summary": None,
        "builder_output_docx_bytes": None,
        "builder_output_filename": None,
        "jd_source_url": "",
        "jd_cleaning_result": None,
        "show_review_changes": False,
        "pending_job_description_input": None,
        "jd_role_hint": "",
        "custom_api_base_url": "http://localhost:11434/v1",
        "custom_api_model": "mistral",
        "custom_api_key": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_flow() -> None:
    """Reset the prototype flow to the landing page."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()


def save_uploaded_resume(uploaded_file) -> None:
    """Store uploaded resume data and extracted plain text in session state."""
    resume_bytes = uploaded_file.getvalue()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(resume_bytes)
        temp_path = temp_file.name

    try:
        resume_text = extract_text(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    st.session_state.resume_name = uploaded_file.name
    st.session_state.resume_bytes = resume_bytes
    st.session_state.resume_text = resume_text
    st.session_state.resume_paragraphs = [
        paragraph.strip()
        for paragraph in resume_text.splitlines()
        if paragraph.strip()
    ]


def analyze_payload(payload: dict) -> dict:
    """Run match diagnostics against the uploaded resume."""
    if not st.session_state.resume_bytes or not st.session_state.resume_name:
        raise ValueError("Upload a resume before validating output.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(st.session_state.resume_bytes)
        temp_path = temp_file.name

    try:
        return analyze_payload_against_document(temp_path, payload)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def build_output_docx(payload: dict) -> tuple[bytes, str]:
    """Apply replacements and return the optimized .docx bytes."""
    if not st.session_state.resume_bytes or not st.session_state.resume_name:
        raise ValueError("Upload a resume before exporting.")

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / st.session_state.resume_name
        input_path.write_bytes(st.session_state.resume_bytes)

        success, message = apply_replacements(str(input_path), payload)
        if not success:
            raise ValueError(message)

        output_path = input_path.with_name(f"{input_path.stem}_Optimized{input_path.suffix}")
        if not output_path.exists():
            raise ValueError("The optimized document was not created.")

        return output_path.read_bytes(), message


def ensure_export_file_ready() -> None:
    """Generate the optimized output once when export is safe."""
    if st.session_state.output_docx_bytes or not st.session_state.validated_payload:
        return

    output_bytes, _message = build_output_docx(st.session_state.validated_payload)
    original_name = Path(st.session_state.resume_name)
    st.session_state.output_docx_bytes = output_bytes
    st.session_state.output_filename = f"{original_name.stem}_Optimized{original_name.suffix}"


def render_landing() -> None:
    """Landing page."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Resume Optimizer</div>
            <h1>Make resume tailoring feel beautifully simple.</h1>
            <p>Start with your draft, aim it at the role you want, and move through a guided flow that feels calm, clear, and polished from start to download.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(
            """
            <div class="apple-landing-card featured">
              <div>
                <div class="apple-kicker">Most Popular</div>
                <div class="apple-landing-card-title">Optimize an existing resume</div>
                <div class="apple-landing-card-copy">Refine the resume you already have for a specific role, then review the final changes before you export it.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-primary">', unsafe_allow_html=True)
        if st.button("Start Optimizing", use_container_width=True, key="landing-optimize"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            """
            <div class="apple-landing-card">
              <div>
                <div class="apple-kicker">Builder Path</div>
                <div class="apple-landing-card-title">Build your first resume</div>
                <div class="apple-landing-card-copy">Start with a plain-English brain dump and shape it into a clean first draft with more guidance built in.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-secondary">', unsafe_allow_html=True)
        if st.button("Build First Resume", use_container_width=True, key="landing-builder"):
            st.session_state.career_stage = "Student"
            st.session_state.screen = "builder_input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_input_screen() -> None:
    """Resume and job input screen."""
    def fetch_and_store_job_description(job_input: str) -> bool:
        """Fetch, clean, and store JD text from a pasted URL."""
        try:
            with st.spinner("Validating link and extracting the job description..."):
                extracted_text, final_url, role_hint = fetch_job_description_from_url(job_input)
            cleaning_result = clean_job_description(extracted_text)
            cleaned_text = cleaning_result["cleaned_text"]
            st.session_state.job_description = cleaned_text
            st.session_state.pending_job_description_input = cleaned_text
            st.session_state.jd_source_url = final_url
            st.session_state.jd_cleaning_result = cleaning_result
            st.session_state.jd_role_hint = role_hint or detect_role_title(cleaned_text)
            st.success("Job description extracted and cleaned successfully. Review the text below before continuing.")
            return True
        except Exception as error:
            st.warning(f"{error} Please paste the job description text manually if the page blocks extraction.")
            return False

    def clean_pasted_job_description(job_input: str) -> bool:
        """Normalize manually pasted JD text so downstream detection is cleaner."""
        cleaned_result = clean_job_description(job_input)
        cleaned_text = cleaned_result["cleaned_text"]
        st.session_state.job_description = cleaned_text
        st.session_state.pending_job_description_input = cleaned_text
        st.session_state.jd_source_url = ""
        st.session_state.jd_cleaning_result = cleaned_result
        st.session_state.jd_role_hint = detect_role_title(cleaned_text)
        st.success("Job description cleaned and ready. Review the text below before continuing.")
        return True

    render_shell_start()
    render_screen_intro(
        "input",
        "Step 1 of 5",
        "Bring in your resume. Then point it at the role you want.",
        "We’ll clean the job description, detect the signals that matter, and keep the next step simple.",
    )

    upload_col, jd_col = st.columns([1, 1.15], gap="large")
    with upload_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Upload your resume</div>
                <div class="apple-section-copy">Use a <code>.docx</code> file. We preserve the document structure so the finished export still feels like your original resume, just sharper.</div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"], label_visibility="collapsed")
            if uploaded_file is not None:
                save_uploaded_resume(uploaded_file)
                st.success(f"Loaded `{uploaded_file.name}`")
                render_chip_row([uploaded_file.name, "Ready for optimization"])

    with jd_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Paste a job description or link</div>
                <div class="apple-section-copy">Use the full posting or a job link. We’ll turn it into a cleaner brief for the next step and surface the role signals automatically.</div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.pending_job_description_input is not None:
                st.session_state.job_description_input = st.session_state.pending_job_description_input
                st.session_state.pending_job_description_input = None

            if "job_description_input" not in st.session_state:
                st.session_state.job_description_input = st.session_state.job_description

            job_description = st.text_area(
                "Job Description",
                height=130,
                placeholder="Paste the job description here, or drop in a job-post URL.",
                key="job_description_input",
                label_visibility="collapsed",
            )
            job_description = st.session_state.get("job_description_input", job_description)
            st.markdown(
                '<div class="apple-minor-copy">We’ll clean the text, detect the target role, and prepare the prompt inputs for you.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Process Job Description", use_container_width=True):
                current_input = st.session_state.get("job_description_input", job_description)
                if looks_like_url(current_input):
                    if fetch_and_store_job_description(current_input):
                        st.rerun()
                elif current_input.strip():
                    if clean_pasted_job_description(current_input):
                        st.rerun()
                else:
                    st.info("Paste a job description or job link first.")
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.jd_source_url and not looks_like_url(st.session_state.job_description):
        st.caption(f"Loaded from URL: {st.session_state.jd_source_url}")
    if st.session_state.jd_cleaning_result:
        cleaning_result = st.session_state.jd_cleaning_result
        st.success(str(cleaning_result["confidence_message"]))

    detected_role = (
        st.session_state.jd_role_hint if st.session_state.jd_source_url else detect_role_title(job_description)
    )
    detected_industry = detect_industry(job_description) if job_description.strip() else ""

    with st.container(border=True):
        st.markdown(
            """
            <div class="apple-kicker">Role Context</div>
            <div class="apple-section-title">We found the important context for this role.</div>
            <div class="apple-section-copy">Use this as a quick checkpoint before continuing. The detected signals and selected tone shape the prompt you run next.</div>
            """,
            unsafe_allow_html=True,
        )

        context_col1, context_col2 = st.columns([1.35, 0.85], gap="large")
        with context_col1:
            st.markdown(
                """
                <div class="apple-kicker">Detected Signals</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                build_inline_chip_row(
                    [
                        f"Role: {detected_role or 'Not detected yet'}",
                        f"Industry: {detected_industry or 'Not detected yet'}",
                    ]
                ),
                unsafe_allow_html=True,
            )
        with context_col2:
            st.markdown(
                """
                <div class="apple-kicker">Tone</div>
                <div class="apple-minor-copy">Choose your career stage.</div>
                """,
                unsafe_allow_html=True,
            )
            career_stage = st.selectbox(
                "Career Stage",
                CAREER_STAGES,
                index=CAREER_STAGES.index(st.session_state.career_stage),
                label_visibility="collapsed",
            )

        with st.expander("Advanced options", expanded=False):
            st.markdown(
                '<div class="apple-section-copy">Override the detected role or industry only if you want to steer the prompt more explicitly.</div>',
                unsafe_allow_html=True,
            )
            target_role = st.text_input(
                "Target Role Title Override",
                value=st.session_state.target_role,
                placeholder=detected_role or "Example: Product Manager Intern",
                help="Leave blank to use the detected role title from the JD.",
            )
            industry_options = INDUSTRIES if st.session_state.target_industry in INDUSTRIES else [""] + INDUSTRIES[1:]
            target_industry = st.selectbox(
                "Industry Override",
                industry_options,
                index=industry_options.index(st.session_state.target_industry),
                help="Leave blank to use the detected industry from the JD.",
            )

    st.session_state.job_description = job_description
    st.session_state.career_stage = career_stage
    st.session_state.target_role = target_role
    st.session_state.target_industry = target_industry

    col1, col2 = st.columns([0.7, 1.3], gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
        )
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Continue", use_container_width=True, disabled=not can_continue):
            if looks_like_url(job_description):
                if fetch_and_store_job_description(job_description):
                    st.rerun()
            else:
                st.session_state.jd_cleaning_result = None
                st.session_state.screen = "mode"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_input_screen() -> None:
    """Student-friendly first-resume intake flow."""
    render_shell_start()
    render_screen_intro(
        "builder_input",
        "Step 1 of 4",
        "Build your first resume.",
        "Tell us about yourself in plain English. We’ll shape it into a professional draft.",
    )

    basics_col, extras_col = st.columns(2, gap="large")
    with basics_col:
        st.markdown('<div class="apple-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">The Basics</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Start with the story you already have.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Add the essentials first: who you are, where you studied, and the experience you want the draft to reflect.</div>',
            unsafe_allow_html=True,
        )
        full_name = st.text_input(
            "Full Name",
            value=st.session_state.builder_full_name,
            placeholder="Example: Jane Doe",
        )
        contact_info = st.text_area(
            "Contact Info",
            value=st.session_state.builder_contact_info,
            height=110,
            placeholder="Email, phone, location, LinkedIn, portfolio, or anything else you want on the resume.",
        )
        education = st.text_area(
            "Education",
            value=st.session_state.builder_education,
            height=140,
            placeholder="School, major, graduation date, GPA, coursework, honors, certifications.",
        )
        experience_dump = st.text_area(
            "Experience Brain Dump",
            value=st.session_state.builder_experience_dump,
            height=200,
            placeholder="Part-time jobs, internships, volunteer work, responsibilities, wins, numbers, anything you remember.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with extras_col:
        st.markdown('<div class="apple-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Extras & Target</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Add anything that sharpens the draft.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">This is where you give the builder more context about your activities, skills, target role, and any job you want to aim for.</div>',
            unsafe_allow_html=True,
        )
        activities = st.text_area(
            "Activities / Leadership / Projects",
            value=st.session_state.builder_activities,
            height=140,
            placeholder="Clubs, leadership roles, case competitions, capstone projects, side projects, community work.",
        )
        skills = st.text_area(
            "Skills",
            value=st.session_state.builder_skills,
            height=110,
            placeholder="Tools, languages, technical skills, certifications, strengths.",
        )
        builder_job_description = st.text_area(
            "Optional Job Description",
            value=st.session_state.builder_job_description,
            height=170,
            placeholder="Paste a target internship or job description if you have one.",
        )
        career_stage = st.selectbox(
            "Career Stage",
            CAREER_STAGES,
            index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
        )
        target_role = st.text_input(
            "Target Role Title",
            value=st.session_state.target_role,
            placeholder="Example: Business Analyst Intern",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.builder_full_name = full_name
    st.session_state.builder_contact_info = contact_info
    st.session_state.builder_education = education
    st.session_state.builder_experience_dump = experience_dump
    st.session_state.builder_activities = activities
    st.session_state.builder_skills = skills
    st.session_state.builder_job_description = builder_job_description
    st.session_state.career_stage = career_stage
    st.session_state.target_role = target_role

    col1, col2 = st.columns([0.8, 1.2], gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="builder-back"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        can_continue = bool(full_name.strip() and education.strip() and experience_dump.strip() and target_role.strip())
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Generate Builder Prompt", use_container_width=True, disabled=not can_continue):
            st.session_state.builder_prompt = build_builder_prompt(
                full_name=full_name,
                contact_info=contact_info,
                education=education,
                experience_dump=experience_dump,
                activities=activities,
                skills=skills,
                job_description=builder_job_description,
                career_stage=career_stage,
                target_role=target_role,
            )
            st.session_state.screen = "builder_stub"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_stub_screen() -> None:
    """Builder prompt handoff screen."""
    render_shell_start()
    render_screen_intro(
        "builder_stub",
        "Step 2 of 4",
        "Generate your draft.",
        "Copy the prompt to your AI tool and bring back the structured result.",
    )

    builder_rows = [
        ("Career stage", st.session_state.career_stage or "Student"),
        ("Target role", st.session_state.target_role or "Not set"),
        ("Has job description", "Yes" if st.session_state.builder_job_description.strip() else "No"),
    ]
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.markdown('<div class="apple-kicker">Builder Context</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-section-title">Your draft setup is ready.</div>', unsafe_allow_html=True)
    st.markdown(build_readiness_rows(builder_rows), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    render_prompt_block("Generated Builder Prompt", st.session_state.builder_prompt, 360, "builder")
    st.markdown("</div>", unsafe_allow_html=True)

    render_instruction_panel(
        "What To Do Next",
        [
            "Copy the builder prompt above and paste it into ChatGPT, Claude, or Gemini.",
            "Ask the AI to return only the structured JSON output for the first resume.",
            "Paste the AI result below, then click Validate Builder Output.",
        ],
    )

    st.markdown('<div class="apple-panel">', unsafe_allow_html=True)
    pasted_output = st.text_area(
        "Paste Builder Output",
        height=280,
        placeholder="Paste the AI response here.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Builder Intake Snapshot", expanded=False):
        st.text_area("Full Name", value=st.session_state.builder_full_name, height=68, disabled=True)
        st.text_area("Contact Info", value=st.session_state.builder_contact_info, height=100, disabled=True)
        st.text_area("Education", value=st.session_state.builder_education, height=120, disabled=True)
        st.text_area("Experience Brain Dump", value=st.session_state.builder_experience_dump, height=160, disabled=True)
        st.text_area("Activities / Leadership / Projects", value=st.session_state.builder_activities, height=140, disabled=True)
        st.text_area("Skills", value=st.session_state.builder_skills, height=100, disabled=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Edit Builder Inputs", use_container_width=True):
            st.session_state.screen = "builder_input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Validate Builder Output", use_container_width=True):
            try:
                payload = parse_builder_payload(pasted_output)
                st.session_state.builder_payload = payload
                st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                st.session_state.builder_output_docx_bytes = None
                st.session_state.builder_output_filename = None
                st.session_state.screen = "builder_review"
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Back to Landing", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_review_screen() -> None:
    """Review validated builder output before full document generation exists."""
    payload = st.session_state.builder_payload or {}
    summary = st.session_state.builder_validation_summary or {}
    stats = summary.get("stats", {})
    basics = payload.get("basics", {})

    render_shell_start()
    render_screen_intro(
        "builder_review",
        "Step 3 of 4",
        "Review your foundation.",
        "Your draft is structurally valid and ready to be converted into a .docx file.",
    )

    st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
    st.markdown('<div class="apple-summary-label">Builder Summary</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-summary-title">A quick view of the content blocks that are ready for your first draft.</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4, gap="large")
    with col1:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Education</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("education_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Education items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Experience</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("experience_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Experience items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Projects</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("project_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Project items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Skills</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("skills_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Skill groups")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.markdown('<div class="apple-kicker">Resume Content Snapshot</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-section-title">Review the structure before you create the .docx file.</div>', unsafe_allow_html=True)
    st.markdown(
        build_readiness_rows(
            [
                ("Full name", basics.get("full_name", "") or "Missing"),
                ("Email", basics.get("email", "") or "Missing"),
                ("Phone", basics.get("phone", "") or "Missing"),
                ("Location", basics.get("location", "") or "Missing"),
                ("LinkedIn", basics.get("linkedin", "") or "Missing"),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.text_area("Professional Summary", value=payload.get("summary", ""), height=120, disabled=True)

    with st.expander("Education Preview", expanded=True):
        for index, item in enumerate(payload.get("education", []), start=1):
            st.markdown(f"**Education {index}**")
            st.write(f"{item.get('school', '')} | {item.get('degree', '')} | {item.get('graduation_date', '')}")
            if item.get("details"):
                st.code("\n".join(item["details"]), language="text")

    with st.expander("Experience Preview", expanded=True):
        for index, item in enumerate(payload.get("experience", []), start=1):
            st.markdown(f"**Experience {index}**")
            st.write(
                f"{item.get('title', '')} | {item.get('organization', '')} | "
                f"{item.get('location', '')} | {item.get('dates', '')}"
            )
            if item.get("bullets"):
                st.code("\n".join(item["bullets"]), language="text")

    with st.expander("Projects Preview", expanded=False):
        for index, item in enumerate(payload.get("projects", []), start=1):
            st.markdown(f"**Project {index}: {item.get('name', '')}**")
            if item.get("details"):
                st.code("\n".join(item["details"]), language="text")

    with st.expander("Skills Preview", expanded=False):
        st.code("\n".join(payload.get("skills", [])), language="text")

    with st.expander("Validated Builder Payload", expanded=False):
        st.json(payload)
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Builder Prompt", use_container_width=True):
            st.session_state.screen = "builder_stub"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Generate Resume .docx", use_container_width=True):
            try:
                st.session_state.builder_output_docx_bytes = build_resume_from_scratch(payload)
                safe_name = (basics.get("full_name", "First_Resume").strip() or "First_Resume").replace(" ", "_")
                st.session_state.builder_output_filename = f"{safe_name}_Resume.docx"
                st.success("First resume document generated successfully.")
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.builder_output_docx_bytes and st.session_state.builder_output_filename:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        st.download_button(
            "Download First Resume (.docx)",
            data=io.BytesIO(st.session_state.builder_output_docx_bytes),
            file_name=st.session_state.builder_output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Back to Landing", use_container_width=True, key="builder-review-landing"):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_mode_screen() -> None:
    """Execution mode selection screen."""
    render_shell_start()
    render_screen_intro(
        "mode",
        "Step 3 of 5",
        "Choose the path that feels right for you.",
        "Every option uses the same prompt logic and the same review flow. The difference is how hands-on you want to be.",
    )

    st.markdown(
        """
        <style>
        [data-testid="stVerticalBlockBorderWrapper"] {
            min-height: 420px;
        }

        [data-testid="stVerticalBlockBorderWrapper"] > div,
        [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
            min-height: 100%;
            height: 100%;
        }

        .apple-choice-copy {
            min-height: 8.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    manual_col, api_col, local_col = st.columns(3, gap="large")
    with manual_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-kicker">Manual</div>
                <div class="apple-choice-title">Copy the prompt and use your favorite AI.</div>
                <div class="apple-choice-copy">Great if you want total control, prefer free tools, or want to compare outputs across ChatGPT, Claude, Gemini, or something else.</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Choose Manual Mode", use_container_width=True):
                st.session_state.execution_mode = "manual"
                st.session_state.generated_prompt = build_optimizer_prompt(
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    st.session_state.career_stage,
                    get_effective_target_role(st.session_state.job_description),
                    get_effective_industry(st.session_state.job_description),
                )
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "manual"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with api_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-kicker">Automatic</div>
                <div class="apple-choice-title">Let the app run the optimization for you.</div>
                <div class="apple-choice-copy">Use your own provider key, get the same validated review flow automatically, and move from prompt to export with much less friction.</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Choose API Mode", use_container_width=True):
                st.session_state.execution_mode = "api"
                st.session_state.generated_prompt = build_optimizer_prompt(
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    st.session_state.career_stage,
                    get_effective_target_role(st.session_state.job_description),
                    get_effective_industry(st.session_state.job_description),
                )
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "api"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    with local_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-kicker">Advanced</div>
                <div class="apple-choice-title">Use a local model or custom endpoint.</div>
                <div class="apple-choice-copy">Ideal for demos, Ollama, or self-hosted setups that still need the same validation and export safeguards.</div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Use Local / Custom", use_container_width=True):
                st.session_state.execution_mode = "api"
                st.session_state.selected_provider = "Local Model / Custom Endpoint"
                st.session_state.generated_prompt = build_optimizer_prompt(
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    st.session_state.career_stage,
                    get_effective_target_role(st.session_state.job_description),
                    get_effective_industry(st.session_state.job_description),
                )
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "api"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    back_col, _, _ = st.columns([1, 2, 2])
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def handle_validated_payload(payload: dict) -> None:
    """Store validation state and move to review."""
    st.session_state.validated_payload = payload
    st.session_state.validation_summary = build_validation_summary(payload)
    st.session_state.review_details = analyze_payload(payload)
    st.session_state.output_docx_bytes = None
    st.session_state.output_filename = None
    st.session_state.show_review_changes = False
    st.session_state.screen = "review"


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


def render_manual_screen() -> None:
    """Manual BYOM screen."""
    render_screen_intro(
        "manual",
        "Step 4 of 5",
        "Manual Optimization",
        "Copy the prompt into your AI tool, then paste the structured result back here.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Step 1</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Copy the generated prompt.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Manual copy-paste works best on desktop. Ask your AI tool to return only the structured JSON result.</div>',
            unsafe_allow_html=True,
        )
        render_prompt_block("Generated Prompt", st.session_state.generated_prompt or "", 320, "manual")
        st.markdown('<div class="apple-kicker">Step 2</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Follow the handoff steps.</div>', unsafe_allow_html=True)
        render_instruction_panel(
            "What To Do Next",
            [
                "Copy the prompt above and paste it into ChatGPT, Claude, or Gemini.",
                "Ask the AI to return only the structured JSON output with no extra explanation.",
                "Paste the AI result into the box below, then click Validate Output.",
            ],
        )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Step 3</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Paste the AI response.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Bring back the full structured output exactly as your AI tool returned it.</div>',
            unsafe_allow_html=True,
        )
        pasted_output = st.text_area(
            "Paste Structured AI Output",
            height=260,
            placeholder="Paste the AI response here.",
        )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Validate Output", use_container_width=True):
            try:
                payload = parse_replacement_payload(pasted_output)
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)


def render_api_screen() -> None:
    """Multi-provider API mode screen."""
    render_screen_intro(
        "api",
        "Step 4 of 5",
        "Run via API",
        "Use your own hosted or local model. The app validates the output before export.",
    )

    if not st.session_state.api_prompt_override and st.session_state.generated_prompt:
        st.session_state.api_prompt_override = st.session_state.generated_prompt

    api_key = ""
    base_url = ""
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Setup</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Choose your provider.</div>', unsafe_allow_html=True)

        provider = st.selectbox(
            "Provider",
            list(PROVIDER_CONFIG.keys()),
            index=list(PROVIDER_CONFIG.keys()).index(st.session_state.selected_provider),
        )
        st.session_state.selected_provider = provider
        provider_config = PROVIDER_CONFIG[provider]
        st.markdown(
            f'<div class="apple-section-copy">{provider_config.get("description", "")}</div>',
            unsafe_allow_html=True,
        )

        if provider == "Local Model / Custom Endpoint":
            st.markdown(
                '<div class="apple-section-copy">Works with Ollama and other OpenAI-compatible local endpoints.</div>',
                unsafe_allow_html=True,
            )
            base_url = st.text_input(
                "Base URL",
                value=st.session_state.custom_api_base_url,
                placeholder="http://localhost:11434/v1",
                help="For Ollama, use http://localhost:11434/v1",
            )
            model = st.text_input(
                "Model name",
                value=st.session_state.custom_api_model,
                placeholder="mistral",
                help="Use the exact local model tag available on your machine.",
            )
            api_key = st.text_input(
                provider_config["key_label"],
                type="password",
                value=st.session_state.custom_api_key,
                placeholder=provider_config["placeholder"],
                help="Most local endpoints do not require a key. Leave blank if not needed.",
            )
            st.session_state.custom_api_base_url = base_url
            st.session_state.custom_api_model = model
            st.session_state.custom_api_key = api_key
            st.markdown(
                '<div class="apple-section-copy">Local models can return malformed JSON. If that happens, retry or switch to Manual Mode.</div>',
                unsafe_allow_html=True,
            )
        else:
            api_key = st.text_input(
                provider_config["key_label"],
                type="password",
                placeholder=provider_config["placeholder"],
            )
            model = st.selectbox("Model", provider_config["models"], index=0)
            st.markdown(
                '<div class="apple-section-copy">Your key is used only for this session and is not stored.</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="apple-section-copy">After the provider responds, the same JSON validator and exact-match review still run before export.</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Prompt Preview", expanded=False):
            customize_prompt = st.checkbox(
                "Customize prompt before sending",
                value=st.session_state.api_prompt_customized,
                help="Advanced option. Editing the prompt may reduce JSON reliability.",
            )
            st.session_state.api_prompt_customized = customize_prompt
            if customize_prompt:
                edited_prompt = st.text_area(
                    "Editable Prompt",
                    value=st.session_state.api_prompt_override or st.session_state.generated_prompt or "",
                    height=260,
                    key="api-prompt-editor",
                    help="Advanced option. Keep the JSON instructions intact for best results.",
                )
                st.session_state.api_prompt_override = edited_prompt
                if st.button("Reset to Recommended Prompt", key="reset-api-prompt"):
                    st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                    st.session_state.api_prompt_customized = False
                    st.rerun()
                st.markdown(
                    '<div class="apple-section-copy">Changing the prompt may reduce JSON reliability. Use this only if you know what you want to adjust.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.text_area(
                    "Prompt Preview",
                    value=st.session_state.generated_prompt or "",
                    height=220,
                    disabled=True,
                )

    prompt_to_send = (
        st.session_state.api_prompt_override.strip()
        if st.session_state.api_prompt_customized and st.session_state.api_prompt_override.strip()
        else st.session_state.generated_prompt
    )

    checklist = [
        ("Resume", "Loaded" if st.session_state.resume_name else "Missing"),
        ("Job description", "Loaded" if st.session_state.job_description.strip() else "Missing"),
        ("Provider", provider),
        ("Model", model if model else "Missing"),
        ("Prompt mode", "Customized" if st.session_state.api_prompt_customized else "Recommended"),
    ]
    if provider == "Local Model / Custom Endpoint":
        checklist.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
    else:
        checklist.append(("API key", "Provided" if api_key.strip() else "Missing"))
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
        st.markdown(build_readiness_rows(checklist), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Run Optimization", use_container_width=True):
            try:
                with st.spinner(f"Sending prompt to {provider}..."):
                    payload = optimize_with_provider(
                        provider=provider,
                        api_key=api_key,
                        prompt=prompt_to_send,
                        model=model,
                        base_url=base_url,
                    )
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Switch to Manual Mode", use_container_width=True):
            st.session_state.execution_mode = "manual"
            st.session_state.screen = "manual"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_review_screen() -> None:
    """Validation and export screen."""
    summary = st.session_state.validation_summary or {}
    stats = summary.get("stats", {})
    review_details = st.session_state.review_details or {}
    review_stats = review_details.get("stats", {})
    review_results = review_details.get("results", [])
    review_warnings = review_details.get("warnings", [])
    ready_for_export = review_stats.get("ready_for_export", False)
    manual_review_count = review_stats.get("unmatched_replacements", 0) + review_stats.get("duplicate_replacements", 0)
    grouped_results = _group_review_results(review_results)

    if ready_for_export and not st.session_state.output_docx_bytes:
        try:
            ensure_export_file_ready()
        except Exception as error:
            st.error(str(error))
            ready_for_export = False

    render_screen_intro(
        "review",
        "Step 4 of 5",
        "Validation and Export",
        "Review the optimized result, confirm the changes, and download when everything looks right.",
    )
    if not st.session_state.show_review_changes:
        if ready_for_export:
            st.success("All replacements validated successfully.")
            st.markdown("Your resume has been optimized and is ready to download.")
        else:
            st.warning("This result needs review before export.")
            st.markdown("We validated the structured output, but some replacements still need attention before download.")

        with st.container(border=True):
            st.markdown('<div class="apple-summary-label">Optimization Summary</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-summary-title">A quick view of what changed before you export.</div>', unsafe_allow_html=True)

            summary_col1, summary_col2, summary_col3 = st.columns(3, gap="large")
            with summary_col1:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Summary Section</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("summary_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("summary_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)
            with summary_col2:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Bullet Points</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("bullet_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("bullet_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)
            with summary_col3:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Skills Section</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("skills_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("skills_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)

            readiness_rows = [
                ("Exact matches", str(review_stats.get("matched_replacements", 0))),
                ("Issues found", "0" if ready_for_export else str(manual_review_count)),
                ("Export status", "Safe to export" if ready_for_export else "Needs review"),
            ]
            st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

        if review_warnings:
            for warning in review_warnings:
                st.caption(warning)

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                st.download_button(
                    "Download Optimized Resume (.docx)",
                    data=io.BytesIO(st.session_state.output_docx_bytes),
                    file_name=st.session_state.output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            else:
                st.button("Download Optimized Resume (.docx)", use_container_width=True, disabled=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with action_col2:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Review Changes", use_container_width=True):
                st.session_state.show_review_changes = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with action_col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Start Over", use_container_width=True):
                reset_flow()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        previous_screen = "manual" if st.session_state.execution_mode == "manual" else "api"
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = previous_screen
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if st.button("Back", key="review-back-button"):
        st.session_state.show_review_changes = False
        st.rerun()

    st.subheader("Optimization Summary")
    st.caption("Review only the sections you care about. Everything is collapsed by default.")

    render_review_section("Summary Section", grouped_results.get("Summary", []), expanded=manual_review_count > 0)
    render_review_section("Bullet Points", grouped_results.get("Bullet", []), expanded=False)
    render_review_section("Skills Section", grouped_results.get("Skills", []), expanded=False)

    if manual_review_count and st.session_state.resume_paragraphs:
        with st.expander("Need help finding the exact resume text?", expanded=False):
            st.caption("If the AI used the wrong wording, use the exact text below from your resume.")
            for index, paragraph in enumerate(st.session_state.resume_paragraphs, start=1):
                st.text_area(
                    f"Resume text {index}",
                    value=paragraph,
                    height=90,
                    disabled=True,
                    key=f"resume-helper-{index}",
                )

    bottom_col1, bottom_col2, bottom_col3 = st.columns(3)
    with bottom_col1:
        if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
            st.download_button(
                "Download Optimized Resume",
                data=io.BytesIO(st.session_state.output_docx_bytes),
                file_name=st.session_state.output_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        else:
            st.button("Download Optimized Resume", use_container_width=True, disabled=True)
    with bottom_col2:
        if st.button("Back", use_container_width=True, key="review-back-bottom"):
            st.session_state.show_review_changes = False
            st.rerun()
    with bottom_col3:
        if st.button("Start Over", use_container_width=True, key="review-start-over"):
            reset_flow()
            st.rerun()


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(page_title="Resume Optimizer", page_icon="📄", layout="wide")
    init_session_state()
    apply_apple_theme()

    with st.sidebar:
        st.markdown("### Resume Optimizer")
        st.caption("A calmer way to tailor resumes with AI-guided review before export.")
        render_chip_row(["Apple-inspired redesign", "Prototype build"])
        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
        st.write("Use the guided flow to upload, target, run, review, and download with confidence.")
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Start Over", use_container_width=True, key="sidebar-start-over"):
            reset_flow()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    screen = st.session_state.screen
    if screen == "landing":
        render_landing()
    elif screen == "input":
        render_input_screen()
    elif screen == "builder_input":
        render_builder_input_screen()
    elif screen == "builder_stub":
        render_builder_stub_screen()
    elif screen == "builder_review":
        render_builder_review_screen()
    elif screen == "mode":
        render_mode_screen()
    elif screen == "manual":
        render_manual_screen()
    elif screen == "api":
        render_api_screen()
    elif screen == "review":
        render_review_screen()


if __name__ == "__main__":
    main()
