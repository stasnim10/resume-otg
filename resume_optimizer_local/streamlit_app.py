"""
Streamlit prototype for the Resume Optimizer MVP.
"""
from __future__ import annotations

import io
import json
import re
import tempfile
import html
from collections import Counter
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
    collect_replacements,
    parse_builder_payload,
    parse_replacement_payload,
)
from profile_extractor import extract_profile_items_from_text
from profile_matcher import rank_profile_items
from profile_schema import ProfileItem
from profile_store import (
    archive_profile_item,
    create_or_get_profile,
    get_application,
    init_profile_db,
    link_profile_items_to_application,
    list_applications,
    list_profile_items,
    list_profile_sources,
    list_resume_assets,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    save_resume_asset,
    update_resume_asset,
    update_profile_item,
    update_profile_item_verification,
    upsert_application,
)
from prompt_engine import build_builder_prompt, build_optimizer_prompt
from resume_evaluator import evaluate_resume_fit
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

        .apple-journey-strip {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0.9rem;
          margin: -0.8rem auto 2.4rem auto;
          max-width: 880px;
        }

        .apple-journey-pill {
          background: rgba(255,255,255,0.72);
          border: 1px solid var(--line);
          border-radius: 22px;
          padding: 1rem 1.1rem;
          min-height: 92px;
        }

        .apple-journey-label {
          font-size: 0.74rem;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted-light);
          font-weight: 600;
          margin-bottom: 0.45rem;
        }

        .apple-journey-value {
          font-size: 1rem;
          line-height: 1.5;
          color: var(--text);
          font-weight: 560;
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
          max-width: 26ch;
        }

        .apple-section-copy {
          color: var(--muted);
          font-size: 1rem;
          line-height: 1.72;
          margin-bottom: 1.1rem;
          max-width: 62ch;
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
          background: linear-gradient(180deg, #ffffff 0%, #fcfcfe 100%);
          border: 1px solid var(--line);
          border-radius: 28px;
          padding: 2.15rem;
          margin: 1rem 0 1.2rem 0;
          box-shadow: var(--shadow-soft);
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
          background: var(--surface-muted);
          border: 1px solid var(--line);
          border-radius: 20px;
          padding: 1rem 1.05rem;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }

        .apple-stat-value {
          font-size: 2.3rem;
          line-height: 1;
          letter-spacing: -0.03em;
          font-weight: 700;
          margin-top: 0.35rem;
        }

        .apple-readiness-card {
          background: linear-gradient(180deg, #f9f9fb 0%, #f5f5f7 100%);
          border: 1px solid var(--line);
          border-radius: 22px;
          padding: 1.3rem 1.4rem;
          margin-top: 0.9rem;
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

        .apple-profile-timeline {
          position: relative;
          margin-top: 0.75rem;
          padding-left: 1.35rem;
        }

        .apple-profile-timeline::before {
          content: "";
          position: absolute;
          left: 0.38rem;
          top: 0.25rem;
          bottom: 0.25rem;
          width: 1px;
          background: rgba(0, 0, 0, 0.09);
        }

        .apple-profile-timeline-item {
          position: relative;
          margin-bottom: 1.2rem;
        }

        .apple-profile-timeline-item:last-child {
          margin-bottom: 0;
        }

        .apple-profile-timeline-dot {
          position: absolute;
          left: -1.36rem;
          top: 1.25rem;
          width: 11px;
          height: 11px;
          border-radius: 999px;
          background: #ffffff;
          border: 1.5px solid rgba(0, 0, 0, 0.18);
          box-shadow: 0 0 0 4px #f5f5f7;
        }

        .apple-profile-date {
          color: var(--muted-light);
          font-size: 0.8rem;
          letter-spacing: 0.04em;
          font-weight: 600;
          margin-bottom: 0.35rem;
        }

        .apple-profile-meta {
          color: var(--muted);
          font-size: 0.95rem;
          line-height: 1.6;
          margin-bottom: 0.6rem;
        }

        .apple-profile-bullets {
          margin: 0.5rem 0 0 0;
          padding-left: 1.1rem;
          color: var(--text);
        }

        .apple-profile-bullets li {
          margin-bottom: 0.42rem;
          line-height: 1.55;
        }

        .apple-profile-header {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .apple-profile-name {
          font-size: clamp(2rem, 3.6vw, 2.8rem);
          line-height: 1.02;
          letter-spacing: -0.03em;
          font-weight: 720;
          margin: 0;
        }

        .apple-profile-headline {
          color: var(--muted);
          font-size: 1.02rem;
          line-height: 1.7;
          max-width: 56ch;
        }

        .apple-profile-pill-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.65rem;
        }

        .apple-profile-pill {
          display: inline-flex;
          align-items: center;
          padding: 0.52rem 0.88rem;
          border-radius: 999px;
          background: #f5f5f7;
          border: 1px solid var(--line);
          color: var(--text);
          font-size: 0.9rem;
          line-height: 1.2;
        }

        .apple-profile-summary-box {
          margin-top: 0.35rem;
          padding: 1.1rem 1.15rem;
          border-radius: 20px;
          background: linear-gradient(180deg, #fafafd 0%, #f7f7fa 100%);
          border: 1px solid rgba(0, 0, 0, 0.05);
          color: var(--muted);
          line-height: 1.75;
          font-size: 0.98rem;
        }

        .apple-signal-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.7rem;
          margin: 0.85rem 0 0.25rem 0;
        }

        .apple-signal-pill {
          display: inline-flex;
          align-items: center;
          gap: 0.42rem;
          padding: 0.58rem 0.9rem;
          border-radius: 999px;
          border: 1px solid var(--line);
          background: #ffffff;
          font-size: 0.88rem;
          line-height: 1.2;
        }

        .apple-signal-pill strong {
          font-weight: 650;
          color: var(--text);
        }

        .apple-edit-note {
          color: var(--muted);
          font-size: 0.9rem;
          line-height: 1.6;
          margin: 0.2rem 0 0.85rem 0;
        }

        .apple-toolbar-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.8rem;
          margin: 0.4rem 0 1.2rem 0;
        }

        .apple-toolbar-card {
          padding: 1rem 1.1rem;
          border-radius: 18px;
          background: linear-gradient(180deg, #fafafd 0%, #f5f5f8 100%);
          border: 1px solid var(--line);
        }

        .apple-meta-band {
          margin-top: 1rem;
          padding-top: 1rem;
          border-top: 1px solid var(--line);
        }

        .apple-quiet-divider {
          height: 1px;
          background: var(--line);
          margin: 1rem 0 0.9rem 0;
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

        div[data-testid="stTabs"] > div:first-child {
          gap: 0.5rem;
          padding: 0.35rem;
          background: #ebecef;
          border-radius: 999px;
          width: fit-content;
          margin-bottom: 1.35rem;
        }

        button[data-baseweb="tab"] {
          height: 42px;
          padding: 0 1rem !important;
          border-radius: 999px !important;
          background: transparent !important;
          color: var(--muted) !important;
          font-weight: 600 !important;
          border: 1px solid transparent !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
          background: #ffffff !important;
          color: var(--text) !important;
          border-color: rgba(0,0,0,0.04) !important;
          box-shadow: var(--shadow-soft);
        }

        button[data-baseweb="tab"]::after {
          display: none !important;
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

        div[data-testid="stFileUploader"] section {
          background: #ffffff !important;
          border: 1px solid rgba(0,0,0,0.06) !important;
          padding: 0.65rem !important;
          box-shadow: none !important;
        }

        div[data-testid="stFileUploaderDropzone"] {
          background: #f7f7fa !important;
          border: 1px dashed rgba(0,0,0,0.12) !important;
          border-radius: 24px !important;
          padding: 0.3rem 0.45rem !important;
        }

        div[data-testid="stFileUploaderDropzone"] * {
          color: var(--text) !important;
        }

        div[data-testid="stFileUploaderDropzoneInstructions"] {
          padding: 0.55rem 0.2rem !important;
        }

        div[data-testid="stFileUploaderFile"] {
          background: #f3f4f7 !important;
          border-radius: 18px !important;
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

        div[data-testid="stExpander"] details {
          background: var(--surface) !important;
          border: 1px solid var(--line) !important;
          padding: 0.2rem 0.4rem !important;
        }

        div[data-testid="stExpander"] summary {
          font-weight: 600 !important;
          color: var(--text) !important;
        }

        div[data-testid="stForm"] {
          border: none !important;
          padding: 0 !important;
          background: transparent !important;
        }

        label[data-testid="stWidgetLabel"] p {
          color: var(--text) !important;
          font-size: 0.9rem !important;
          font-weight: 600 !important;
          letter-spacing: -0.01em;
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

          .apple-journey-pill {
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.08);
          }

          .apple-summary-grid,
          .apple-readiness-card,
          .apple-stat-card,
          .apple-profile-summary-box,
          .apple-signal-pill,
          .apple-toolbar-card {
            background: var(--surface-muted);
            border-color: var(--line);
          }

          div[data-testid="stTabs"] > div:first-child {
            background: #23242a;
          }

          button[data-baseweb="tab"][aria-selected="true"] {
            background: #34353c !important;
            border-color: rgba(255,255,255,0.06) !important;
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

          .apple-journey-strip {
            grid-template-columns: 1fr;
            margin-top: -0.4rem;
          }

          div[data-testid="stTabs"] > div:first-child {
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


def _build_journey_status_line(step_key: str) -> str:
    """Summarize where the user is in the guided workflow."""
    canonical_key = FLOW_STEP_ALIASES.get(step_key, step_key)
    has_resume = bool(st.session_state.resume_name)
    has_jd = bool(st.session_state.job_description.strip())
    has_profile_selection = bool(st.session_state.get("selected_profile_item_ids"))
    has_fit_report = bool(st.session_state.resume_fit_report)
    has_validated_output = bool(st.session_state.validated_payload)

    if canonical_key == "input":
        parts = [
            "Resume loaded" if has_resume else "Resume not loaded yet",
            "Job description ready" if has_jd else "Add a target job",
        ]
        return " · ".join(parts)
    if canonical_key == "mode":
        parts = [
            "Fit checked" if has_fit_report else "Fit check optional",
            "Profile evidence linked" if has_profile_selection else "No profile evidence selected",
        ]
        return " · ".join(parts)
    if canonical_key == "review":
        return "Validated output ready for review" if has_validated_output else "Waiting for structured output"
    if canonical_key == "complete":
        return "Download the strongest finished version and save it for reuse."
    return ""


def _build_journey_panel(step_key: str) -> str:
    """Render a compact completed/current/next summary beneath the stepper."""
    canonical_key = FLOW_STEP_ALIASES.get(step_key, step_key)

    has_resume = bool(st.session_state.resume_name)
    has_jd = bool(st.session_state.job_description.strip())
    has_profile_selection = bool(st.session_state.get("selected_profile_item_ids"))
    has_fit_report = bool(st.session_state.resume_fit_report)
    has_validated_output = bool(st.session_state.validated_payload)
    has_download = bool(st.session_state.output_docx_bytes or st.session_state.builder_output_docx_bytes)

    if _is_builder_flow_screen(st.session_state.screen):
        completed = []
        if st.session_state.builder_full_name.strip():
            completed.append("Builder basics captured")
        if st.session_state.builder_prompt:
            completed.append("Draft prompt prepared")
        if st.session_state.builder_payload:
            completed.append("Structured draft validated")
        completed_text = " · ".join(completed) if completed else "No completed milestones yet"

        if canonical_key == "input":
            current_focus = "Capture the core background that should shape the first draft."
            next_step = "Generate the builder prompt and choose how you want to run it."
        elif canonical_key == "mode":
            current_focus = "Choose manual copy-paste or API generation for the first draft."
            next_step = "Bring back the structured draft so you can review and save it."
        elif canonical_key == "review":
            current_focus = "Review the draft structure, save strong signals to profile, and generate the first .docx."
            next_step = "Download the resume or keep the profile memory for future applications."
        else:
            current_focus = "Start the builder flow from profile or quick-start inputs."
            next_step = "Move into the first draft workflow."
    else:
        completed = []
        if has_resume:
            completed.append("Resume loaded")
        if has_jd:
            completed.append("Job description cleaned")
        if has_fit_report:
            completed.append("Fit report ready")
        if has_profile_selection:
            completed.append("Profile evidence linked")
        if has_validated_output:
            completed.append("Structured output validated")
        if has_download:
            completed.append("Export ready")
        completed_text = " · ".join(completed) if completed else "No completed milestones yet"

        if canonical_key == "input":
            current_focus = "Add the resume and target job so the app can understand the opportunity."
            next_step = "Check fit, connect profile evidence if needed, then choose how to run the optimization."
        elif canonical_key == "mode":
            current_focus = "Choose the best run path for this role: manual, API, or profile-assisted drafting."
            next_step = "Generate or validate the structured output so you can review changes."
        elif canonical_key == "review":
            current_focus = "Review quality, check the fit improvement, and decide whether the result is strong enough to export."
            next_step = "Download the best version and save it into your reusable workspace."
        elif canonical_key == "complete":
            current_focus = "Reuse, download, or carry this version into the next application."
            next_step = "Return to the workspace to start the next target faster."
        else:
            current_focus = "Choose how you want to start the next application."
            next_step = "Move into upload or profile setup."

    return f"""
    <div class="apple-journey-strip">
      <div class="apple-journey-pill">
        <div class="apple-journey-label">Completed</div>
        <div class="apple-journey-value">{completed_text}</div>
      </div>
      <div class="apple-journey-pill">
        <div class="apple-journey-label">Current Focus</div>
        <div class="apple-journey-value">{current_focus}</div>
      </div>
      <div class="apple-journey-pill">
        <div class="apple-journey-label">Next Step</div>
        <div class="apple-journey-value">{next_step}</div>
      </div>
    </div>
    """


def render_screen_intro(
    step_key: str,
    eyebrow: str,
    title: str,
    subtitle: str,
    *,
    show_journey: bool = True,
    show_status_line: bool = True,
) -> None:
    """Render a calm screen header with progress."""
    render_progress_stepper(step_key)
    if show_journey:
        st.markdown(_build_journey_panel(step_key), unsafe_allow_html=True)
    journey_line = _build_journey_status_line(step_key)
    st.markdown(
        f"""
        <div class="apple-hero">
          <div class="apple-eyebrow">{eyebrow}</div>
          <div class="apple-page-title">{title}</div>
          <p class="apple-subtitle">{subtitle}</p>
          {f'<div class="apple-minor-copy" style="margin-top:0.85rem;">{journey_line}</div>' if (journey_line and show_status_line) else ''}
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
        "builder_execution_mode": None,
        "builder_payload": None,
        "builder_validation_summary": None,
        "builder_output_docx_bytes": None,
        "builder_output_filename": None,
        "builder_profile_saved": False,
        "builder_profile_saved_source_id": None,
        "builder_profile_save_dismissed": False,
        "jd_source_url": "",
        "jd_cleaning_result": None,
        "show_review_changes": False,
        "pending_job_description_input": None,
        "jd_role_hint": "",
        "custom_api_base_url": "http://localhost:11434/v1",
        "custom_api_model": "mistral",
        "custom_api_key": "",
        "profile_import_notes": "",
        "profile_import_personal": "",
        "profile_import_experience": "",
        "profile_import_education": "",
        "profile_import_projects": "",
        "profile_import_skills": "",
        "profile_import_additional": "",
        "profile_import_source_name": "",
        "profile_extracted_basics": {},
        "profile_extracted_items": [],
        "profile_last_source_id": None,
        "profile_last_source_raw_text": "",
        "use_career_profile": False,
        "selected_profile_item_ids": [],
        "profile_job_signals": {},
        "last_saved_resume_asset_id": None,
        "current_application_id": None,
        "current_application_company": "",
        "resume_fit_report": None,
        "baseline_fit_report": None,
        "optimized_fit_report": None,
        "resume_fit_report_signature": "",
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
    _load_resume_bytes_into_session(uploaded_file.getvalue(), uploaded_file.name)


def _load_resume_bytes_into_session(resume_bytes: bytes, resume_name: str) -> None:
    """Hydrate resume bytes into the same session fields used by uploaded resumes."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(resume_bytes)
        temp_path = temp_file.name

    try:
        resume_text = extract_text(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    st.session_state.resume_name = resume_name
    st.session_state.resume_bytes = resume_bytes
    st.session_state.resume_text = resume_text
    st.session_state.resume_paragraphs = [
        paragraph.strip()
        for paragraph in resume_text.splitlines()
        if paragraph.strip()
    ]


def _load_resume_asset_into_session(asset) -> None:
    """Use a saved resume asset as the base document for a new optimization run."""
    _load_resume_bytes_into_session(asset.file_bytes, asset.file_name)

    if asset.application_id:
        _load_application_into_session(asset.application_id)
    else:
        st.session_state.current_application_id = None
        st.session_state.current_application_company = asset.company or ""
        st.session_state.job_description = ""
        st.session_state.pending_job_description_input = ""
        st.session_state.jd_source_url = ""
        st.session_state.jd_cleaning_result = None
        st.session_state.jd_role_hint = ""
        st.session_state.target_industry = ""
        st.session_state.selected_profile_item_ids = []
        st.session_state.use_career_profile = False
        st.session_state.target_role = asset.target_role or ""

    # Clear stale execution state so the next run starts cleanly from this resume.
    st.session_state.generated_prompt = None
    st.session_state.api_prompt_customized = False
    st.session_state.api_prompt_override = ""
    st.session_state.validated_payload = None
    st.session_state.validation_summary = None
    st.session_state.output_docx_bytes = None
    st.session_state.output_filename = None
    st.session_state.last_error = None
    st.session_state.review_details = None
    st.session_state.show_review_changes = False
    st.session_state.resume_fit_report = None
    st.session_state.baseline_fit_report = None
    st.session_state.optimized_fit_report = None
    st.session_state.builder_payload = None
    st.session_state.builder_validation_summary = None
    st.session_state.builder_output_docx_bytes = None
    st.session_state.builder_output_filename = None


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


def _build_optimized_resume_text(payload: dict) -> str:
    """Approximate the post-optimization resume text from exact-match replacements."""
    paragraphs = list(st.session_state.resume_paragraphs or [])
    if not paragraphs:
        return st.session_state.resume_text or ""

    updated_paragraphs = paragraphs[:]
    replacements = collect_replacements(payload)
    for replacement in replacements:
        anchor = replacement["match_anchor"].strip()
        replacement_text = replacement["replacement_text"].strip()
        matching_indexes = [index for index, paragraph in enumerate(updated_paragraphs) if paragraph.strip() == anchor]
        if len(matching_indexes) == 1:
            updated_paragraphs[matching_indexes[0]] = replacement_text

    return "\n".join(updated_paragraphs)


def ensure_export_file_ready() -> None:
    """Generate the optimized output once when export is safe."""
    if st.session_state.output_docx_bytes or not st.session_state.validated_payload:
        return

    output_bytes, _message = build_output_docx(st.session_state.validated_payload)
    original_name = Path(st.session_state.resume_name)
    st.session_state.output_docx_bytes = output_bytes
    st.session_state.output_filename = f"{original_name.stem}_Optimized{original_name.suffix}"


def render_landing() -> None:
    """First-touch onboarding entry screen."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Resume Optimizer</div>
            <h1>Start with your career profile, or jump straight into the work.</h1>
            <p>Build a reusable profile that powers future applications, or jump straight to resume building if you want immediate value first.</p>
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
                <div class="apple-kicker">Recommended</div>
                <div class="apple-landing-card-title">Build Career Profile</div>
                <div class="apple-landing-card-copy">Create your reusable source of truth once, then use it to tailor resumes, generate fresh drafts, and guide future applications.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-primary">', unsafe_allow_html=True)
        if st.button("Build Career Profile", use_container_width=True, key="landing-profile-primary"):
            st.session_state.screen = "profile_welcome"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            """
            <div class="apple-landing-card">
              <div>
                <div class="apple-kicker">Quick Start</div>
                <div class="apple-landing-card-title">Jump Straight to Resume Building</div>
                <div class="apple-landing-card-copy">Go directly to the resume tools. You can optimize an existing resume or build a fresh one, then decide later what should be saved into your profile.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-secondary">', unsafe_allow_html=True)
        if st.button("Jump Straight to Resume Building", use_container_width=True, key="landing-skip"):
            st.session_state.screen = "quickstart"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_quickstart_screen() -> None:
    """Secondary entry screen for users who skip profile onboarding."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Quick Start</div>
            <h1>Choose the fastest way to get moving.</h1>
            <p>Jump into editing the resume you already have, or build a fresh resume now and decide later whether to save that information into your profile.</p>
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
                <div class="apple-landing-card-title">Optimize Existing Resume</div>
                <div class="apple-landing-card-copy">Refine the resume you already have for a specific role, then review the final changes before you export it.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-primary">', unsafe_allow_html=True)
        if st.button("Start Optimizing", use_container_width=True, key="quickstart-optimize"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            """
            <div class="apple-landing-card">
              <div>
                <div class="apple-kicker">Fresh Build</div>
                <div class="apple-landing-card-title">Build a Fresh Resume</div>
                <div class="apple-landing-card-copy">Start with a plain-English brain dump and shape it into a clean draft. You’ll be able to save what you enter into your profile later.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-secondary">', unsafe_allow_html=True)
        if st.button("Build a Fresh Resume", use_container_width=True, key="quickstart-builder"):
            st.session_state.career_stage = "Student"
            st.session_state.screen = "builder_input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    back_col, _, _ = st.columns([1, 1.5, 1.5])
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="quickstart-back"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def _profile_items_from_session() -> list[ProfileItem]:
    """Convert session-stored dict items back into ProfileItem objects."""
    return [ProfileItem(**item) for item in st.session_state.profile_extracted_items]


def _split_csv_input(value: str) -> list[str]:
    """Turn comma-separated text into a clean list."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _split_line_input(value: str) -> list[str]:
    """Turn multiline text into a clean list of non-empty lines."""
    return [line.strip() for line in value.splitlines() if line.strip()]


def _build_profile_review_preview(item: ProfileItem) -> tuple[str, str]:
    """Return a compact subtitle and preview line for section preview cards."""
    subtitle_parts = [item.item_type.title()]
    if item.organization:
        subtitle_parts.append(item.organization)
    if item.location:
        subtitle_parts.append(item.location)
    if item.start_date or item.end_date:
        if item.start_date and item.end_date:
            subtitle_parts.append(f"{item.start_date} - {item.end_date}")
        elif item.start_date:
            subtitle_parts.append(item.start_date)
        elif item.end_date:
            subtitle_parts.append(item.end_date)
    elif item.is_current:
        subtitle_parts.append("Current")
    subtitle = " | ".join(subtitle_parts)

    if item.item_type == "skills":
        preview_source = ", ".join(item.skills[:6] or item.keywords[:6])
    elif item.bullets:
        preview_source = item.bullets[0]
    else:
        preview_source = item.description or item.organization or "Review this item before saving."
    return subtitle, format_preview_text(preview_source, max_len=120)


def render_profile_preview_cards(items: list[ProfileItem], max_cards: int = 3) -> None:
    """Render compact preview cards for extracted profile items."""
    if not items:
        return
    preview_items = items[:max_cards]
    columns = st.columns(len(preview_items), gap="large")
    for column, item in zip(columns, preview_items):
        subtitle, preview = _build_profile_review_preview(item)
        with column:
            with st.container(border=True):
                st.markdown(
                    f'<div class="apple-kicker" style="margin-bottom:0.55rem;">{subtitle}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="apple-section-title" style="font-size:1.1rem; margin-bottom:0.5rem;">{item.title or "Untitled item"}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="apple-minor-copy">{preview}</div>',
                    unsafe_allow_html=True,
                )


def _save_profile_review_result(
    *,
    basics_snapshot: dict,
    drafted_items: list[ProfileItem],
    full_name: str,
    email: str,
    phone: str,
    location: str,
    linkedin: str,
    headline: str,
    career_stage: str,
    summary: str,
    target_roles: str,
    target_industries: str,
    preferred_locations: str,
    work_authorization: str,
) -> list[ProfileItem]:
    """Persist reviewed profile basics, source, and items from the import-review flow."""
    profile = save_profile_basics(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        headline=headline,
        career_stage=career_stage,
        summary=summary,
        target_roles=[part.strip() for part in target_roles.split(",")],
        target_industries=[part.strip() for part in target_industries.split(",")],
        preferred_locations=[part.strip() for part in preferred_locations.split(",")],
        work_authorization=work_authorization,
    )
    source_name = st.session_state.profile_import_source_name or "Imported Notes"
    source_type = _detect_profile_source_type(source_name)
    source_id = save_profile_source(
        source_type=source_type,
        source_name=source_name,
        raw_text=st.session_state.get("profile_last_source_raw_text", ""),
        parsed_payload={"basics": basics_snapshot, "item_count": len(drafted_items)},
    )
    for item in drafted_items:
        item.profile_id = profile.id
        item.source_id = source_id
        item.verification_status = "verified"
    saved_items = save_profile_items(drafted_items, replace_existing_for_source=source_id)
    st.session_state.career_stage = career_stage
    if target_roles.strip():
        st.session_state.target_role = target_roles.split(",")[0].strip()
    if target_industries.strip():
        st.session_state.target_industry = target_industries.split(",")[0].strip()
    st.session_state.profile_last_source_id = source_id
    st.session_state.profile_extracted_items = [item.to_dict() for item in saved_items]
    return saved_items


def _save_builder_payload_to_profile(payload: dict) -> int:
    """Promote a validated fresh-resume draft into the persistent career profile."""
    basics = payload.get("basics", {}) or {}
    profile = create_or_get_profile()

    full_name = (basics.get("full_name") or st.session_state.builder_full_name or profile.full_name).strip()
    email = (basics.get("email") or profile.email).strip()
    phone = (basics.get("phone") or profile.phone).strip()
    location = (basics.get("location") or profile.location).strip()
    linkedin = (basics.get("linkedin") or profile.linkedin).strip()

    summary = (payload.get("summary") or profile.summary).strip()
    target_roles = _split_csv_input(st.session_state.target_role) or profile.target_roles
    target_industries = profile.target_industries
    preferred_locations = profile.preferred_locations or ([location] if location else [])

    updated_profile = save_profile_basics(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        headline=profile.headline,
        career_stage=st.session_state.career_stage or profile.career_stage,
        summary=summary,
        target_roles=target_roles,
        target_industries=target_industries,
        preferred_locations=preferred_locations,
        work_authorization=profile.work_authorization,
    )

    source_payload = {
        "mode": "fresh_resume_builder",
        "target_role": st.session_state.target_role,
        "career_stage": st.session_state.career_stage,
        "payload": payload,
    }
    source_id = save_profile_source(
        source_type="fresh_resume_builder",
        source_name=f"Fresh Resume Draft · {full_name or 'Candidate'}",
        raw_text="\n\n".join(
            part
            for part in [
                st.session_state.builder_contact_info.strip(),
                st.session_state.builder_education.strip(),
                st.session_state.builder_experience_dump.strip(),
                st.session_state.builder_activities.strip(),
                st.session_state.builder_skills.strip(),
                st.session_state.builder_job_description.strip(),
            ]
            if part
        ),
        parsed_payload=source_payload,
    )

    items: list[ProfileItem] = []
    for education_item in payload.get("education", []):
        degree_parts = [education_item.get("degree", "").strip(), education_item.get("graduation_date", "").strip()]
        education_summary = " | ".join(part for part in degree_parts if part)
        items.append(
            ProfileItem(
                profile_id=updated_profile.id,
                source_id=source_id,
                item_type="education",
                title=(education_item.get("school") or "").strip(),
                organization=(education_item.get("school") or "").strip(),
                description=education_summary,
                bullets=[detail.strip() for detail in education_item.get("details", []) if detail.strip()],
                keywords=_split_csv_input(" ".join(degree_parts + education_item.get("details", [])))[:12],
                verification_status="verified",
            )
        )

    for experience_item in payload.get("experience", []):
        items.append(
            ProfileItem(
                profile_id=updated_profile.id,
                source_id=source_id,
                item_type="experience",
                title=(experience_item.get("title") or "").strip(),
                organization=(experience_item.get("organization") or "").strip(),
                location=(experience_item.get("location") or "").strip(),
                description=(experience_item.get("dates") or "").strip(),
                bullets=[bullet.strip() for bullet in experience_item.get("bullets", []) if bullet.strip()],
                keywords=_split_csv_input(
                    ", ".join(
                        part
                        for part in [
                            experience_item.get("title", ""),
                            experience_item.get("organization", ""),
                            experience_item.get("location", ""),
                        ]
                        if part
                    )
                )[:12],
                verification_status="verified",
            )
        )

    for project_item in payload.get("projects", []):
        items.append(
            ProfileItem(
                profile_id=updated_profile.id,
                source_id=source_id,
                item_type="project",
                title=(project_item.get("name") or "").strip(),
                description="Project or leadership experience captured from the fresh resume flow.",
                bullets=[detail.strip() for detail in project_item.get("details", []) if detail.strip()],
                keywords=_split_csv_input(", ".join(project_item.get("details", [])))[:12],
                verification_status="verified",
            )
        )

    skills = [skill.strip() for skill in payload.get("skills", []) if skill.strip()]
    if skills:
        items.append(
            ProfileItem(
                profile_id=updated_profile.id,
                source_id=source_id,
                item_type="skills",
                title="Core Skills",
                description="Skill bank captured from a validated fresh resume draft.",
                skills=skills,
                keywords=skills[:12],
                verification_status="verified",
            )
        )

    save_profile_items(items, replace_existing_for_source=source_id)
    st.session_state.builder_profile_saved = True
    st.session_state.builder_profile_saved_source_id = source_id
    st.session_state.builder_profile_save_dismissed = False
    return source_id


def _build_builder_profile_memory_rows(payload: dict, stats: dict) -> list[tuple[str, str]]:
    """Summarize what will be preserved if the user saves this draft to profile."""
    basics = payload.get("basics", {}) or {}
    contact_fields = [
        basics.get("full_name", "").strip(),
        basics.get("email", "").strip(),
        basics.get("phone", "").strip(),
        basics.get("location", "").strip(),
        basics.get("linkedin", "").strip(),
    ]
    captured_basics = sum(1 for value in contact_fields if value)
    return [
        ("Basics captured", f"{captured_basics}/5"),
        ("Education", str(stats.get("education_items", 0))),
        ("Experience", str(stats.get("experience_items", 0))),
        ("Projects", str(stats.get("project_items", 0))),
        ("Skills", str(stats.get("skills_items", 0))),
    ]


def _get_selected_profile_items() -> list[ProfileItem]:
    """Resolve selected profile item ids from session state."""
    selected_ids = set(st.session_state.get("selected_profile_item_ids", []))
    if not selected_ids:
        return []
    items_by_id = {item.id: item for item in list_profile_items() if item.visibility == "active"}
    return [items_by_id[item_id] for item_id in st.session_state.get("selected_profile_item_ids", []) if item_id in items_by_id]


def _profile_item_meta_line(item: ProfileItem) -> str:
    """Build a compact metadata line for profile display cards."""
    parts: list[str] = []
    if item.organization:
        parts.append(item.organization)
    if item.location:
        parts.append(item.location)
    if item.start_date and item.end_date:
        parts.append(f"{item.start_date} - {item.end_date}")
    elif item.start_date:
        parts.append(item.start_date)
    elif item.end_date:
        parts.append(item.end_date)
    elif item.is_current:
        parts.append("Current")
    return " · ".join(part for part in parts if part)


def _render_profile_display_cards(
    items: list[ProfileItem],
    *,
    empty_message: str,
    item_label: str,
    key_prefix: str,
) -> None:
    """Render clean, readable profile cards with optional editing expanders."""
    if not items:
        st.markdown(f'<div class="apple-minor-copy">{empty_message}</div>', unsafe_allow_html=True)
        return

    for item in items:
        with st.container(border=True):
            meta_line = _profile_item_meta_line(item)
            if meta_line:
                st.markdown(f'<div class="apple-kicker">{meta_line}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{item.title or f"Untitled {item_label}"}</div>', unsafe_allow_html=True)
            if item.description:
                st.markdown(f'<div class="apple-section-copy">{item.description}</div>', unsafe_allow_html=True)
            if item.skills:
                render_chip_row(item.skills[:12])
            elif item.bullets:
                preview_bullets = item.bullets[:4]
                for bullet in preview_bullets:
                    st.markdown(f"- {bullet}")

            with st.expander("Quick edit", expanded=False):
                st.markdown('<div class="apple-edit-note">Make small corrections here without leaving the main profile view.</div>', unsafe_allow_html=True)
                with st.form(key=f"{key_prefix}-{item.id}"):
                    col1, col2 = st.columns(2, gap="large")
                    with col1:
                        edited_type = st.selectbox(
                            "Type",
                            PROFILE_ITEM_TYPES,
                            index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                            key=f"{key_prefix}-type-{item.id}",
                        )
                        edited_title = st.text_input("Title", value=item.title, key=f"{key_prefix}-title-{item.id}")
                    with col2:
                        edited_org = st.text_input("Organization", value=item.organization, key=f"{key_prefix}-org-{item.id}")
                        edited_location = st.text_input("Location", value=item.location, key=f"{key_prefix}-location-{item.id}")
                    edited_description = st.text_area("Summary", value=item.description, height=100, key=f"{key_prefix}-desc-{item.id}")
                    edited_bullets = st.text_area("Details / Bullets", value="\n".join(item.bullets), height=140, key=f"{key_prefix}-bullets-{item.id}")
                    edited_skills = st.text_input("Skills", value=", ".join(item.skills or item.keywords), key=f"{key_prefix}-skills-{item.id}")
                    row1, row2, row3 = st.columns(3, gap="large")
                    with row1:
                        save_pressed = st.form_submit_button("Save changes", use_container_width=True)
                    with row2:
                        verify_pressed = st.form_submit_button("Mark reviewed", use_container_width=True)
                    with row3:
                        archive_pressed = st.form_submit_button("Hide", use_container_width=True)
                if save_pressed or verify_pressed:
                    update_profile_item(
                        ProfileItem(
                            id=item.id,
                            user_id=item.user_id,
                            profile_id=item.profile_id,
                            source_id=item.source_id,
                            item_type=edited_type,
                            title=edited_title.strip(),
                            organization=edited_org.strip(),
                            location=edited_location.strip(),
                            start_date=item.start_date,
                            end_date=item.end_date,
                            is_current=item.is_current,
                            description=edited_description.strip(),
                            bullets=_split_line_input(edited_bullets),
                            skills=_split_csv_input(edited_skills),
                            keywords=_split_csv_input(edited_skills)[:12] or item.keywords,
                            confidence_score=item.confidence_score,
                            verification_status="verified" if verify_pressed else item.verification_status,
                            visibility=item.visibility,
                            created_at=item.created_at,
                            updated_at=item.updated_at,
                        )
                    )
                    if verify_pressed and item.id is not None:
                        update_profile_item_verification(item.id, "verified")
                    st.rerun()
                if archive_pressed and item.id is not None:
                    archive_profile_item(item.id)
                    st.rerun()


def _render_profile_timeline_section(
    items: list[ProfileItem],
    *,
    empty_message: str,
    item_label: str,
    key_prefix: str,
) -> None:
    """Render a timeline-style profile section closer to editorial profile products."""
    if not items:
        st.markdown(f'<div class="apple-minor-copy">{empty_message}</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="apple-profile-timeline">', unsafe_allow_html=True)
    for item in items:
        date_line = ""
        if item.start_date and item.end_date:
            date_line = f"{item.start_date} to {item.end_date}"
        elif item.start_date:
            date_line = item.start_date
        elif item.end_date:
            date_line = item.end_date
        elif item.is_current:
            date_line = "Current"

        meta_line = " · ".join(part for part in [item.organization, item.location] if part)

        st.markdown('<div class="apple-profile-timeline-item">', unsafe_allow_html=True)
        st.markdown('<div class="apple-profile-timeline-dot"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            if date_line:
                st.markdown(f'<div class="apple-profile-date">{date_line}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{item.title or f"Untitled {item_label}"}</div>', unsafe_allow_html=True)
            if meta_line:
                st.markdown(f'<div class="apple-profile-meta">{meta_line}</div>', unsafe_allow_html=True)
            if item.description:
                st.markdown(f'<div class="apple-section-copy">{item.description}</div>', unsafe_allow_html=True)
            if item.bullets:
                bullet_items = "".join(f"<li>{html.escape(bullet)}</li>" for bullet in item.bullets[:4] if bullet.strip())
                if bullet_items:
                    st.markdown(f'<ul class="apple-profile-bullets">{bullet_items}</ul>', unsafe_allow_html=True)
            if item.skills:
                render_chip_row(item.skills[:10])

            with st.expander("Quick edit", expanded=False):
                st.markdown('<div class="apple-edit-note">Adjust dates, wording, or supporting bullets without breaking the clean timeline view.</div>', unsafe_allow_html=True)
                with st.form(key=f"{key_prefix}-{item.id}"):
                    col1, col2 = st.columns(2, gap="large")
                    with col1:
                        edited_type = st.selectbox(
                            "Type",
                            PROFILE_ITEM_TYPES,
                            index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                            key=f"{key_prefix}-type-{item.id}",
                        )
                        edited_title = st.text_input("Title", value=item.title, key=f"{key_prefix}-title-{item.id}")
                        edited_start_date = st.text_input("Start Date", value=item.start_date, key=f"{key_prefix}-start-{item.id}")
                    with col2:
                        edited_org = st.text_input("Organization", value=item.organization, key=f"{key_prefix}-org-{item.id}")
                        edited_location = st.text_input("Location", value=item.location, key=f"{key_prefix}-location-{item.id}")
                        edited_end_date = st.text_input("End Date", value=item.end_date, key=f"{key_prefix}-end-{item.id}")
                    edited_is_current = st.checkbox("This is current / ongoing", value=item.is_current, key=f"{key_prefix}-current-{item.id}")
                    edited_description = st.text_area("Summary", value=item.description, height=100, key=f"{key_prefix}-desc-{item.id}")
                    edited_bullets = st.text_area("Details / Bullets", value="\n".join(item.bullets), height=140, key=f"{key_prefix}-bullets-{item.id}")
                    edited_skills = st.text_input("Skills", value=", ".join(item.skills or item.keywords), key=f"{key_prefix}-skills-{item.id}")
                    row1, row2, row3 = st.columns(3, gap="large")
                    with row1:
                        save_pressed = st.form_submit_button("Save changes", use_container_width=True)
                    with row2:
                        verify_pressed = st.form_submit_button("Mark reviewed", use_container_width=True)
                    with row3:
                        archive_pressed = st.form_submit_button("Hide", use_container_width=True)
                if save_pressed or verify_pressed:
                    update_profile_item(
                        ProfileItem(
                            id=item.id,
                            user_id=item.user_id,
                            profile_id=item.profile_id,
                            source_id=item.source_id,
                            item_type=edited_type,
                            title=edited_title.strip(),
                            organization=edited_org.strip(),
                            location=edited_location.strip(),
                            start_date=edited_start_date.strip(),
                            end_date=edited_end_date.strip(),
                            is_current=edited_is_current,
                            description=edited_description.strip(),
                            bullets=_split_line_input(edited_bullets),
                            skills=_split_csv_input(edited_skills),
                            keywords=_split_csv_input(edited_skills)[:12] or item.keywords,
                            confidence_score=item.confidence_score,
                            verification_status="verified" if verify_pressed else item.verification_status,
                            visibility=item.visibility,
                            created_at=item.created_at,
                            updated_at=item.updated_at,
                        )
                    )
                    if verify_pressed and item.id is not None:
                        update_profile_item_verification(item.id, "verified")
                    st.rerun()
                if archive_pressed and item.id is not None:
                    archive_profile_item(item.id)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _build_profile_context(items: list[ProfileItem]) -> str:
    """Convert selected profile items into a compact prompt context block."""
    sections: list[str] = []
    for index, item in enumerate(items, start=1):
        bullet_lines = "\n".join(f"- {bullet}" for bullet in item.bullets[:4])
        skills_line = f"Skills: {', '.join(item.skills[:8])}" if item.skills else ""
        parts = [
            f"{index}. {item.item_type.title()}: {item.title or 'Untitled item'}",
            f"Organization: {item.organization}" if item.organization else "",
            item.description.strip(),
            bullet_lines,
            skills_line,
        ]
        section = "\n".join(part for part in parts if part)
        if section:
            sections.append(section)
    return "\n\n".join(sections)


def _build_optimizer_prompt_from_state() -> str:
    """Build the optimizer prompt, optionally enriched with selected profile evidence."""
    profile_context = _build_profile_context(_get_selected_profile_items()) if st.session_state.get("use_career_profile") else ""
    return build_optimizer_prompt(
        st.session_state.resume_text,
        st.session_state.job_description,
        st.session_state.career_stage,
        get_effective_target_role(st.session_state.job_description),
        get_effective_industry(st.session_state.job_description),
        profile_context=profile_context,
    )


def _resume_fit_signature() -> str:
    """Return a compact signature for the current report inputs."""
    selected_ids = ",".join(str(item_id) for item_id in st.session_state.get("selected_profile_item_ids", []))
    return "|".join(
        [
            str(len(st.session_state.resume_text or "")),
            str(len(st.session_state.job_description or "")),
            selected_ids,
            st.session_state.resume_name or "",
        ]
    )


def _evaluate_current_resume_fit(force: bool = False) -> dict:
    """Evaluate the current resume/JD pair and cache the report."""
    signature = _resume_fit_signature()
    if (
        force
        or not st.session_state.resume_fit_report
        or st.session_state.resume_fit_report_signature != signature
    ):
        report = evaluate_resume_fit(
            st.session_state.resume_text or "",
            st.session_state.job_description or "",
            selected_profile_items=_get_selected_profile_items(),
        )
        st.session_state.resume_fit_report = report
        st.session_state.baseline_fit_report = report
        st.session_state.resume_fit_report_signature = signature
    return st.session_state.resume_fit_report or {}


def _infer_basics_from_resume_text(resume_text: str) -> tuple[str, str]:
    """Infer a name and contact line from the uploaded resume text when possible."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    full_name = lines[0] if lines else "Candidate Name"
    contact_info = ""
    for line in lines[1:4]:
        if "@" in line or "|" in line or re.search(r"\d{3}[-.)\s]?\d{3}", line):
            contact_info = line
            break
    return full_name, contact_info


def _profile_items_to_builder_inputs(items: list[ProfileItem]) -> dict[str, str]:
    """Convert selected profile items into builder-style source fields."""
    education_chunks: list[str] = []
    experience_chunks: list[str] = []
    activity_chunks: list[str] = []
    skill_bank: list[str] = []

    for item in items:
        heading_parts = [part for part in [item.title, item.organization] if part]
        heading = " | ".join(heading_parts) if heading_parts else item.item_type.title()
        body_parts = [item.description.strip()] if item.description.strip() else []
        if item.bullets:
            body_parts.extend(item.bullets[:5])
        chunk = "\n".join([heading] + [part for part in body_parts if part])

        if item.item_type == "education":
            education_chunks.append(chunk)
        elif item.item_type in {"experience", "business", "volunteering"}:
            experience_chunks.append(chunk)
        else:
            activity_chunks.append(chunk)

        for skill in item.skills:
            if skill not in skill_bank:
                skill_bank.append(skill)

    return {
        "education": "\n\n".join(education_chunks),
        "experience_dump": "\n\n".join(experience_chunks),
        "activities": "\n\n".join(activity_chunks),
        "skills": ", ".join(skill_bank),
    }


def _start_profile_draft_flow() -> None:
    """Seed the builder flow from selected career-profile evidence."""
    selected_items = _get_selected_profile_items()
    if not selected_items:
        raise ValueError("Choose at least one profile item before creating a draft.")

    profile = create_or_get_profile()
    inferred_name, inferred_contact = _infer_basics_from_resume_text(st.session_state.resume_text or "")
    full_name = profile.full_name.strip() or inferred_name
    contact_parts = [profile.email, profile.phone, profile.location, profile.linkedin]
    contact_info = " | ".join([part.strip() for part in contact_parts if part.strip()]) or inferred_contact
    builder_inputs = _profile_items_to_builder_inputs(selected_items)

    st.session_state.builder_full_name = full_name
    st.session_state.builder_contact_info = contact_info
    st.session_state.builder_education = builder_inputs["education"]
    st.session_state.builder_experience_dump = builder_inputs["experience_dump"]
    st.session_state.builder_activities = builder_inputs["activities"]
    st.session_state.builder_skills = builder_inputs["skills"]
    st.session_state.builder_job_description = st.session_state.job_description
    st.session_state.career_stage = profile.career_stage or st.session_state.career_stage
    if profile.target_roles and not st.session_state.target_role.strip():
        st.session_state.target_role = profile.target_roles[0]
    st.session_state.builder_prompt = build_builder_prompt(
        full_name=st.session_state.builder_full_name,
        contact_info=st.session_state.builder_contact_info,
        education=st.session_state.builder_education,
        experience_dump=st.session_state.builder_experience_dump,
        activities=st.session_state.builder_activities,
        skills=st.session_state.builder_skills,
        job_description=st.session_state.builder_job_description,
        career_stage=st.session_state.career_stage,
        target_role=st.session_state.target_role or "the target role",
    )
    st.session_state.builder_execution_mode = None
    st.session_state.builder_payload = None
    st.session_state.builder_validation_summary = None
    st.session_state.builder_output_docx_bytes = None
    st.session_state.builder_output_filename = None
    st.session_state.screen = "builder_stub"


def _save_current_application(status: str = "matched") -> int:
    """Persist the current job target and selected profile evidence."""
    job_description = st.session_state.job_description.strip()
    if not job_description:
        raise ValueError("Add a job description before saving an application workspace.")

    application = upsert_application(
        application_id=st.session_state.get("current_application_id"),
        job_title=get_effective_target_role(job_description),
        company=st.session_state.get("current_application_company", ""),
        job_description=job_description,
        role_family=get_effective_target_role(job_description),
        industry=get_effective_industry(job_description),
        job_url=st.session_state.jd_source_url,
        status=status,
    )
    st.session_state.current_application_id = application.id
    if application.id is not None:
        link_profile_items_to_application(
            application.id,
            [item_id for item_id in st.session_state.get("selected_profile_item_ids", []) if isinstance(item_id, int)],
        )
    return application.id or 0


def _infer_resume_category(target_role: str, target_industry: str) -> str:
    """Infer a lightweight category for saved resume assets."""
    if target_role.strip():
        return target_role.strip()
    if target_industry.strip():
        return target_industry.strip()
    return "general"


def _infer_workspace_tags(*values: str) -> list[str]:
    """Infer richer, human-readable tags from role/category text."""
    text = " ".join(value.strip().lower() for value in values if value).strip()
    if not text:
        return []

    tag_rules = [
        ("Internship", ["intern", "internship"]),
        ("Full-time", ["full time", "full-time"]),
        ("MBA", ["mba", "master of business administration"]),
        ("Early Career", ["student", "entry", "early career", "new grad", "graduate"]),
        ("Leadership", ["manager", "lead", "director", "head of"]),
        ("Consulting", ["consult", "strategy"]),
        ("Operations", ["operations", "supply chain", "logistics", "procurement"]),
        ("Finance", ["finance", "fp&a", "financial", "accounting"]),
        ("Marketing", ["marketing", "growth", "brand"]),
        ("Product", ["product manager", "product management"]),
        ("Software", ["software", "engineer", "developer", "data scientist"]),
        ("Pivot", ["transition", "pivot", "career change"]),
    ]
    tags: list[str] = []
    for tag, needles in tag_rules:
        if any(needle in text for needle in needles):
            tags.append(tag)
    return tags[:4]


def _derive_resume_asset_tags(asset) -> list[str]:
    """Create lightweight reusable tags for library display."""
    tags: list[str] = []
    if asset.source_kind:
        tags.append(asset.source_kind.replace("_", " ").title())
    if asset.category and asset.category.lower() not in {tag.lower() for tag in tags}:
        tags.append(asset.category)
    if asset.company:
        tags.append(asset.company)
    role = asset.target_role.lower()
    if "intern" in role:
        tags.append("Internship")
    elif any(token in role for token in ["manager", "lead", "director"]):
        tags.append("Leadership")
    elif role:
        tags.append("Role-specific")
    for inferred_tag in _infer_workspace_tags(asset.target_role, asset.category, asset.notes):
        if inferred_tag.lower() not in {tag.lower() for tag in tags}:
            tags.append(inferred_tag)
    return tags[:5]


def _asset_reuse_copy(asset) -> str:
    """Explain when a saved resume is most useful to reuse."""
    role = asset.target_role.strip()
    company = asset.company.strip()
    category = asset.category.strip()
    source = asset.source_kind.replace("_", " ").title()

    if role and company:
        return f"Best reused when you want a fast restart for a {role} application at {company}."
    if role:
        return f"Best reused when you want a head start for another {role} opportunity."
    if category:
        return f"Best reused when you need a version tailored to {category} roles."
    return f"Best reused when you want to revisit a previously saved {source.lower()} version."


def _sort_resume_assets(assets: list, sort_mode: str) -> list:
    """Keep resume library ordering predictable and user-friendly."""
    if sort_mode == "Oldest updated":
        return sorted(assets, key=lambda asset: ((asset.updated_at or ""), (asset.id or 0)))
    if sort_mode == "Role A-Z":
        return sorted(assets, key=lambda asset: ((asset.target_role or "").lower(), -(asset.id or 0)))
    if sort_mode == "Company A-Z":
        return sorted(assets, key=lambda asset: ((asset.company or "").lower(), -(asset.id or 0)))
    if sort_mode == "Category A-Z":
        return sorted(assets, key=lambda asset: ((asset.category or "").lower(), -(asset.id or 0)))
    return sorted(assets, key=lambda asset: ((asset.updated_at or ""), (asset.id or 0)), reverse=True)


def _format_application_status(status: str) -> tuple[str, str]:
    """Map internal application statuses to cleaner workspace language."""
    mapping = {
        "draft": ("Draft", "Just started"),
        "ready_to_optimize": ("Ready to optimize", "Resume + target loaded"),
        "ready_to_draft": ("Ready to draft", "Profile evidence selected"),
        "matched": ("Profile matched", "Evidence chosen for this role"),
        "saved_resume": ("Resume saved", "Optimized version stored"),
        "saved_builder_resume": ("Fresh resume saved", "Builder version stored"),
    }
    return mapping.get(status, (status.replace("_", " ").title(), "In progress"))


def _derive_application_tags(application) -> list[str]:
    """Create lightweight tags so saved job workspaces scan faster."""
    tags: list[str] = []
    if application.status:
        tags.append(application.status.replace("_", " ").title())
    if application.company:
        tags.append(application.company)
    if application.industry and application.industry.lower() not in {tag.lower() for tag in tags}:
        tags.append(application.industry)
    if application.job_title and "intern" in application.job_title.lower():
        tags.append("Internship")
    elif application.job_title and any(token in application.job_title.lower() for token in ["manager", "lead", "director"]):
        tags.append("Leadership")
    for inferred_tag in _infer_workspace_tags(application.job_title, application.industry, application.role_family):
        if inferred_tag.lower() not in {tag.lower() for tag in tags}:
            tags.append(inferred_tag)
    if application.selected_profile_item_ids:
        tags.append(f"{len(application.selected_profile_item_ids)} evidence items")
    return tags[:5]


def _application_next_move(application) -> tuple[str, str]:
    """Turn internal workspace state into a clearer user-facing next step."""
    if application.status == "ready_to_optimize":
        return ("Optimize this resume", "Resume and target are ready for job-specific tailoring.")
    if application.status == "ready_to_draft":
        return ("Create a fresh draft", "Profile evidence is already selected for this role.")
    if application.status in {"saved_resume", "saved_builder_resume"}:
        return ("Reuse a saved version", "A finished resume exists for this target and can be reused as a starting point.")
    if application.selected_profile_item_ids:
        return ("Review or refresh evidence", "Evidence is selected, so you can continue tailoring or build a new draft.")
    return ("Finish setup", "Add evidence or return to the job setup flow to continue.")


def _save_current_resume_asset(
    *,
    source_kind: str,
    title: str,
    file_name: str,
    file_bytes: bytes,
    notes: str = "",
) -> int:
    """Persist the current generated resume into the resume library."""
    target_role = st.session_state.target_role or get_effective_target_role(st.session_state.job_description or "")
    target_industry = st.session_state.target_industry or get_effective_industry(st.session_state.job_description or "")
    company = st.session_state.get("current_application_company", "")
    application_id = None
    if st.session_state.job_description.strip():
        application_id = _save_current_application(
            status="saved_resume" if source_kind == "optimized_resume" else "saved_builder_resume"
        )
    asset = save_resume_asset(
        application_id=application_id or None,
        source_kind=source_kind,
        category=_infer_resume_category(target_role, target_industry),
        title=title,
        target_role=target_role,
        company=company,
        file_name=file_name,
        file_bytes=file_bytes,
        notes=notes,
    )
    st.session_state.last_saved_resume_asset_id = asset.id
    return asset.id or 0


def _load_application_into_session(application_id: int) -> None:
    """Load a saved application into the current Streamlit session."""
    application = get_application(application_id)
    if application is None:
        return
    st.session_state.current_application_id = application.id
    st.session_state.current_application_company = application.company
    st.session_state.job_description = application.job_description
    st.session_state.pending_job_description_input = application.job_description
    st.session_state.target_role = application.job_title
    st.session_state.target_industry = application.industry
    st.session_state.jd_source_url = application.job_url
    st.session_state.selected_profile_item_ids = application.selected_profile_item_ids
    st.session_state.use_career_profile = bool(application.selected_profile_item_ids)


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF upload using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError(
            "PDF import needs the `pypdf` package. Install dependencies again with "
            "`python3 -m pip install -r requirements.txt` and retry the upload."
        ) from error

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text.strip())

    raw_text = "\n\n".join(pages)
    if not raw_text.strip():
        raise ValueError("We could not extract readable text from that PDF. Try a different export or paste the text manually.")
    return raw_text


def _detect_profile_source_type(source_name: str) -> str:
    """Map uploaded source names to a user-facing source type."""
    suffix = Path(source_name).suffix.lower()
    if suffix == ".pdf":
        return "profile_pdf"
    if suffix == ".docx":
        return "resume"
    if suffix in {".txt", ".md"}:
        return "notes"
    return "manual_notes"


def _extract_profile_from_import(uploaded_file, notes_text: str) -> tuple[str, str, dict, list[dict]]:
    """Extract raw text, source name, profile basics, and item dicts from uploaded material."""
    raw_text_parts: list[str] = []
    source_name = "Manual Notes"

    if uploaded_file is not None:
        source_name = uploaded_file.name
        suffix = Path(uploaded_file.name).suffix.lower()
        file_bytes = uploaded_file.getvalue()
        if suffix == ".docx":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            try:
                raw_text_parts.append(extract_text(temp_path))
            finally:
                Path(temp_path).unlink(missing_ok=True)
        elif suffix == ".pdf":
            raw_text_parts.append(_extract_pdf_text(file_bytes))
        elif suffix in {".txt", ".md"}:
            raw_text_parts.append(file_bytes.decode("utf-8", errors="ignore"))
        else:
            raise ValueError("For profile import, use .pdf, .docx, .txt, .md, or pasted notes.")

    if notes_text.strip():
        raw_text_parts.append(notes_text.strip())

    raw_text = "\n\n".join(part for part in raw_text_parts if part.strip())
    if not raw_text.strip():
        raise ValueError("Upload a source document or paste notes to build the profile.")

    basics, items = extract_profile_items_from_text(raw_text)
    return raw_text, source_name, basics, [item.to_dict() for item in items]


def _build_profile_import_notes() -> str:
    """Combine sectioned profile notes into one extraction-friendly text block."""
    section_map = [
        ("Personal background", st.session_state.profile_import_personal),
        ("Work experience", st.session_state.profile_import_experience),
        ("Education and certifications", st.session_state.profile_import_education),
        ("Projects and leadership", st.session_state.profile_import_projects),
        ("Skills and tools", st.session_state.profile_import_skills),
        ("Additional context", st.session_state.profile_import_additional),
    ]
    blocks = [f"{label}\n{value.strip()}" for label, value in section_map if str(value).strip()]
    combined = "\n\n".join(blocks)
    if not combined and st.session_state.profile_import_notes.strip():
        combined = st.session_state.profile_import_notes.strip()
    st.session_state.profile_import_notes = combined
    return combined


def render_profile_welcome_screen() -> None:
    """Entry point for Career Profile onboarding."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Career Profile</div>
            <h1>Tell us about yourself once.</h1>
            <p>Build a reusable profile the app can draw from for future job applications, instead of starting from scratch every time.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Fast Import</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Import from a resume or notes.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Upload a LinkedIn PDF, an existing resume, or paste detailed notes. We’ll extract reusable profile items for you to review.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Import Materials", use_container_width=True, key="profile-import-entry"):
                st.session_state.screen = "profile_import"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Profile Dashboard</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">View your saved career profile.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Open your stored experience bank, saved sources, and target-role settings. Great for updating your long-term career memory.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Open Profile Dashboard", use_container_width=True, key="profile-dashboard-entry"):
                st.session_state.screen = "profile_dashboard"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    back_col_left, back_col_center, back_col_right = st.columns([1.2, 1.6, 1.2])
    with back_col_center:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Home", use_container_width=True, key="profile-welcome-back"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_import_screen() -> None:
    """Collect source material for first-pass profile extraction."""
    render_shell_start()
    render_screen_intro(
        "input",
        "Career Profile Import",
        "Build your profile from what you already have.",
        "Start with a LinkedIn PDF, a resume, or pasted career notes. We’ll turn them into reusable profile sections you can review and edit.",
        show_journey=False,
        show_status_line=False,
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Source Material</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Choose the easiest starting point.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Upload a LinkedIn PDF or resume, then add any missing details in the sections below. When you continue, we will extract everything into an editable profile preview.</div>',
            unsafe_allow_html=True,
        )

        top_left, top_right = st.columns([1.2, 1], gap="large")
        with top_left:
            st.markdown('<div class="apple-kicker" style="margin-top:0.4rem;">Upload source file</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-minor-copy" style="margin-bottom:0.85rem;">Best for LinkedIn PDF exports, old resumes, and master profile documents you already have.</div>',
                unsafe_allow_html=True,
            )
            uploaded_source = st.file_uploader(
                "Upload source file",
                type=["pdf", "docx", "txt", "md"],
                help="Profile import supports LinkedIn/profile PDFs, .docx resumes, .txt files, and .md files.",
                key="profile-import-file",
                label_visibility="collapsed",
            )
            if uploaded_source is not None:
                st.markdown(
                    f'<div class="apple-minor-copy" style="margin-top:0.65rem;"><strong>{uploaded_source.name}</strong> is ready. Add any missing context below, then extract the preview.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="apple-minor-copy" style="margin-top:0.65rem;">No file selected yet. You can still continue with notes only.</div>',
                    unsafe_allow_html=True,
                )

        with top_right:
            st.markdown('<div class="apple-kicker" style="margin-top:0.4rem;">What happens next</div>', unsafe_allow_html=True)
            st.markdown(
                """
                <div class="apple-minor-copy">
                  1. Upload a file, add notes, or do both.<br/>
                  2. Click <strong>Extract and Preview Profile</strong>.<br/>
                  3. Review the imported personal info, education, experience, projects, and skills before saving.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown('<div class="apple-quiet-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Add missing details</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy" style="margin-bottom:1.15rem;">Use these sections to add anything your uploaded file does not capture cleanly. This keeps the profile import easy to review later.</div>',
            unsafe_allow_html=True,
        )

        notes_left, notes_right = st.columns(2, gap="large")
        with notes_left:
            st.text_area(
                "Personal summary or headline",
                key="profile_import_personal",
                height=120,
                placeholder="Headline, location, contact context, portfolio, LinkedIn, or a short summary of who you are.",
            )
            st.text_area(
                "Work experience",
                key="profile_import_experience",
                height=180,
                placeholder="Jobs, internships, businesses, freelance work, promotions, leadership responsibilities, and bullet highlights.",
            )
            st.text_area(
                "Education and certifications",
                key="profile_import_education",
                height=150,
                placeholder="Schools, degrees, dates, coursework, GPA, scholarships, certifications, or licenses.",
            )
        with notes_right:
            st.text_area(
                "Projects and leadership",
                key="profile_import_projects",
                height=150,
                placeholder="Clubs, case competitions, volunteer work, side projects, research, founder work, awards, or community leadership.",
            )
            st.text_area(
                "Skills and tools",
                key="profile_import_skills",
                height=120,
                placeholder="Tools, software, languages, technical skills, platforms, methods, and domain knowledge.",
            )
            st.text_area(
                "Additional context",
                key="profile_import_additional",
                height=120,
                placeholder="Anything else you want the app to remember for future resumes and applications.",
            )

        st.markdown('<div class="apple-meta-band"></div>', unsafe_allow_html=True)
        helper_left, helper_right = st.columns(2, gap="large")
        with helper_left:
            st.markdown('<div class="apple-kicker">Works Well With</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-minor-copy">LinkedIn PDF exports, current resumes, old resumes, portfolio summaries, and copied profile text.</div>',
                unsafe_allow_html=True,
            )
        with helper_right:
            st.markdown('<div class="apple-kicker">Good To Add Here</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-minor-copy">Businesses, certifications, club leadership, side work, research, volunteer work, and anything you want reusable later.</div>',
                unsafe_allow_html=True,
            )

    notes_text = _build_profile_import_notes()
    can_extract = uploaded_source is not None or bool(notes_text.strip())
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="profile-import-back"):
            st.session_state.screen = "profile_welcome"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Extract and Preview Profile", use_container_width=True, key="profile-extract", disabled=not can_extract):
            try:
                raw_text, source_name, basics, item_dicts = _extract_profile_from_import(uploaded_source, notes_text)
                st.session_state.profile_import_source_name = source_name
                st.session_state.profile_extracted_basics = basics
                st.session_state.profile_extracted_items = item_dicts
                st.session_state.profile_last_source_raw_text = raw_text
                st.session_state.screen = "profile_review"
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_review_screen() -> None:
    """Review extracted profile basics and items before saving."""
    render_shell_start()
    render_screen_intro(
        "review",
        "Career Profile Review",
        "Review your extracted profile.",
        "Confirm the imported details before saving them as your reusable career profile.",
        show_journey=False,
        show_status_line=False,
    )

    basics = st.session_state.profile_extracted_basics or {}
    extracted_items = _profile_items_from_session()
    extracted_type_counts = Counter(item.item_type for item in extracted_items)
    review_groups = [
        ("Experience", ["experience", "business", "volunteering"]),
        ("Education", ["education", "certification"]),
        ("Projects & Leadership", ["project", "leadership", "activity", "award"]),
        ("Skills", ["skills"]),
    ]

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Basics</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Confirm the essentials first.</div>', unsafe_allow_html=True)
        source_name = st.session_state.profile_import_source_name or "Imported source"
        source_summary = [
            ("Imported from", source_name),
            ("Detected name", basics.get("full_name", "Missing")),
            ("Detected contact", "Yes" if basics.get("email") or basics.get("phone") or basics.get("linkedin") else "Missing"),
            ("Suggested items", str(len(extracted_items))),
        ]
        st.markdown(build_readiness_rows(source_summary), unsafe_allow_html=True)
        identity_col1, identity_col2 = st.columns(2, gap="large")
        with identity_col1:
            full_name = st.text_input("Full Name", value=basics.get("full_name", ""), placeholder="Example: Jane Doe")
            email = st.text_input("Email", value=basics.get("email", ""), placeholder="jane@example.com")
            phone = st.text_input("Phone", value=basics.get("phone", ""), placeholder="(555) 555-5555")
        with identity_col2:
            location = st.text_input("Location", value=basics.get("location", ""), placeholder="New York, NY")
            linkedin = st.text_input("LinkedIn", value=basics.get("linkedin", ""), placeholder="linkedin.com/in/janedoe")
        headline = st.text_input("Headline", value=basics.get("headline", ""), placeholder="Example: Supply Chain Analyst | Operations | Analytics")
        summary = st.text_area("Summary", value=basics.get("summary", ""), height=120, placeholder="A concise profile summary.")
        career_stage = st.selectbox(
            "Career Stage",
            CAREER_STAGES,
            index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
            key="profile-review-stage",
        )
        target_roles = st.text_input("Target Roles", value=st.session_state.target_role, placeholder="Example: Operations Analyst, Supply Chain Analyst")
        target_industries = st.text_input("Target Industries", value=st.session_state.target_industry, placeholder="Example: Supply Chain / Operations, Technology")
        preferred_locations = st.text_input("Preferred Locations", value=basics.get("preferred_locations", ""), placeholder="Example: New York, Boston, Remote")
        work_authorization = st.text_input("Work Authorization", value="", placeholder="Example: U.S. Citizen, OPT, No sponsorship needed")

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Extracted Items</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-title">Review the suggested items section by section.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="apple-section-copy">{len(extracted_items)} items were detected. Keep the pieces that should become part of your long-term profile, and leave out anything noisy or irrelevant.</div>',
            unsafe_allow_html=True,
        )
        grouped_indexes: list[tuple[str, list[int]]] = []
        for section_label, item_types in review_groups:
            section_indexes = [index for index, item in enumerate(extracted_items) if item.item_type in item_types]
            if section_indexes:
                grouped_indexes.append((section_label, section_indexes))

        drafted_items: list[ProfileItem] = []
        included_count = 0
        if grouped_indexes:
            tabs = st.tabs([f"{section_label} ({len(indexes)})" for section_label, indexes in grouped_indexes])
            for tab, (section_label, indexes) in zip(tabs, grouped_indexes):
                with tab:
                    section_guidance = {
                        "Experience": "Keep the roles, businesses, and volunteering entries you want the app to reuse when tailoring future applications.",
                        "Education": "Keep clean school, degree, and certification records so the profile stays easy to trust and reuse.",
                        "Projects & Leadership": "This is the right place for leadership, awards, activities, side work, and project-based evidence that strengthens future applications.",
                        "Skills": "Trim this down to the skills you actually want the system to remember and surface later.",
                    }
                    section_item_types = sorted({extracted_items[index].item_type.title() for index in indexes})
                    st.markdown(
                        f'<div class="apple-section-title" style="margin-bottom:0.35rem;">{section_label}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="apple-minor-copy" style="margin-bottom:0.6rem;">{section_guidance.get(section_label, f"Review the extracted {section_label.lower()} items below and keep only what should become reusable profile memory.")}</div>',
                        unsafe_allow_html=True,
                    )
                    action_col1, action_col2, action_col3 = st.columns([1, 1, 2.4], gap="small")
                    with action_col1:
                        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                        if st.button("Keep all", use_container_width=True, key=f"profile-review-keep-all-{section_label}"):
                            for index in indexes:
                                st.session_state[f"profile-review-keep-{index}"] = True
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    with action_col2:
                        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                        if st.button("Skip section", use_container_width=True, key=f"profile-review-skip-all-{section_label}"):
                            for index in indexes:
                                st.session_state[f"profile-review-keep-{index}"] = False
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    with action_col3:
                        kept_now = sum(1 for index in indexes if st.session_state.get(f"profile-review-keep-{index}", extracted_items[index].visibility != "archived"))
                        st.markdown(
                            f'<div class="apple-minor-copy" style="margin-top:0.55rem; text-align:right;">{kept_now} of {len(indexes)} items currently selected</div>',
                            unsafe_allow_html=True,
                        )
                    for order_in_section, index in enumerate(indexes):
                        item = extracted_items[index]
                        expander_title = f"{order_in_section + 1}. {item.title or 'Untitled item'}"
                        with st.expander(expander_title, expanded=order_in_section == 0):
                            keep_item = st.checkbox(
                                "Include in career profile",
                                value=item.visibility != "archived",
                                key=f"profile-review-keep-{index}",
                            )
                            title_col, org_col = st.columns(2, gap="large")
                            with title_col:
                                item_type = st.selectbox(
                                    "Item Type",
                                    PROFILE_ITEM_TYPES,
                                    index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                                    key=f"profile-review-type-{index}",
                                )
                                title = st.text_input(
                                    "Title",
                                    value=item.title,
                                    placeholder="Example: Operations Analyst Intern",
                                    key=f"profile-review-title-{index}",
                                )
                            with org_col:
                                organization = st.text_input(
                                    "Organization",
                                    value=item.organization,
                                    placeholder="Example: Amazon or Simon Business School",
                                    key=f"profile-review-organization-{index}",
                                )
                                confidence_label = f"{int(item.confidence_score * 100)}% extracted confidence"
                                st.markdown(f'<div class="apple-minor-copy">{confidence_label}</div>', unsafe_allow_html=True)

                            meta_col1, meta_col2 = st.columns(2, gap="large")
                            with meta_col1:
                                edited_location = st.text_input(
                                    "Location",
                                    value=item.location,
                                    placeholder="Example: New York, NY",
                                    key=f"profile-review-location-{index}",
                                )
                                edited_start_date = st.text_input(
                                    "Start Date",
                                    value=item.start_date,
                                    placeholder="Example: Jan 2024",
                                    key=f"profile-review-start-date-{index}",
                                )
                            with meta_col2:
                                inferred_current = item.is_current or (item.end_date.lower() == "present" if item.end_date else False)
                                edited_end_date = st.text_input(
                                    "End Date",
                                    value=item.end_date,
                                    placeholder="Example: Present or Jun 2025",
                                    key=f"profile-review-end-date-{index}",
                                )
                                edited_is_current = st.checkbox(
                                    "This is current / ongoing",
                                    value=inferred_current,
                                    key=f"profile-review-current-{index}",
                                )

                            if item.item_type == "skills":
                                st.markdown(
                                    '<div class="apple-minor-copy" style="margin-bottom:0.45rem;">This section works best as a clean skill bank rather than a long paragraph.</div>',
                                    unsafe_allow_html=True,
                                )
                                description = st.text_area(
                                    "Skill Notes",
                                    value=item.description,
                                    height=90,
                                    placeholder="Optional context about these skills.",
                                    key=f"profile-review-description-{index}",
                                )
                                bullets_text = st.text_area(
                                    "Optional Supporting Bullets",
                                    value="\n".join(item.bullets),
                                    height=90,
                                    placeholder="Optional evidence bullets, one per line.",
                                    key=f"profile-review-bullets-{index}",
                                )
                                skills_text = st.text_input(
                                    "Skills",
                                    value=", ".join(item.skills or item.keywords),
                                    placeholder="SQL, Tableau, stakeholder management",
                                    key=f"profile-review-skills-{index}",
                                )
                                parsed_skills = _split_csv_input(skills_text)
                                if parsed_skills:
                                    render_chip_row(parsed_skills[:12])
                            else:
                                description_label = "Description"
                                description_placeholder = "What did you do and why does it matter?"
                                bullets_label = "Achievement Bullets"
                                bullets_placeholder = "One bullet per line."
                                if item.item_type == "education":
                                    description_label = "Education Details"
                                    description_placeholder = "Degree, focus area, GPA, honors, or academic context."
                                    bullets_label = "Highlights"
                                    bullets_placeholder = "Relevant coursework, honors, certifications, or campus achievements."
                                elif item.item_type in {"experience", "business", "volunteering"}:
                                    description_label = "Role Snapshot"
                                    description_placeholder = "A short summary of the work, scope, and impact."
                                    bullets_label = "Impact Bullets"
                                    bullets_placeholder = "One impact-oriented bullet per line."
                                elif item.item_type in {"project", "leadership", "activity", "award", "certification"}:
                                    description_label = "Context"
                                    description_placeholder = "Why this matters and what it shows about you."
                                    bullets_label = "Supporting Points"
                                    bullets_placeholder = "Outcomes, responsibilities, or proof points."

                                description = st.text_area(
                                    description_label,
                                    value=item.description,
                                    height=120,
                                    placeholder=description_placeholder,
                                    key=f"profile-review-description-{index}",
                                )
                                bullets_text = st.text_area(
                                    bullets_label,
                                    value="\n".join(item.bullets),
                                    height=120,
                                    placeholder=bullets_placeholder,
                                    key=f"profile-review-bullets-{index}",
                                )
                                skills_text = st.text_input(
                                    "Skills / Keywords",
                                    value=", ".join(item.skills or item.keywords),
                                    placeholder="SQL, Tableau, stakeholder management",
                                    key=f"profile-review-skills-{index}",
                                )

                            drafted_item = ProfileItem(
                                item_type=item_type,
                                title=title.strip(),
                                organization=organization.strip(),
                                location=edited_location.strip(),
                                start_date=edited_start_date.strip(),
                                end_date=edited_end_date.strip(),
                                is_current=edited_is_current,
                                description=description.strip(),
                                bullets=_split_line_input(bullets_text),
                                skills=_split_csv_input(skills_text),
                                keywords=_split_csv_input(skills_text)[:12] or item.keywords,
                                confidence_score=item.confidence_score,
                                verification_status="verified",
                                visibility="active" if keep_item else "archived",
                            )
                            if keep_item and (drafted_item.title or drafted_item.description or drafted_item.bullets):
                                included_count += 1
                                drafted_items.append(drafted_item)
        else:
            st.markdown(
                '<div class="apple-minor-copy" style="margin-top:0.75rem;">No reusable items were detected from this import yet. You can go back, add more source material, and try again.</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div class="apple-minor-copy" style="margin-top:0.75rem;">{included_count} items will be saved into the reusable profile library.</div>',
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="profile-review-back"):
            st.session_state.screen = "profile_import"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Save Career Profile", use_container_width=True, key="profile-save"):
            _save_profile_review_result(
                basics_snapshot=basics,
                drafted_items=drafted_items,
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                linkedin=linkedin,
                headline=headline,
                career_stage=career_stage,
                summary=summary,
                target_roles=target_roles,
                target_industries=target_industries,
                preferred_locations=preferred_locations,
                work_authorization=work_authorization,
            )
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Save and Continue", use_container_width=True, key="profile-save-continue"):
            _save_profile_review_result(
                basics_snapshot=basics,
                drafted_items=drafted_items,
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                linkedin=linkedin,
                headline=headline,
                career_stage=career_stage,
                summary=summary,
                target_roles=target_roles,
                target_industries=target_industries,
                preferred_locations=preferred_locations,
                work_authorization=work_authorization,
            )
            if st.session_state.job_description.strip():
                st.session_state.screen = "application_match"
            else:
                st.session_state.screen = "quickstart"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_dashboard_screen() -> None:
    """Simplified, section-based profile dashboard."""
    render_shell_start()
    profile = create_or_get_profile()
    sources = list_profile_sources()
    items = list_profile_items()
    active_items = [item for item in items if item.visibility == "active"]
    archived_items = [item for item in items if item.visibility == "archived"]
    verification_total = sum(1 for item in active_items if item.verification_status == "verified")

    grouped_items: dict[str, list[ProfileItem]] = {}
    for item in active_items:
        grouped_items.setdefault(item.item_type, []).append(item)

    education_items = grouped_items.get("education", [])
    experience_items = grouped_items.get("experience", []) + grouped_items.get("business", []) + grouped_items.get("volunteering", [])
    project_items = grouped_items.get("project", []) + grouped_items.get("leadership", []) + grouped_items.get("activity", []) + grouped_items.get("award", []) + grouped_items.get("certification", [])
    skill_items = grouped_items.get("skills", [])

    collected_skills: list[str] = []
    for item in active_items:
        for skill in item.skills:
            if skill and skill not in collected_skills:
                collected_skills.append(skill)

    render_screen_intro(
        "complete",
        "Career Profile",
        "Your career profile.",
        "Keep this simple, readable, and up to date. The app uses it as the source of truth for future applications and profile-driven resume generation.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-profile-header">', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-profile-name">{profile.full_name or "Set up your profile."}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-profile-headline">{profile.headline or "Add a clear headline so the app understands how to position you across future applications."}</div>',
            unsafe_allow_html=True,
        )
        profile_pills = [
            value
            for value in [
                profile.location,
                profile.email,
                profile.phone,
                profile.linkedin,
            ]
            if value
        ]
        if profile_pills:
            pill_markup = "".join(f'<div class="apple-profile-pill">{html.escape(value)}</div>' for value in profile_pills)
            st.markdown(f'<div class="apple-profile-pill-row">{pill_markup}</div>', unsafe_allow_html=True)
        if profile.summary:
            st.markdown(f'<div class="apple-profile-summary-box">{html.escape(profile.summary)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        toolbar_col1, toolbar_col2, toolbar_col3 = st.columns(3, gap="large")
        with toolbar_col1:
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">Next Best Move</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-section-title">Refresh or extend your profile.</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-minor-copy">Import a newer resume, LinkedIn PDF, or profile notes when your story changes.</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Import or Refresh Profile", use_container_width=True, key="profile-dashboard-import-source-top"):
                    st.session_state.screen = "profile_import"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        with toolbar_col2:
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">Workspace</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-section-title">Use this profile on live applications.</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-minor-copy">Open the saved-job workspace to match evidence, reuse resumes, and continue where you left off.</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Open Application Workspace", use_container_width=True, key="profile-dashboard-open-workspace-top"):
                    st.session_state.screen = "application_workspace"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        with toolbar_col3:
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">Profile Health</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-section-title">How complete is the reusable profile?</div>', unsafe_allow_html=True)
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Imported sources", str(len(sources))),
                            ("Active items", str(len(active_items))),
                            ("Reviewed items", str(verification_total)),
                        ]
                    ),
                    unsafe_allow_html=True,
                )

        overview_cols = st.columns(4, gap="large")
        overview_stats = [
            ("Experience", str(len(experience_items)), "Roles and operating history"),
            ("Education", str(len(education_items)), "Schools and programs"),
            ("Projects", str(len(project_items)), "Leadership, projects, activities"),
            ("Skills", str(len(collected_skills)), "Reusable capabilities"),
        ]
        for col, (label, value, caption) in zip(overview_cols, overview_stats):
            with col:
                render_score_tile(label, int(value), caption)

    personal_tab, education_tab, experience_tab, projects_tab, skills_tab, preferences_tab, sources_tab = st.tabs(
        ["Personal", "Education", "Work Experience", "Projects & Leadership", "Skills", "Preferences", "Imports & History"]
    )

    with personal_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Personal</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Your profile at a glance.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">This is the identity layer the app will reuse when it writes profile-driven resumes, matches evidence, and stores future application context.</div>',
                unsafe_allow_html=True,
            )
            glance_col1, glance_col2 = st.columns(2, gap="large")
            with glance_col1:
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Headline", profile.headline or "Not set"),
                            ("Career stage", profile.career_stage or "Not set"),
                            ("Work authorization", profile.work_authorization or "Not set"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
            with glance_col2:
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Target roles", ", ".join(profile.target_roles) if profile.target_roles else "Not set"),
                            ("Target industries", ", ".join(profile.target_industries) if profile.target_industries else "Not set"),
                            ("Preferred locations", ", ".join(profile.preferred_locations) if profile.preferred_locations else "Not set"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )

            with st.expander("Edit personal details", expanded=False):
                with st.form("profile-personal-form"):
                    col1, col2 = st.columns(2, gap="large")
                    with col1:
                        full_name = st.text_input("Full Name", value=profile.full_name, placeholder="Example: Jane Doe")
                        email = st.text_input("Email", value=profile.email, placeholder="jane@example.com")
                        phone = st.text_input("Phone", value=profile.phone, placeholder="(555) 555-5555")
                    with col2:
                        location = st.text_input("Location", value=profile.location, placeholder="New York, NY")
                        linkedin = st.text_input("LinkedIn", value=profile.linkedin, placeholder="linkedin.com/in/janedoe")
                        headline = st.text_input("Headline", value=profile.headline, placeholder="Supply Chain Analyst | Operations | Analytics")
                    summary = st.text_area("Summary", value=profile.summary, height=140, placeholder="A short, readable summary of your background and strengths.")
                    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                    save_personal = st.form_submit_button("Save Personal Profile", use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                if save_personal:
                    save_profile_basics(
                        full_name=full_name,
                        email=email,
                        phone=phone,
                        location=location,
                        linkedin=linkedin,
                        headline=headline,
                        career_stage=profile.career_stage,
                        summary=summary,
                        target_roles=profile.target_roles,
                        target_industries=profile.target_industries,
                        preferred_locations=profile.preferred_locations,
                        work_authorization=profile.work_authorization,
                    )
                    st.rerun()

    with education_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Education</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Your academic foundation.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Read this like a timeline of the schools, programs, and credentials that shape your foundation.</div>',
                unsafe_allow_html=True,
            )
            _render_profile_timeline_section(
                education_items,
                empty_message="No education entries yet. Import a profile source or add academic history into your profile imports.",
                item_label="education entry",
                key_prefix="profile-education",
            )

    with experience_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Work Experience</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">What you have done professionally.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">A timeline of the roles, businesses, and operating work that should shape future tailored resumes.</div>', unsafe_allow_html=True)
            _render_profile_timeline_section(
                experience_items,
                empty_message="No experience entries yet. Import a resume, LinkedIn PDF, or profile notes to populate this section.",
                item_label="work entry",
                key_prefix="profile-experience",
            )

    with projects_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Projects & Leadership</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Everything that strengthens the story beyond formal jobs.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">A story-driven timeline of projects, leadership, activities, awards, and certifications that make your profile richer and more memorable.</div>', unsafe_allow_html=True)
            _render_profile_timeline_section(
                project_items,
                empty_message="No project or leadership entries yet. Import profile material or save a fresh resume draft into your profile to populate this section.",
                item_label="project or leadership entry",
                key_prefix="profile-projects",
            )

    with skills_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Skills</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Capabilities the app can reuse.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">This is your reusable skill bank, collected from imports and manually edited profile entries.</div>', unsafe_allow_html=True)
            if collected_skills:
                render_chip_row(collected_skills)
            else:
                st.markdown('<div class="apple-minor-copy">No skill tags yet. Skills will appear here as you import and edit profile entries.</div>', unsafe_allow_html=True)

            _render_profile_display_cards(
                skill_items,
                empty_message="No skill groups yet. Skills will appear here as you import and edit profile entries.",
                item_label="skill group",
                key_prefix="profile-skills",
            )

    with preferences_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Preferences</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">How you want to be positioned.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">These preferences steer matching, profile-driven drafting, and the direction of future tailored resumes.</div>', unsafe_allow_html=True)
            with st.form("profile-preferences-form"):
                career_stage = st.selectbox(
                    "Career Stage",
                    CAREER_STAGES,
                    index=CAREER_STAGES.index(profile.career_stage) if profile.career_stage in CAREER_STAGES else 0,
                )
                work_authorization = st.text_input("Work Authorization", value=profile.work_authorization, placeholder="OPT, U.S. Citizen, No sponsorship needed")
                target_roles = st.text_input("Target Roles", value=", ".join(profile.target_roles), placeholder="Operations Analyst, Supply Chain Analyst")
                target_industries = st.text_input("Target Industries", value=", ".join(profile.target_industries), placeholder="Supply Chain / Operations, Technology")
                preferred_locations = st.text_input("Preferred Locations", value=", ".join(profile.preferred_locations), placeholder="New York, Boston, Remote")
                st.markdown(build_readiness_rows([
                    ("Career stage", profile.career_stage or "Not set"),
                    ("Target roles", ", ".join(profile.target_roles) if profile.target_roles else "Missing"),
                    ("Preferred locations", ", ".join(profile.preferred_locations) if profile.preferred_locations else "Missing"),
                ]), unsafe_allow_html=True)
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                save_preferences = st.form_submit_button("Save Preferences", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            if save_preferences:
                save_profile_basics(
                    full_name=profile.full_name,
                    email=profile.email,
                    phone=profile.phone,
                    location=profile.location,
                    linkedin=profile.linkedin,
                    headline=profile.headline,
                    career_stage=career_stage,
                    summary=profile.summary,
                    target_roles=_split_csv_input(target_roles),
                    target_industries=_split_csv_input(target_industries),
                    preferred_locations=_split_csv_input(preferred_locations),
                    work_authorization=work_authorization,
                )
                st.rerun()

    with sources_tab:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Imports & History</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Where this profile came from.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">Most people will only check this occasionally. It is here when you want to review imported profile sources, restore hidden items, or understand how the profile was built over time.</div>', unsafe_allow_html=True)
            st.markdown(
                build_readiness_rows(
                    [
                        ("Imported sources", str(len(sources))),
                        ("Active profile items", str(len(active_items))),
                        ("Verified items", str(verification_total)),
                        ("Hidden items", str(len(archived_items))),
                    ]
                ),
                unsafe_allow_html=True,
            )
            source_action_col1, source_action_col2 = st.columns(2, gap="large")
            with source_action_col1:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Import New Source", use_container_width=True, key="profile-history-import-source"):
                    st.session_state.screen = "profile_import"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with source_action_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Return to Profile Overview", use_container_width=True, key="profile-history-overview"):
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with st.expander("View imported sources", expanded=False):
                if not sources:
                    st.markdown('<div class="apple-minor-copy">No imported sources yet. Bring in a PDF, DOCX, or notes to begin building your long-term profile memory.</div>', unsafe_allow_html=True)
                else:
                    for source in sources[:12]:
                        with st.container(border=True):
                            st.markdown(f"**{source.source_name or 'Untitled source'}**")
                            st.markdown(build_readiness_rows([
                                ("Type", source.source_type.replace("_", " ").title()),
                                ("Status", source.parsed_status.title()),
                                ("Created", source.created_at[:10] if source.created_at else "Unknown"),
                            ]), unsafe_allow_html=True)

            with st.expander(f"Restore hidden profile items ({len(archived_items)})", expanded=False):
                if not archived_items:
                    st.markdown('<div class="apple-minor-copy">Nothing is hidden right now.</div>', unsafe_allow_html=True)
                else:
                    for item in archived_items:
                        row_col1, row_col2 = st.columns([4, 1], gap="large")
                        with row_col1:
                            st.markdown(f"**{item.title or 'Untitled item'}**")
                            st.markdown(f'<div class="apple-minor-copy">{item.item_type.title()} · {item.organization or "Organization not specified"}</div>', unsafe_allow_html=True)
                        with row_col2:
                            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                            if st.button("Restore", use_container_width=True, key=f"profile-restore-{item.id}"):
                                archive_profile_item(item.id, visibility="active")
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Import More Materials", use_container_width=True, key="profile-dashboard-import"):
            st.session_state.screen = "profile_import"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Match Profile to Job", use_container_width=True, key="profile-dashboard-match"):
            st.session_state.screen = "application_match"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Application Workspace", use_container_width=True, key="profile-dashboard-workspace"):
            st.session_state.screen = "application_workspace"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Back to Home", use_container_width=True, key="profile-dashboard-home"):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_application_match_screen() -> None:
    """Recommend profile evidence to use for the current application."""
    render_shell_start()
    render_screen_intro(
        "application_match",
        "Career Profile Match",
        "Choose the strongest evidence for this job.",
        "We ranked your saved profile items against the current job description so you can decide what should guide the prompt.",
    )

    active_items = [item for item in list_profile_items() if item.visibility == "active"]
    job_description = st.session_state.job_description.strip()
    resume_loaded = bool(st.session_state.resume_text)

    if not job_description or not active_items:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Not Ready Yet</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">This step needs a job description and active profile items.</div>', unsafe_allow_html=True)
            readiness_rows = [
                ("Resume uploaded", "Yes" if resume_loaded else "Optional for draft mode"),
                ("Job description", "Loaded" if job_description else "Missing"),
                ("Active profile items", str(len(active_items))),
            ]
            st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)
        left_col, right_col = st.columns(2, gap="large")
        with left_col:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Upload", use_container_width=True, key="application-match-back-input"):
                st.session_state.screen = "input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with right_col:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Open Profile Dashboard", use_container_width=True, key="application-match-profile-dashboard"):
                st.session_state.screen = "profile_dashboard"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        render_shell_end()
        return

    target_role = get_effective_target_role(job_description)
    target_industry = get_effective_industry(job_description)
    job_signals, ranked_results = rank_profile_items(active_items, job_description, target_role=target_role, target_industry=target_industry)

    recommended_ids = [result["item"].id for result in ranked_results[:5] if result["score"] > 0 and result["item"].id is not None]
    current_selection = st.session_state.get("selected_profile_item_ids", [])
    if not current_selection:
        st.session_state.selected_profile_item_ids = recommended_ids
        current_selection = recommended_ids

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Job Signals</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">What we detected from the target job.</div>', unsafe_allow_html=True)
        company = st.text_input(
            "Company",
            value=st.session_state.get("current_application_company", ""),
            placeholder="Optional company name",
            key="application-match-company",
        )
        st.session_state.current_application_company = company
        signal_rows = [
            ("Target role", target_role or "Not detected"),
            ("Company", company or "Not set yet"),
            ("Industry", target_industry or "Not detected"),
            ("Top keywords", ", ".join(job_signals.get("keywords", [])[:8]) or "No clear keywords yet"),
        ]
        st.markdown(build_readiness_rows(signal_rows), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Recommended Evidence</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Select what should guide the tailored resume.</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-copy">The prompt will use these saved items as relevance guidance while still staying anchored to the uploaded resume.</div>', unsafe_allow_html=True)

        selected_ids: list[int] = []
        for index, result in enumerate(ranked_results[:10], start=1):
            item = result["item"]
            item_id = item.id if item.id is not None else -index
            default_selected = item_id in current_selection
            with st.container(border=True):
                include_item = st.checkbox(
                    f"Use item {index}",
                    value=default_selected,
                    key=f"profile-match-include-{item_id}",
                )
                st.markdown(f"**{item.title or 'Untitled item'}**")
                st.markdown(f'<div class="apple-minor-copy">{item.item_type.title()} · {item.organization or "Organization not specified"} · Score {result["score"]:.1f}</div>', unsafe_allow_html=True)
                if item.description:
                    st.markdown(item.description)
                if result["reasons"]:
                    st.markdown(f'<div class="apple-minor-copy">Why selected: {" | ".join(result["reasons"][:3])}</div>', unsafe_allow_html=True)
                if item.skills:
                    st.markdown(f'<div class="apple-minor-copy">Skills: {", ".join(item.skills[:8])}</div>', unsafe_allow_html=True)
                if include_item and item.id is not None:
                    selected_ids.append(item.id)

        st.session_state.selected_profile_item_ids = selected_ids
        st.session_state.profile_job_signals = job_signals

    back_col, optimize_col, draft_col = st.columns([0.8, 1.1, 1.1], gap="large")
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="application-match-back"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with optimize_col:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Optimize Existing Resume", use_container_width=True, key="application-match-continue", disabled=not (selected_ids and resume_loaded)):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_optimize")
            _evaluate_current_resume_fit(force=True)
            st.session_state.screen = "fit_report"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with draft_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Create Draft from Profile", use_container_width=True, key="application-match-draft", disabled=not selected_ids):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_draft")
            _start_profile_draft_flow()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_application_workspace_screen() -> None:
    """Saved jobs / application workspaces."""
    render_shell_start()
    applications = list_applications()
    resume_assets = list_resume_assets()
    status_counts = Counter(application.status for application in applications)
    companies = sorted({application.company for application in applications if application.company})
    render_screen_intro(
        "application_match",
        "Application Workspace",
        "Your saved job targets.",
        "Return to a job, review selected profile evidence, or start a new application from the profile system.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Workspace Summary</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(applications)} saved applications</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Each application stores the job target, job description, selected career-profile evidence, and current workflow status.</div>',
            unsafe_allow_html=True,
        )
        if not applications:
            st.markdown('<div class="apple-minor-copy">No saved applications yet. Paste a job description, use your Career Profile, and choose evidence to create the first workspace.</div>', unsafe_allow_html=True)
        else:
            workspace_rows = [
                ("Draft", str(status_counts.get("draft", 0))),
                ("Ready to optimize", str(status_counts.get("ready_to_optimize", 0))),
                ("Ready to draft", str(status_counts.get("ready_to_draft", 0))),
                ("Resumes saved", str(status_counts.get("saved_resume", 0) + status_counts.get("saved_builder_resume", 0))),
            ]
            st.markdown(build_readiness_rows(workspace_rows), unsafe_allow_html=True)

    if applications:
        latest_application = applications[0]
        latest_label, latest_hint = _format_application_status(latest_application.status)
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Continue Where You Left Off</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-title">{latest_application.job_title or "Untitled target role"}{f" at {latest_application.company}" if latest_application.company else ""}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="apple-minor-copy">{latest_hint}</div>', unsafe_allow_html=True)
            st.markdown(
                build_readiness_rows(
                    [
                        ("Status", latest_label),
                        ("Industry", latest_application.industry or "Not detected"),
                        ("Selected evidence", str(len(latest_application.selected_profile_item_ids))),
                    ]
                ),
                unsafe_allow_html=True,
            )
            continue_col1, continue_col2 = st.columns(2, gap="large")
            with continue_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Open Latest Application", use_container_width=True, key="workspace-open-latest"):
                    _load_application_into_session(latest_application.id)
                    st.session_state.screen = "application_match"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with continue_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Go to Resume Library", use_container_width=True, key="workspace-go-library-top"):
                    st.session_state.screen = "resume_library"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Application Filters</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Focus on the right saved target.</div>', unsafe_allow_html=True)
        filter_col1, filter_col2, filter_col3 = st.columns(3, gap="large")
        with filter_col1:
            selected_status = st.selectbox(
                "Status",
                [
                    "All",
                    "Draft",
                    "Ready to optimize",
                    "Ready to draft",
                    "Profile matched",
                    "Resume saved",
                    "Fresh resume saved",
                ],
                index=0,
                key="application-workspace-status-filter",
            )
        with filter_col2:
            selected_company = st.selectbox(
                "Company",
                ["All"] + companies,
                index=0,
                key="application-workspace-company-filter",
            )
        with filter_col3:
            application_search = st.text_input(
                "Search",
                value=st.session_state.get("application-workspace-search", ""),
                placeholder="Role, company, industry, job text",
                key="application-workspace-search",
            )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Resume Library</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(resume_assets)} saved resume assets</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">These are your saved generated resumes. Each one keeps a category, source type, and optional application link for future reuse.</div>',
            unsafe_allow_html=True,
        )
        if not resume_assets:
            st.markdown('<div class="apple-minor-copy">No saved resumes yet. Save an optimized resume or fresh builder resume to start your library.</div>', unsafe_allow_html=True)
        else:
            preview_assets = resume_assets[:3]
            for asset in preview_assets:
                with st.container(border=True):
                    st.markdown(f'<div class="apple-section-title">{asset.title or asset.file_name}</div>', unsafe_allow_html=True)
                    render_chip_row(_derive_resume_asset_tags(asset))
                    st.markdown(
                        build_readiness_rows(
                            [
                                ("Category", asset.category or "General"),
                                ("Source", asset.source_kind.replace("_", " ").title()),
                                ("Target role", asset.target_role or "Not set"),
                                ("Company", asset.company or "Not set"),
                            ]
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="apple-minor-copy">Saved: {asset.updated_at}</div>', unsafe_allow_html=True)
                    st.download_button(
                        "Download Saved Resume",
                        data=io.BytesIO(asset.file_bytes),
                        file_name=asset.file_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"resume-asset-download-{asset.id}",
                    )
                    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                    if st.button("Use as Starting Point", use_container_width=True, key=f"workspace-resume-asset-use-{asset.id}"):
                        _load_resume_asset_into_session(asset)
                        st.session_state.screen = "input"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            if len(resume_assets) > len(preview_assets):
                st.markdown(
                    f'<div class="apple-minor-copy">Showing {len(preview_assets)} of {len(resume_assets)} saved resumes here. Open the full library to browse every version.</div>',
                    unsafe_allow_html=True,
                )

    filtered_applications = applications
    if selected_status != "All":
        normalized_status = selected_status.lower().replace(" ", "_")
        filtered_applications = [
            application
            for application in filtered_applications
            if _format_application_status(application.status)[0].lower() == selected_status.lower()
            or application.status == normalized_status
        ]
    if selected_company != "All":
        filtered_applications = [application for application in filtered_applications if application.company == selected_company]
    if application_search.strip():
        query = application_search.strip().lower()
        filtered_applications = [
            application
            for application in filtered_applications
            if query in " ".join(
                [
                    application.job_title,
                    application.company,
                    application.industry,
                    application.role_family,
                    application.job_description,
                    application.status,
                ]
            ).lower()
        ]

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Applications In View</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(filtered_applications)} saved targets match the current filters</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Each saved target remembers the job brief, selected profile evidence, and where you left off so you can pick up work without rebuilding context.</div>',
            unsafe_allow_html=True,
        )
        if not filtered_applications:
            st.markdown('<div class="apple-minor-copy">No saved applications match the current filters yet.</div>', unsafe_allow_html=True)

    for application in filtered_applications:
        with st.container(border=True):
            title = application.job_title or "Untitled target role"
            company_suffix = f" at {application.company}" if application.company else ""
            status_label, status_hint = _format_application_status(application.status)
            next_move_label, next_move_copy = _application_next_move(application)
            st.markdown('<div class="apple-kicker">Saved Application</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{title}{company_suffix}</div>', unsafe_allow_html=True)
            render_chip_row(_derive_application_tags(application))
            rows = [
                ("Company", application.company or "Not set"),
                ("Industry", application.industry or "Not detected"),
                ("Status", status_label),
                ("Selected evidence", str(len(application.selected_profile_item_ids))),
                ("Best next move", next_move_label),
                ("Updated", application.updated_at),
            ]
            st.markdown(build_readiness_rows(rows), unsafe_allow_html=True)
            st.markdown(f'<div class="apple-minor-copy">{status_hint}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-minor-copy">{next_move_copy}</div>', unsafe_allow_html=True)
            preview = " ".join(application.job_description.split())[:320]
            if preview:
                st.markdown(f'<div class="apple-section-copy">{preview}{"..." if len(preview) == 320 else ""}</div>', unsafe_allow_html=True)

            action_col1, action_col2, action_col3 = st.columns(3, gap="large")
            with action_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Open Evidence Match", use_container_width=True, key=f"application-open-match-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "application_match"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with action_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Optimize / Run", use_container_width=True, key=f"application-open-mode-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "mode" if st.session_state.resume_text else "application_match"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with action_col3:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Create Profile Draft", use_container_width=True, key=f"application-open-draft-{application.id}", disabled=not application.selected_profile_item_ids):
                    _load_application_into_session(application.id)
                    _start_profile_draft_flow()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Profile", use_container_width=True, key="application-workspace-profile"):
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Add Job / Upload", use_container_width=True, key="application-workspace-input"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Resume Library", use_container_width=True, key="application-workspace-library"):
            st.session_state.screen = "resume_library"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Home", use_container_width=True, key="application-workspace-home"):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_resume_library_screen() -> None:
    """Dedicated library for saved resume assets."""
    render_shell_start()
    assets = list_resume_assets()
    companies = sorted({asset.company for asset in assets if asset.company})
    source_counts = Counter(asset.source_kind for asset in assets)
    use_case_tags = sorted(
        {
            tag
            for asset in assets
            for tag in _infer_workspace_tags(asset.target_role, asset.category, asset.notes)
        }
    )
    render_screen_intro(
        "complete",
        "Resume Library",
        "Your saved resumes.",
        "Browse the resumes you have saved, filter by category, update labels and notes, and download them again whenever you need them.",
    )

    categories = sorted({asset.category for asset in assets if asset.category})
    source_kinds = sorted({asset.source_kind for asset in assets if asset.source_kind})

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Library Filters</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Find the right saved version fast.</div>', unsafe_allow_html=True)
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4, gap="large")
        with filter_col1:
            selected_category = st.selectbox(
                "Category",
                ["All"] + categories,
                index=0,
                key="resume-library-category",
            )
        with filter_col2:
            selected_source = st.selectbox(
                "Source Type",
                ["All"] + [kind.replace("_", " ").title() for kind in source_kinds],
                index=0,
                key="resume-library-source",
            )
        with filter_col3:
            selected_company = st.selectbox(
                "Company",
                ["All"] + companies,
                index=0,
                key="resume-library-company",
            )
        with filter_col4:
            selected_use_case = st.selectbox(
                "Use Case",
                ["All"] + use_case_tags,
                index=0,
                key="resume-library-use-case",
            )
        sort_col, _ = st.columns([0.55, 1.45], gap="large")
        with sort_col:
            sort_mode = st.selectbox(
                "Sort By",
                ["Recently updated", "Oldest updated", "Role A-Z", "Company A-Z", "Category A-Z"],
                index=0,
                key="resume-library-sort",
            )
        with _:
            search_query = st.text_input(
                "Search",
                value=st.session_state.get("resume-library-search", ""),
                placeholder="Role, company, title, notes",
                key="resume-library-search",
            )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Library Snapshot</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">How your saved resume shelf is shaping up.</div>', unsafe_allow_html=True)
        snapshot_rows = [
            ("Saved resumes", str(len(assets))),
            ("Optimized versions", str(source_counts.get("optimized_resume", 0))),
            ("Fresh builds", str(source_counts.get("fresh_resume", 0))),
            ("Linked to applications", str(sum(1 for asset in assets if asset.application_id))),
        ]
        st.markdown(build_readiness_rows(snapshot_rows), unsafe_allow_html=True)

    filtered_assets = assets
    if selected_category != "All":
        filtered_assets = [asset for asset in filtered_assets if asset.category == selected_category]
    if selected_source != "All":
        normalized_source = selected_source.lower().replace(" ", "_")
        filtered_assets = [asset for asset in filtered_assets if asset.source_kind == normalized_source]
    if selected_company != "All":
        filtered_assets = [asset for asset in filtered_assets if asset.company == selected_company]
    if selected_use_case != "All":
        filtered_assets = [
            asset
            for asset in filtered_assets
            if selected_use_case in _infer_workspace_tags(asset.target_role, asset.category, asset.notes)
        ]
    if search_query.strip():
        query = search_query.strip().lower()
        filtered_assets = [
            asset
            for asset in filtered_assets
            if query in " ".join(
                [
                    asset.title,
                    asset.file_name,
                    asset.target_role,
                    asset.company,
                    asset.category,
                    asset.notes,
                    asset.source_kind,
                ]
            ).lower()
        ]
    filtered_assets = _sort_resume_assets(filtered_assets, sort_mode)

    if filtered_assets:
        featured_asset = filtered_assets[0]
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Recommended Starting Point</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{featured_asset.title or featured_asset.file_name}</div>', unsafe_allow_html=True)
            render_chip_row(_derive_resume_asset_tags(featured_asset))
            st.markdown(
                f'<div class="apple-section-copy">{featured_asset.notes or _asset_reuse_copy(featured_asset)}</div>',
                unsafe_allow_html=True,
            )
            starter_col1, starter_col2 = st.columns(2, gap="large")
            with starter_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Use This Version", use_container_width=True, key=f"resume-library-featured-use-{featured_asset.id}"):
                    _load_resume_asset_into_session(featured_asset)
                    st.session_state.screen = "input"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with starter_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Open Workspace Context", use_container_width=True, key=f"resume-library-featured-workspace-{featured_asset.id}", disabled=not bool(featured_asset.application_id)):
                    if featured_asset.application_id:
                        _load_resume_asset_into_session(featured_asset)
                        st.session_state.screen = "application_workspace"
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Saved Assets</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(filtered_assets)} resumes in view</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Treat this as your reusable resume shelf. Rename versions, refine categories, keep notes about when to reuse each one, and reopen the right version without rebuilding context.</div>',
            unsafe_allow_html=True,
        )
        if not filtered_assets:
            st.markdown('<div class="apple-minor-copy">No resume assets match the current filters yet.</div>', unsafe_allow_html=True)
        for asset in filtered_assets:
            with st.container(border=True):
                st.markdown(f'<div class="apple-section-title">{asset.title or asset.file_name}</div>', unsafe_allow_html=True)
                render_chip_row(_derive_resume_asset_tags(asset))
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Category", asset.category or "General"),
                            ("Source", asset.source_kind.replace("_", " ").title()),
                            ("Target role", asset.target_role or "Not set"),
                            ("Company", asset.company or "Not set"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                with st.expander("Edit Resume Details", expanded=False):
                    with st.form(f"resume-asset-form-{asset.id}"):
                        edited_title = st.text_input("Title", value=asset.title, placeholder="Resume name")
                        edited_category = st.text_input("Category", value=asset.category, placeholder="Operations Analyst")
                        edited_target_role = st.text_input("Target Role", value=asset.target_role, placeholder="Operations Analyst")
                        edited_company = st.text_input("Company", value=asset.company, placeholder="Amazon")
                        edited_notes = st.text_area("Notes", value=asset.notes, height=100, placeholder="When should you reuse this version?")
                        if st.form_submit_button("Save Resume Details", use_container_width=True):
                            update_resume_asset(
                                asset.__class__(
                                    id=asset.id,
                                    user_id=asset.user_id,
                                    application_id=asset.application_id,
                                    source_kind=asset.source_kind,
                                    category=edited_category.strip() or asset.category,
                                    title=edited_title.strip() or asset.title,
                                    target_role=edited_target_role.strip(),
                                    company=edited_company.strip(),
                                    file_name=asset.file_name,
                                    file_bytes=asset.file_bytes,
                                    notes=edited_notes.strip(),
                                    created_at=asset.created_at,
                                    updated_at=asset.updated_at,
                                )
                            )
                            st.rerun()
                if asset.notes:
                    st.markdown(f'<div class="apple-minor-copy">{asset.notes}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="apple-minor-copy">{_asset_reuse_copy(asset)}</div>', unsafe_allow_html=True)
                if asset.application_id:
                    st.markdown(
                        '<div class="apple-minor-copy">Linked to a saved application workspace, so you can reopen the exact job context later.</div>',
                        unsafe_allow_html=True,
                    )
                download_col1, download_col2 = st.columns(2, gap="large")
                with download_col1:
                    st.markdown(f'<div class="apple-minor-copy">Saved: {asset.updated_at}</div>', unsafe_allow_html=True)
                with download_col2:
                    st.download_button(
                        "Download Resume",
                        data=io.BytesIO(asset.file_bytes),
                        file_name=asset.file_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"resume-library-download-{asset.id}",
                    )
                action_col1, action_col2 = st.columns(2, gap="large")
                with action_col1:
                    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                    if st.button("Use as Starting Point", use_container_width=True, key=f"resume-library-use-{asset.id}"):
                        _load_resume_asset_into_session(asset)
                        st.session_state.screen = "input"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with action_col2:
                    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                    if st.button("Open in Workspace", use_container_width=True, key=f"resume-library-workspace-open-{asset.id}", disabled=not bool(asset.application_id)):
                        if asset.application_id:
                            _load_resume_asset_into_session(asset)
                            st.session_state.screen = "application_workspace"
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    nav_col1, nav_col2, nav_col3 = st.columns(3, gap="large")
    with nav_col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Workspace", use_container_width=True, key="resume-library-workspace"):
            st.session_state.screen = "application_workspace"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with nav_col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Profile", use_container_width=True, key="resume-library-profile"):
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with nav_col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Home", use_container_width=True, key="resume-library-home"):
            st.session_state.screen = "landing"
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

    active_profile_items = [item for item in list_profile_items() if item.visibility == "active"]

    col1, col2, col3 = st.columns([0.7, 0.9, 1.1], gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Use Career Profile", use_container_width=True, disabled=not bool(job_description.strip() and active_profile_items), key="input-use-profile"):
            st.session_state.use_career_profile = True
            st.session_state.screen = "application_match"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
        )
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Continue", use_container_width=True, disabled=not can_continue):
            st.session_state.use_career_profile = False
            st.session_state.selected_profile_item_ids = []
            if looks_like_url(job_description):
                if fetch_and_store_job_description(job_description):
                    st.rerun()
            else:
                st.session_state.jd_cleaning_result = None
                _evaluate_current_resume_fit(force=True)
                st.session_state.screen = "fit_report"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_score_tile(label: str, score: int, caption: str = "") -> None:
    """Render one compact score tile."""
    st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="apple-kicker">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="apple-stat-value">{score}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_fit_delta_card(before_report: dict, after_report: dict) -> None:
    """Render an honest before/after fit comparison."""
    before_score = int(before_report.get("overall_score", 0))
    after_score = int(after_report.get("overall_score", 0))
    delta = after_score - before_score
    percent_delta = 0 if before_score == 0 else round((delta / before_score) * 100)
    before_signal = before_report.get("opportunity_worthiness", before_report.get("apply_signal", "Not rated"))
    after_signal = after_report.get("opportunity_worthiness", after_report.get("apply_signal", "Not rated"))

    if delta > 0:
        title = f"Estimated fit improved by {delta} point{'s' if delta != 1 else ''}."
    elif delta < 0:
        title = f"Estimated fit dropped by {abs(delta)} point{'s' if abs(delta) != 1 else ''}."
    else:
        title = "Estimated fit stayed flat."

    new_keyword_matches = [
        keyword
        for keyword in after_report.get("matched_keywords", [])
        if keyword not in before_report.get("matched_keywords", [])
    ]

    with st.container(border=True):
        st.markdown('<div class="apple-summary-label">Improvement Report</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-summary-title">{title}</div>', unsafe_allow_html=True)

        score_col1, score_col2, score_col3, score_col4 = st.columns(4, gap="large")
        with score_col1:
            render_score_tile("Before", before_score, "Pre-optimization")
        with score_col2:
            render_score_tile("After", after_score, "Validated replacement draft")
        with score_col3:
            render_score_tile("Change", delta, "Point movement")
        with score_col4:
            render_score_tile(
                "Improvement %",
                percent_delta,
                "Overall movement",
            )

        readiness_rows = [
            ("Keyword score", f"{before_report.get('keyword_score', 0)} → {after_report.get('keyword_score', 0)}"),
            ("Skill score", f"{before_report.get('skill_score', 0)} → {after_report.get('skill_score', 0)}"),
            ("ATS / clarity", f"{before_report.get('ats_score', 0)} → {after_report.get('ats_score', 0)}"),
            ("New matched keywords", ", ".join(new_keyword_matches[:6]) if new_keyword_matches else "No new keyword wins yet"),
            ("Opportunity", f"{before_signal} → {after_signal}"),
            ("Apply signal", after_report.get("apply_signal", "No decision yet")),
            ("Gap severity", after_report.get("gap_severity", "Unknown")),
        ]
        st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

        if delta <= 0:
            st.caption("Honest take: this revision may still need stronger evidence or sharper job-language alignment before it is truly better.")
        else:
            st.caption("Best-case interpretation: the revised version is surfacing stronger job language, but you should still review the remaining gaps before you export.")


def render_fit_report_screen() -> None:
    """Show a free deterministic resume/job fit report before choosing run mode."""
    report = _evaluate_current_resume_fit()
    render_shell_start()
    render_screen_intro(
        "fit_report",
        "Resume Fit Report",
        "See the fit before you run.",
        "A fast, honest checkpoint from Python scoring. Use it to spot gaps before spending time in Manual or API mode.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-summary-label">Fit Snapshot</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-summary-title">{report.get("verdict", "We need a resume and job description to score fit.")}</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="apple-signal-row">
              <div class="apple-signal-pill"><strong>Opportunity</strong> {html.escape(report.get("opportunity_worthiness", "No decision yet"))}</div>
              <div class="apple-signal-pill"><strong>Confidence</strong> {html.escape(report.get("apply_confidence", "Unknown"))}</div>
              <div class="apple-signal-pill"><strong>Gap severity</strong> {html.escape(report.get("gap_severity", "Unknown"))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        score_col1, score_col2, score_col3, score_col4 = st.columns(4, gap="large")
        with score_col1:
            render_score_tile("Overall", int(report.get("overall_score", 0)), "Resume + role match")
        with score_col2:
            render_score_tile("Keywords", int(report.get("keyword_score", 0)), "JD language visible")
        with score_col3:
            render_score_tile("Skills", int(report.get("skill_score", 0)), "Tools and capabilities")
        with score_col4:
            render_score_tile("ATS / Clarity", int(report.get("ats_score", 0)), "Structure and basics")

        st.markdown(
            build_readiness_rows(
                [
                    ("Opportunity", report.get("opportunity_worthiness", "No decision yet")),
                    ("Apply signal", report.get("apply_signal", "No decision yet")),
                    ("Confidence", report.get("apply_confidence", "Unknown")),
                    ("Gap severity", report.get("gap_severity", "Unknown")),
                    ("Best next move", report.get("improvement_priority", "Review the gaps below")),
                    ("Resume bullets detected", str(report.get("bullet_count", 0))),
                    ("Bullets with numbers", str(report.get("quantified_bullet_count", 0))),
                    ("Action-led bullets", str(report.get("action_verb_bullet_count", 0))),
                    ("Profile evidence selected", str(len(report.get("selected_evidence_titles", [])))),
                ]
            ),
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Honest Career Signal</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Should you spend time on this application?</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-copy">{report.get("opportunity_worthiness", "No decision yet")} · {report.get("apply_signal", "No decision yet")} · {report.get("apply_confidence", "Unknown")}. {report.get("recommendation_strength", "")}</div>',
            unsafe_allow_html=True,
        )
        decision_rows = [
            ("Overall fit", str(report.get("overall_score", 0))),
            ("Gap severity", report.get("gap_severity", "Unknown")),
            ("Keyword overlap", str(len(report.get("matched_keywords", [])))),
            ("Missing skills", str(len(report.get("missing_skills", [])))),
            ("Profile evidence", ", ".join(report.get("selected_evidence_titles", [])[:3]) or "None selected"),
        ]
        st.markdown(build_readiness_rows(decision_rows), unsafe_allow_html=True)

    detail_col1, detail_col2 = st.columns(2, gap="large")
    with detail_col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Strongest Area</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{report.get("strongest_area", "Unknown")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-copy">This is the part of the current resume that is carrying the application most clearly right now. Score: {report.get("strongest_area_score", 0)}.</div>',
                unsafe_allow_html=True,
            )
    with detail_col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Weakest Area</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{report.get("weakest_area", "Unknown")}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-copy">This is the area that most needs improvement before the application feels stronger. Score: {report.get("weakest_area_score", 0)}.</div>',
                unsafe_allow_html=True,
            )

    insight_col, gap_col = st.columns(2, gap="large")
    with insight_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">What Already Matches</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Signals the resume already shares with the job.</div>', unsafe_allow_html=True)
            render_chip_row(report.get("matched_keywords", [])[:12] or ["No strong keyword overlap yet"])
            matched_skills = report.get("matched_skills", [])
            if matched_skills:
                st.caption(f"Matched skills: {', '.join(matched_skills[:8])}")

    with gap_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Gaps To Consider</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Important job language that is not obvious yet.</div>', unsafe_allow_html=True)
            render_chip_row(report.get("missing_keywords", [])[:12] or ["No major keyword gaps detected"])
            missing_skills = report.get("missing_skills", [])
            if missing_skills:
                st.caption(f"Missing skills from common skill scan: {', '.join(missing_skills[:8])}")

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Honest Recommendations</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">What I would fix before export.</div>', unsafe_allow_html=True)
        focus_areas = report.get("focus_areas", [])
        if focus_areas:
            st.markdown('<div class="apple-section-copy">Focus in this order so the next revision earns the biggest quality gain:</div>', unsafe_allow_html=True)
            for recommendation in focus_areas[:4]:
                st.markdown(f"- {recommendation}")
        recommendations = report.get("recommendations", []) + report.get("warnings", [])
        if recommendations:
            st.markdown('<div class="apple-section-copy" style="margin-top:0.85rem;">Additional clean-up suggestions:</div>', unsafe_allow_html=True)
            for recommendation in recommendations[:8]:
                st.markdown(f"- {recommendation}")
        if not focus_areas and not recommendations:
            st.markdown("No urgent structural gaps detected. Continue to optimization and make the language more role-specific.")

    back_col, profile_col, run_col = st.columns([0.85, 1.0, 1.15], gap="large")
    active_profile_items = [item for item in list_profile_items() if item.visibility == "active"]
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Upload", use_container_width=True, key="fit-back-upload"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with profile_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Improve with Profile", use_container_width=True, disabled=not bool(active_profile_items), key="fit-use-profile"):
            st.session_state.use_career_profile = True
            st.session_state.screen = "application_match"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with run_col:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Continue to Run", use_container_width=True, key="fit-continue-run"):
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    render_shell_end()


def render_builder_input_screen() -> None:
    """Student-friendly first-resume intake flow."""
    render_shell_start()
    render_screen_intro(
        "builder_input",
        "Step 2 of 5",
        "Build your first resume.",
        "Tell us about yourself in plain English. We’ll shape it into a professional draft.",
    )

    basics_col, extras_col = st.columns(2, gap="large")
    with basics_col:
        with st.container(border=True):
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

    with extras_col:
        with st.container(border=True):
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
            st.session_state.builder_execution_mode = None
            st.session_state.builder_profile_saved = False
            st.session_state.builder_profile_saved_source_id = None
            st.session_state.builder_profile_save_dismissed = False
            st.session_state.screen = "builder_stub"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_stub_screen() -> None:
    """Builder prompt handoff screen."""
    render_shell_start()
    render_screen_intro(
        "builder_stub",
        "Step 3 of 5",
        "Generate your draft.",
        "Choose how you want to generate the first draft, then move on to review.",
    )

    builder_rows = [
        ("Career stage", st.session_state.career_stage or "Student"),
        ("Target role", st.session_state.target_role or "Not set"),
        ("Has job description", "Yes" if st.session_state.builder_job_description.strip() else "No"),
    ]

    mode_col1, mode_col2 = st.columns(2, gap="large")
    with mode_col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Manual</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Copy the prompt and use your favorite AI.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Best if you want to compare outputs, stay in control, or use ChatGPT, Claude, or Gemini directly.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Use Manual Mode", use_container_width=True, key="builder-use-manual"):
                st.session_state.builder_execution_mode = "manual"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    with mode_col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">API</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Let the app generate the draft for you.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Use your own provider key or local endpoint and move straight from prompt to structured draft review.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Use API Mode", use_container_width=True, key="builder-use-api"):
                st.session_state.builder_execution_mode = "api"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    builder_mode = st.session_state.get("builder_execution_mode")

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Builder Context</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Your draft setup is ready.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">This is the information the builder will use, regardless of whether you run it manually or through API mode.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(build_readiness_rows(builder_rows), unsafe_allow_html=True)

    if builder_mode == "manual":
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Manual Drafting</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Copy the builder prompt.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Paste this into your AI tool, ask for only the structured JSON output, then bring the result back below.</div>',
                unsafe_allow_html=True,
            )
            render_prompt_block("Generated Builder Prompt", st.session_state.builder_prompt, 360, "builder")

        render_instruction_panel(
            "What To Do Next",
            [
                "Copy the builder prompt above and paste it into ChatGPT, Claude, or Gemini.",
                "Ask the AI to return only the structured JSON output for the first resume.",
                "Paste the AI result below, then click Validate Builder Output.",
            ],
        )

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Builder Output</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Paste the AI response.</div>', unsafe_allow_html=True)
            pasted_output = st.text_area(
                "Paste Builder Output",
                height=280,
                placeholder="Paste the AI response here.",
            )

        with st.expander("Builder Intake Snapshot", expanded=False):
            st.text_area("Full Name", value=st.session_state.builder_full_name, height=68, disabled=True)
            st.text_area("Contact Info", value=st.session_state.builder_contact_info, height=100, disabled=True)
            st.text_area("Education", value=st.session_state.builder_education, height=120, disabled=True)
            st.text_area("Experience Brain Dump", value=st.session_state.builder_experience_dump, height=160, disabled=True)
            st.text_area("Activities / Leadership / Projects", value=st.session_state.builder_activities, height=140, disabled=True)
            st.text_area("Skills", value=st.session_state.builder_skills, height=100, disabled=True)

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-manual"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Validate Builder Output", use_container_width=True, key="builder-validate-output-manual"):
                try:
                    payload = parse_builder_payload(pasted_output)
                    st.session_state.builder_payload = payload
                    st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                    st.session_state.builder_output_docx_bytes = None
                    st.session_state.builder_output_filename = None
                    st.session_state.builder_profile_saved = False
                    st.session_state.builder_profile_saved_source_id = None
                    st.session_state.builder_profile_save_dismissed = False
                    st.session_state.screen = "builder_review"
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
            st.markdown("</div>", unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-manual"):
                st.session_state.screen = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    elif builder_mode == "api":
        if st.session_state.selected_provider not in PROVIDER_CONFIG:
            st.session_state.selected_provider = "OpenAI"

        api_key = ""
        base_url = ""
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">API Setup</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Choose your provider.</div>', unsafe_allow_html=True)

            provider = st.selectbox(
                "Provider",
                list(PROVIDER_CONFIG.keys()),
                index=list(PROVIDER_CONFIG.keys()).index(st.session_state.selected_provider),
                key="builder-provider",
            )
            st.session_state.selected_provider = provider
            provider_config = PROVIDER_CONFIG[provider]
            st.markdown(
                f'<div class="apple-section-copy">{provider_config.get("description", "")}</div>',
                unsafe_allow_html=True,
            )

            if provider == "Local Model / Custom Endpoint":
                base_url = st.text_input(
                    "Base URL",
                    value=st.session_state.custom_api_base_url,
                    placeholder="http://localhost:11434/v1",
                    help="For Ollama, use http://localhost:11434/v1",
                    key="builder-base-url",
                )
                model = st.text_input(
                    "Model name",
                    value=st.session_state.custom_api_model,
                    placeholder="mistral",
                    help="Use the exact local model tag available on your machine.",
                    key="builder-model-local",
                )
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    value=st.session_state.custom_api_key,
                    placeholder=provider_config["placeholder"],
                    help="Most local endpoints do not require a key. Leave blank if not needed.",
                    key="builder-api-key-local",
                )
                st.session_state.custom_api_base_url = base_url
                st.session_state.custom_api_model = model
                st.session_state.custom_api_key = api_key
            else:
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    placeholder=provider_config["placeholder"],
                    key="builder-api-key",
                )
                model = st.selectbox("Model", provider_config["models"], index=0, key="builder-model")
                st.markdown(
                    '<div class="apple-section-copy">Your key is used only for this session and is not stored.</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("Prompt Preview", expanded=False):
                st.text_area(
                    "Builder Prompt Preview",
                    value=st.session_state.builder_prompt,
                    height=240,
                    disabled=True,
                    key="builder-prompt-preview-api",
                )

        api_rows = builder_rows + [
            ("Provider", provider),
            ("Model", model if model else "Missing"),
        ]
        if provider == "Local Model / Custom Endpoint":
            api_rows.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
        else:
            api_rows.append(("API key", "Provided" if api_key.strip() else "Missing"))

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
            st.markdown(build_readiness_rows(api_rows), unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-api"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Run Builder via API", use_container_width=True, key="builder-run-api"):
                try:
                    with st.spinner(f"Sending prompt to {provider}..."):
                        payload = optimize_with_provider(
                            provider=provider,
                            api_key=api_key,
                            prompt=st.session_state.builder_prompt,
                            model=model,
                            base_url=base_url,
                        )
                    st.session_state.builder_payload = payload
                    st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                    st.session_state.builder_output_docx_bytes = None
                    st.session_state.builder_output_filename = None
                    st.session_state.builder_profile_saved = False
                    st.session_state.builder_profile_saved_source_id = None
                    st.session_state.builder_profile_save_dismissed = False
                    st.session_state.screen = "builder_review"
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
            st.markdown("</div>", unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-api"):
                st.session_state.screen = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="apple-minor-copy" style="margin-top:0.35rem;">Choose a run mode above to continue.</div>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-preselect"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-preselect"):
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
    memory_rows = _build_builder_profile_memory_rows(payload, stats)

    render_shell_start()
    render_screen_intro(
        "builder_review",
        "Step 4 of 5",
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

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Save For Future Jobs</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Keep this draft as reusable profile memory.</div>', unsafe_allow_html=True)
        if st.session_state.builder_profile_saved:
            st.markdown(
                '<div class="apple-section-copy">Saved. The strongest basics, experience, projects, and skills from this draft are now part of your reusable career profile, so future applications can start from a much smarter foundation.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                build_readiness_rows(
                    [
                        ("Status", "Saved to profile"),
                        ("Career stage", st.session_state.career_stage or "Not set"),
                        ("Target role", st.session_state.target_role or "Not set"),
                        ("Imported blocks", f"{sum(stats.get(key, 0) for key in ['education_items', 'experience_items', 'project_items', 'skills_items'])}"),
                    ]
                ),
                unsafe_allow_html=True,
            )
            saved_col1, saved_col2 = st.columns(2, gap="large")
            with saved_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Open Career Profile", use_container_width=True, key="builder-open-profile-after-save"):
                    st.session_state.screen = "profile_dashboard"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with saved_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Keep Building Resume", use_container_width=True, key="builder-continue-after-save"):
                    st.session_state.builder_profile_save_dismissed = False
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        elif st.session_state.builder_profile_save_dismissed:
            st.markdown(
                '<div class="apple-section-copy">You can keep moving for now. If this draft feels like a good representation of your background, save it once and the app can reuse the strongest parts for future roles.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(build_readiness_rows(memory_rows), unsafe_allow_html=True)
            reopen_col1, reopen_col2 = st.columns(2, gap="large")
            with reopen_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Save to Profile Now", use_container_width=True, key="builder-save-to-profile-reopen"):
                    try:
                        _save_builder_payload_to_profile(payload)
                        st.success("This draft has been added to your career profile.")
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))
                st.markdown("</div>", unsafe_allow_html=True)
            with reopen_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Keep It One-Off", use_container_width=True, key="builder-keep-one-off"):
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="apple-section-copy">Save this once and future applications can reuse the strongest parts of this draft instead of making you type everything again. This is the easiest way to turn a one-off draft into a long-term career profile.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(build_readiness_rows(memory_rows), unsafe_allow_html=True)
            profile_cta_col1, profile_cta_col2 = st.columns(2, gap="large")
            with profile_cta_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Yes, Save to Profile", use_container_width=True, key="builder-save-to-profile"):
                    try:
                        _save_builder_payload_to_profile(payload)
                        st.success("This draft has been added to your career profile.")
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))
                st.markdown("</div>", unsafe_allow_html=True)
            with profile_cta_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Not Now", use_container_width=True, key="builder-skip-save-profile"):
                    st.session_state.builder_profile_save_dismissed = True
                    st.rerun()
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
        asset_col1, asset_col2 = st.columns(2, gap="large")
        with asset_col1:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            st.download_button(
                "Download First Resume (.docx)",
                data=io.BytesIO(st.session_state.builder_output_docx_bytes),
                file_name=st.session_state.builder_output_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        with asset_col2:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Save to Resume Library", use_container_width=True, key="builder-save-library"):
                _save_current_resume_asset(
                    source_kind="fresh_resume",
                    title=st.session_state.builder_full_name.strip() or "Fresh Resume Draft",
                    file_name=st.session_state.builder_output_filename,
                    file_bytes=st.session_state.builder_output_docx_bytes,
                    notes="Generated from the fresh-resume builder flow.",
                )
                st.success("Saved to your resume library.")
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

    selected_profile_items = _get_selected_profile_items()
    if st.session_state.get("use_career_profile") and selected_profile_items:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Career Profile Guidance</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-title">{len(selected_profile_items)} saved profile items will guide this run.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="apple-section-copy">The prompt will prioritize these items as relevance evidence while still keeping all output anchored to the uploaded resume text.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                build_inline_chip_row([item.title or item.item_type.title() for item in selected_profile_items[:4]]),
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
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
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
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
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
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "api"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    back_col, _, _ = st.columns([1, 2, 2])
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "application_match" if st.session_state.get("use_career_profile") else "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def handle_validated_payload(payload: dict) -> None:
    """Store validation state and move to review."""
    baseline_report = st.session_state.baseline_fit_report or _evaluate_current_resume_fit(force=True)
    optimized_resume_text = _build_optimized_resume_text(payload)
    st.session_state.optimized_fit_report = evaluate_resume_fit(
        optimized_resume_text,
        st.session_state.job_description or "",
        selected_profile_items=_get_selected_profile_items(),
    )
    st.session_state.baseline_fit_report = baseline_report
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
    baseline_report = st.session_state.baseline_fit_report or {}
    optimized_report = st.session_state.optimized_fit_report or {}

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

        if baseline_report and optimized_report:
            _render_fit_delta_card(baseline_report, optimized_report)

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
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                if st.button("Save to Resume Library", use_container_width=True, key="review-save-library"):
                    _save_current_resume_asset(
                        source_kind="optimized_resume",
                        title=st.session_state.output_filename.replace(".docx", ""),
                        file_name=st.session_state.output_filename,
                        file_bytes=st.session_state.output_docx_bytes,
                        notes="Saved from the optimized resume review flow.",
                    )
                    st.success("Saved to your resume library.")
            else:
                if st.button("Review Changes", use_container_width=True):
                    st.session_state.show_review_changes = True
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with action_col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                if st.button("Review Changes", use_container_width=True, key="review-changes-when-ready"):
                    st.session_state.show_review_changes = True
                    st.rerun()
            else:
                if st.button("Start Over", use_container_width=True):
                    reset_flow()
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Start Over", use_container_width=True, key="review-start-over-when-ready"):
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
    init_profile_db()
    init_session_state()
    handle_step_navigation_request()
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
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Application Workspace", use_container_width=True, key="sidebar-application-workspace"):
            st.session_state.screen = "application_workspace"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Resume Library", use_container_width=True, key="sidebar-resume-library"):
            st.session_state.screen = "resume_library"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    screen = st.session_state.screen
    if screen == "landing":
        render_landing()
    elif screen == "quickstart":
        render_quickstart_screen()
    elif screen == "profile_welcome":
        render_profile_welcome_screen()
    elif screen == "profile_import":
        render_profile_import_screen()
    elif screen == "profile_review":
        render_profile_review_screen()
    elif screen == "profile_dashboard":
        render_profile_dashboard_screen()
    elif screen == "application_match":
        render_application_match_screen()
    elif screen == "application_workspace":
        render_application_workspace_screen()
    elif screen == "resume_library":
        render_resume_library_screen()
    elif screen == "input":
        render_input_screen()
    elif screen == "fit_report":
        render_fit_report_screen()
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
