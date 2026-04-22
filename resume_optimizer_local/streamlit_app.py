"""
Streamlit app for Resume OTG.
"""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
import time
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
from local_ai_tasks import (
    draft_resume_improvements,
    draft_first_resume,
    extract_or_create_profile,
    get_last_task_meta,
    process_job_description,
    summarize_job_signals_for_ui,
)
from ollama_local_ai import (
    DEFAULT_LOCAL_AI_LABEL,
    DEFAULT_LOCAL_AI_MODEL,
    OLLAMA_BASE_URL,
    check_ollama_status,
    get_ollama_download_url,
    get_platform_label,
    is_model_installed,
    pull_model_stream,
    run_readiness_check,
)
from profile_extractor import extract_profile_basics, extract_profile_items_from_text
from profile_matcher import extract_key_signals, rank_profile_items
from profile_schema import ProfileItem, utc_now_iso
from profile_store import (
    archive_profile_item,
    create_or_get_profile,
    get_application,
    init_profile_db,
    link_profile_items_to_application,
    list_applications,
    list_profile_items,
    list_profile_sources,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    update_profile_item,
    update_profile_item_verification,
    upsert_application,
    create_or_update_profile_from_optimization,
    save_optimization_result,
    get_optimization_history,
)
from prompt_engine import build_builder_prompt, build_optimizer_prompt
from resume_evaluator import calculate_match_score, evaluate_resume_fit
from improvements_generator import generate_improvements_summary
from review_engine import analyze_payload_against_document
from optimization_history_ui import render_optimization_history_screen
from ui_helpers import primary_button, primary_download_button, primary_form_submit, secondary_button
from help_widget import render_help_section, render_support_button
from profile_screen import render_profile_screen
from onboarding_screen import render_onboarding_screen
from job_tracker_screen import render_job_tracker_screen
from job_tracker_detail import render_job_tracker_detail_screen
from job_tracker_store import init_tracker_tables
from shell import (
    FLOW_STEPS,
    FLOW_STEP_ALIASES,
    _group_review_results,
    build_inline_chip_row,
    build_readiness_rows,
    format_preview_text,
    handle_step_navigation_request,
    render_chip_row,
    render_replacement_preview,
    render_review_section,
    render_screen_intro,
    render_shell_end,
    render_shell_start,
    render_progress_stepper,
)
from session_state import CAREER_STAGES, init_session_state, reset_flow
from auth_state import is_authenticated, load_auth_into_session, sign_out
from auth_screen import render_auth_screen
from hosted_mode import is_hosted_web, show_local_ai_cards, show_private_mode
from settings_screen import render_help_screen, render_settings_screen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cached helpers — avoid re-running expensive calls on every Streamlit rerun
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def _cached_check_ollama_status(base_url: str) -> dict:
    return check_ollama_status(base_url=base_url)


@st.cache_data(ttl=30)
def _cached_run_readiness_check(model_name: str, base_url: str) -> dict:
    return run_readiness_check(model_name=model_name, base_url=base_url)


@st.cache_data(ttl=5)
def _cached_list_profile_items() -> list:
    return list_profile_items()


@st.cache_data(ttl=5)
def _cached_list_applications() -> list:
    return list_applications()


@st.cache_data(ttl=5)
def _cached_list_profile_sources() -> list:
    return list_profile_sources()


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

# Mapping to 5 required user-facing categories
PROFILE_CATEGORY_MAP = {
    "experience": "Work Experience",
    "project": "Work Experience",
    "business": "Work Experience",
    "leadership": "Work Experience",
    "volunteering": "Volunteer Experience",
    "education": "Education",
    "certification": "Certifications & Accomplishments",
    "award": "Certifications & Accomplishments",
    "activity": "Certifications & Accomplishments",
    "skills": "Skills",
}

PROFILE_CATEGORY_ORDER = [
    "Education",
    "Work Experience",
    "Volunteer Experience",
    "Skills",
    "Certifications & Accomplishments",
]



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


def get_category_for_item_type(item_type: str) -> str:
    """Map item type to one of the 5 required categories."""
    return PROFILE_CATEGORY_MAP.get(item_type, "Work Experience")


def group_items_by_category(items: list[ProfileItem]) -> dict[str, list[ProfileItem]]:
    """Group profile items by the 5 required categories."""
    grouped: dict[str, list[ProfileItem]] = {cat: [] for cat in PROFILE_CATEGORY_ORDER}
    for item in items:
        category = get_category_for_item_type(item.item_type)
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(item)
    return grouped


def detect_duplicate_items(items: list[ProfileItem]) -> dict[str, list[ProfileItem]]:
    """
    Detect likely duplicate items (same org/position but possibly different dates).
    Returns dict mapping from canonical key to list of duplicates (includes original).
    Users can have multiple roles at same company - differentiate by title.
    """
    duplicates: dict[str, list[ProfileItem]] = {}
    seen_keys: dict[str, str] = {}  # Maps key to canonical key

    for item in items:
        if not item.organization or not item.title:
            continue

        # Create key: org + title (case-insensitive, normalized)
        org_norm = re.sub(r"[^a-z0-9]+", " ", item.organization.lower()).strip()
        title_norm = re.sub(r"[^a-z0-9]+", " ", item.title.lower()).strip()
        key = f"{org_norm}|{title_norm}"

        if key not in seen_keys:
            seen_keys[key] = key
            duplicates[key] = [item]
        else:
            canonical = seen_keys[key]
            duplicates[canonical].append(item)

    # Return only groups with actual duplicates
    return {k: v for k, v in duplicates.items() if len(v) > 1}


def save_profile_edit_to_history(items: list[ProfileItem]) -> None:
    """Save current state to undo/redo history."""
    items_dict = [item.to_dict() for item in items]
    # Clear redo history if we're making a new edit
    st.session_state.profile_items_edit_history = (
        st.session_state.profile_items_edit_history[:st.session_state.profile_items_edit_history_index + 1]
    )
    st.session_state.profile_items_edit_history.append(items_dict)
    st.session_state.profile_items_edit_history_index = len(st.session_state.profile_items_edit_history) - 1


def undo_profile_edit() -> bool:
    """Undo to previous state. Returns True if successful."""
    if st.session_state.profile_items_edit_history_index > 0:
        st.session_state.profile_items_edit_history_index -= 1
        items_dict = st.session_state.profile_items_edit_history[st.session_state.profile_items_edit_history_index]
        st.session_state.profile_extracted_items = items_dict
        return True
    return False


def redo_profile_edit() -> bool:
    """Redo to next state. Returns True if successful."""
    if st.session_state.profile_items_edit_history_index < len(st.session_state.profile_items_edit_history) - 1:
        st.session_state.profile_items_edit_history_index += 1
        items_dict = st.session_state.profile_items_edit_history[st.session_state.profile_items_edit_history_index]
        st.session_state.profile_extracted_items = items_dict
        return True
    return False


def is_likely_garbage_entry(item: ProfileItem) -> bool:
    """Detect obviously invalid extracted entries."""
    garbage_patterns = [
        r'^\s*page\s+\d+\s+of\s+\d+\s*$',
        r'^\s*page\s+\d+\s*$',
        r'^---+$',
        r'^\s*\.\.\.\s*$',
        r'^\|+$',
        r'^[a-z0-9]{40,}$',  # Corrupted/hashed text
    ]

    title_to_check = (item.title or "").lower().strip()
    org_to_check = (item.organization or "").lower().strip()

    # Pattern matching against title
    for pattern in garbage_patterns:
        if re.match(pattern, title_to_check):
            return True
        if re.match(pattern, org_to_check):
            return True

    # Very short titles (< 3 chars) are usually garbage
    if len(title_to_check) < 3:
        return True

    # Title too long (> 120 chars) is suspicious
    if len(title_to_check) > 120:
        return True

    # Low confidence is a red flag, but don't filter immediately
    # Let user decide via UI

    return False


def filter_and_sort_items_for_review(items: list[ProfileItem]) -> tuple[list[ProfileItem], list[ProfileItem]]:
    """Separate valid items from garbage and sort by priority."""
    valid = []
    garbage = []

    for item in items:
        if is_likely_garbage_entry(item):
            garbage.append(item)
        else:
            valid.append(item)

    # Sort valid items by priority
    sorted_valid = sorted(
        valid,
        key=lambda item: (
            PROFILE_ITEM_PRIORITY.get(item.item_type, 99),
            -float(item.confidence_score or 0),
            (item.title or "").lower(),
            (item.organization or "").lower(),
        ),
    )

    return sorted_valid, garbage


def sort_profile_items_for_review(items: list[ProfileItem]) -> list[ProfileItem]:
    """Prioritize high-signal evidence items first in the import review flow."""
    valid_items, _ = filter_and_sort_items_for_review(items)
    return valid_items


def summarize_fit_recommendation(report: dict) -> tuple[int, str, str, str, str]:
    """Map a fit score to a plain-English recommendation and action."""
    score = int(report.get("overall_score", 0))
    if score >= 75:
        return (
            score,
            "Strong Match",
            "You should apply. Your resume already lines up with most of the role's core signals.",
            "Apply Now",
            "This is a strong match.",
        )
    if score >= 60:
        return (
            score,
            "Promising Match",
            "You should apply after one quick enhancement. The role is within reach, but a few missing signals are still worth tightening.",
            "Review Enhancement",
            "One improvement would boost your chances.",
        )
    return (
        score,
        "Stretch Match",
        "This role looks like a stretch right now. Review the biggest gaps before you spend more time here.",
        "Skip This Role",
        "Major gaps are still visible.",
    )


def build_change_examples(review_results: list[dict], limit: int = 3) -> list[dict[str, str]]:
    """Extract concise before/after examples from replacement review data."""
    examples: list[dict[str, str]] = []
    for result in review_results:
        before_text = (result.get("anchor") or "").strip()
        after_text = (result.get("replacement_text") or "").strip()
        label = result.get("category_label") or result.get("section_label") or "Resume update"
        if before_text and after_text:
            examples.append(
                {
                    "label": label,
                    "before": format_preview_text(before_text, max_len=88),
                    "after": format_preview_text(after_text, max_len=88),
                }
            )
        if len(examples) >= limit:
            break
    return examples


def build_optimization_metrics_summary(before_report: dict, after_report: dict) -> list[dict[str, str | int]]:
    """Create user-facing metric summaries for the success state."""
    before_keyword = int(before_report.get("keyword_score", 0))
    after_keyword = int(after_report.get("keyword_score", 0))
    before_ats = int(before_report.get("ats_score", 0))
    after_ats = int(after_report.get("ats_score", 0))
    before_overall = int(before_report.get("overall_score", 0))
    after_overall = int(after_report.get("overall_score", 0))
    before_action = int(before_report.get("action_verb_bullet_count", 0))
    after_action = int(after_report.get("action_verb_bullet_count", 0))

    return [
        {
            "label": "Keyword Alignment",
            "before": before_keyword,
            "after": after_keyword,
            "delta": after_keyword - before_keyword,
            "suffix": "pts",
        },
        {
            "label": "ATS / Clarity",
            "before": before_ats,
            "after": after_ats,
            "delta": after_ats - before_ats,
            "suffix": "pts",
        },
        {
            "label": "Action-Led Bullets",
            "before": before_action,
            "after": after_action,
            "delta": after_action - before_action,
            "suffix": "bullets",
        },
        {
            "label": "Overall Fit",
            "before": before_overall,
            "after": after_overall,
            "delta": after_overall - before_overall,
            "suffix": "pts",
        },
    ]


def apply_apple_theme() -> None:
    """Inject a restrained, editorial Apple-inspired visual system."""
    # Load Inter — top SaaS/professional recommendation from ui-ux-pro-max
    st.markdown(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        /* ── Motion ── */
        @keyframes _fade-up {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        /* Respect user preference */
        /* Suppress all motion for users who prefer it */
        @media (prefers-reduced-motion: reduce) {
          *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
          .apple-landing-card:hover,
          [data-testid="stVerticalBlockBorderWrapper"]:has(button):hover {
            transform: none !important;
          }
        }

        @media (prefers-reduced-motion: no-preference) {
          .apple-hero {
            animation: _fade-up 360ms cubic-bezier(0.16, 1, 0.3, 1) both;
          }

          /* Stagger landing cards */
          .apple-landing-card:nth-child(1) {
            animation: _fade-up 280ms 40ms  cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          .apple-landing-card:nth-child(2) {
            animation: _fade-up 280ms 100ms cubic-bezier(0.16, 1, 0.3, 1) both;
          }
          .apple-landing-card:nth-child(3) {
            animation: _fade-up 280ms 160ms cubic-bezier(0.16, 1, 0.3, 1) both;
          }

          /* Streamlit border-wrapper cards on other screens */
          [data-testid="stVerticalBlockBorderWrapper"] {
            animation: _fade-up 260ms 60ms cubic-bezier(0.16, 1, 0.3, 1) both;
          }
        }

        :root {
          --bg: #f5f5f7;
          --surface: #ffffff;
          --surface-muted: #fbfbfd;
          --panel-fill: #f7f7f9;
          --text: #1d1d1f;
          --muted: #6e6e73;
          --muted-light: #5a5a5f;
          --line: rgba(0,0,0,0.05);
          --line-strong: rgba(0,0,0,0.08);
          --shadow-soft: 0 6px 18px rgba(0,0,0,0.04);
          --shadow-raised: 0 8px 20px rgba(0,0,0,0.06);
          --blue: #0071e3;
          --green: #1f8f4e;
          --amber: #b7791f;
          --danger: #c9342f;
          --font-main: "Inter", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
          /* Semantic tokens */
          --sidebar-bg: #f5f5f7;
          --input-fill: #ffffff;
          --input-fill-focus: #ffffff;
          --step-active-bg: #eaeaef;
          --alert-bg: #f0faf4;
          --btn-primary-bg: #d97757;
          --btn-primary-text: #ffffff;
          --header-bg: rgba(245,245,247,0.94);
          --card-border: rgba(0,0,0,0.06);
          --focus-blue: rgba(0,113,227,0.5);
          --focus-blue-halo: rgba(0,113,227,0.18);
          --disabled-bg: #ececf1;
          --disabled-text: #8b8b93;
          --disabled-border: #e1e1e6;
        }

        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #0e0f12;
            --surface: #16181b;
            --surface-muted: #1d2024;
            --panel-fill: #181b1f;
            --text: #f5f5f7;
            --muted: #b0b3ba;
            --muted-light: #d0d4db;
            --line: rgba(255,255,255,0.08);
            --line-strong: rgba(255,255,255,0.16);
            --shadow-soft: 0 10px 30px rgba(0,0,0,0.28);
            --shadow-raised: 0 14px 36px rgba(0,0,0,0.36);
            --blue: #4ea1ff;
            --green: #4ac26b;
            --amber: #e3a54b;
            --danger: #ff7b72;
            --sidebar-bg: #121417;
            --input-fill: #101215;
            --input-fill-focus: #181c20;
            --step-active-bg: #20242a;
            --alert-bg: #112017;
            --btn-primary-bg: #d97757;
            --btn-primary-text: #ffffff;
            --header-bg: rgba(14,15,18,0.94);
            --card-border: rgba(255,255,255,0.10);
            --focus-blue: rgba(78,161,255,0.55);
            --focus-blue-halo: rgba(78,161,255,0.20);
            --disabled-bg: #24272c;
            --disabled-text: #8a8f98;
            --disabled-border: rgba(255,255,255,0.10);
          }
        }

        .stApp {
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-main);
          color-scheme: light dark;
        }

        [data-testid="stSidebar"] {
          background: var(--sidebar-bg);
          border-right: 1px solid var(--line);
        }

        [data-testid="stHeader"] {
          background: var(--header-bg);
          border-bottom: 1px solid var(--line);
        }

        h1, h2, h3, h4, h5, h6, p, label, li, a, button, input, textarea, select {
          color: var(--text);
          font-family: var(--font-main);
        }

        .block-container {
          max-width: 1200px !important;
          padding-top: clamp(1.5rem, 4vw, 4rem) !important;
          padding-bottom: clamp(1.5rem, 4vw, 4rem) !important;
          padding-left: clamp(1rem, 3vw, 3rem) !important;
          padding-right: clamp(1rem, 3vw, 3rem) !important;
        }

        .apple-hero {
          padding: clamp(0.5rem, 1.5vw, 1rem) 0 clamp(2rem, 4vw, 4rem) 0;
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
          background: var(--surface);
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
          background: var(--step-active-bg);
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
          min-height: 44px;
          text-decoration: none !important;
          white-space: nowrap;
          cursor: pointer;
        }

        .apple-step:hover {
          background: var(--surface-muted);
        }

        .apple-step.active {
          background: var(--surface);
          color: var(--text);
          border-color: var(--line);
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
          border-color: var(--line-strong);
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
          font-weight: 700;
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

        /* ── Interactive container cursors & hover ── */
        [data-testid="stVerticalBlockBorderWrapper"],
        .apple-choice,
        .apple-card,
        .apple-panel {
          cursor: default;
          transition: box-shadow 200ms ease, border-color 200ms ease, transform 200ms ease;
        }

        /* Cards that act as clickable affordances get pointer + lift */
        .apple-landing-card,
        [data-testid="stVerticalBlockBorderWrapper"]:has(button) {
          cursor: pointer;
        }

        [data-testid="stVerticalBlockBorderWrapper"]:has(button):hover {
          box-shadow: var(--shadow-soft) !important;
          border-color: var(--line-strong) !important;
          transform: translateY(-1px);
        }

        /* ── Focus rings on non-button interactive elements ── */
        [data-testid="stSelectbox"] > div:focus-within,
        [data-testid="stMultiSelect"] > div:focus-within,
        [data-testid="stTextInput"] > div:focus-within,
        [data-testid="stTextArea"] > div:focus-within {
          outline: 2px solid #d97757 !important;
          outline-offset: 2px !important;
          border-radius: 8px;
        }

        .apple-landing-card {
          min-height: 380px;
          padding: 2.75rem;
          border-radius: 30px;
          background: var(--surface);
          border: 1px solid var(--line);
          box-shadow: none;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          transition: box-shadow 200ms ease, transform 200ms ease;
        }

        .apple-landing-card:hover {
          box-shadow: var(--shadow-raised);
          transform: translateY(-2px);
        }

        .apple-landing-card.featured {
          background: var(--text) !important;
          border-color: transparent !important;
          box-shadow: var(--shadow-raised) !important;
        }

        .apple-landing-card.featured .apple-kicker {
          color: var(--bg) !important;
          opacity: 0.7 !important;
        }

        .apple-landing-card.featured .apple-landing-card-title,
        .apple-landing-card.featured .apple-landing-card-copy {
          color: var(--bg) !important;
        }

        /* Button inside the featured card gets an inverted (light) style */
        .apple-landing-card.featured .stButton button {
          background: rgba(255,255,255,0.12) !important;
          color: #ffffff !important;
          border-color: rgba(255,255,255,0.22) !important;
        }

        .apple-landing-card.featured .stButton button:hover {
          background: rgba(255,255,255,0.2) !important;
          opacity: 1 !important;
        }

        .apple-landing-card.featured .stButton button * {
          color: #ffffff !important;
        }

        .apple-landing-card-title {
          font-size: 2rem;
          line-height: 1.08;
          letter-spacing: -0.022em;
          font-weight: 700;
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
          margin-top: 1rem;
        }

        .apple-landing-actions .stButton button {
          min-height: 56px;
        }

        .apple-landing-status {
          margin-top: 1rem;
          padding: 0.9rem 1rem;
          border-radius: 16px;
          background: var(--bg);
          border: 1px solid var(--line);
        }

        .apple-landing-status-kicker {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 0.35rem;
        }

        .apple-landing-status-copy {
          font-size: 0.92rem;
          line-height: 1.45;
          color: var(--text);
        }

        .apple-running-card {
          margin-top: 1rem;
          padding: 1rem 1.1rem;
          border-radius: 18px;
          background: var(--bg);
          border: 1px solid var(--line);
        }

        .apple-running-title {
          font-size: 0.92rem;
          font-weight: 700;
          color: var(--text);
          margin-bottom: 0.35rem;
        }

        .apple-running-copy {
          font-size: 0.92rem;
          line-height: 1.55;
          color: var(--muted);
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
          background: var(--surface);
          font-size: 0.82rem;
          color: var(--muted);
          line-height: 1;
        }

        .instruction-panel {
          margin: 0.65rem 0 1rem 0;
          padding: 1.45rem 1.5rem;
          border-radius: 20px;
          border: 1px solid var(--line);
          background: var(--bg);
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
          background: var(--surface);
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

        .builder-preview-block {
          background: var(--bg);
          border-radius: 14px;
          padding: 1rem 1.25rem;
          margin: 0.75rem 0;
        }
        .builder-preview-label {
          font-size: 0.7rem;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 0.4rem;
        }
        .builder-preview-body {
          font-size: 0.9rem;
          line-height: 1.6;
          color: var(--text);
        }

        .apple-readiness-card {
          background: var(--bg);
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
          border-bottom: 1px solid var(--line);
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
          background-color: var(--surface) !important;
          border: 1px solid var(--card-border) !important;
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
          background: var(--input-fill) !important;
          border: 1px solid transparent !important;
          color: var(--text) !important;
          box-shadow: none !important;
          transition: background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
        }

        .stTextArea textarea:focus,
        .stTextInput input:focus {
          background: var(--input-fill-focus) !important;
          border-color: var(--focus-blue) !important;
          box-shadow: 0 0 0 3px var(--focus-blue-halo) !important;
          outline: none !important;
        }

        .stSelectbox > div > div,
        .stMultiSelect > div > div {
          background: var(--input-fill) !important;
          border: 1px solid transparent !important;
        }

        .stButton button, .stDownloadButton button {
          border-radius: 999px !important;
          min-height: 54px;
          font-weight: 600;
          font-size: 1rem !important;
          line-height: 1.2 !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
          border: 1px solid transparent !important;
          box-shadow: none !important;
          transition: opacity 180ms ease, background-color 180ms ease, border-color 180ms ease;
        }

        .stLinkButton > a {
          border-radius: 999px !important;
          min-height: 54px !important;
          font-weight: 600 !important;
          font-size: 1rem !important;
          line-height: 1.2 !important;
          white-space: nowrap !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
          border: 1px solid var(--line-strong) !important;
          box-shadow: none !important;
          transition: opacity 180ms ease, background-color 180ms ease, border-color 180ms ease;
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          text-decoration: none !important;
          background: var(--surface) !important;
          color: var(--text) !important;
        }

        .stLinkButton > a:hover {
          opacity: 0.82;
        }

        .stLinkButton > a *,
        .stLinkButton > a p,
        .stLinkButton > a span,
        .stLinkButton > a div {
          color: var(--text) !important;
          fill: var(--text) !important;
          opacity: 1 !important;
        }

        .stButton button:hover, .stDownloadButton button:hover {
          opacity: 0.82;
        }

        .stApp button[kind="primary"],
        .stApp [data-testid="stBaseButton-primary"] button {
          background: var(--btn-primary-bg) !important;
          color: var(--btn-primary-text) !important;
          border-color: var(--btn-primary-bg) !important;
        }

        .stApp button[kind="primary"] *,
        .stApp [data-testid="stBaseButton-primary"] button * {
          color: var(--btn-primary-text) !important;
          fill: var(--btn-primary-text) !important;
          opacity: 1 !important;
        }

        .stButton button:focus-visible,
        .stDownloadButton button:focus-visible {
          outline: 2px solid #d97757 !important;
          outline-offset: 2px !important;
          box-shadow: 0 0 0 4px rgba(217,119,87,0.22) !important;
        }

        .stApp .apple-primary button,
        .stApp .apple-primary [data-testid="stDownloadButton"] button,
        .apple-primary button,
        .apple-primary [data-testid="stDownloadButton"] button {
          background: #d97757 !important;
          color: #ffffff !important;
          border-color: #d97757 !important;
        }

        .stApp .apple-primary button *,
        .stApp .apple-primary button p,
        .stApp .apple-primary button span,
        .stApp .apple-primary button div,
        .stApp .apple-primary [data-testid="stDownloadButton"] button *,
        .apple-primary button *,
        .apple-primary button p,
        .apple-primary button span,
        .apple-primary button div,
        .apple-primary [data-testid="stDownloadButton"] button * {
          color: #ffffff !important;
          fill: #ffffff !important;
          opacity: 1 !important;
        }

        .apple-primary button:disabled,
        .apple-primary button[disabled] {
          background: var(--disabled-bg) !important;
          color: var(--disabled-text) !important;
          border-color: var(--disabled-border) !important;
          opacity: 1 !important;
        }

        .apple-primary button:disabled *,
        .apple-primary button[disabled] *,
        .apple-primary button:disabled p,
        .apple-primary button[disabled] p,
        .apple-primary button:disabled span,
        .apple-primary button[disabled] span,
        .apple-primary button:disabled div,
        .apple-primary button[disabled] div {
          color: var(--disabled-text) !important;
          fill: var(--disabled-text) !important;
          opacity: 1 !important;
        }

        .stApp .apple-secondary button,
        .apple-secondary button {
          background: #d97757 !important;
          color: #ffffff !important;
          box-shadow: none !important;
          border-color: #d97757 !important;
        }

        .stApp .apple-secondary button *,
        .stApp .apple-secondary button p,
        .stApp .apple-secondary button span,
        .stApp .apple-secondary button div,
        .apple-secondary button *,
        .apple-secondary button p,
        .apple-secondary button span,
        .apple-secondary button div {
          color: #ffffff !important;
          fill: #ffffff !important;
          opacity: 1 !important;
        }

        .apple-secondary button:disabled,
        .apple-secondary button[disabled] {
          background: transparent !important;
          color: var(--muted) !important;
          border-color: var(--line) !important;
          opacity: 1 !important;
        }

        .apple-secondary button:disabled *,
        .apple-secondary button[disabled] *,
        .apple-secondary button:disabled p,
        .apple-secondary button[disabled] p,
        .apple-secondary button:disabled span,
        .apple-secondary button[disabled] span,
        .apple-secondary button:disabled div,
        .apple-secondary button[disabled] div {
          color: var(--muted) !important;
          fill: var(--muted) !important;
          opacity: 1 !important;
        }

        div[data-testid="stAlert"] {
          border-radius: 20px;
          border: 1px solid var(--line);
          box-shadow: none;
          background: var(--alert-bg);
        }

        div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
          color: var(--text) !important;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stCaptionContainer"],
        .stCaption,
        label,
        .st-emotion-cache-10trblm,
        .st-emotion-cache-16idsys {
          color: var(--text);
        }

        div[data-baseweb="notification"] {
          border-radius: 20px !important;
          border: 1px solid var(--line) !important;
          box-shadow: none !important;
        }

        /* Featured card: highlight the first column on the landing page */
        [data-testid="column"]:first-child [data-testid="stVerticalBlockBorderWrapper"] {
          border-color: var(--line-strong) !important;
          box-shadow: var(--shadow-soft) !important;
        }

        /* Score/delta cards: use design-system border radius consistently */
        .apple-delta-bar {
          margin-top: 1.5rem;
          padding: 1rem;
          background: var(--surface-muted);
          border-radius: 20px;
          border-left: 3px solid var(--green);
          text-align: center;
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

        /* ── Global font enforcement ── */
        .stApp,
        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        .element-container,
        .stMarkdown,
        .stCaption {
          font-family: var(--font-main) !important;
        }
        /* Restore Streamlit icon fonts — the global * override breaks Material Icons and
           surfaces raw ligature names like `keyboard_arrow_right` as visible text.
           Use .stApp-prefixed selectors so specificity beats .stApp * (0,0,1,0). */
        .stApp [data-testid="stExpanderToggleIcon"],
        .stApp [data-testid="stExpanderToggleIcon"] span,
        .stApp [data-testid="stExpanderToggleIcon"] *,
        .stApp [data-testid="stSidebarCollapseButton"],
        .stApp [data-testid="stSidebarCollapseButton"] *,
        .stApp [data-testid="collapsedControl"],
        .stApp [data-testid="collapsedControl"] *,
        .stApp button[aria-label="Collapse sidebar"],
        .stApp button[aria-label="Collapse sidebar"] *,
        .stApp button[aria-label="Expand sidebar"],
        .stApp button[aria-label="Expand sidebar"] *,
        .stApp .material-icons,
        .stApp .material-symbols-outlined,
        .stApp .material-symbols-rounded,
        .stApp .material-symbols-sharp,
        .stApp [class*="MaterialIcons"],
        .stApp span[class*="-icon"],
        .stApp span[class*="Icon"] {
          font-family: "Material Symbols Rounded", "Material Symbols Outlined",
                       "Material Icons" !important;
          font-size: 1.25rem !important;
          font-feature-settings: "liga" !important;
          -webkit-font-feature-settings: "liga" !important;
          speak: none !important;
          text-rendering: optimizeLegibility !important;
        }
        /* Exclude the expander label text itself from the icon font */
        details summary [data-testid="stExpanderTitle"],
        details summary [data-testid="stExpanderHeader"] > div:last-child {
          font-family: var(--font-main) !important;
          font-size: inherit !important;
          font-feature-settings: normal !important;
          -webkit-font-feature-settings: normal !important;
        }

        /* Hide Streamlit's floating sidebar collapse control in-app.
           It clashes with the custom shell and can render broken icon text. */
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[aria-label="Collapse sidebar"],
        button[aria-label="Expand sidebar"] {
          display: none !important;
        }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
          gap: 0;
          border-bottom: 1px solid var(--line) !important;
          background: transparent !important;
        }
        .stTabs [data-baseweb="tab"] {
          background: transparent !important;
          border: none !important;
          border-bottom: 2px solid transparent !important;
          padding: 0.55rem 1.1rem !important;
          font-size: 0.875rem !important;
          font-weight: 500 !important;
          color: var(--muted) !important;
          border-radius: 0 !important;
          font-family: var(--font-main) !important;
        }
        .stTabs [aria-selected="true"] {
          color: var(--text) !important;
          border-bottom-color: var(--text) !important;
          font-weight: 600 !important;
        }
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] { display: none !important; }

        /* ── Form labels — consistent sizing ── */
        .stTextInput label, .stTextArea label,
        .stSelectbox label, .stMultiSelect label,
        .stCheckbox label span, .stRadio label span,
        .stNumberInput label, [data-testid="stWidgetLabel"] {
          font-size: 0.875rem !important;
          font-weight: 600 !important;
          color: var(--text) !important;
          font-family: var(--font-main) !important;
        }

        /* ── Selectbox / multiselect dropdown text ── */
        .stSelectbox [data-baseweb="select"] div,
        .stMultiSelect [data-baseweb="select"] div,
        [data-baseweb="popover"] li,
        [data-baseweb="menu"] li {
          font-family: var(--font-main) !important;
          font-size: 0.875rem !important;
        }

        /* ── Caption / help ── */
        .stCaption, [data-testid="stCaptionContainer"] p {
          font-size: 0.8rem !important;
          color: var(--muted) !important;
          font-family: var(--font-main) !important;
        }

        /* ── Expander label ── */
        [data-testid="stExpander"] summary {
          font-size: 0.875rem !important;
          font-weight: 500 !important;
          font-family: var(--font-main) !important;
        }

        /* ── Sidebar layout ── */
        [data-testid="stSidebar"] > div:first-child {
          padding: 1rem 0.75rem !important;
        }
        [data-testid="stSidebar"] .stButton {
          margin-bottom: 1px !important;
        }
        /* Sidebar nav buttons — compact, left-aligned, Claude-style */
        [data-testid="stSidebar"] .stButton button {
          min-height: 36px !important;
          height: 36px !important;
          font-size: 0.875rem !important;
          font-weight: 500 !important;
          border-radius: 8px !important;
          padding: 0 0.75rem !important;
          background: transparent !important;
          border: none !important;
          color: var(--text) !important;
          text-align: left !important;
          justify-content: flex-start !important;
          box-shadow: none !important;
          line-height: 36px !important;
        }
        /* ✨ Force sidebar buttons to respect day/night mode text colors ✨ */
        .stApp [data-testid="stSidebar"] .apple-secondary button,
        .stApp [data-testid="stSidebar"] .apple-secondary button *,
        .stApp [data-testid="stSidebar"] .apple-secondary button p,
        .stApp [data-testid="stSidebar"] .apple-secondary button div,
        .stApp [data-testid="stSidebar"] .apple-primary button,
        .stApp [data-testid="stSidebar"] .apple-primary button *,
        .stApp [data-testid="stSidebar"] .apple-primary button p,
        .stApp [data-testid="stSidebar"] .apple-primary button div {
          background: transparent !important;
          border-color: transparent !important;
          color: var(--text) !important;
          fill: var(--text) !important;
          box-shadow: none !important;
          opacity: 1 !important;
        }
        [data-testid="stSidebar"] .stButton button:hover {
          background: var(--line) !important;
        }

        [data-testid="stSidebar"] .stLinkButton > a {
          min-height: 36px !important;
          height: 36px !important;
          font-size: 0.875rem !important;
          font-weight: 500 !important;
          border-radius: 8px !important;
          padding: 0 0.75rem !important;
          line-height: 36px !important;
        }

        /* ── Progress bar — coral fill, smooth animation ── */
        [data-testid="stProgressBar"] {
          height: 6px !important;
          border-radius: 999px !important;
          background: rgba(217,119,87,0.15) !important;
        }
        [data-testid="stProgressBar"] > div {
          border-radius: 999px !important;
          background: #d97757 !important;
          transition: width 0.35s cubic-bezier(0.4,0,0.2,1) !important;
        }
        [data-testid="stProgressBar"] > div > div {
          border-radius: 999px !important;
          background: #d97757 !important;
        }

        /* ULTIMATE SIDEBAR OVERRIDE: ID-level specificity beats all other rules */
        #root [data-testid="stSidebar"] button,
        #root [data-testid="stSidebar"] button *,
        #root [data-testid="stSidebar"] button p,
        #root [data-testid="stSidebar"] button span,
        #root [data-testid="stSidebar"] button div {
          color: var(--text) !important;
          fill: var(--text) !important;
          background-color: transparent !important;
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
        }

        #root [data-testid="stSidebar"] button:hover {
          background-color: var(--line) !important;
          background: var(--line) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )




def render_coral_download_button(
    label: str,
    data: bytes,
    file_name: str,
    mime: str = "application/octet-stream",
) -> None:
    """Render a full-width coral-styled download button.

    Uses CSS injection on st.download_button — avoids the base64-in-markdown
    approach which breaks when Streamlit's markdown processor chokes on the
    very long data URL string.
    """
    st.markdown(
        """
        <style>
        [data-testid="stDownloadButton"] > button {
            background: linear-gradient(135deg, #d97757 0%, #c9683f 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 9999px !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            padding: 0 1.5rem !important;
            width: 100% !important;
            cursor: pointer !important;
            box-shadow: 0 2px 12px rgba(217,119,87,0.35) !important;
            transition: all 0.18s ease !important;
            letter-spacing: 0.01em !important;
            min-height: 54px !important;
            height: 54px !important;
            line-height: 1.2 !important;
        }
        [data-testid="stDownloadButton"] > button:hover {
            background: linear-gradient(135deg, #c9683f 0%, #b85934 100%) !important;
            box-shadow: 0 4px 18px rgba(217,119,87,0.45) !important;
            transform: translateY(-1px) !important;
        }
        [data-testid="stDownloadButton"] > button * {
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=mime,
        use_container_width=True,
    )


_TITLE_SENTENCE_WORDS: frozenset[str] = frozenset({
    "is", "are", "was", "were", "be", "been", "being",
    "seeking", "looking", "hiring", "searching", "recruiting",
    "for", "the", "a", "an", "will", "has", "have", "had",
    "and", "or", "to", "with", "in", "of", "at", "on",
    "our", "we", "you", "your", "they", "their", "us",
    "this", "that", "which", "who", "where", "when",
})


def _is_clean_role_title(text: str) -> bool:
    """Return True if text looks like a role title, not a sentence fragment."""
    words = text.split()
    if len(words) > 8:
        return False
    sentence_word_count = sum(1 for w in words if w.lower() in _TITLE_SENTENCE_WORDS)
    return sentence_word_count == 0


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
            "Director",
            "Officer",
            "Lead",
            "Architect",
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
        # Explicit label — most reliable
        r"(?im)^\s*(?:job title|title|role|position)\s*[:\-]\s*(.+)$",
        # Standalone line that ends with a role suffix — likely a title heading
        rf"(?im)^\s*([A-Z][A-Za-z/&,\-\s]{{2,80}}(?:{role_suffixes}))\s*$",
        # "the X plays/is/will..." — capture just the title part
        rf"(?i)\bthe\s+([A-Z][A-Za-z/&,\-\s]{{1,60}}(?:{role_suffixes}))\s+(?:plays|is|will|works|supports|leads)\b",
        # "seeking/hiring/looking for a [Title]" — captures just the title after the filler
        rf"(?i)\b(?:seeking|hiring|recruiting|looking\s+for)\s+(?:a|an|the)?\s*([A-Z][A-Za-z/&,\-\s]{{1,60}}(?:{role_suffixes}))\b",
        # Seniority-prefixed titles (strict — requires explicit seniority word to avoid greedy sentence match)
        rf"\b((?:Senior|Lead|Principal|Staff|Junior|Associate|Assistant|VP of|Head of|Director of|Chief)\s+[A-Z][A-Za-z/&,\-\s]{{1,60}}(?:{role_suffixes}))\b",
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
                cleaned_match = re.sub(r"^(?:the|a|an)\s+", "", cleaned_match, flags=re.IGNORECASE).strip()
                cleaned_match = re.sub(r"\s+-\s+remote$", "", cleaned_match, flags=re.IGNORECASE).strip()
                lowered = cleaned_match.lower()
                if any(marker in lowered for marker in ignore_markers):
                    continue
                if len(cleaned_match) > 90:
                    continue
                if not _is_clean_role_title(cleaned_match):
                    continue
                return cleaned_match

    for line in job_description.splitlines()[:12]:
        cleaned = " ".join(line.split())
        if not cleaned or len(cleaned) > 90:
            continue
        lowered = cleaned.lower()
        if any(marker in lowered for marker in ignore_markers):
            continue
        if not _is_clean_role_title(cleaned):
            continue
        if any(keyword.lower() in cleaned.lower() for keyword in ROLE_KEYWORDS):
            return cleaned

    return ""


def detect_company_name(job_description: str) -> str:
    """Infer the company name from the pasted job description."""
    if not job_description.strip():
        return ""

    top_section = job_description[:800]
    _non_company_first_words = frozenset({
        "the", "our", "we", "this", "your", "a", "an", "that", "it",
        "they", "their", "us", "you", "as", "are", "is", "for", "in",
        "at", "on", "about", "with", "and", "or", "to", "of", "from",
        "if", "when", "what", "who", "how", "why", "all", "any",
    })

    # Company name: 1–5 capitalized words (allows & / , between them, no lowercase connectors)
    _CN = r"(?:[A-Z][A-Za-z0-9&'.,\-]*(?:[ &]+[A-Z][A-Za-z0-9&'.,\-]*){0,4})"

    def _clean_company(raw: str) -> str:
        return " ".join(raw.split()).strip(" -.,:")

    def _valid_company(name: str) -> bool:
        if not name or len(name) < 2 or len(name) > 60:
            return False
        first = name.split()[0].lower()
        if first in _non_company_first_words:
            return False
        words = name.split()
        sentence_hits = sum(1 for w in words if w.lower() in _TITLE_SENTENCE_WORDS)
        return sentence_hits == 0

    patterns = [
        # Explicit label: "Company: Acme Corp" (case-insensitive for the label only)
        rf"(?m)^\s*(?:[Cc]ompany|[Ee]mployer|[Oo]rganiz[as]tion)\s*[:\-]\s*({_CN})",
        # Section header on its own line: "About Stripe"
        rf"(?m)^\s*[Aa]bout\s+({_CN})\s*$",
        # "Join Acme Corp" — no (?i) so [A-Z] stays strict
        rf"\b[Jj]oin\s+({_CN})\b",
        # "[Company] is seeking/hiring/looking for" — no (?i)
        rf"\b({_CN})\s+(?:[Ii]s\s+)?(?:seeking|hiring|recruiting|[Ll]ooking\s+for|[Ss]earching\s+for)\b",
        # "[Company] is a/an [adjective]..."
        rf"\b({_CN})\s+[Ii]s\s+(?:a|an)\s+[a-z]",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, top_section)
        for raw in matches:
            cleaned = _clean_company(raw)
            if _valid_company(cleaned):
                return cleaned

    return ""


def detect_industry(job_description: str) -> str:
    """Infer an industry bucket from the pasted job description."""
    text = job_description.lower()
    if not text:
        return ""

    keyword_map = {
        "Supply Chain / Operations": [
            "supply chain", "logistics", "transportation", "warehouse",
            "inventory", "distribution", "carrier", "routing", "fulfillment",
            "delivery network", "procurement", "sourcing", "3pl", "s&op",
            "demand planning",
        ],
        "Software Engineering": [
            "software engineer", "backend", "frontend", "full stack",
            "api", "microservices", "devops", "ci/cd", "kubernetes", "docker",
            "software development", "system design", "architecture",
        ],
        "Data & Analytics": [
            "data science", "machine learning", "ml", "deep learning", "nlp",
            "data engineer", "data analyst", "analytics engineer",
            "bi", "tableau", "power bi", "looker", "databricks",
        ],
        "Product Management": [
            "product manager", "product owner", "roadmap", "product strategy",
            "user stories", "backlog", "product requirements", "go-to-market",
            "product-market fit",
        ],
        "Finance": [
            "finance", "financial", "fp&a", "banking", "investment",
            "accounting", "budget", "forecasting", "valuation", "p&l",
            "audit", "gaap", "ifrs", "tax", "treasury",
        ],
        "Consulting": [
            "consulting", "client engagement", "advisory", "strategy projects",
            "management consulting", "due diligence", "m&a", "workstream",
        ],
        "Technology": [
            "software", "saas", "cloud", "developer", "product", "tech",
            "automation platform", "platform", "enterprise software",
        ],
        "Healthcare": [
            "healthcare", "clinical", "patient", "medical", "hospital",
            "pharma", "ehr", "emr", "hipaa", "revenue cycle", "health system",
        ],
        "Marketing": [
            "marketing", "brand", "campaign", "growth", "content", "seo",
            "paid", "acquisition", "retention", "demand generation", "cmo",
        ],
        "Human Resources": [
            "human resources", "hr", "talent acquisition", "recruiting",
            "hrbp", "people operations", "employee engagement",
            "compensation", "benefits", "hris", "workforce planning",
        ],
        "Sales": [
            "sales", "account executive", "business development", "revenue",
            "quota", "pipeline", "crm", "salesforce", "enterprise sales",
            "account management", "customer success",
        ],
        "Legal": [
            "legal", "attorney", "counsel", "compliance", "regulatory",
            "contract review", "litigation", "intellectual property", "law",
        ],
        "Education": [
            "education", "teaching", "curriculum", "students", "learning",
            "instruction", "classroom", "higher education", "k-12",
        ],
        "Real Estate": [
            "real estate", "property management", "leasing", "acquisitions",
            "asset management", "brokerage", "cre", "commercial real estate",
        ],
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


def get_fresh_detected_target_role(job_description: str) -> str:
    """Prefer the latest JD-derived title over older session carry-over values."""
    local_ai_signals = st.session_state.get("local_ai_job_signals") or {}
    return (
        str(local_ai_signals.get("normalized_role_title", "")).strip()
        or st.session_state.get("jd_role_hint", "").strip()
        or detect_role_title(job_description)
        or ""
    )


def get_effective_industry(job_description: str) -> str:
    """Use the manual override when present, otherwise JD detection."""
    return st.session_state.target_industry.strip() or detect_industry(job_description)


def save_uploaded_resume(uploaded_file) -> None:
    """Store uploaded resume data and extracted plain text in session state."""
    resume_bytes = uploaded_file.getvalue()

    # Determine file suffix based on uploaded filename
    filename_lower = uploaded_file.name.lower()
    if filename_lower.endswith('.pdf'):
        suffix = ".pdf"
    else:
        suffix = ".docx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
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
    logger.info(
        "Resume uploaded: filename=%s, paragraphs=%s",
        uploaded_file.name,
        len(st.session_state.resume_paragraphs),
    )
    st.session_state.local_ai_job_signals = {}
    st.session_state.local_ai_profile_summary = ""
    st.session_state.local_ai_profile_headline = ""


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
    """Landing page."""
    render_shell_start()
    profile = create_or_get_profile()
    applications = _cached_list_applications()
    optimization_history = get_optimization_history()
    has_profile_identity = bool(profile.full_name.strip() or profile.email.strip() or profile.linkedin.strip())
    has_profile_targets = bool(profile.target_roles or profile.target_industries)
    has_profile_memory = bool(_cached_list_profile_items() or _cached_list_profile_sources())
    profile_setup_complete = has_profile_identity and (has_profile_targets or has_profile_memory)
    is_returning_user = has_profile_identity or bool(applications) or bool(optimization_history)
    local_ai_card_status = ""
    local_ai_status_copy = ""
    local_ai_button_text = ""
    local_ai_button_key = ""
    local_ai_cta_route = ""

    if show_local_ai_cards():
        local_ai_base_url = st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL)
        local_ai_model = _get_local_ai_model_name()
        ollama_status = _cached_check_ollama_status(base_url=local_ai_base_url)
        model_installed = ollama_status["reachable"] and is_model_installed(local_ai_model, base_url=local_ai_base_url)

        if not ollama_status["reachable"]:
            local_ai_card_status = "Not Installed"
            local_ai_status_copy = "Install Ollama once to unlock private on-device AI."
            local_ai_button_text = "Set Up Private Mode"
            local_ai_button_key = "landing-local-ai-setup"
            local_ai_cta_route = "local_ai_setup"
            st.session_state.local_ai_ready = False
        elif model_installed:
            readiness = _cached_run_readiness_check(model_name=local_ai_model, base_url=local_ai_base_url)
            st.session_state.local_ai_setup_status = readiness
            st.session_state.local_ai_ready = readiness.get("ready", False)
            if readiness.get("ready", False):
                local_ai_card_status = "Local AI Ready"
                local_ai_status_copy = f"{DEFAULT_LOCAL_AI_LABEL} is ready on this computer."
                local_ai_button_text = "Start in Private Mode"
                local_ai_button_key = "landing-local-ai-start"
                local_ai_cta_route = "input"
            else:
                local_ai_card_status = "Setup Needed"
                local_ai_status_copy = readiness.get("message", "Finish the one-time Local AI check.")
                local_ai_button_text = "Finish Private Mode Setup"
                local_ai_button_key = "landing-local-ai-finish"
                local_ai_cta_route = "local_ai_setup"
        else:
            local_ai_card_status = "Setup Needed"
            local_ai_status_copy = "Ollama is available, but Gemma 4 still needs to be downloaded."
            local_ai_button_text = "Finish Private Mode Setup"
            local_ai_button_key = "landing-local-ai-model"
            local_ai_cta_route = "local_ai_setup"
            st.session_state.local_ai_ready = False

    hero_eyebrow = "Welcome Back" if is_returning_user else "Resume OTG"
    hero_title = f"Welcome back, {profile.full_name.strip()}." if is_returning_user and profile.full_name.strip() else "Make resume tailoring feel beautifully simple."
    hero_copy = (
        "Pick up where you left off, build from your saved profile, or jump back into an application already in progress."
        if is_returning_user
        else "Start with the task you need right now. The app will quietly build your profile in the background so future applications get easier."
    )
    local_ai_chip = (
        (
            f'<div class="apple-landing-status" style="max-width: 430px; margin: 1.4rem auto 0 auto;">'
            f'<div class="apple-landing-status-kicker">{local_ai_card_status}</div>'
            f'<div class="apple-landing-status-copy">{local_ai_status_copy}</div>'
            f'</div>'
        )
        if show_local_ai_cards() and local_ai_card_status
        else ""
    )
    st.markdown(
        f"""
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">{hero_eyebrow}</div>
            <h1>{hero_title}</h1>
            <p>{hero_copy}</p>
            {local_ai_chip}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_returning_user:
        # --- Returning users: 2-column layout (no builder card) ---
        col1, col2 = st.columns(2, gap="large")

        with col1:
            with st.container(border=True):
                st.markdown(
                    """
                    <div class="apple-kicker">Continue</div>
                    <div class="apple-landing-card-title">Optimize my existing resume</div>
                    <div class="apple-landing-card-copy">Jump back into targeting a role with your current resume and saved context.</div>
                    """,
                    unsafe_allow_html=True,
                )
                if primary_button("Continue Optimizing", use_container_width=True, key="landing-optimize"):
                    st.session_state.optimization_path = "fast_start"
                    st.session_state.execution_mode = None
                    _clear_tracker_linkage()
                    st.session_state.screen = "input"
                    st.rerun()

        with col2:
            with st.container(border=True):
                if not profile_setup_complete:
                    st.markdown(
                        """
                        <div class="apple-kicker">Profile Setup</div>
                        <div class="apple-landing-card-title">Complete your profile foundation</div>
                        <div class="apple-landing-card-copy">Add your identity, target roles, and reusable background once so every future draft starts from stronger context.</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if secondary_button("Complete Profile Setup", use_container_width=True, key="landing-import"):
                        st.session_state.screen = "profile"
                        st.rerun()
                else:
                    st.markdown(
                        """
                        <div class="apple-kicker">Job Tracker</div>
                        <div class="apple-landing-card-title">Track your applications</div>
                        <div class="apple-landing-card-copy">View all tracked jobs, update statuses, add notes, and jump back into an optimization.</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if secondary_button("Open Job Tracker", use_container_width=True, key="landing-import"):
                        st.session_state.screen = "job_tracker"
                        st.rerun()

    else:
        # --- New users: 3-column layout ---
        col1, col2, col3 = st.columns(3, gap="large")

        with col1:
            with st.container(border=True):
                st.markdown(
                    """
                    <div class="apple-kicker">Most Popular</div>
                    <div class="apple-landing-card-title">Optimize my existing resume</div>
                    <div class="apple-landing-card-copy">Upload your current resume, aim it at a job description, and improve it with guided review before export.</div>
                    """,
                    unsafe_allow_html=True,
                )
                if primary_button("Start Optimizing", use_container_width=True, key="landing-optimize"):
                    st.session_state.optimization_path = "fast_start"
                    st.session_state.execution_mode = None
                    _clear_tracker_linkage()
                    st.session_state.screen = "input"
                    st.rerun()

        with col2:
            with st.container(border=True):
                st.markdown(
                    """
                    <div class="apple-kicker">Build</div>
                    <div class="apple-landing-card-title">Build your resume from scratch</div>
                    <div class="apple-landing-card-copy">Tell us about yourself in plain English, get a draft quickly, and let the app turn that into reusable profile memory.</div>
                    """,
                    unsafe_allow_html=True,
                )
                if secondary_button("Build First Resume", use_container_width=True, key="landing-builder"):
                    st.session_state.career_stage = "Student"
                    st.session_state.screen = "builder_input"
                    st.rerun()

        with col3:
            with st.container(border=True):
                st.markdown(
                    """
                    <div class="apple-kicker">Import</div>
                    <div class="apple-landing-card-title">Import resume or LinkedIn</div>
                    <div class="apple-landing-card-copy">Bring in a resume, LinkedIn export, or notes so the app can build your profile and save reusable evidence.</div>
                    """,
                    unsafe_allow_html=True,
                )
                if secondary_button("Import Materials", use_container_width=True, key="landing-import"):
                    st.session_state.screen = "profile"
                    st.rerun()

    render_shell_end()


def _profile_setup_complete() -> bool:
    """Return whether the user has enough saved profile context to skip setup prompts."""
    profile = create_or_get_profile()
    has_identity = bool(profile.full_name.strip() or profile.email.strip() or profile.linkedin.strip())
    has_targets = bool(profile.target_roles or profile.target_industries)
    has_memory = bool(list_profile_items() or list_profile_sources())
    return has_identity and (has_targets or has_memory)


def _route_to_profile_setup() -> None:
    """Send the user to the unified Profile screen."""
    st.session_state.screen = "profile"


def _profile_items_from_session() -> list[ProfileItem]:
    """Convert session-stored dict items back into ProfileItem objects."""
    return [ProfileItem(**item) for item in st.session_state.profile_extracted_items]


def _seed_onboarding_from_profile() -> None:
    """Prefill onboarding fields from the saved profile once fields are empty."""
    profile = create_or_get_profile()
    if not st.session_state.get("onboarding_name"):
        st.session_state.onboarding_name = profile.full_name or ""
    if not st.session_state.get("onboarding_email"):
        st.session_state.onboarding_email = profile.email or ""
    if not st.session_state.get("onboarding_phone"):
        st.session_state.onboarding_phone = profile.phone or ""
    if not st.session_state.get("onboarding_location"):
        st.session_state.onboarding_location = profile.location or ""
    if not st.session_state.get("onboarding_linkedin"):
        st.session_state.onboarding_linkedin = profile.linkedin or ""
    if not st.session_state.get("onboarding_target_roles"):
        st.session_state.onboarding_target_roles = ", ".join(profile.target_roles or [])
    if not st.session_state.get("onboarding_target_industries"):
        st.session_state.onboarding_target_industries = ", ".join(profile.target_industries or [])
    if not st.session_state.get("onboarding_summary"):
        st.session_state.onboarding_summary = profile.summary or ""


def _apply_onboarding_to_profile_and_builder() -> None:
    """Persist onboarding answers and reuse them as builder inputs."""
    full_name = st.session_state.get("onboarding_name", "").strip()
    email = st.session_state.get("onboarding_email", "").strip()
    phone = st.session_state.get("onboarding_phone", "").strip()
    location = st.session_state.get("onboarding_location", "").strip()
    linkedin = st.session_state.get("onboarding_linkedin", "").strip()
    target_roles = _split_csv_input(st.session_state.get("onboarding_target_roles", ""))
    target_industries = _split_csv_input(st.session_state.get("onboarding_target_industries", ""))
    education = st.session_state.get("onboarding_education", "").strip()
    experience = st.session_state.get("onboarding_experience", "").strip()
    projects = st.session_state.get("onboarding_projects", "").strip()
    skills = st.session_state.get("onboarding_skills", "").strip()
    summary = st.session_state.get("onboarding_summary", "").strip()

    headline_parts = []
    if target_roles:
        headline_parts.append(target_roles[0])
    if target_industries:
        headline_parts.append(target_industries[0])
    headline = " · ".join(headline_parts)

    save_profile_basics(
        full_name=full_name,
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        headline=headline,
        career_stage=st.session_state.career_stage,
        summary=summary,
        target_roles=target_roles,
        target_industries=target_industries,
        preferred_locations=[location] if location else [],
        work_authorization="",
    )

    contact_lines = [value for value in [email, phone, location, linkedin] if value]
    builder_extras = []
    if projects:
        builder_extras.append(projects)

    st.session_state.builder_full_name = full_name
    st.session_state.builder_contact_info = "\n".join(contact_lines)
    st.session_state.builder_education = education
    st.session_state.builder_experience_dump = experience
    st.session_state.builder_activities = "\n\n".join(builder_extras)
    st.session_state.builder_skills = skills
    st.session_state.target_role = target_roles[0] if target_roles else st.session_state.target_role
    if target_industries:
        st.session_state.target_industry = target_industries[0]
    st.session_state.onboarding_complete = True
    st.session_state.profile_dashboard_section = "overview"


def _seed_builder_from_profile() -> None:
    """Prefill builder inputs from saved profile data when fields are still empty."""
    profile = create_or_get_profile()
    if not st.session_state.get("builder_full_name"):
        st.session_state.builder_full_name = profile.full_name or ""
    if not st.session_state.get("builder_contact_info"):
        contact_lines = [value for value in [profile.email, profile.phone, profile.location, profile.linkedin] if value]
        st.session_state.builder_contact_info = "\n".join(contact_lines)
    if not st.session_state.get("target_role") and profile.target_roles:
        st.session_state.target_role = profile.target_roles[0]
    if not st.session_state.get("target_industry") and profile.target_industries:
        st.session_state.target_industry = profile.target_industries[0]
    if profile.career_stage and st.session_state.get("career_stage") == "Student":
        st.session_state.career_stage = profile.career_stage


def _save_builder_profile_snapshot(
    full_name: str,
    contact_info: str,
    education: str,
    experience_dump: str,
    activities: str,
    skills: str,
    career_stage: str,
    target_role: str,
) -> None:
    """Persist builder intake as profile basics and starter evidence."""
    profile = create_or_get_profile()

    email = ""
    phone = ""
    location = ""
    linkedin = ""
    for line in _split_line_input(contact_info):
        lower = line.lower()
        if "@" in line and not email:
            email = line
        elif ("linkedin" in lower or "portfolio" in lower or "http" in lower) and not linkedin:
            linkedin = line
        elif any(char.isdigit() for char in line) and not phone:
            phone = line
        elif not location:
            location = line

    save_profile_basics(
        full_name=full_name,
        email=email or profile.email,
        phone=phone or profile.phone,
        location=location or profile.location,
        linkedin=linkedin or profile.linkedin,
        headline=target_role.strip(),
        career_stage=career_stage,
        summary=profile.summary or "",
        target_roles=[target_role.strip()] if target_role.strip() else profile.target_roles,
        target_industries=profile.target_industries,
        preferred_locations=[location] if location else profile.preferred_locations,
        work_authorization=profile.work_authorization,
    )

    source_text = "\n\n".join(part for part in [education, experience_dump, activities, skills] if part.strip())
    if not source_text:
        return

    source_id = save_profile_source(
        source_type="manual_notes",
        source_name="Builder Intake",
        raw_text=source_text,
        parsed_payload={"type": "builder_intake", "career_stage": career_stage, "target_role": target_role},
    )
    items_to_save: list[ProfileItem] = []
    if education.strip():
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="education",
                title="Education Background",
                description=education.strip(),
                bullets=_split_line_input(education),
                verification_status="verified",
                confidence_score=0.9,
            )
        )
    if experience_dump.strip():
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="experience",
                title="Experience Highlights",
                description=experience_dump.strip(),
                bullets=_split_line_input(experience_dump),
                verification_status="verified",
                confidence_score=0.85,
            )
        )
    if activities.strip():
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="project",
                title="Projects and Activities",
                description=activities.strip(),
                bullets=_split_line_input(activities),
                verification_status="verified",
                confidence_score=0.8,
            )
        )
    parsed_skills = _split_csv_input(skills) or _split_line_input(skills)
    if parsed_skills:
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="skills",
                title="Core Skills",
                description="Skills captured from the builder intake.",
                skills=parsed_skills,
                keywords=parsed_skills[:12],
                verification_status="verified",
                confidence_score=0.95,
            )
        )
    if items_to_save:
        save_profile_items(items_to_save, replace_existing_for_source=source_id)


def _save_onboarding_profile_items() -> None:
    """Create lightweight reusable profile items from onboarding answers."""
    profile = create_or_get_profile()
    raw_segments = [
        st.session_state.get("onboarding_summary", "").strip(),
        st.session_state.get("onboarding_education", "").strip(),
        st.session_state.get("onboarding_experience", "").strip(),
        st.session_state.get("onboarding_projects", "").strip(),
        st.session_state.get("onboarding_skills", "").strip(),
    ]
    raw_text = "\n\n".join(segment for segment in raw_segments if segment)
    if not raw_text:
        return

    source_id = save_profile_source(
        source_type="manual_notes",
        source_name="Onboarding Intake",
        raw_text=raw_text,
        parsed_payload={"type": "onboarding", "career_stage": st.session_state.career_stage},
    )

    items_to_save: list[ProfileItem] = []
    education = st.session_state.get("onboarding_education", "").strip()
    if education:
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="education",
                title="Education Background",
                organization="",
                description=education,
                bullets=_split_line_input(education),
                keywords=_split_csv_input(st.session_state.get("onboarding_target_roles", ""))[:6],
                verification_status="verified",
                confidence_score=0.9,
            )
        )

    experience = st.session_state.get("onboarding_experience", "").strip()
    if experience:
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="experience",
                title="Experience Highlights",
                organization="",
                description=experience,
                bullets=_split_line_input(experience),
                keywords=_split_csv_input(st.session_state.get("onboarding_target_industries", ""))[:6],
                verification_status="verified",
                confidence_score=0.85,
            )
        )

    projects = st.session_state.get("onboarding_projects", "").strip()
    if projects:
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="project",
                title="Projects and Activities",
                organization="",
                description=projects,
                bullets=_split_line_input(projects),
                verification_status="verified",
                confidence_score=0.8,
            )
        )

    skills = st.session_state.get("onboarding_skills", "").strip()
    if skills:
        parsed_skills = _split_csv_input(skills) or _split_line_input(skills)
        items_to_save.append(
            ProfileItem(
                profile_id=profile.id,
                source_id=source_id,
                item_type="skills",
                title="Core Skills",
                organization="",
                description="Skills captured during onboarding.",
                skills=parsed_skills,
                keywords=parsed_skills[:12],
                verification_status="verified",
                confidence_score=0.95,
            )
        )

    if items_to_save:
        save_profile_items(items_to_save, replace_existing_for_source=source_id)


def _split_csv_input(value: str) -> list[str]:
    """Turn comma-separated text into a clean list."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _split_line_input(value: str) -> list[str]:
    """Turn multiline text into a clean list of non-empty lines."""
    return [line.strip() for line in value.splitlines() if line.strip()]


def _get_selected_profile_items() -> list[ProfileItem]:
    """Resolve selected profile item ids from session state."""
    selected_ids = set(st.session_state.get("selected_profile_item_ids", []))
    if not selected_ids:
        return []
    items_by_id = {item.id: item for item in list_profile_items() if item.visibility == "active"}
    return [items_by_id[item_id] for item_id in st.session_state.get("selected_profile_item_ids", []) if item_id in items_by_id]


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
    """Build the optimizer prompt enriched with profile evidence and JD gap analysis."""
    # Sync profile fields into session state when the session still has un-set defaults.
    _profile = create_or_get_profile()
    if _profile.career_stage and st.session_state.get("career_stage") == CAREER_STAGES[0]:
        st.session_state.career_stage = _profile.career_stage
    if not st.session_state.get("target_role") and _profile.target_roles:
        st.session_state.target_role = _profile.target_roles[0]
    if not st.session_state.get("target_industry") and _profile.target_industries:
        st.session_state.target_industry = _profile.target_industries[0]

    profile_context = _build_profile_context(_get_selected_profile_items()) if st.session_state.get("use_career_profile") else ""

    # Pull missing keywords/skills from the current fit report so the LLM knows
    # exactly which JD signals are absent from the resume and should be incorporated.
    fit_report = st.session_state.get("resume_fit_report") or {}
    missing_keywords: list[str] = fit_report.get("missing_keywords", [])
    missing_skills: list[str] = fit_report.get("missing_skills", [])

    return build_optimizer_prompt(
        st.session_state.resume_text,
        st.session_state.job_description,
        st.session_state.career_stage,
        get_effective_target_role(st.session_state.job_description),
        get_effective_industry(st.session_state.job_description),
        profile_context=profile_context,
        missing_keywords=missing_keywords,
        missing_skills=missing_skills,
    )


def _get_local_ai_model_name() -> str:
    """Return the current Local AI model name."""
    return st.session_state.get("local_ai_model_name", DEFAULT_LOCAL_AI_MODEL) or DEFAULT_LOCAL_AI_MODEL


def _save_local_ai_profile_suggestions(profile_result: dict) -> int:
    """Store Local AI profile suggestions in the existing profile review flow."""
    merged_items: list[ProfileItem] = []
    allowed_profile_item_keys = {
        "id",
        "user_id",
        "profile_id",
        "source_id",
        "item_type",
        "title",
        "organization",
        "location",
        "start_date",
        "end_date",
        "is_current",
        "description",
        "bullets",
        "skills",
        "tools",
        "industry_tags",
        "function_tags",
        "keywords",
        "confidence_score",
        "verification_status",
        "visibility",
        "created_at",
        "updated_at",
    }

    for raw_item in profile_result.get("deterministic_items", []):
        if isinstance(raw_item, dict):
            merged_items.append(ProfileItem(**{key: value for key, value in raw_item.items() if key in allowed_profile_item_keys}))
    for raw_item in profile_result.get("suggested_items", []):
        if isinstance(raw_item, dict):
            merged_items.append(ProfileItem(**{key: value for key, value in raw_item.items() if key in allowed_profile_item_keys}))

    valid_items, _garbage_items = filter_and_sort_items_for_review(merged_items)
    st.session_state.profile_extracted_basics = profile_result.get("basics", {})
    st.session_state.profile_extracted_items = [item.to_dict() for item in valid_items]
    st.session_state.profile_import_source_name = "Resume Import + Local AI"
    st.session_state.profile_last_source_raw_text = st.session_state.resume_text or ""
    st.session_state.local_ai_profile_summary = profile_result.get("summary", "")
    st.session_state.local_ai_profile_headline = profile_result.get("headline", "")
    return len(valid_items)


def _render_task_meta_card(title: str, task_meta: dict) -> None:
    """Render a small user-facing Local AI status card."""
    if not task_meta:
        return

    rows = [
        ("Model", task_meta.get("model_name", "") or "Local AI"),
        ("Evidence used", str(task_meta.get("retrieved_evidence_count", 0))),
        ("Repair step", "Used" if task_meta.get("repair_attempted") else "Not needed"),
        ("Latency", f"{task_meta.get('latency_ms', 0)} ms"),
    ]
    with st.container(border=True):
        st.markdown(f'<div class="apple-kicker">{title}</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">How Local AI handled this step.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">We keep these details lightweight so you can trust what the app is doing without needing to think like an engineer.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(build_readiness_rows(rows), unsafe_allow_html=True)
        evidence_previews = task_meta.get("retrieved_evidence_previews") or []
        if evidence_previews:
            st.markdown(
                '<div class="apple-minor-copy" style="margin-top:0.75rem;">What it looked at</div>',
                unsafe_allow_html=True,
            )
            for preview in evidence_previews[:3]:
                source_label = str(preview.get("source_type", "evidence")).replace("_", " ").title()
                section_label = str(preview.get("section", "")).replace("_", " ").title()
                label = source_label if not section_label else f"{source_label} · {section_label}"
                snippet = format_preview_text(str(preview.get("text", "")).strip(), max_len=140)
                if snippet:
                    st.caption(f"{label}: {snippet}")
        errors = task_meta.get("validation_errors") or []
        if errors:
            st.caption("Validation notes: " + " | ".join(errors[:2]))


def _humanize_local_ai_error(error: Exception | str, task_label: str) -> str:
    """Translate technical Local AI failures into clearer next-step guidance."""
    raw_message = str(error).strip()
    lowered = raw_message.lower()

    if "no json block found" in lowered or "valid json" in lowered or "unsupported top-level key" in lowered:
        return f"{task_label} finished, but the model responded in the wrong format. The app blocked it before anything unsafe reached your resume. Please retry once."
    if "anchor" in lowered and "not found" in lowered:
        return f"{task_label} drafted changes that did not line up cleanly with the exact text in your resume, so the app stopped the run for safety. Try retrying after re-uploading a cleaner resume file."
    if "keyword alignment dropped" in lowered or "overall match score dropped" in lowered:
        return f"{task_label} produced a draft that scored worse than your current resume, so the app kept the original version instead of applying weaker edits."
    if "validation" in lowered or "guardrail" in lowered:
        return f"{task_label} was blocked by a safety check because the result was incomplete or unreliable. Please retry or switch to Standard mode if you need a faster path."
    if "connection" in lowered or "ollama" in lowered or "refused" in lowered or "timed out" in lowered:
        return "Private Mode could not reach Ollama reliably. Check that Ollama is still running on this computer, then retry."
    if not raw_message:
        return f"{task_label} could not finish this step yet. Please retry."
    return f"{task_label} could not finish cleanly yet. {raw_message}"


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
        logger.info(
            "Fit score calculated: overall=%s, keyword=%s, skills=%s, ats=%s",
            int(report.get("overall_score", 0)),
            int(report.get("keyword_score", 0)),
            int(report.get("skill_score", 0)),
            int(report.get("ats_score", 0)),
        )
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
    logger.info(
        "Application saved: id=%s, job_title=%s, company=%s, status=%s, selected_items=%s",
        application.id,
        application.job_title,
        application.company,
        status,
        len(st.session_state.get("selected_profile_item_ids", [])),
    )
    return application.id or 0


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


def _clear_tracker_linkage() -> None:
    """Clear tracker-linked optimization context before starting a fresh run."""
    st.session_state.active_tracker_job_id = None


def _extract_profile_from_import(uploaded_files, notes_text: str) -> tuple[str, str, dict, list[dict]]:
    """Extract raw text, source name, profile basics, and item dicts from uploaded material(s)."""
    raw_text_parts: list[str] = []
    source_names: list[str] = []

    # Handle both single file and multiple files
    if uploaded_files is not None:
        files_list = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]

        for uploaded_file in files_list:
            if uploaded_file is None:
                continue

            source_names.append(uploaded_file.name)
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
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file_bytes)
                    temp_path = temp_file.name
                try:
                    raw_text_parts.append(extract_text(temp_path))
                finally:
                    Path(temp_path).unlink(missing_ok=True)
            elif suffix in {".txt", ".md"}:
                raw_text_parts.append(file_bytes.decode("utf-8", errors="ignore"))
            else:
                raise ValueError(f"Unsupported file type: {suffix}. Supported: .docx, .pdf, .txt, .md")

    if notes_text.strip():
        raw_text_parts.append(notes_text.strip())

    raw_text = "\n\n".join(part for part in raw_text_parts if part.strip())
    if not raw_text.strip():
        raise ValueError("Upload source documents or paste notes to build the profile.")

    # Create source name from uploaded files
    if source_names:
        source_name = ", ".join(source_names) if len(source_names) <= 2 else f"{source_names[0]} + {len(source_names)-1} more"
    else:
        source_name = "Manual Notes"

    basics, all_items = extract_profile_items_from_text(raw_text)

    # Filter out garbage items
    valid_items, garbage_items = filter_and_sort_items_for_review(all_items)

    logger.info(
        "Profile import extracted: source=%s, files=%s, chars=%s, valid_items=%s, garbage_filtered=%s",
        source_name,
        len(source_names),
        len(raw_text),
        len(valid_items),
        len(garbage_items),
    )

    return raw_text, source_name, basics, [item.to_dict() for item in valid_items]


def render_profile_welcome_screen() -> None:
    """Entry point for Career Profile onboarding."""
    render_shell_start()
    profile_is_ready = _profile_setup_complete()
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
                "<div class=\"apple-choice-copy\">Upload an existing resume or paste detailed notes. We'll extract reusable profile items for you to review.</div>",
                unsafe_allow_html=True,
            )
            if primary_button("Import Materials", use_container_width=True, key="profile-import-entry"):
                st.session_state.screen = "profile_import"
                st.rerun()
    with col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Profile Dashboard</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-choice-title">{"View your saved career profile." if profile_is_ready else "Finish setting up your reusable profile."}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                (
                    '<div class="apple-choice-copy">Open your stored experience bank, saved sources, and target-role settings. Great for updating your long-term career memory.</div>'
                    if profile_is_ready
                    else '<div class="apple-choice-copy">Add your identity, target roles, and reusable evidence so future applications and drafts start from stronger context.</div>'
                ),
                unsafe_allow_html=True,
            )
            if secondary_button("Open Profile Dashboard" if profile_is_ready else "Complete Profile Setup", use_container_width=True, key="profile-dashboard-entry"):
                _route_to_profile_setup()
                st.rerun()

    back_col_left, back_col_center, back_col_right = st.columns([1.2, 1.6, 1.2])
    with back_col_center:
        if secondary_button("Back to Home", use_container_width=True, key="profile-welcome-back"):
            st.session_state.screen = "landing"
            st.rerun()
    render_shell_end()


def render_onboarding_welcome_screen() -> None:
    """Welcome screen for first-time personalization."""
    render_shell_start()
    _seed_onboarding_from_profile()
    render_screen_intro(
        "onboarding_welcome",
        "Step 1 of 5",
        "Let us get to know you first.",
        "Answer a few quick questions so the app can personalize your profile, prefill your resume, and save you time later.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Why This Helps</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">We can turn one short intro into a reusable foundation.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Your answers help us build your Career Profile, prefill the first-resume builder, and personalize future Local AI drafting without asking you to repeat yourself every time.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            build_readiness_rows(
                [
                    ("What we save", "Your basics, goals, and background"),
                    ("What it powers", "Profile, first resume, and future drafts"),
                    ("Time required", "About 2 minutes"),
                    ("Can you skip fields?", "Yes"),
                ]
            ),
            unsafe_allow_html=True,
        )

    action_col1, action_col2 = st.columns(2, gap="large")
    with action_col1:
        if secondary_button("Back", use_container_width=True, key="onboarding-welcome-back"):
            st.session_state.screen = "landing"
            st.rerun()
    with action_col2:
        if primary_button("Start Personal Setup", use_container_width=True, key="onboarding-welcome-next"):
            st.session_state.screen = "onboarding_questions"
            st.rerun()
    render_shell_end()


def render_onboarding_questions_screen() -> None:
    """Collect reusable profile answers and prefill the builder."""
    render_shell_start()
    _seed_onboarding_from_profile()
    render_screen_intro(
        "onboarding_questions",
        "Step 1 of 5",
        "Tell us about yourself.",
        "Keep it simple and natural. We will use these answers to build your profile and prefill your first resume draft.",
    )

    left_col, right_col = st.columns(2, gap="large")
    with left_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Basics</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Start with who you are.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">These details help us personalize the app and create a clean resume header automatically.</div>',
                unsafe_allow_html=True,
            )
            st.session_state.onboarding_name = st.text_input("Full Name", value=st.session_state.onboarding_name, placeholder="Example: Jane Doe")
            st.session_state.onboarding_email = st.text_input("Email", value=st.session_state.onboarding_email, placeholder="name@email.com")
            st.session_state.onboarding_phone = st.text_input("Phone", value=st.session_state.onboarding_phone, placeholder="(555) 555-5555")
            st.session_state.onboarding_location = st.text_input("Location", value=st.session_state.onboarding_location, placeholder="City, State")
            st.session_state.onboarding_linkedin = st.text_input("LinkedIn or Portfolio", value=st.session_state.onboarding_linkedin, placeholder="LinkedIn URL or portfolio")

    with right_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Goals</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">What are you aiming for?</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Use plain language. We will reuse this when building your profile and shaping the resume draft.</div>',
                unsafe_allow_html=True,
            )
            st.session_state.onboarding_target_roles = st.text_input(
                "Target Role Titles",
                value=st.session_state.onboarding_target_roles,
                placeholder="Business Analyst Intern, Supply Chain Analyst, Consultant",
            )
            st.session_state.onboarding_target_industries = st.text_input(
                "Target Industries",
                value=st.session_state.onboarding_target_industries,
                placeholder="Consulting, Supply Chain, Technology",
            )
            st.session_state.career_stage = st.selectbox(
                "Career Stage",
                CAREER_STAGES,
                index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
                key="onboarding-career-stage",
            )
            st.session_state.onboarding_summary = st.text_area(
                "What should we know about you?",
                value=st.session_state.onboarding_summary,
                height=120,
                placeholder="A short intro about your interests, strengths, or the kind of work you want to do.",
            )

    background_col1, background_col2 = st.columns(2, gap="large")
    with background_col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Background</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Capture your education and experience.</div>', unsafe_allow_html=True)
            st.session_state.onboarding_education = st.text_area(
                "Education",
                value=st.session_state.onboarding_education,
                height=150,
                placeholder="School, degree, graduation date, GPA, honors, coursework, certifications.",
            )
            st.session_state.onboarding_experience = st.text_area(
                "Experience So Far",
                value=st.session_state.onboarding_experience,
                height=190,
                placeholder="Internships, part-time work, volunteer roles, responsibilities, wins, projects, measurable outcomes.",
            )

    with background_col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Extras</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Add anything that can strengthen your profile.</div>', unsafe_allow_html=True)
            st.session_state.onboarding_projects = st.text_area(
                "Projects / Activities / Leadership",
                value=st.session_state.onboarding_projects,
                height=150,
                placeholder="Case competitions, clubs, side projects, leadership roles, volunteering, presentations.",
            )
            st.session_state.onboarding_skills = st.text_area(
                "Skills",
                value=st.session_state.onboarding_skills,
                height=150,
                placeholder="Tools, technical skills, languages, certifications, strengths, domains you know well.",
            )

    action_col1, action_col2 = st.columns(2, gap="large")
    with action_col1:
        if secondary_button("Back", use_container_width=True, key="onboarding-questions-back"):
            st.session_state.screen = "onboarding_welcome"
            st.rerun()
    with action_col2:
        can_continue = bool(
            st.session_state.onboarding_name.strip()
            and (
                st.session_state.onboarding_education.strip()
                or st.session_state.onboarding_experience.strip()
                or st.session_state.onboarding_projects.strip()
            )
        )
        if primary_button("Save and Continue", use_container_width=True, disabled=not can_continue, key="onboarding-save-continue"):
            _apply_onboarding_to_profile_and_builder()
            _save_onboarding_profile_items()
            st.session_state.screen = "builder_input"
            st.rerun()
    render_shell_end()


def render_profile_import_screen() -> None:
    """Collect source material for first-pass profile extraction."""
    render_shell_start()
    render_screen_intro(
        "input",
        "Career Profile Import",
        "Import your background.",
        "Upload a resume or paste detailed notes. We'll turn them into reusable profile items you can confirm.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Source Material</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Add what you already have.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Upload resumes, LinkedIn profiles, or paste detailed notes from your background. Supports .docx, .pdf, .txt, and .md files.</div>',
            unsafe_allow_html=True,
        )
        uploaded_sources = st.file_uploader(
            "Upload source files",
            type=["docx", "pdf", "txt", "md"],
            accept_multiple_files=True,
            help="Upload one or more files: resumes, LinkedIn PDFs, text exports, or markdown notes.",
            key="profile-import-file",
        )
        notes_text = st.text_area(
            "Notes",
            value=st.session_state.profile_import_notes,
            height=220,
            placeholder="Paste LinkedIn text, old resume content, project notes, certifications, activities, or any other career history here.",
        )
        st.session_state.profile_import_notes = notes_text

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if secondary_button("Back", use_container_width=True, key="profile-import-back"):
            st.session_state.screen = "profile_welcome"
            st.rerun()
    with col2:
        if primary_button("Extract Profile", use_container_width=True, key="profile-extract"):
            try:
                logger.info(
                    "Profile import started: num_files=%s, notes_chars=%s",
                    len(uploaded_sources) if uploaded_sources else 0,
                    len(notes_text.strip()),
                )
                raw_text, source_name, basics, item_dicts = _extract_profile_from_import(uploaded_sources, notes_text)
                st.session_state.profile_import_source_name = source_name
                st.session_state.profile_extracted_basics = basics
                st.session_state.profile_extracted_items = item_dicts
                st.session_state.profile_last_source_raw_text = raw_text
                st.session_state.profile_review_show_all_items = False
                st.session_state.screen = "profile_review"
                st.rerun()
            except Exception as error:
                st.error(str(error))
    render_shell_end()


def render_profile_review_screen() -> None:
    """Tab-based profile review with inline editing and 5 required categories."""
    render_shell_start()
    render_screen_intro(
        "review",
        "Career Profile Review",
        "Simple & Clean",
        "Review and edit your profile organized by category. Changes are saved automatically.",
    )

    # Personal Info basics section (unchanged from original)
    basics = st.session_state.profile_extracted_basics or {}
    extracted_items = sort_profile_items_for_review(_profile_items_from_session())

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Basics</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Your professional identity.</div>', unsafe_allow_html=True)
        identity_col1, identity_col2 = st.columns(2, gap="large")
        with identity_col1:
            full_name = st.text_input("Full Name", value=basics.get("full_name", ""), placeholder="Jane Doe")
            email = st.text_input("Email", value=basics.get("email", ""), placeholder="jane@example.com")
            phone = st.text_input("Phone", value=basics.get("phone", ""), placeholder="(555) 555-5555")
        with identity_col2:
            location = st.text_input("Location", value=basics.get("location", ""), placeholder="New York, NY")
            linkedin = st.text_input("LinkedIn", value=basics.get("linkedin", ""), placeholder="linkedin.com/in/janedoe")

        headline = st.text_input(
            "Headline",
            value=basics.get("headline", "") or st.session_state.get("local_ai_profile_headline", ""),
            placeholder="Operations Analyst | Supply Chain | Analytics",
        )
        summary = st.text_area(
            "Summary",
            value=basics.get("summary", "") or st.session_state.get("local_ai_profile_summary", ""),
            height=100,
            placeholder="Brief professional summary.",
        )
        career_stage = st.selectbox(
            "Career Stage",
            CAREER_STAGES,
            index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
            key="profile-review-stage",
        )
        target_roles = st.text_input("Target Roles", value=st.session_state.target_role, placeholder="Operations Analyst, Supply Chain Analyst")
        target_industries = st.text_input("Target Industries", value=st.session_state.target_industry, placeholder="Supply Chain / Operations, Technology")
        preferred_locations = st.text_input("Preferred Locations", value=basics.get("preferred_locations", ""), placeholder="New York, Boston, Remote")
        work_authorization = st.text_input("Work Authorization", value="", placeholder="U.S. Citizen, OPT, etc.")

    # Tab-based items section
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Career Evidence</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-title">We found {len(extracted_items)} items from your materials.</div>',
            unsafe_allow_html=True,
        )

        # Group items by 5 required categories
        grouped_items = group_items_by_category(extracted_items)
        active_tabs = [cat for cat in PROFILE_CATEGORY_ORDER if grouped_items[cat]]

        # Undo/Redo controls
        undo_col, redo_col, info_col = st.columns([1, 1, 8])
        with undo_col:
            can_undo = st.session_state.profile_items_edit_history_index > 0
            if st.button("↶ Undo", disabled=not can_undo, key="profile-undo", use_container_width=True):
                undo_profile_edit()
                st.rerun()
        with redo_col:
            can_redo = st.session_state.profile_items_edit_history_index < len(st.session_state.profile_items_edit_history) - 1
            if st.button("↷ Redo", disabled=not can_redo, key="profile-redo", use_container_width=True):
                redo_profile_edit()
                st.rerun()
        with info_col:
            st.caption("Edit items inline by clicking into fields. Changes save automatically.")

        # Duplicate detection
        duplicates = detect_duplicate_items(extracted_items)
        if duplicates:
            st.warning(
                f"⚠️ **Possible duplicates detected:** {len(duplicates)} group(s) found. "
                f"Same company with different roles? Review below to merge or keep separate."
            )

        if active_tabs:
            tabs = st.tabs(active_tabs)
            drafted_items: list[ProfileItem] = []

            for tab, category_name in zip(tabs, active_tabs):
                with tab:
                    items_in_category = grouped_items[category_name]
                    # Sort by confidence within category
                    items_in_category.sort(key=lambda x: -x.confidence_score)

                    # Show top 4, allow "View More"
                    show_more_key = f"show-more-{category_name}"
                    if show_more_key not in st.session_state:
                        st.session_state[show_more_key] = False

                    display_limit = 8 if st.session_state[show_more_key] else 4
                    visible_items = items_in_category[:display_limit]
                    hidden_count = len(items_in_category) - display_limit

                    # Render each item in category
                    for item_idx, item in enumerate(visible_items):
                        render_profile_item_card_new(item, category_name, item_idx, drafted_items)

                    # View More button
                    if hidden_count > 0:
                        if st.button(f"View {hidden_count} more {category_name.lower()} items", key=f"view-more-{category_name}"):
                            st.session_state[show_more_key] = True
                            st.rerun()
        else:
            st.info("No items extracted. Upload your resume or paste detailed notes to extract profile items.")
            drafted_items = []

        # Display count summary
        included_count = len(drafted_items)
        st.markdown(f'<div class="apple-minor-copy">{included_count} items will be saved to your profile.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if secondary_button("Back", use_container_width=True, key="profile-review-back"):
            st.session_state.screen = "local_ai_run" if st.session_state.get("execution_mode") == "local_ai" else "profile_import"
            st.rerun()
    with col2:
        if primary_button("Save Career Profile", use_container_width=True, key="profile-save"):
            profile = save_profile_basics(
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                linkedin=linkedin,
                headline=headline,
                career_stage=career_stage,
                summary=summary,
                target_roles=[part.strip() for part in target_roles.split(",") if part.strip()],
                target_industries=[part.strip() for part in target_industries.split(",") if part.strip()],
                preferred_locations=[part.strip() for part in preferred_locations.split(",") if part.strip()],
                work_authorization=work_authorization,
            )
            source_type = "manual_notes"
            source_name = st.session_state.profile_import_source_name or "Imported Notes"
            if source_name and source_name != "Manual Notes":
                source_type = "resume"
            source_id = save_profile_source(
                source_type=source_type,
                source_name=source_name,
                raw_text=st.session_state.get("profile_last_source_raw_text", ""),
                parsed_payload={"basics": basics, "item_count": len(drafted_items)},
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
            st.session_state.profile_review_show_all_items = False
            logger.info(
                "Career profile saved: source=%s, included_items=%s, stage=%s",
                source_name,
                len(saved_items),
                career_stage,
            )

            # Check if this is first-time user with no resumes - show build resume prompt
            if len(list_applications()) == 0:
                # First time - show build resume prompt
                st.session_state.screen = "profile_build_resume_prompt"
            else:
                # Returning user - go to profile home
                st.session_state.screen = "profile"
            st.rerun()
    render_shell_end()


def render_profile_build_resume_prompt_screen() -> None:
    """Prompt to build first resume after creating profile."""
    render_shell_start()
    render_screen_intro(
        "complete",
        "Profile Created ✓",
        "Ready to build your first resume?",
        "We can use your profile as the foundation—no need to re-enter your information.",
    )

    st.markdown(
        """
        <div style="
            display: flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.75rem 1rem;
            background: #f5f5f5;
            border-radius: 8px;
            margin-bottom: 1.75rem;
        ">
            <span style="
                display: inline-flex; align-items: center; justify-content: center;
                width: 1.25rem; height: 1.25rem;
                background: #1a1a1a; border-radius: 50%; flex-shrink: 0;
            ">
                <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                    <path d="M1 4L3.5 6.5L9 1" stroke="white" stroke-width="1.5"
                          stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </span>
            <span style="font-size: 0.875rem; font-weight: 500; color: #1a1a1a;">
                Profile saved. Every future optimization will draw on it automatically.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if secondary_button("View Profile", use_container_width=True, key="profile-prompt-dashboard"):
            st.session_state.screen = "profile"
            st.rerun()

    with col2:
        if primary_button("Build Resume Now", use_container_width=True, key="profile-prompt-build"):
            _start_profile_draft_flow()
            st.session_state.screen = "builder_input"
            st.rerun()

    render_shell_end()


def render_profile_item_card_new(item: ProfileItem, category: str, index: int, drafted_items: list[ProfileItem]) -> None:
    """Render an editable profile item card with inline fields (no expander)."""
    card_id = f"{category}-{index}-{item.title}"

    # Confidence badge styling
    conf_pct = int(item.confidence_score * 100)
    if conf_pct >= 85:
        conf_color, conf_icon = "#10a760", "✓"  # Green, checkmark
    elif conf_pct >= 70:
        conf_color, conf_icon = "#fea500", "○"  # Orange, circle
    else:
        conf_color, conf_icon = "#d0d0d0", "□"  # Gray, square

    # Compact display
    with st.container(border=False):
        display_cols = st.columns([0.5, 4, 1, 0.8])

        # Confidence icon
        with display_cols[0]:
            st.markdown(f'<div style="color:{conf_color};font-size:20px;font-weight:bold;">{conf_icon}</div>', unsafe_allow_html=True)

        # Title & Organization (clickable expand)
        with display_cols[1]:
            st.markdown(f'**{item.title}**')
            if item.organization:
                st.caption(f"@ {item.organization}")
            if item.start_date:
                st.caption(f"📅 {item.start_date}")

        # Confidence percentage
        with display_cols[2]:
            st.caption(f"{conf_pct}%")

        # Edit button
        with display_cols[3]:
            if st.checkbox("✏️", value=False, key=f"edit-checkbox-{card_id}"):
                st.session_state[f"edit-{card_id}"] = True

    # Edit form (expandable)
    if st.session_state.get(f"edit-{card_id}", False):
        st.markdown("---")
        with st.container(border=True):
            st.markdown("<div style='font-weight:bold;'>Edit Item</div>", unsafe_allow_html=True)
            edit_cols = st.columns([2, 2, 1])

            with edit_cols[0]:
                title = st.text_input("Title", value=item.title, key=f"title-{card_id}")
            with edit_cols[1]:
                organization = st.text_input("Organization", value=item.organization, key=f"org-{card_id}")
            with edit_cols[2]:
                keep_item = st.checkbox("Keep", value=item.visibility != "archived", key=f"keep-{card_id}")

            description = st.text_area("Description", value=item.description, height=80, key=f"desc-{card_id}")
            bullets_text = st.text_area("Bullets", value="\n".join(item.bullets), height=80, key=f"bullets-{card_id}", placeholder="One per line")
            skills_text = st.text_input("Skills", value=", ".join(item.skills or item.keywords), key=f"skills-{card_id}")

            save_col1, save_col2 = st.columns(2)
            with save_col1:
                if st.button("✓ Save", key=f"save-{card_id}", use_container_width=True):
                    edited_item = ProfileItem(
                        id=item.id,
                        user_id=item.user_id,
                        profile_id=item.profile_id,
                        source_id=item.source_id,
                        item_type=item.item_type,
                        title=title.strip(),
                        organization=organization.strip(),
                        location=item.location,
                        start_date=item.start_date,
                        end_date=item.end_date,
                        is_current=item.is_current,
                        description=description.strip(),
                        bullets=_split_line_input(bullets_text),
                        skills=_split_csv_input(skills_text),
                        tools=list(item.tools),
                        industry_tags=list(item.industry_tags),
                        function_tags=list(item.function_tags),
                        keywords=_split_csv_input(skills_text)[:12] or item.keywords,
                        confidence_score=item.confidence_score,
                        verification_status="verified",
                        visibility="active" if keep_item else "archived",
                        created_at=item.created_at,
                        updated_at=utc_now_iso(),
                    )
                    if keep_item:
                        drafted_items.append(edited_item)
                    st.session_state[f"edit-{card_id}"] = False
                    # Save to edit history
                    save_profile_edit_to_history([ProfileItem(**d) for d in st.session_state.profile_extracted_items])
                    st.success("✓ Saved")
                    st.rerun()

            with save_col2:
                if st.button("Cancel", key=f"cancel-{card_id}", use_container_width=True):
                    st.session_state[f"edit-{card_id}"] = False
                    st.rerun()
        st.markdown("---")
    else:
        # Non-edit display: show description and bullets compactly
        if item.description:
            st.caption(f"*{item.description[:150]}...*" if len(item.description) > 150 else f"*{item.description}*")
        if item.bullets:
            bullet_text = " • ".join(item.bullets[:2])
            st.caption(f"💡 {bullet_text}")
        if item.skills or item.keywords:
            skills_display = item.skills or item.keywords
            skills_tags = " · ".join(skills_display[:4])
            st.caption(f"🔧 {skills_tags}")

        # Auto-add to drafted if not archived
        if item.visibility != "archived":
            drafted_items.append(item)


def render_profile_dashboard_screen() -> None:
    """Persistent profile dashboard."""
    render_shell_start()
    profile = create_or_get_profile()
    sources = list_profile_sources()
    items = list_profile_items()
    active_items = [item for item in items if item.visibility == "active"]
    archived_items = [item for item in items if item.visibility == "archived"]
    verification_total = sum(1 for item in active_items if item.verification_status == "verified")
    item_type_counts = Counter(item.item_type for item in active_items)
    top_types = item_type_counts.most_common(3)

    render_screen_intro(
        "complete",
        "Career Profile Dashboard",
        "Your career profile.",
        "This is your reusable source of truth for future applications and resume generation.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Overview</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{profile.full_name or "Set up your profile identity."}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-copy">{profile.headline or "Add a headline and preferences so the app understands how to position you."}</div>',
            unsafe_allow_html=True,
        )

        summary_stats = [
            ("Active items", str(len(active_items)), "Reusable evidence"),
            ("Verified items", str(verification_total), "Ready to reuse"),
            ("Source files", str(len(sources)), "Imported materials"),
        ]
        st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
        overview_cols = st.columns(3, gap="large")
        for col, (label, value, caption) in zip(overview_cols, summary_stats):
            with col:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-label">{label}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-value">{value}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-caption">{caption}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    identity_col, targets_col = st.columns(2, gap="large")
    with identity_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Identity</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Who you are.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">These details are used when the app creates profile-driven drafts and application materials.</div>', unsafe_allow_html=True)
            with st.form("profile-identity-form"):
                full_name = st.text_input("Full Name", value=profile.full_name, placeholder="Example: Jane Doe")
                email = st.text_input("Email", value=profile.email, placeholder="jane@example.com")
                phone = st.text_input("Phone", value=profile.phone, placeholder="(555) 555-5555")
                location = st.text_input("Location", value=profile.location, placeholder="New York, NY")
                linkedin = st.text_input("LinkedIn", value=profile.linkedin, placeholder="linkedin.com/in/janedoe")
                headline = st.text_input("Headline", value=profile.headline, placeholder="Supply Chain Analyst | Operations | Analytics")
                summary = st.text_area("Summary", value=profile.summary, height=120, placeholder="A concise career summary.")
                st.markdown(build_readiness_rows([
                    ("Email", profile.email or "Missing"),
                    ("Phone", profile.phone or "Missing"),
                    ("LinkedIn", profile.linkedin or "Missing"),
                ]), unsafe_allow_html=True)
                identity_saved = primary_form_submit("Save Identity", use_container_width=True)

            if identity_saved:
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

    with targets_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Targets & Preferences</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">How you want to be positioned.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">These preferences help the matching and drafting system choose the strongest direction for each application.</div>', unsafe_allow_html=True)
            with st.form("profile-targets-form"):
                career_stage = st.selectbox(
                    "Career Stage",
                    CAREER_STAGES,
                    index=CAREER_STAGES.index(profile.career_stage) if profile.career_stage in CAREER_STAGES else 0,
                )
                work_authorization = st.text_input(
                    "Work Authorization",
                    value=profile.work_authorization,
                    placeholder="OPT, U.S. Citizen, No sponsorship needed",
                )
                target_roles = st.text_input(
                    "Target Roles",
                    value=", ".join(profile.target_roles),
                    placeholder="Operations Analyst, Supply Chain Analyst",
                )
                target_industries = st.text_input(
                    "Target Industries",
                    value=", ".join(profile.target_industries),
                    placeholder="Supply Chain / Operations, Technology",
                )
                preferred_locations = st.text_input(
                    "Preferred Locations",
                    value=", ".join(profile.preferred_locations),
                    placeholder="New York, Boston, Remote",
                )
                st.markdown(build_readiness_rows([
                    ("Career stage", profile.career_stage or "Not set"),
                    ("Target roles", ", ".join(profile.target_roles) if profile.target_roles else "Missing"),
                    ("Preferred locations", ", ".join(profile.preferred_locations) if profile.preferred_locations else "Missing"),
                ]), unsafe_allow_html=True)
                targets_saved = primary_form_submit("Save Targets", use_container_width=True)

            if targets_saved:
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

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Source Documents</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">What your profile was built from.</div>', unsafe_allow_html=True)
        if not sources:
            st.markdown('<div class="apple-minor-copy">No source documents yet. Import a resume or notes to start building your profile memory.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="apple-section-copy">These materials helped create and expand your reusable evidence library.</div>', unsafe_allow_html=True)
            for source in sources[:8]:
                with st.container(border=True):
                    source_rows = [
                        ("Type", source.source_type.replace("_", " ").title()),
                        ("Name", source.source_name or "Untitled source"),
                        ("Status", source.parsed_status.title()),
                    ]
                    st.markdown(f"**{source.source_name or 'Untitled source'}**")
                    st.markdown(build_readiness_rows(source_rows), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Library</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(active_items)} active evidence items</div>', unsafe_allow_html=True)
        source_names = ", ".join(source.source_name for source in sources[:4]) if sources else "No imported sources yet"
        st.markdown(f'<div class="apple-section-copy">Recent sources: {source_names}</div>', unsafe_allow_html=True)
        if active_items:
            summary_stats = [
                ("Verified items", str(verification_total), "Ready to reuse"),
                ("Source files", str(len(sources)), "Imported materials"),
                ("Top category", top_types[0][0].title() if top_types else "None yet", f"{top_types[0][1]} items" if top_types else "Add your first item"),
            ]
            st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
            stat_cols = st.columns(3, gap="large")
            for col, (label, value, caption) in zip(stat_cols, summary_stats):
                with col:
                    st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-label">{label}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-value">{value}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-caption">{caption}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if top_types:
                st.markdown(
                    f'<div class="apple-minor-copy" style="margin-top:0.75rem;">Your strongest saved categories right now: {", ".join(f"{name.title()} ({count})" for name, count in top_types)}.</div>',
                    unsafe_allow_html=True,
                )
        if not active_items:
            st.markdown('<div class="apple-minor-copy">Import a resume or notes to start building your reusable experience bank.</div>', unsafe_allow_html=True)
        else:
            grouped_items: dict[str, list[ProfileItem]] = {}
            for item in active_items:
                grouped_items.setdefault(item.item_type, []).append(item)

            for group_name, group_items in grouped_items.items():
                with st.expander(f"{group_name.title()} · {len(group_items)} items", expanded=group_name in {"experience", "project"}):
                    for index, item in enumerate(group_items, start=1):
                        with st.container(border=True):
                            st.markdown(f"**{index}. {item.title or 'Untitled item'}**")
                            st.markdown(f'<div class="apple-minor-copy">{item.organization or "Organization not specified"} · {item.verification_status.title()}</div>', unsafe_allow_html=True)
                            with st.form(key=f"profile-edit-form-{item.id}"):
                                meta_col1, meta_col2 = st.columns(2, gap="large")
                                with meta_col1:
                                    edited_type = st.selectbox(
                                        "Item Type",
                                        PROFILE_ITEM_TYPES,
                                        index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                                        key=f"profile-edit-type-{item.id}",
                                    )
                                    edited_title = st.text_input(
                                        "Title",
                                        value=item.title,
                                        placeholder="Role, project, certification, or activity name",
                                        key=f"profile-edit-title-{item.id}",
                                    )
                                with meta_col2:
                                    edited_org = st.text_input(
                                        "Organization",
                                        value=item.organization,
                                        placeholder="Company, school, club, or organization",
                                        key=f"profile-edit-org-{item.id}",
                                    )
                                    edited_location = st.text_input(
                                        "Location",
                                        value=item.location,
                                        placeholder="Optional location",
                                        key=f"profile-edit-location-{item.id}",
                                    )

                                edited_description = st.text_area(
                                    "Description",
                                    value=item.description,
                                    height=100,
                                    placeholder="What happened here and why does it matter?",
                                    key=f"profile-edit-description-{item.id}",
                                )
                                edited_bullets = st.text_area(
                                    "Achievement Bullets",
                                    value="\n".join(item.bullets),
                                    height=120,
                                    placeholder="One bullet per line.",
                                    key=f"profile-edit-bullets-{item.id}",
                                )
                                edited_skills = st.text_input(
                                    "Skills / Keywords",
                                    value=", ".join(item.skills or item.keywords),
                                    placeholder="SQL, operations, leadership, Tableau",
                                    key=f"profile-edit-skills-{item.id}",
                                )

                                action_col1, action_col2, action_col3 = st.columns([1, 1, 1], gap="large")
                                with action_col1:
                                    save_pressed = st.form_submit_button("Save Changes", use_container_width=True)
                                with action_col2:
                                    verify_pressed = st.form_submit_button("Verify", use_container_width=True)
                                with action_col3:
                                    archive_pressed = st.form_submit_button("Archive", use_container_width=True)

                            if save_pressed or verify_pressed:
                                updated_item = ProfileItem(
                                    id=item.id,
                                    user_id=item.user_id,
                                    profile_id=item.profile_id,
                                    source_id=item.source_id,
                                    item_type=edited_type,
                                    title=edited_title.strip(),
                                    organization=edited_org.strip(),
                                    location=edited_location.strip(),
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
                                update_profile_item(updated_item)
                                if verify_pressed and item.verification_status != "verified":
                                    update_profile_item_verification(item.id, "verified")
                                st.rerun()

                            if archive_pressed:
                                archive_profile_item(item.id)
                                st.rerun()

            if archived_items:
                with st.expander(f"Archived Items · {len(archived_items)}", expanded=False):
                    st.markdown('<div class="apple-minor-copy">Archived items stay in memory but are not used as active profile evidence.</div>', unsafe_allow_html=True)
                    for item in archived_items:
                        row_col1, row_col2 = st.columns([4, 1], gap="large")
                        with row_col1:
                            st.markdown(f"**{item.title or 'Untitled item'}**")
                            st.markdown(f'<div class="apple-minor-copy">{item.item_type.title()} · {item.organization or "Organization not specified"}</div>', unsafe_allow_html=True)
                        with row_col2:
                            if secondary_button("Restore", use_container_width=True, key=f"profile-restore-{item.id}"):
                                archive_profile_item(item.id, visibility="active")
                                st.rerun()

    col1, col2, col3, col4 = st.columns(4, gap="large")
    with col1:
        if secondary_button("Import More Materials", use_container_width=True, key="profile-dashboard-import"):
            st.session_state.screen = "profile_import"
            st.rerun()
    with col2:
        if secondary_button("Add Profile Item", use_container_width=True, key="profile-dashboard-add-item"):
            st.session_state.screen = "profile_add_item"
            st.rerun()
    with col3:
        if secondary_button("Match Profile to Job", use_container_width=True, key="profile-dashboard-match"):
            st.session_state.screen = "application_match"
            st.rerun()
    with col4:
        if secondary_button("Build Resume", use_container_width=True, key="profile-dashboard-build-resume"):
            _start_profile_draft_flow()
            st.session_state.screen = "builder_input"
            st.rerun()
    extra_cols = st.columns(2, gap="large")
    with extra_cols[0]:
        if primary_button("Job Tracker", use_container_width=True, key="profile-dashboard-workspace"):
            st.session_state.screen = "job_tracker"
            st.rerun()
    with extra_cols[1]:
        if secondary_button("Back to Home", use_container_width=True, key="profile-dashboard-home"):
            st.session_state.screen = "landing"
            st.rerun()
    render_shell_end()


def render_profile_add_item_screen() -> None:
    """Manually add a reusable item to the career profile."""
    render_shell_start()
    profile = create_or_get_profile()
    render_screen_intro(
        "complete",
        "Add to Career Profile",
        "Create a reusable profile item.",
        "Add a new experience, project, skill section, certification, or other evidence you want the app to remember.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Manual Entry</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Add a section you can reuse later.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">This is useful when you want to add something from memory, a recent project, or an experience that was not captured during onboarding or import.</div>',
            unsafe_allow_html=True,
        )

        with st.form("profile-manual-add-form"):
            meta_col1, meta_col2 = st.columns(2, gap="large")
            with meta_col1:
                item_type = st.selectbox("Item Type", PROFILE_ITEM_TYPES, index=0)
                title = st.text_input("Title", placeholder="Example: Supply Chain Intern")
                organization = st.text_input("Organization", placeholder="Company, school, club, or team")
                location = st.text_input("Location", placeholder="Optional location")
            with meta_col2:
                start_date = st.text_input("Start Date", placeholder="Jun 2024")
                end_date = st.text_input("End Date", placeholder="Aug 2024")
                is_current = st.checkbox("Ongoing / current", value=False)
                confidence_score = st.slider("Confidence", min_value=0.5, max_value=1.0, value=0.85, step=0.05)

            description = st.text_area("Description", height=120, placeholder="What happened here and why does it matter?")
            bullets = st.text_area("Achievement Bullets", height=140, placeholder="One bullet per line")
            skills = st.text_input("Skills / Keywords", placeholder="Excel, SQL, stakeholder management, analytics")

            action_col1, action_col2 = st.columns(2, gap="large")
            with action_col1:
                cancel_pressed = st.form_submit_button("Back to Profile", use_container_width=True)
            with action_col2:
                add_pressed = st.form_submit_button("Save Profile Item", use_container_width=True)

        if cancel_pressed:
            st.session_state.screen = "profile"
            st.rerun()

        if add_pressed:
            new_item = ProfileItem(
                profile_id=profile.id,
                item_type=item_type,
                title=title.strip(),
                organization=organization.strip(),
                location=location.strip(),
                start_date=start_date.strip(),
                end_date=end_date.strip(),
                is_current=is_current,
                description=description.strip(),
                bullets=_split_line_input(bullets),
                skills=_split_csv_input(skills),
                keywords=_split_csv_input(skills)[:12],
                confidence_score=float(confidence_score),
                verification_status="verified",
                visibility="active",
            )
            save_profile_items([new_item])
            st.session_state.screen = "profile"
            st.rerun()

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
            if secondary_button("Back to Upload", use_container_width=True, key="application-match-back-input"):
                _clear_tracker_linkage()
                st.session_state.screen = "input"
                st.rerun()
        with right_col:
            if secondary_button("Open Profile Dashboard", use_container_width=True, key="application-match-profile-dashboard"):
                st.session_state.screen = "profile_dashboard"
                st.rerun()
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
        if secondary_button("Back", use_container_width=True, key="application-match-back"):
            _clear_tracker_linkage()
            st.session_state.screen = "input"
            st.rerun()
    with optimize_col:
        if primary_button("Optimize Existing Resume", use_container_width=True, key="application-match-continue", disabled=not (selected_ids and resume_loaded)):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_optimize")
            st.session_state.show_fit_details = False
            _evaluate_current_resume_fit(force=True)
            st.session_state.screen = "fit_report"
            st.rerun()
    with draft_col:
        if secondary_button("Create Draft from Profile", use_container_width=True, key="application-match-draft", disabled=not selected_ids):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_draft")
            _start_profile_draft_flow()
            st.rerun()
    render_shell_end()


def render_application_workspace_screen() -> None:
    """Saved jobs / application workspaces."""
    render_shell_start()
    applications = list_applications()
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

    for application in applications:
        with st.container(border=True):
            title = application.job_title or "Untitled target role"
            company_suffix = f" at {application.company}" if application.company else ""
            st.markdown('<div class="apple-kicker">Saved Application</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{title}{company_suffix}</div>', unsafe_allow_html=True)
            rows = [
                ("Company", application.company or "Not set"),
                ("Industry", application.industry or "Not detected"),
                ("Status", application.status.replace("_", " ").title()),
                ("Selected evidence", str(len(application.selected_profile_item_ids))),
                ("Updated", application.updated_at),
            ]
            st.markdown(build_readiness_rows(rows), unsafe_allow_html=True)
            preview = " ".join(application.job_description.split())[:320]
            if preview:
                st.markdown(f'<div class="apple-section-copy">{preview}{"..." if len(preview) == 320 else ""}</div>', unsafe_allow_html=True)

            action_col1, action_col2, action_col3 = st.columns(3, gap="large")
            with action_col1:
                if primary_button("Open Evidence Match", use_container_width=True, key=f"application-open-match-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "application_match"
                    st.rerun()
            with action_col2:
                if secondary_button("Optimize / Run", use_container_width=True, key=f"application-open-mode-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "mode" if st.session_state.resume_text else "application_match"
                    st.rerun()
            with action_col3:
                if secondary_button("Create Profile Draft", use_container_width=True, key=f"application-open-draft-{application.id}", disabled=not application.selected_profile_item_ids):
                    _load_application_into_session(application.id)
                    _start_profile_draft_flow()
                    st.rerun()

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        if secondary_button("Back to Profile", use_container_width=True, key="application-workspace-profile"):
            st.session_state.screen = "profile"
            st.rerun()
    with col2:
        if secondary_button("Add Job / Upload", use_container_width=True, key="application-workspace-input"):
            _clear_tracker_linkage()
            st.session_state.screen = "input"
            st.rerun()
    with col3:
        if secondary_button("Home", use_container_width=True, key="application-workspace-home"):
            st.session_state.screen = "landing"
            st.rerun()
    render_shell_end()


def render_input_screen() -> None:
    """Resume and job input screen (redesigned for simplicity)."""
    local_ai_selected = st.session_state.get("optimization_path") == "local_ai" or st.session_state.get("execution_mode") == "local_ai"
    local_ai_ready = st.session_state.get("local_ai_ready", False)

    def maybe_process_job_description_with_local_ai() -> None:
        """Enrich the cleaned JD with Local AI signals when enabled."""
        if not local_ai_selected or not local_ai_ready:
            return
        try:
            cleaned_text = (st.session_state.get("jd_cleaning_result") or {}).get("cleaned_text", "")
            with st.spinner("Local AI is reading the job description and building a role brief. This can take a few seconds."):
                signals = process_job_description(
                    raw_job_description=st.session_state.job_description,
                    cleaned_job_description=cleaned_text,
                    model_name=_get_local_ai_model_name(),
                    base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                )
            st.session_state.local_ai_job_signals = signals
            st.session_state.local_ai_last_job_meta = get_last_task_meta("process_job_description")
            if signals.get("normalized_role_title"):
                st.session_state.target_role = signals["normalized_role_title"]
            if signals.get("industry_hint"):
                st.session_state.target_industry = signals["industry_hint"]
            if signals.get("seniority") in CAREER_STAGES:
                st.session_state.career_stage = signals["seniority"]
        except Exception as error:
            logger.warning("Local AI JD processing failed: %s", error)

    def fetch_and_store_job_description(job_input: str) -> bool:
        """Fetch, clean, and store JD text from a pasted URL."""
        try:
            with st.spinner("Validating link and extracting the job description..."):
                extracted_text, final_url, role_hint = fetch_job_description_from_url(job_input)
            cleaning_result = clean_job_description(extracted_text)
            cleaned_text = cleaning_result["cleaned_text"]
            # A newly processed JD should not inherit the prior application's identity.
            st.session_state.current_application_id = None
            st.session_state.current_application_company = ""
            st.session_state.target_role = ""
            st.session_state.target_industry = ""
            st.session_state.job_description = cleaned_text
            st.session_state.pending_job_description_input = cleaned_text
            st.session_state.jd_source_url = final_url
            st.session_state.jd_cleaning_result = cleaning_result
            st.session_state.jd_role_hint = role_hint or detect_role_title(cleaned_text)
            st.session_state.target_role = st.session_state.jd_role_hint
            st.session_state.target_industry = detect_industry(cleaned_text)
            detected_company = detect_company_name(cleaned_text)
            if detected_company:
                st.session_state.current_application_company = detected_company
            st.session_state.local_ai_job_signals = {}
            maybe_process_job_description_with_local_ai()
            st.success("Job description extracted and cleaned successfully. Review the text below before continuing.")
            return True
        except Exception as error:
            st.warning(f"{error} Please paste the job description text manually if the page blocks extraction.")
            return False

    def clean_pasted_job_description(job_input: str) -> bool:
        """Normalize manually pasted JD text so downstream detection is cleaner."""
        cleaned_result = clean_job_description(job_input)
        cleaned_text = cleaned_result["cleaned_text"]
        st.session_state.current_application_id = None
        st.session_state.current_application_company = ""
        st.session_state.target_role = ""
        st.session_state.target_industry = ""
        st.session_state.job_description = cleaned_text
        st.session_state.pending_job_description_input = cleaned_text
        st.session_state.jd_source_url = ""
        st.session_state.jd_cleaning_result = cleaned_result
        st.session_state.jd_role_hint = detect_role_title(cleaned_text)
        st.session_state.target_role = st.session_state.jd_role_hint
        st.session_state.target_industry = detect_industry(cleaned_text)
        detected_company = detect_company_name(cleaned_text)
        if detected_company:
            st.session_state.current_application_company = detected_company
        st.session_state.local_ai_job_signals = {}
        maybe_process_job_description_with_local_ai()
        st.success("Job description cleaned and ready. Review the text below before continuing.")
        return True

    render_shell_start()
    render_screen_intro(
        "input",
        "Step 1 of 5",
        "Bring in your resume. Then point it at the role you want.",
        "We'll clean the job description, detect the signals that matter, and keep the next step simple.",
    )

    upload_col, jd_col = st.columns([1, 1.15], gap="large")
    with upload_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Upload your resume</div>
                <div class="apple-section-copy">Use a <code>.docx</code> or <code>.pdf</code> file. We preserve the document structure so the finished export still feels like your original resume, just sharper.</div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader("Upload Resume (.docx or .pdf)", type=["docx", "pdf"], label_visibility="collapsed")
            if uploaded_file is not None:
                save_uploaded_resume(uploaded_file)
                st.success(f"Loaded `{uploaded_file.name}`")
                chips = [uploaded_file.name, "Ready for optimization"]
                if local_ai_selected:
                    chips.append("Private Mode")
                render_chip_row(chips)

            if st.session_state.resume_text and local_ai_selected:
                st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
                if local_ai_ready:
                    if secondary_button("Extract Profile in Private Mode", use_container_width=True, key="input-local-ai-profile"):
                        try:
                            profile = create_or_get_profile()
                            with st.spinner("Local AI is extracting reusable profile evidence from your resume. This may take 10-20 seconds."):
                                profile_result = extract_or_create_profile(
                                    resume_text=st.session_state.resume_text or "",
                                    existing_profile_summary=profile.summary,
                                    model_name=_get_local_ai_model_name(),
                                    base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                                )
                            st.session_state.local_ai_last_profile_meta = get_last_task_meta("extract_or_create_profile")
                            suggestion_count = _save_local_ai_profile_suggestions(profile_result)
                            st.success(f"Prepared {suggestion_count} profile suggestions.")
                            st.session_state.screen = "profile_review"
                            st.rerun()
                        except Exception as error:
                            st.warning(f"Private Mode could not extract profile suggestions yet. {error}")
                    st.caption("Heads up: Private Mode tasks can take a few seconds. Wait for the loading message before clicking elsewhere.")
                else:
                    if secondary_button("Set Up Private Mode", use_container_width=True, key="input-local-ai-setup-upload"):
                        st.session_state.screen = "local_ai_setup"
                        st.rerun()

    with jd_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Paste a job description or link</div>
                <div class="apple-section-copy">Use the full posting or a job link. We'll turn it into a cleaner brief for the next step and surface the role signals automatically.</div>
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
                "<div class=\"apple-minor-copy\">We'll clean the text, detect the target role, and prepare the prompt inputs for you.</div>",
                unsafe_allow_html=True,
            )
            if local_ai_selected and local_ai_ready:
                st.caption("Private Mode is on for this run. After cleanup, Gemma 4 will also generate a job brief with role, skills, and prioritization signals.")
            if secondary_button("Process Job Description", use_container_width=True, key="input-process-jd"):
                current_input = st.session_state.get("job_description_input", job_description)
                if looks_like_url(current_input):
                    if fetch_and_store_job_description(current_input):
                        st.rerun()
                elif current_input.strip():
                    if clean_pasted_job_description(current_input):
                        st.rerun()
                else:
                    st.info("Paste a job description or job link first.")
            st.caption("This step may take a few seconds when Private Mode is active.")

            if local_ai_selected and st.session_state.get("local_ai_job_signals"):
                signals = st.session_state.local_ai_job_signals
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Detected role", signals.get("normalized_role_title", "Unknown")),
                            ("Seniority", signals.get("seniority", "Unknown")),
                            ("Industry", signals.get("industry_hint", "Unknown")),
                            ("Priority skills", ", ".join(signals.get("required_skills", [])[:4]) or "Not available yet"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )

    st.session_state.job_description = job_description
    if st.session_state.jd_role_hint and not st.session_state.target_role.strip():
        st.session_state.target_role = st.session_state.jd_role_hint

    col1, col2, col3 = st.columns([0.7, 0.9, 1.1], gap="large")
    with col1:
        if secondary_button("Back", use_container_width=True, key="input-back"):
            st.session_state.screen = "landing"
            st.rerun()
    with col2:
        active_profile_items = [item for item in list_profile_items() if item.visibility == "active"]
        if secondary_button("Use Career Profile", use_container_width=True, disabled=not bool(job_description.strip() and active_profile_items), key="input-use-profile"):
            st.session_state.use_career_profile = True
            st.session_state.screen = "application_match"
            st.rerun()
    with col3:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
        )
        if primary_button("Continue", use_container_width=True, disabled=not can_continue, key="input-continue"):
            if local_ai_selected and not local_ai_ready:
                st.session_state.screen = "local_ai_setup"
                st.rerun()
            # Auto-enable profile context when the user has active profile items.
            # They can still override this on the mode screen if needed.
            active_profile_items_for_continue = [item for item in list_profile_items() if item.visibility == "active"]
            if active_profile_items_for_continue:
                st.session_state.use_career_profile = True
                st.session_state.selected_profile_item_ids = [item.id for item in active_profile_items_for_continue]
            else:
                st.session_state.use_career_profile = False
                st.session_state.selected_profile_item_ids = []
            st.session_state.show_fit_details = False
            if looks_like_url(job_description):
                if fetch_and_store_job_description(job_description):
                    st.rerun()
            else:
                st.session_state.jd_cleaning_result = None
                _evaluate_current_resume_fit(force=True)
                st.session_state.screen = "mode"
                st.rerun()
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
                "Keyword Gain",
                int(after_report.get("keyword_score", 0)) - int(before_report.get("keyword_score", 0)),
                "Job-language movement",
            )

        readiness_rows = [
            ("Keyword score", f"{before_report.get('keyword_score', 0)} → {after_report.get('keyword_score', 0)}"),
            ("Skill score", f"{before_report.get('skill_score', 0)} → {after_report.get('skill_score', 0)}"),
            ("ATS / clarity", f"{before_report.get('ats_score', 0)} → {after_report.get('ats_score', 0)}"),
            ("New matched keywords", ", ".join(new_keyword_matches[:6]) if new_keyword_matches else "No new keyword wins yet"),
        ]
        st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

        if delta <= 0:
            st.caption("Honest take: this revision may still need stronger evidence or sharper job-language alignment before it is truly better.")


def render_fit_report_screen() -> None:
    """Pre-optimization match report with match % circle and key signals (redesigned)."""
    report = _evaluate_current_resume_fit()
    score = report.get("overall_score", 0)
    local_ai_selected = st.session_state.get("optimization_path") == "local_ai" or st.session_state.get("execution_mode") == "local_ai"

    # Get match band label — use CSS variables so dark mode colours apply correctly
    if score >= 85:
        band = "EXCELLENT MATCH"
        band_color = "var(--green)"
    elif score >= 70:
        band = "STRONG MATCH"
        band_color = "var(--green)"
    elif score >= 50:
        band = "FAIR MATCH"
        band_color = "var(--amber)"
    else:
        band = "POOR MATCH"
        band_color = "var(--danger)"

    # Extract key signals
    signals = extract_key_signals(
        st.session_state.resume_text,
        st.session_state.job_description
    )

    job_title = get_effective_target_role(st.session_state.job_description) or "This role"
    company = st.session_state.get("current_application_company", "").strip()

    logger.info(
        "Pre-optimization match shown: score=%s, job_title=%s, company=%s, signals=%s",
        score,
        job_title,
        company or "Unknown",
        len(signals.get("matches", [])) + len(signals.get("gaps", []))
    )

    render_shell_start()
    render_screen_intro(
        "fit_report",
        "Step 2 of 5",
        "Answer the big question first: should you apply?",
        "We show your match score and the key signals. Start with the recommendation, then decide whether to optimize.",
    )

    # Match % Circle Display - Centered
    st.markdown(f"""
    <div style="text-align: center; margin: 1.5rem 0;">
        <div style="position: relative; width: 180px; height: 180px; margin: 0 auto; display: inline-block;">
            <svg width="180" height="180" viewBox="0 0 180 180" style="transform: rotate(-90deg);">
                <circle cx="90" cy="90" r="80" fill="none" stroke="var(--line-strong)" stroke-width="16"/>
                <circle cx="90" cy="90" r="80" fill="none" stroke="{band_color}" stroke-width="16"
                        stroke-dasharray="{score * 1.676} 502.6" stroke-linecap="round"/>
            </svg>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
                <div style="font-size: 48px; font-weight: bold; color: var(--text);">{score}%</div>
                <div style="font-size: 12px; color: var(--muted); margin-top: 0.25rem;">{band}</div>
            </div>
        </div>
    </div>

    <div style="text-align: center; margin: 1rem 0 2rem 0;">
        <div style="font-size: 16px; font-weight: 600; color: var(--text);">{job_title}{f" at {company}" if company else ""}</div>
    </div>
    """, unsafe_allow_html=True)

    # ===== SINGLE UNIFIED INSIGHT BOX =====
    matches = signals.get("matches", [])

    if score >= 80:
        recommendation = "Strong fit"
        motivation = "Your resume aligns well with what they're looking for. You're a solid candidate."
        color = "var(--green)"
        potential_low = max(score, 85)
        potential_high = min(score + 8, 99)
    elif score >= 60:
        recommendation = "Fair fit"
        motivation = "You have the core experience. With focused optimization, you could be competitive."
        color = "var(--amber)"
        potential_low = score + 5
        potential_high = score + 15
    else:
        recommendation = "Weak fit"
        motivation = "There's a gap, but optimization can help bridge it. Consider whether this aligns with your goals."
        color = "var(--danger)"
        potential_low = min(score + 8, 60)
        potential_high = min(score + 20, 75)

    with st.container(border=True):
        # Recommendation header
        st.markdown(f"""
        <div style="padding-bottom: 1rem; margin-bottom: 1rem; border-bottom: 1px solid var(--line);">
            <div style="display: inline-block; padding: 0.4rem 0.9rem; background: {color}; color: var(--surface); border-radius: 20px; font-weight: 600; font-size: 12px; text-transform: uppercase; margin-right: 0.75rem;">
                {recommendation}
            </div>
            <span style="font-size: 14px; color: var(--muted);">{motivation}</span>
        </div>
        """, unsafe_allow_html=True)

        # Why it matches
        if matches:
            st.markdown('<div style="font-size: 12px; color: var(--muted-light); text-transform: uppercase; font-weight: 600; margin-bottom: 0.5rem;">Why It Matches</div>', unsafe_allow_html=True)
            for match in matches[:3]:
                signal = match.get("signal", "")
                strength = match.get("strength", "moderate")

                if strength == "strong":
                    label = "Strong"
                    color_badge = "var(--green)"
                elif strength == "moderate":
                    label = "Relevant"
                    color_badge = "var(--blue)"
                else:
                    label = "Minor"
                    color_badge = "var(--muted)"

                st.markdown(f'<div style="margin-bottom: 0.5rem; font-size: 13px;"><span style="color: {color_badge}; font-weight: 600;">{label}</span> — {signal}</div>', unsafe_allow_html=True)

            st.markdown('<div style="height: 0.75rem;"></div>', unsafe_allow_html=True)

        # Optimization potential
        st.markdown(f"""
        <div style="padding: 1rem; background: var(--surface-muted); border-radius: 20px; border-left: 3px solid {color};">
            <div style="font-size: 12px; color: var(--muted-light); text-transform: uppercase; font-weight: 600; margin-bottom: 0.5rem;">Optimization Potential</div>
            <div style="font-size: 13px; color: var(--muted); margin-bottom: 0.75rem;">By aligning your language with their priorities, typically improves matches like this by:</div>
            <div style="font-size: 20px; font-weight: bold; color: {color}; text-align: center; margin: 0.75rem 0;">+{potential_high - score}% to +{potential_high - score + 5}%</div>
            <div style="font-size: 12px; color: var(--muted); text-align: center;">Could reach <strong>{potential_low}–{potential_high}%</strong></div>
        </div>
        """, unsafe_allow_html=True)

    # Save to Profile Prompt (if user doesn't have profile yet)
    active_items = list_profile_items()
    if not active_items and st.session_state.resume_text:
        st.markdown("<div style='margin: 2rem 0;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">💾 Build Your Profile</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Keep this experience forever</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Extract your profile from this resume so you never have to upload it again. Build future resumes faster using your saved profile.</div>',
                unsafe_allow_html=True,
            )

            save_to_profile_col1, save_to_profile_col2 = st.columns(2, gap="large")
            with save_to_profile_col1:
                if primary_button("Save to Profile", use_container_width=True, key="fit-save-to-profile"):
                    # Extract profile data from current resume
                    try:
                        basics, items = extract_profile_items_from_text(st.session_state.resume_text)
                        st.session_state.profile_extracted_basics = basics
                        st.session_state.profile_extracted_items = [item.to_dict() for item in items]
                        st.session_state.screen = "profile_review"
                        logger.info("User initiated save to profile from fit_report: %d items extracted", len(items))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to extract profile: {str(e)}")
                        logger.error("Profile extraction failed: %s", e)
            with save_to_profile_col2:
                if secondary_button("Later", use_container_width=True, key="fit-save-later"):
                    pass  # Just dismiss the prompt

    # Action Buttons
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    action_col1, action_col2 = st.columns(2, gap="large")

    with action_col1:
        if secondary_button("Back to Upload", use_container_width=True, key="fit-back"):
            logger.info("User returned to upload from fit_report: score=%s", score)
            _clear_tracker_linkage()
            st.session_state.screen = "input"
            st.rerun()

    with action_col2:
        if local_ai_selected:
            button_text = "Continue in Private Mode"
        else:
            button_text = "See Details" if score < 50 else "Optimize Now"
        if primary_button(button_text, use_container_width=True, key="fit-optimize"):
            logger.info("User proceeding to optimization: score=%s, button=%s", score, button_text)
            if local_ai_selected and st.session_state.get("local_ai_ready", False):
                st.session_state.screen = "local_ai_run"
            elif local_ai_selected:
                st.session_state.screen = "local_ai_setup"
            else:
                st.session_state.screen = "mode"
            st.rerun()

    render_shell_end()


def render_builder_input_screen() -> None:
    """Student-friendly first-resume intake flow."""
    render_shell_start()
    _seed_builder_from_profile()
    render_screen_intro(
        "builder_input",
        "Step 1 of 5",
        "Build your first resume.",
        "Tell us about yourself once. We will use this to draft your resume now and grow your profile for future applications.",
    )

    basics_col, extras_col = st.columns(2, gap="large")
    with basics_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">About You</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Share the essentials once.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">This single intake acts like onboarding and resume setup at the same time. We will use it to personalize the draft and save a reusable profile foundation.</div>',
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
            st.markdown('<div class="apple-kicker">Goals & Extras</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Add direction so the draft feels intentional.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">This helps the app understand what kind of opportunities you want and what should stand out on the page.</div>',
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
        if secondary_button("Back", use_container_width=True, key="builder-back"):
            st.session_state.screen = "landing"
            st.rerun()
    with col2:
        can_continue = bool(full_name.strip() and education.strip() and experience_dump.strip() and target_role.strip())
        if primary_button("Generate Builder Prompt", use_container_width=True, disabled=not can_continue, key="builder-generate-prompt"):
            _save_builder_profile_snapshot(
                full_name=full_name,
                contact_info=contact_info,
                education=education,
                experience_dump=experience_dump,
                activities=activities,
                skills=skills,
                career_stage=career_stage,
                target_role=target_role,
            )
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
            st.session_state.screen = "builder_stub"
            st.rerun()
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

    _b_show_private = show_local_ai_cards()
    _b_cols = st.columns(3 if _b_show_private else 2, gap="large")
    _b_idx = 0

    with _b_cols[_b_idx]:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Manual</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Copy the prompt and use your favorite AI.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Best if you want to compare outputs, stay in control, or use ChatGPT, Claude, or Gemini directly.</div>',
                unsafe_allow_html=True,
            )
            if secondary_button("Use Manual Mode", use_container_width=True, key="builder-use-manual"):
                st.session_state.builder_execution_mode = "manual"
                st.rerun()
    _b_idx += 1

    if _b_show_private:
        with _b_cols[_b_idx]:
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">100% Private</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-choice-title">Run it on this device.</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="apple-choice-copy">Best if you want the draft to stay on your computer. The app uses Gemma 4 privately and still validates everything before review.</div>',
                    unsafe_allow_html=True,
                )
                button_wrapper = "apple-primary" if st.session_state.get("local_ai_ready", False) else "apple-secondary"
                st.markdown(f'<div class="{button_wrapper}">', unsafe_allow_html=True)
                if st.button("Use Private Mode", use_container_width=True, key="builder-use-local-ai"):
                    st.session_state.builder_execution_mode = "local_ai"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        _b_idx += 1

    with _b_cols[_b_idx]:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Standard</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Use a cloud provider.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Best if you want the fastest hosted option using OpenAI, Anthropic, Gemini, or another supported provider.</div>',
                unsafe_allow_html=True,
            )
            if secondary_button("Use Full AI Optimization", use_container_width=True, key="builder-use-api"):
                st.session_state.builder_execution_mode = "api"
                st.rerun()

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
            if secondary_button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-manual"):
                st.session_state.screen = "builder_input"
                st.rerun()
        with col2:
            if primary_button("Validate Builder Output", use_container_width=True, key="builder-validate-output-manual"):
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
        with col3:
            if secondary_button("Back to Landing", use_container_width=True, key="builder-back-landing-manual"):
                st.session_state.screen = "landing"
                st.rerun()
    elif builder_mode == "local_ai":
        model_name = _get_local_ai_model_name()

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Private Builder</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Generate your first resume privately on this device.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">We will use your notes, target role, and optional job description to draft a structured first resume, then validate it before review.</div>',
                unsafe_allow_html=True,
            )
            readiness_rows = builder_rows + [
                ("Private mode", "Ready" if st.session_state.get("local_ai_ready", False) else "Setup needed"),
                ("Model", model_name),
            ]
            st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

            if not st.session_state.get("local_ai_ready", False):
                st.info("Finish the private on-device setup first, then come back here to generate your draft.")

            with st.expander("Builder Prompt Preview", expanded=False):
                st.text_area(
                    "Builder Prompt Preview",
                    value=st.session_state.builder_prompt,
                    height=240,
                    disabled=True,
                    key="builder-prompt-preview-local-ai",
                )

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            if secondary_button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-local-ai"):
                st.session_state.screen = "builder_input"
                st.rerun()
        with col2:
            if secondary_button("Set Up Private Mode", use_container_width=True, key="builder-local-ai-setup"):
                st.session_state.screen = "local_ai_setup"
                st.rerun()
        with col3:
            if primary_button("Generate in Private Mode", use_container_width=True, key="builder-run-local-ai", disabled=not st.session_state.get("local_ai_ready", False)):
                try:
                    with st.spinner("Private mode is drafting your first resume..."):
                        payload = draft_first_resume(
                            full_name=st.session_state.builder_full_name,
                            contact_info=st.session_state.builder_contact_info,
                            education=st.session_state.builder_education,
                            experience_dump=st.session_state.builder_experience_dump,
                            activities=st.session_state.builder_activities,
                            skills=st.session_state.builder_skills,
                            job_description=st.session_state.builder_job_description,
                            career_stage=st.session_state.career_stage,
                            target_role=st.session_state.target_role or "the target role",
                            model_name=model_name,
                            base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                        )
                    st.session_state.local_ai_last_builder_meta = get_last_task_meta("draft_first_resume")
                    st.session_state.builder_payload = payload
                    st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                    st.session_state.builder_output_docx_bytes = None
                    st.session_state.builder_output_filename = None
                    st.session_state.screen = "builder_review"
                    st.rerun()
                except Exception as error:
                    st.error(str(error))

    elif builder_mode == "api":
        if st.session_state.selected_provider not in PROVIDER_CONFIG:
            st.session_state.selected_provider = "OpenAI"

        api_key = ""
        base_url = ""
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">API Setup</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Choose a hosted provider or advanced connection.</div>', unsafe_allow_html=True)

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

            if provider == "Advanced Custom Endpoint":
                base_url = st.text_input(
                    "Base URL",
                    value=st.session_state.custom_api_base_url,
                    placeholder="http://localhost:11434/v1",
                    help="Use the base URL for your custom OpenAI-compatible endpoint.",
                    key="builder-base-url",
                )
                model = st.text_input(
                    "Model name",
                    value=st.session_state.custom_api_model,
                    placeholder="mistral",
                    help="Use the exact model name exposed by your custom endpoint.",
                    key="builder-model-local",
                )
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    value=st.session_state.custom_api_key,
                    placeholder=provider_config["placeholder"],
                    help="Leave blank if your endpoint does not require a key.",
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
        if provider == "Advanced Custom Endpoint":
            api_rows.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
        else:
            api_rows.append(("API key", "Provided" if api_key.strip() else "Missing"))

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
            st.markdown(build_readiness_rows(api_rows), unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            if secondary_button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-api"):
                st.session_state.screen = "builder_input"
                st.rerun()
        with col2:
            if primary_button("Run Builder via API", use_container_width=True, key="builder-run-api"):
                try:
                    _bp = st.progress(0)
                    _bs = st.empty()
                    for _pct, _msg in [(15, "Preparing resume structure..."), (35, "Sending to AI..."), (55, "Building your first resume...")]:
                        _bp.progress(_pct)
                        _bs.caption(_msg)
                        time.sleep(0.3)
                    payload = optimize_with_provider(
                        provider=provider,
                        api_key=api_key,
                        prompt=st.session_state.builder_prompt,
                        model=model,
                        base_url=base_url,
                    )
                    for _pct, _msg in [(80, "Formatting output..."), (100, "Done!")]:
                        _bp.progress(_pct)
                        _bs.caption(_msg)
                        time.sleep(0.25)
                    _bp.empty()
                    _bs.empty()
                    st.session_state.builder_payload = payload
                    st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                    st.session_state.builder_output_docx_bytes = None
                    st.session_state.builder_output_filename = None
                    st.session_state.screen = "builder_review"
                    st.rerun()
                except Exception as error:
                    _bp.empty()  # type: ignore[possibly-undefined]
                    _bs.empty()  # type: ignore[possibly-undefined]
                    st.error(str(error))
        with col3:
            if secondary_button("Back to Landing", use_container_width=True, key="builder-back-landing-api"):
                st.session_state.screen = "landing"
                st.rerun()
    else:
        st.markdown(
            '<div class="apple-minor-copy" style="margin-top:0.35rem;">Choose a run mode above to continue.</div>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2, gap="large")
        with col1:
            if secondary_button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-preselect"):
                st.session_state.screen = "builder_input"
                st.rerun()
        with col2:
            if secondary_button("Back to Landing", use_container_width=True, key="builder-back-landing-preselect"):
                st.session_state.screen = "landing"
                st.rerun()
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

    _summary_text = payload.get("summary", "")
    if _summary_text:
        st.markdown(
            f'<div class="builder-preview-block">'
            f'<div class="builder-preview-label">Professional Summary</div>'
            f'<div class="builder-preview-body">{_summary_text}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    _education_items = payload.get("education", [])
    if _education_items:
        with st.expander("Education", expanded=True):
            for item in _education_items:
                _meta = " · ".join(filter(None, [
                    item.get("school", ""),
                    item.get("degree", ""),
                    item.get("graduation_date", ""),
                ]))
                st.markdown(f"**{_meta}**" if _meta else "**Education entry**")
                if item.get("details"):
                    _bullets_md = "\n".join(f"- {d}" for d in item["details"] if d.strip())
                    st.markdown(_bullets_md)

    _experience_items = payload.get("experience", [])
    if _experience_items:
        with st.expander("Experience", expanded=True):
            for item in _experience_items:
                _title = item.get("title", "")
                _org = item.get("organization", "")
                _loc = item.get("location", "")
                _dates = item.get("dates", "")
                _meta = " · ".join(filter(None, [_org, _loc, _dates]))
                st.markdown(f"**{_title}**" if _title else "**Role**")
                if _meta:
                    st.caption(_meta)
                if item.get("bullets"):
                    _bullets_md = "\n".join(f"- {b}" for b in item["bullets"] if b.strip())
                    st.markdown(_bullets_md)

    _projects = payload.get("projects", [])
    if _projects:
        with st.expander("Projects", expanded=False):
            for item in _projects:
                st.markdown(f"**{item.get('name', 'Project')}**")
                if item.get("details"):
                    _bullets_md = "\n".join(f"- {d}" for d in item["details"] if d.strip())
                    st.markdown(_bullets_md)

    _skills = payload.get("skills", [])
    if _skills:
        with st.expander("Skills", expanded=False):
            st.markdown(build_inline_chip_row(_skills), unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    _render_task_meta_card("Local AI Builder", st.session_state.get("local_ai_last_builder_meta", {}))

    col1, col2 = st.columns(2)
    with col1:
        if secondary_button("Back to Builder Prompt", use_container_width=True, key="builder-review-back-prompt"):
            st.session_state.screen = "builder_stub"
            st.rerun()
    with col2:
        if primary_button("Generate Resume .docx", use_container_width=True, key="builder-generate-docx"):
            try:
                st.session_state.builder_output_docx_bytes = build_resume_from_scratch(payload)
                safe_name = (basics.get("full_name", "First_Resume").strip() or "First_Resume").replace(" ", "_")
                st.session_state.builder_output_filename = f"{safe_name}_Resume.docx"
                st.success("First resume document generated successfully.")
            except Exception as error:
                st.error(str(error))

    if st.session_state.builder_output_docx_bytes and st.session_state.builder_output_filename:
        primary_download_button(
            "Download First Resume (.docx)",
            data=io.BytesIO(st.session_state.builder_output_docx_bytes),
            file_name=st.session_state.builder_output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    if secondary_button("Back to Landing", use_container_width=True, key="builder-review-landing"):
        st.session_state.screen = "landing"
        st.rerun()
    render_shell_end()


def render_mode_screen() -> None:
    """Execution mode selection screen focused on user intent."""
    render_shell_start()
    render_screen_intro(
        "mode",
        "Step 3 of 5",
        "Choose how you'd like to work.",
        "Pick the path that feels easiest. You can run everything privately on this device, use a standard cloud provider, or keep everything manual.",
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

    _show_private = show_local_ai_cards()
    _mode_cols = st.columns(3 if _show_private else 2, gap="large")
    _col_idx = 0

    if _show_private:
        with _mode_cols[_col_idx]:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div class="apple-kicker">Recommended</div>
                    </div>
                    <div class="apple-choice-title">100% Private (On Your Device)</div>
                    <div class="apple-choice-copy">Private, guided, and beginner-friendly. The app will help you set up {DEFAULT_LOCAL_AI_LABEL} on this computer and keep your resume work local.</div>
                    """,
                    unsafe_allow_html=True,
                )
                if primary_button("Use Private Mode", use_container_width=True, key="mode-local-ai"):
                    logger.info("User selected private mode")
                    st.session_state.execution_mode = "local_ai"
                    st.session_state.optimization_path = "local_ai"
                    st.session_state.screen = "local_ai_setup"
                    st.rerun()
        _col_idx += 1

    with _mode_cols[_col_idx]:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-kicker">Recommended</div>
                <div class="apple-choice-title">Full AI Optimization</div>
                <div class="apple-choice-copy">Use your OpenAI, Anthropic, or Gemini API key. Save it once and it auto-fills every run.</div>
                """,
                unsafe_allow_html=True,
            )
            if primary_button("Use Full AI Optimization", use_container_width=True, key="mode-api"):
                logger.info("User selected hosted API mode")
                st.session_state.execution_mode = "api"
                st.session_state.optimization_path = "fast_start"
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "api"
                st.rerun()
    _col_idx += 1

    with _mode_cols[_col_idx]:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-kicker">Manual</div>
                <div class="apple-choice-title">Bring your own AI tool</div>
                <div class="apple-choice-copy">Copy the prompt into ChatGPT, Claude, Gemini, or another tool, then paste the result back for validation and review.</div>
                """,
                unsafe_allow_html=True,
            )
            if secondary_button("Manual", use_container_width=True, key="mode-manual"):
                logger.info("User selected manual mode")
                st.session_state.execution_mode = "manual"
                st.session_state.optimization_path = "manual"
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "manual"
                st.rerun()

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

    back_col = st.columns([1])[0]
    with back_col:
        if secondary_button("Back", use_container_width=True, key="mode-back"):
            _clear_tracker_linkage()
            st.session_state.screen = "input"
            st.rerun()
    render_shell_end()


def render_local_ai_setup_screen() -> None:
    """Guided setup for first-time Local AI users."""
    render_shell_start()
    render_screen_intro(
        "mode",
        "Step 4 of 5",
        "Set up Local AI once.",
        "This keeps your resume work on your computer. We’ll guide you through the one-time setup and check that everything is ready.",
    )

    model_name = _get_local_ai_model_name()
    base_url = st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL)
    status = check_ollama_status(base_url=base_url)
    model_installed = status["reachable"] and is_model_installed(model_name, base_url=base_url)
    stored_status = st.session_state.get("local_ai_setup_status", {})
    if stored_status.get("ready") and not (status["reachable"] and model_installed):
        st.session_state.local_ai_ready = False
        st.session_state.local_ai_setup_status = {}
        stored_status = {}

    intro_rows = [
        ("Privacy", "Your setup runs on this computer"),
        ("Recommended model", DEFAULT_LOCAL_AI_LABEL),
        ("One-time setup", "Install Ollama, then download the AI model"),
    ]
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">What this does</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">A private AI assistant for resume work.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">You only need to do this once. After setup, the app can process job descriptions, suggest profile items, and draft resume improvements without asking you to use Terminal.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(build_readiness_rows(intro_rows), unsafe_allow_html=True)

    if not status["reachable"]:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Step 1</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">Install Ollama on {get_platform_label()}.</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-copy">To run Local AI privately on your device, first install the free Ollama engine. When that is finished, come back here and click <strong>Check Setup</strong>.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(f"[Download Ollama]({get_ollama_download_url()})")
    else:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Engine Status</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Local AI engine found.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Great. The app can talk to Ollama on this computer. Next we’ll make sure the recommended AI model is available.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                build_readiness_rows(
                    [
                        ("Local AI engine", "Ready"),
                        ("Recommended model", "Installed" if model_installed else "Needs download"),
                    ]
                ),
                unsafe_allow_html=True,
            )

    if status["reachable"] and not model_installed:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Step 2</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Download the recommended AI model.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">This is a one-time download. Depending on your connection, it may take a few minutes.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Download AI Model", use_container_width=True, key="local-ai-download-model"):
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                try:
                    last_percent = 0
                    for event in pull_model_stream(model_name, base_url=base_url):
                        percent = event.get("percent")
                        if isinstance(percent, int):
                            last_percent = percent
                            progress_bar.progress(percent)
                        status_placeholder.info(
                            f"{event.get('status', 'Downloading model')} {f'({last_percent}%)' if last_percent else ''}"
                        )
                    progress_bar.progress(100)
                    readiness = run_readiness_check(model_name=model_name, base_url=base_url)
                    st.session_state.local_ai_ready = readiness.get("ready", False)
                    st.session_state.local_ai_setup_status = readiness
                    if readiness.get("ready"):
                        st.success("Local AI is ready.")
                    else:
                        st.warning(readiness.get("message", "The model finished downloading, but the final check needs another try."))
                    st.rerun()
                except Exception as error:
                    st.session_state.local_ai_ready = False
                    st.session_state.local_ai_setup_status = {"ready": False, "message": str(error)}
                    st.error(f"Model download failed. {error}")

    if status["reachable"] and model_installed:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Step 3</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Check setup.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Run a quick readiness check before continuing to Local AI tasks.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Check Setup", use_container_width=True, key="local-ai-check-setup"):
                readiness = run_readiness_check(model_name=model_name, base_url=base_url)
                st.session_state.local_ai_ready = readiness.get("ready", False)
                st.session_state.local_ai_setup_status = readiness
                st.rerun()

    if stored_status:
        if stored_status.get("ready"):
            st.success(stored_status.get("message", "Local AI is ready."))
        else:
            st.warning(stored_status.get("message", "Local AI still needs attention before it can run."))

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        if secondary_button("Back", use_container_width=True, key="local-ai-setup-back"):
            st.session_state.screen = "mode"
            st.rerun()
    with col2:
        if secondary_button("Use Full AI Optimization Instead", use_container_width=True, key="local-ai-setup-fallback"):
            st.session_state.execution_mode = "api"
            st.session_state.optimization_path = "fast_start"
            st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
            st.session_state.api_prompt_customized = False
            st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
            st.session_state.screen = "api"
            st.rerun()
    with col3:
        if primary_button("Continue with Local AI", use_container_width=True, key="local-ai-setup-continue", disabled=not st.session_state.get("local_ai_ready", False)):
            st.session_state.screen = "local_ai_run"
            st.rerun()
    render_shell_end()


def render_local_ai_run_screen() -> None:
    """Run the guided Local AI tasks and draft an optimized payload."""
    if not st.session_state.get("local_ai_ready", False):
        st.session_state.screen = "local_ai_setup"
        st.rerun()

    render_shell_start()
    render_screen_intro(
        "review",
        "Step 5 of 5",
        "Use Private Mode with guardrails.",
        "Run the helpful parts automatically, then review everything before you download your resume.",
    )

    model_name = _get_local_ai_model_name()
    job_signals = st.session_state.get("local_ai_job_signals", {})
    signal_summary = summarize_job_signals_for_ui(job_signals)
    _render_task_meta_card("Local AI Job Brief", st.session_state.get("local_ai_last_job_meta", {}))
    _render_task_meta_card("Local AI Profile Suggestions", st.session_state.get("local_ai_last_profile_meta", {}))

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Private Mode Status</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Private Mode is ready.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">This guided path can cleanly interpret the job description, suggest profile items from your resume, and draft resume improvements that still pass through the existing validation and review flow.</div>',
            unsafe_allow_html=True,
        )
        readiness_rows = [
            ("Private mode", "Ready"),
            ("Model", model_name),
            ("Resume", "Loaded" if st.session_state.resume_text else "Missing"),
            ("Job description", "Loaded" if st.session_state.job_description.strip() else "Missing"),
        ]
        if signal_summary:
            readiness_rows.append(("Current job brief", signal_summary))
        st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

    task_col1, task_col2 = st.columns(2, gap="large")
    with task_col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Task 1</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Process the job description.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Turn the posting into a cleaner role brief with key responsibilities, skills, and prioritization signals.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Refresh Job Brief", use_container_width=True, key="local-ai-process-jd"):
                try:
                    cleaned_text = (st.session_state.get("jd_cleaning_result") or {}).get("cleaned_text", "")
                    with st.spinner("Private Mode is refreshing your job brief. This can take a few seconds."):
                        signals = process_job_description(
                            raw_job_description=st.session_state.job_description,
                            cleaned_job_description=cleaned_text,
                            model_name=model_name,
                            base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                        )
                    st.session_state.local_ai_job_signals = signals
                    st.session_state.local_ai_last_job_meta = get_last_task_meta("process_job_description")
                    if signals.get("normalized_role_title"):
                        st.session_state.target_role = signals["normalized_role_title"]
                    if signals.get("industry_hint"):
                        st.session_state.target_industry = signals["industry_hint"]
                    if signals.get("seniority") in CAREER_STAGES:
                        st.session_state.career_stage = signals["seniority"]
                    st.success("Job brief updated.")
                    st.rerun()
                except Exception as error:
                    st.warning(_humanize_local_ai_error(error, "Job description processing"))
            st.caption("Wait for the loading message to finish before continuing.")

            if job_signals:
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Role", job_signals.get("normalized_role_title", "Unknown")),
                            ("Seniority", job_signals.get("seniority", "Unknown")),
                            ("Industry", job_signals.get("industry_hint", "Unknown")),
                            ("Priority skills", ", ".join(job_signals.get("required_skills", [])[:4]) or "Not available yet"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )

    with task_col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Task 2</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Suggest profile items from your resume.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Use your current resume to create reusable profile evidence you can review before saving.</div>',
                unsafe_allow_html=True,
            )
            if st.button("Extract Profile Suggestions", use_container_width=True, key="local-ai-extract-profile"):
                try:
                    profile = create_or_get_profile()
                    with st.spinner("Private Mode is extracting profile suggestions from your resume. This may take 10-20 seconds."):
                        profile_result = extract_or_create_profile(
                            resume_text=st.session_state.resume_text or "",
                            existing_profile_summary=profile.summary,
                            model_name=model_name,
                            base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                        )
                    st.session_state.local_ai_last_profile_meta = get_last_task_meta("extract_or_create_profile")
                    suggestion_count = _save_local_ai_profile_suggestions(profile_result)
                    st.session_state.local_ai_profile_error = ""
                    st.success(f"Prepared {suggestion_count} profile items for review.")
                except Exception as error:
                    st.session_state.local_ai_profile_error = _humanize_local_ai_error(error, "Profile extraction")
            st.caption("Profile extraction can take a little longer than job processing.")
            if st.session_state.get("local_ai_profile_error"):
                st.warning(st.session_state.local_ai_profile_error)

            if st.session_state.get("profile_extracted_items"):
                st.markdown(
                    build_readiness_rows(
                        [
                            ("Suggested items", str(len(st.session_state.profile_extracted_items))),
                            ("Headline", st.session_state.get("local_ai_profile_headline", "") or "Generated"),
                            ("Summary", "Ready" if st.session_state.get("local_ai_profile_summary", "") else "Not generated"),
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                if secondary_button("Review Profile Suggestions", use_container_width=True, key="local-ai-open-profile-review"):
                    st.session_state.screen = "profile_review"
                    st.rerun()

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Task 3</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Draft resume improvements.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">When you run this, Private Mode drafts the resume changes and the app immediately validates them before opening the usual review screen.</div>',
            unsafe_allow_html=True,
        )

        preview_rows = [
            ("Role target", job_signals.get("normalized_role_title") or st.session_state.target_role or "Using your current job description"),
            ("Industry hint", job_signals.get("industry_hint") or st.session_state.target_industry or "Will infer from job description"),
            ("Career stage", job_signals.get("seniority") if job_signals.get("seniority") in CAREER_STAGES else st.session_state.career_stage),
            ("Saved profile guidance", "On" if st.session_state.get("use_career_profile") and _get_selected_profile_items() else "Off"),
        ]
        st.markdown(build_readiness_rows(preview_rows), unsafe_allow_html=True)

        action_col1, action_col2, action_col3 = st.columns(3, gap="large")
        with action_col1:
            if secondary_button("Back", use_container_width=True, key="local-ai-run-back"):
                st.session_state.screen = "local_ai_setup"
                st.rerun()
        with action_col2:
            if secondary_button("Use Full AI Optimization Instead", use_container_width=True, key="local-ai-run-fallback"):
                st.session_state.execution_mode = "api"
                st.session_state.optimization_path = "fast_start"
                st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
                st.session_state.api_prompt_customized = False
                st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                st.session_state.screen = "api"
                st.rerun()
        with action_col3:
            if primary_button("Draft Resume Improvements", use_container_width=True, key="local-ai-run-draft"):
                try:
                    _lai_progress = st.progress(0)
                    _lai_status = st.empty()

                    current_job_signals = st.session_state.get("local_ai_job_signals", {})
                    if not current_job_signals:
                        cleaned_text = (st.session_state.get("jd_cleaning_result") or {}).get("cleaned_text", "")
                        _lai_progress.progress(10)
                        _lai_status.caption("Preparing job brief...")
                        with st.spinner("Private Mode is preparing the job brief first."):
                            current_job_signals = process_job_description(
                                raw_job_description=st.session_state.job_description,
                                cleaned_job_description=cleaned_text,
                                model_name=model_name,
                                base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                            )
                        st.session_state.local_ai_job_signals = current_job_signals
                        st.session_state.local_ai_last_job_meta = get_last_task_meta("process_job_description")

                    _lai_progress.progress(35)
                    _lai_status.caption("Analyzing resume and keywords...")
                    time.sleep(0.3)
                    _lai_progress.progress(55)
                    _lai_status.caption("Drafting resume improvements (this may take 10–30 s)...")

                    with st.spinner("Private Mode is drafting resume improvements and validating them. This may take 10-30 seconds."):
                        payload = draft_resume_improvements(
                            resume_text=st.session_state.resume_text or "",
                            job_description=st.session_state.job_description or "",
                            career_stage=current_job_signals.get("seniority") if current_job_signals.get("seniority") in CAREER_STAGES else st.session_state.career_stage,
                            target_role=current_job_signals.get("normalized_role_title") or get_effective_target_role(st.session_state.job_description),
                            target_industry=current_job_signals.get("industry_hint") or get_effective_industry(st.session_state.job_description),
                            profile_context=_build_profile_context(_get_selected_profile_items()) if st.session_state.get("use_career_profile") else "",
                            model_name=model_name,
                            base_url=st.session_state.get("local_ai_base_url", OLLAMA_BASE_URL),
                        )
                    st.session_state.local_ai_last_draft_meta = get_last_task_meta("draft_resume_improvements")
                    st.session_state.local_ai_draft_error = ""
                    _lai_progress.progress(90)
                    _lai_status.caption("Validating changes...")
                    time.sleep(0.3)
                    _lai_progress.progress(100)
                    _lai_status.caption("Done!")
                    time.sleep(0.2)
                    _lai_progress.empty()
                    _lai_status.empty()
                    handle_validated_payload(payload)
                    st.rerun()
                except Exception as error:
                    _lai_progress.empty()  # type: ignore[possibly-undefined]
                    _lai_status.empty()    # type: ignore[possibly-undefined]
                    st.session_state.local_ai_draft_error = _humanize_local_ai_error(error, "Resume drafting")
        st.caption("Drafting is the longest Private Mode step. Let it finish before clicking again.")
        if st.session_state.get("local_ai_draft_error"):
            st.warning(st.session_state.local_ai_draft_error)
            st.info("You can retry, switch to Full AI Optimization, or use Manual Mode if you want more control.")

    render_shell_end()


def handle_validated_payload(payload: dict) -> None:
    """Store validation state and move to review."""
    baseline_report = st.session_state.baseline_fit_report or _evaluate_current_resume_fit(force=True)
    optimized_resume_text = _build_optimized_resume_text(payload)
    replacements = collect_replacements(payload)
    logger.info(
        "Optimization started: replacements=%s, resume=%s",
        len(replacements),
        st.session_state.resume_name or "unknown",
    )
    st.session_state.optimized_fit_report = evaluate_resume_fit(
        optimized_resume_text,
        st.session_state.job_description or "",
        selected_profile_items=_get_selected_profile_items(),
    )

    baseline_keyword_score = int(baseline_report.get("keyword_score", 0))
    baseline_score = int(baseline_report.get("overall_score", 0))
    optimized_keyword_score = int((st.session_state.optimized_fit_report or {}).get("keyword_score", 0))
    optimized_score = int((st.session_state.optimized_fit_report or {}).get("overall_score", 0))
    if optimized_score < baseline_score or optimized_keyword_score < baseline_keyword_score:
        degradation_reasons = []
        if optimized_score < baseline_score:
            degradation_reasons.append(f"overall match score dropped from {baseline_score}% to {optimized_score}%")
        if optimized_keyword_score < baseline_keyword_score:
            degradation_reasons.append(
                f"keyword alignment dropped from {baseline_keyword_score} to {optimized_keyword_score}"
            )
        logger.warning(
            "Optimization failed quality gate: overall=%d->%d, keyword=%d->%d",
            baseline_score,
            optimized_score,
            baseline_keyword_score,
            optimized_keyword_score,
        )
        raise ValueError(
            "The AI draft did not improve the resume yet: "
            + "; ".join(degradation_reasons)
            + ". Retry to get a stronger draft."
        )

    st.session_state.baseline_fit_report = baseline_report
    st.session_state.validated_payload = payload
    st.session_state.validation_summary = build_validation_summary(payload)
    st.session_state.review_details = analyze_payload(payload)
    st.session_state.output_docx_bytes = None
    st.session_state.output_filename = None
    st.session_state.show_review_changes = False
    st.session_state.optimization_change_examples = build_change_examples(
        st.session_state.review_details.get("results", []),
        limit=3,
    )
    st.session_state.optimization_metrics_summary = build_optimization_metrics_summary(
        baseline_report,
        st.session_state.optimized_fit_report or {},
    )

    # Calculate match scores and save optimization result for history
    match_score_before = int(baseline_report.get("overall_score", 0))
    match_score_after = int((st.session_state.optimized_fit_report or {}).get("overall_score", 0))

    # Generate improvements summary
    improvements = generate_improvements_summary(
        optimized_replacements=collect_replacements(payload) if isinstance(payload, dict) else [],
        jd_text=st.session_state.job_description or "",
        max_improvements=5,
        min_impact="high"
    )

    # Save to optimization history database
    _opt_title   = get_fresh_detected_target_role(st.session_state.job_description)
    _opt_company = st.session_state.get("current_application_company", "").strip()
    try:
        _saved_application_id = save_optimization_result(
            user_id=st.session_state.get("auth_user_id") or "local-user",
            company_name=_opt_company or "Unknown",
            job_title=_opt_title or "Unknown",
            job_description=st.session_state.job_description or "",
            match_before=match_score_before,
            match_after=match_score_after,
            improvements=improvements,
            resume_used_id="",
            application_id=st.session_state.get("current_application_id"),
        )
        st.session_state.current_application_id = _saved_application_id
    except Exception as e:
        logger.warning("Failed to save optimization result: %s", str(e))
        _saved_application_id = st.session_state.get("current_application_id")

    # Job Tracker integration — decide whether to auto-save or show save card
    _active_tracker_job = st.session_state.get("active_tracker_job_id")
    if _active_tracker_job:
        # Optimize Again flow: silently append the run to the existing tracker job
        try:
            from job_tracker_store import (
                add_optimization_run as _jt_add_run,
                get_job as _jt_get_job,
                update_job_metadata as _jt_update_job,
            )
            _existing_job = _jt_get_job(_active_tracker_job) or {}
            _metadata_updates = {}
            if (st.session_state.job_description or "").strip():
                _metadata_updates["jd_text"] = st.session_state.job_description
            if _opt_title and not (_existing_job.get("job_title") or "").strip():
                _metadata_updates["job_title"] = _opt_title
            if _opt_company and not (_existing_job.get("company") or "").strip():
                _metadata_updates["company"] = _opt_company
            if _metadata_updates:
                _jt_update_job(_active_tracker_job, **_metadata_updates)
            _jt_add_run(
                job_id=_active_tracker_job,
                match_before=match_score_before,
                match_after=match_score_after,
                improvements=improvements,
            )
            st.session_state.tracker_auto_saved_to = _active_tracker_job
        except Exception as e:
            logger.warning("Failed to auto-save tracker run: %s", e)
        st.session_state.tracker_pending_save = None
    elif st.session_state.get("current_application_id"):
        try:
            from job_tracker_store import (
                add_optimization_run as _jt_add_run,
                get_job as _jt_get_job,
                update_job_metadata as _jt_update_job,
            )
            _existing_job = _jt_get_job(st.session_state.current_application_id) or {}
            _metadata_updates = {}
            if (st.session_state.job_description or "").strip():
                _metadata_updates["jd_text"] = st.session_state.job_description
            if _opt_title:
                _metadata_updates["job_title"] = _opt_title
            if _opt_company:
                _metadata_updates["company"] = _opt_company
            if _metadata_updates:
                _jt_update_job(st.session_state.current_application_id, **_metadata_updates)
            _jt_add_run(
                job_id=st.session_state.current_application_id,
                match_before=match_score_before,
                match_after=match_score_after,
                improvements=improvements,
            )
            st.session_state.tracker_auto_saved_to = st.session_state.current_application_id
        except Exception as e:
            logger.warning("Failed to attach optimization to existing application: %s", e)
        st.session_state.tracker_pending_save = None
    else:
        # Fresh optimization: stash data so the review screen can show the save card
        st.session_state.tracker_pending_save = {
            "match_before":     match_score_before,
            "match_after":      match_score_after,
            "improvements":     improvements,
            "prefill_title":    _opt_title,
            "prefill_company":  _opt_company,
            "jd_text":          st.session_state.job_description or "",
        }
        st.session_state.tracker_auto_saved_to = None

    logger.info(
        "Optimization completed: replacements=%s, before_fit=%s, after_fit=%s",
        len(replacements),
        match_score_before,
        match_score_after,
    )
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
              --instruction-bg: #181b1f;
              --instruction-border: rgba(255,255,255,0.08);
              --instruction-title: #f5f5f7;
              --instruction-copy: #b0b3ba;
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
                "Copy the prompt above and paste it into ChatGPT, Claude, or Gemini. Include the same resume you uploaded in the box.",
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
        if secondary_button("Back", use_container_width=True, key="manual-back"):
            st.session_state.screen = "mode"
            st.rerun()
    with col2:
        if primary_button("Validate Output", use_container_width=True, key="manual-validate-output"):
            try:
                payload = parse_replacement_payload(pasted_output)
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))


def render_api_screen() -> None:
    """Multi-provider API mode screen."""
    render_screen_intro(
        "api",
        "Step 4 of 5",
        "Fast Start",
        "Use your own hosted provider or an advanced custom endpoint. The app validates the output before export.",
    )

    if not st.session_state.api_prompt_override and st.session_state.generated_prompt:
        st.session_state.api_prompt_override = st.session_state.generated_prompt
    if st.session_state.selected_provider not in PROVIDER_CONFIG:
        st.session_state.selected_provider = "OpenAI"

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

        if provider == "Advanced Custom Endpoint":
            with st.expander("Advanced Custom Endpoint", expanded=False):
                st.markdown(
                    '<div class="apple-section-copy">Use this only if you already have a custom OpenAI-compatible endpoint. For the guided local experience, go back and choose <strong>Use Local AI</strong>.</div>',
                    unsafe_allow_html=True,
                )
                base_url = st.text_input(
                    "Base URL",
                    value=st.session_state.custom_api_base_url,
                    placeholder="http://localhost:11434/v1",
                    help="Use the base URL for your custom OpenAI-compatible endpoint.",
                )
                model = st.text_input(
                    "Model name",
                    value=st.session_state.custom_api_model,
                    placeholder="mistral",
                    help="Use the exact model name exposed by your endpoint.",
                )
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    value=st.session_state.custom_api_key,
                    placeholder=provider_config["placeholder"],
                    help="Leave blank if your endpoint does not require a key.",
                )
                st.session_state.custom_api_base_url = base_url
                st.session_state.custom_api_model = model
                st.session_state.custom_api_key = api_key
                st.caption("If this path returns malformed JSON, retry once or use Manual Mode.")
        else:
            # ── Per-provider saved key logic ──────────────────────────
            _is_hosted_auth = is_hosted_web() and is_authenticated()
            _key_info: dict = {"last4": "", "valid": False}
            _saved_key_val = ""
            _api_settings: dict = {}
            if _is_hosted_auth:
                try:
                    from supabase_settings_store import (
                        get_provider_api_key,
                        get_provider_key_info,
                        get_user_settings,
                    )
                    _key_info = get_provider_key_info(provider)
                    _api_settings = get_user_settings()
                    if _key_info.get("last4"):
                        _saved_key_val = get_provider_api_key(provider)
                except Exception:
                    pass

            # Reset change-key mode when provider changes
            if st.session_state.get("_api_last_provider") != provider:
                st.session_state["_api_last_provider"] = provider
                st.session_state["_api_chg_mode"] = False

            _has_saved = bool(_key_info.get("last4"))
            _in_chg_mode = bool(st.session_state.get("_api_chg_mode"))

            if _has_saved and not _in_chg_mode:
                # Show saved key status pill
                _valid = _key_info.get("valid", False)
                _dot_color = "#2d9b5a" if _valid else "#b45309"
                _status_label = "Verified" if _valid else "Not tested"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:0.75rem;'
                    f'padding:0.75rem 1rem;background:#f9fafb;border:1px solid #e5e7eb;'
                    f'border-radius:10px;margin:0.25rem 0 0.5rem;">'
                    f'<span style="font-size:0.8rem;color:#6b7280;font-weight:500;">'
                    f'{provider_config["key_label"]}</span>'
                    f'<code style="font-size:0.9rem;font-weight:600;color:#111827;">'
                    f'····{_key_info["last4"]}</code>'
                    f'<span style="font-size:0.75rem;color:{_dot_color};font-weight:500;">'
                    f'● {_status_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Change key", key="api-chg-key"):
                    st.session_state["_api_chg_mode"] = True
                    st.rerun()
                api_key = _saved_key_val
                _save_key_on_run = False
            else:
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    placeholder=provider_config["placeholder"],
                )
                _save_key_on_run = (
                    st.checkbox(
                        "Save to my account for future runs",
                        value=True,
                        key="api-save-key-cb",
                        help="Stored encrypted. Remove anytime in Settings → AI Settings.",
                    )
                    if _is_hosted_auth
                    else False
                )
                if _has_saved:
                    if st.button("Cancel", key="api-cancel-chg"):
                        st.session_state["_api_chg_mode"] = False
                        st.rerun()
                _note = (
                    "Saved encrypted to your account. Remove anytime in Settings."
                    if (_is_hosted_auth and _save_key_on_run)
                    else "Key used only for this session and not stored."
                )
                st.markdown(
                    f'<div class="apple-section-copy">{_note}</div>',
                    unsafe_allow_html=True,
                )

            # Model — pre-select saved preference
            _models = provider_config["models"]
            _saved_model = _api_settings.get("default_model", _models[0])
            _model_idx = _models.index(_saved_model) if _saved_model in _models else 0
            model = st.selectbox("Model", _models, index=_model_idx)

            # Stash for Run button handler
            st.session_state["_api_save_key_on_run"] = _save_key_on_run
            st.session_state["_api_run_key"] = api_key
            st.session_state["_api_run_model"] = model

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
    if provider == "Advanced Custom Endpoint":
        checklist.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
    else:
        checklist.append(("API key", "Provided" if api_key.strip() else "Missing"))
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
        st.markdown(build_readiness_rows(checklist), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        if secondary_button("Back", use_container_width=True, key="api-back"):
            st.session_state.screen = "mode"
            st.rerun()
    with col2:
        if primary_button("Run Optimization", use_container_width=True, key="api-run-optimization"):
            try:
                # Save key if user opted in (first-time entry)
                if (
                    provider != "Advanced Custom Endpoint"
                    and st.session_state.get("_api_save_key_on_run")
                    and api_key.strip()
                ):
                    try:
                        from supabase_settings_store import save_provider_api_key
                        save_provider_api_key(provider, model, api_key.strip())
                        st.session_state["_api_chg_mode"] = False
                        st.session_state["_api_save_key_on_run"] = False
                    except Exception:
                        pass

                _progress = st.progress(0)
                _status = st.empty()
                _opt_stages = [
                    (12, "Analyzing resume structure..."),
                    (28, "Matching job description keywords..."),
                    (48, "Sending prompt to the AI..."),
                ]
                for _pct, _msg in _opt_stages:
                    _progress.progress(_pct)
                    _status.caption(_msg)
                    time.sleep(0.35)

                payload = optimize_with_provider(
                    provider=provider,
                    api_key=api_key,
                    prompt=prompt_to_send,
                    model=model,
                    base_url=base_url,
                )

                for _pct, _msg in [(72, "Processing AI response..."), (88, "Validating changes..."), (100, "Done!")]:
                    _progress.progress(_pct)
                    _status.caption(_msg)
                    time.sleep(0.25)

                _progress.empty()
                _status.empty()
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                _progress.empty()  # type: ignore[possibly-undefined]
                _status.empty()    # type: ignore[possibly-undefined]
                st.error(str(error))
    with col3:
        if secondary_button("Switch to Manual Mode", use_container_width=True, key="api-switch-manual"):
            st.session_state.execution_mode = "manual"
            st.session_state.screen = "manual"
            st.rerun()


def render_review_screen() -> None:
    """Validation and export screen - simplified with focus on score improvement."""
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
    change_examples = st.session_state.get("optimization_change_examples", [])
    metrics_summary = st.session_state.get("optimization_metrics_summary", [])
    target_job_title = get_effective_target_role(st.session_state.job_description) or "your target role"
    target_company = st.session_state.get("current_application_company", "").strip()
    before_score = int(baseline_report.get("overall_score", 0))
    after_score = int(optimized_report.get("overall_score", 0))
    score_delta = after_score - before_score
    summary_changes = int(stats.get("summary_replacements", 0))
    bullet_changes = int(stats.get("bullet_replacements", 0))
    skill_changes = int(stats.get("skills_replacements", 0))
    total_changes = summary_changes + bullet_changes + skill_changes
    strongest_metrics = [metric for metric in metrics_summary if int(metric.get("delta", 0)) > 0]
    review_attention_items: list[str] = []

    if ready_for_export and not st.session_state.output_docx_bytes:
        try:
            ensure_export_file_ready()
        except Exception as error:
            st.error(str(error))
            ready_for_export = False

    if manual_review_count:
        review_attention_items.append(
            "Take a screenshot of the points below and ask your AI to rewrite the output in the correct format."
        )
    if review_warnings:
        review_attention_items.extend(str(warning) for warning in review_warnings[:3] if str(warning).strip())
    if not ready_for_export and not review_attention_items:
        review_attention_items.append("This draft is not fully export-ready yet, so a manual review is still recommended.")

    render_screen_intro(
        "review",
        "Step 4 of 5",
        "Validation and Export",
        "Your optimized resume is ready. Download it or review the changes.",
    )

    if not st.session_state.show_review_changes:
        if ready_for_export:
            st.success("Optimization complete. Your resume is validated and ready to download.")
        else:
            st.warning("This result needs review before export.")

        if st.session_state.get("execution_mode") == "local_ai" or st.session_state.get("optimization_path") == "local_ai":
            _render_task_meta_card("Local AI Draft", st.session_state.get("local_ai_last_draft_meta", {}))

        if score_delta > 0:
            delta_color = "var(--green)"
            delta_label = "Improved"
        elif score_delta == 0:
            delta_color = "var(--amber)"
            delta_label = "Maintained"
        else:
            delta_color = "var(--danger)"
            delta_label = "Review Needed"

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Before and After</div>', unsafe_allow_html=True)
            headline_target = target_job_title
            if target_company:
                headline_target = f"{target_job_title} at {target_company}"
            st.markdown(
                f'<div class="apple-section-title">How this draft now lines up for {headline_target}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="apple-section-copy">Start with the score shift, then inspect the exact edits only if you want more detail.</div>',
                unsafe_allow_html=True,
            )

            cols = st.columns([1, 0.3, 1])
            with cols[0]:
                st.markdown(f'<div style="text-align: center;"><div style="font-size: 12px; color: var(--muted-light); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">Before</div><div style="font-size: 48px; font-weight: bold; color: var(--text);">{before_score}%</div></div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown('<div style="text-align: center; padding-top: 1.2rem; font-size: 24px; color: var(--muted);" aria-hidden="true">→</div>', unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f'<div style="text-align: center;"><div style="font-size: 12px; color: var(--muted-light); margin-bottom: 0.5rem; text-transform: uppercase; font-weight: 600;">After</div><div style="font-size: 48px; font-weight: bold; color: {delta_color};">{after_score}%</div></div>', unsafe_allow_html=True)

            st.markdown(
                f'<div class="apple-delta-bar" style="border-left-color: {delta_color};">'
                f'<span style="color: {delta_color}; font-weight: 600; font-size: 16px;" aria-label="Score change: {score_delta:+d} percent">{score_delta:+d}%</span>'
                f' <span style="color: var(--muted);">— {delta_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with st.container(border=True):
            if score_delta > 0:
                _why_kicker = "Why It Improved"
                _why_title = "What the optimizer strengthened"
            else:
                _why_kicker = "What Changed"
                _why_title = "How the optimizer repositioned this draft"
            st.markdown(f'<div class="apple-kicker">{_why_kicker}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{_why_title}</div>', unsafe_allow_html=True)

            if strongest_metrics:
                metric_cols = st.columns(min(3, len(strongest_metrics)), gap="large")
                for column, metric in zip(metric_cols, strongest_metrics[:3]):
                    delta = int(metric["delta"])
                    suffix = str(metric.get("suffix", "")).strip()
                    with column:
                        st.metric(
                            str(metric["label"]),
                            f"{metric['after']}",
                            f"{delta:+d} {suffix}".strip(),
                        )
            else:
                # Flat score — explain why and what to do next
                new_kw = [k for k in optimized_report.get("matched_keywords", [])
                          if k not in baseline_report.get("matched_keywords", [])]
                still_missing = optimized_report.get("missing_keywords", [])
                _flat_msg = (
                    "The automated score stayed flat — this resume already had strong keyword coverage "
                    "so the optimizer focused on clarity and phrasing. "
                )
                if still_missing:
                    _flat_msg += (
                        f"To push the score higher, run again with a prompt that emphasises: "
                        f"**{', '.join(still_missing[:6])}**."
                    )
                elif new_kw:
                    _flat_msg += f"The draft added {len(new_kw)} new keyword match{'es' if len(new_kw) != 1 else ''}: {', '.join(new_kw[:6])}."
                st.markdown(
                    f'<div class="apple-section-copy">{_flat_msg}</div>',
                    unsafe_allow_html=True,
                )

            if change_examples:
                st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
                example_cols = st.columns(min(2, len(change_examples)), gap="large")
                for column, example in zip(example_cols, change_examples[:2]):
                    with column:
                        with st.container(border=True):
                            st.caption(str(example["label"]))
                            st.markdown(f"**Before**  \n{example['before']}")
                            st.markdown(f"**After**  \n{example['after']}")

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">What Changed</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-title">A quick breakdown of the edits in this draft</div>',
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div style="text-align: center; padding: 1rem;"><div style="font-size: 24px; font-weight: bold; color: var(--text);">{summary_changes}</div><div style="font-size: 12px; color: var(--muted-light); margin-top: 0.25rem;">Summary edits</div></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div style="text-align: center; padding: 1rem;"><div style="font-size: 24px; font-weight: bold; color: var(--text);">{bullet_changes}</div><div style="font-size: 12px; color: var(--muted-light); margin-top: 0.25rem;">Bullet edits</div></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div style="text-align: center; padding: 1rem;"><div style="font-size: 24px; font-weight: bold; color: var(--text);">{skill_changes}</div><div style="font-size: 12px; color: var(--muted-light); margin-top: 0.25rem;">Skills edits</div></div>', unsafe_allow_html=True)

            st.caption(f"{total_changes} total edit(s) were proposed across your draft.")

        if review_attention_items:
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">What Needs Attention</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="apple-section-title">We found a few edits that need attention.</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="apple-section-copy">Your resume file is fine. A few of the AI-generated edits were unclear, so the app could not place them safely.</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="apple-section-copy">What to do next: ask the AI to rewrite those edits more clearly, then run it again. Take a screenshot of the points below and ask your AI to rewrite the output in correct format.</div>',
                    unsafe_allow_html=True,
                )

                for attention_item in review_attention_items:
                    st.markdown(f"- {attention_item}")

        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        action_col1, action_col2 = st.columns(2, gap="large")

        with action_col1:
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                render_coral_download_button(
                    "Download Resume",
                    data=st.session_state.output_docx_bytes,
                    file_name=st.session_state.output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                secondary_button("Download Resume", key="review-dl-disabled", use_container_width=True, disabled=True)

        with action_col2:
            if secondary_button("Inspect Exact Changes", use_container_width=True, key="review-inspect-changes"):
                logger.info("User opened detailed change review")
                st.session_state.show_review_changes = True
                st.rerun()

        # ===== Success confirmation strip =====
        st.markdown(
            """
            <style>
            @keyframes slideInBanner {
                from { opacity: 0; transform: translateY(8px); }
                to   { opacity: 1; transform: translateY(0); }
            }
            .resume-ready-banner {
                animation: slideInBanner 0.45s cubic-bezier(0.16,1,0.3,1) both;
                margin: 0.75rem 0 1rem;
            }
            </style>
            <div class="resume-ready-banner">
            <div style="
                background: linear-gradient(135deg, #d97757 0%, #c9683f 60%, #b85934 100%);
                border-radius: 14px;
                padding: 1.25rem 1.5rem;
                display: flex;
                align-items: center;
                gap: 1rem;
                flex-wrap: wrap;
                box-shadow: 0 4px 20px rgba(217,119,87,0.30);
            ">
                <span style="
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 2rem;
                    height: 2rem;
                    background: rgba(255,255,255,0.20);
                    border-radius: 50%;
                    flex-shrink: 0;
                    backdrop-filter: blur(4px);
                ">
                    <svg width="12" height="10" viewBox="0 0 12 10" fill="none">
                        <path d="M1.5 5L4.5 8L10.5 1.5" stroke="white" stroke-width="2.2"
                              stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </span>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 1rem; font-weight: 700; color: #fff; line-height: 1.3;">
                        Resume optimized and ready to download.
                    </div>
                </div>
                <div style="font-size: 0.82rem; color: rgba(255,255,255,0.85); white-space: nowrap; flex-shrink: 0;">
                    Found this useful?&nbsp;
                    <a href="https://buy.stripe.com/cNiaEZ4KwgLJdtA2C0dMI01" target="_blank"
                       style="color: #fff; font-weight: 700; text-decoration: none;
                              border-bottom: 1.5px solid rgba(255,255,255,0.55);
                              padding-bottom: 1px;">
                        Support development
                    </a>
                    &nbsp;·&nbsp;
                    <a href="https://resume-optimizer-otg.streamlit.app" target="_blank"
                       style="color: #fff; font-weight: 700; text-decoration: none;
                              border-bottom: 1.5px solid rgba(255,255,255,0.55);
                              padding-bottom: 1px;">
                        Share
                    </a>
                </div>
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Save to Job Tracker ────────────────────────────────────────────────
        _tracker_auto = st.session_state.get("tracker_auto_saved_to")
        _tracker_pending = st.session_state.get("tracker_pending_save")

        # ===== Bottom Actions =====
        bottom_spacer, bottom_col1, bottom_col2, bottom_col3, _ = st.columns([0.45, 1.6, 1.6, 1.6, 0.45], gap="medium")

        with bottom_col1:
            if _tracker_auto:
                if secondary_button("View in Tracker", key="review-view-tracker", use_container_width=True):
                    st.session_state.active_job_detail_id = _tracker_auto
                    st.session_state.screen = "job_detail"
                    st.rerun()

        with bottom_col2:
            if secondary_button("Start Over", use_container_width=True, key="review-start-over-summary"):
                logger.info("User started a new optimization from success state")
                reset_flow()
                st.rerun()

        with bottom_col3:
            if secondary_button("Back", use_container_width=True, key="review-back-summary"):
                previous_screen = "manual" if st.session_state.execution_mode == "manual" else "api"
                st.session_state.screen = previous_screen
                st.rerun()

        if _tracker_auto:
            st.markdown(
                """
                <div style="display:flex; align-items:center; gap:0.5rem;
                            font-size:0.85rem; color:#555; padding:0.5rem 0;">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="6.25" stroke="#22c55e" stroke-width="1.5"/>
                        <path d="M4.5 7L6 8.5L9.5 5" stroke="#22c55e" stroke-width="1.5"
                              stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    Saved to Job Tracker.
                </div>
                """,
                unsafe_allow_html=True,
            )

        elif _tracker_pending:
            st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">Job Tracker</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="apple-section-title">Save this to Job Tracker?</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="apple-section-copy" style="margin-bottom:1rem;">'
                    "Confirm the role and company so this application has a proper record."
                    "</div>",
                    unsafe_allow_html=True,
                )
                ts1, ts2 = st.columns(2)
                with ts1:
                    ts_title = st.text_input(
                        "Job Title",
                        value=_tracker_pending.get("prefill_title", ""),
                        key="review-tracker-title",
                        placeholder="e.g. Product Manager",
                    )
                with ts2:
                    ts_company = st.text_input(
                        "Company",
                        value=_tracker_pending.get("prefill_company", ""),
                        key="review-tracker-company",
                        placeholder="e.g. Acme Corp",
                    )
                ts3, ts4 = st.columns(2)
                with ts3:
                    ts_location = st.text_input(
                        "Location (optional)", key="review-tracker-location",
                        placeholder="e.g. New York, NY",
                    )
                with ts4:
                    ts_url = st.text_input(
                        "Job URL (optional)", key="review-tracker-url",
                        placeholder="https://…",
                    )
                ts_status = st.selectbox(
                    "Status",
                    ["Bookmarked", "Preparing", "Applied"],
                    index=1,   # default Preparing — they just optimized
                    key="review-tracker-status",
                )

                ta_col, tb_col, _ = st.columns([1.5, 1.5, 4])
                with ta_col:
                    can_save_tracker = bool(ts_title.strip() or ts_company.strip())
                    if primary_button(
                        "Save to Tracker", key="review-tracker-save",
                        use_container_width=True,
                        disabled=not can_save_tracker,
                    ):
                        try:
                            from job_tracker_store import (
                                add_job_manually as _jt_add_job,
                                add_optimization_run as _jt_add_run,
                            )
                            _new_jid = _jt_add_job(
                                job_title=ts_title.strip(),
                                company=ts_company.strip(),
                                location=ts_location.strip(),
                                job_url=ts_url.strip(),
                                jd_text=_tracker_pending.get("jd_text", ""),
                                status=ts_status,
                            )
                            _jt_add_run(
                                job_id=_new_jid,
                                match_before=_tracker_pending.get("match_before", 0),
                                match_after=_tracker_pending.get("match_after", 0),
                                improvements=_tracker_pending.get("improvements", []),
                            )
                            st.session_state.tracker_pending_save = None
                            st.session_state.tracker_auto_saved_to = _new_jid
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Could not save to tracker: {_e}")
                with tb_col:
                    if secondary_button("Not now", key="review-tracker-dismiss", use_container_width=True):
                        st.session_state.tracker_pending_save = None
                        st.rerun()

        if st.session_state.is_first_optimization and not _profile_setup_complete():
            st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
            st.markdown(
                """
                <div style="
                    border-left: 3px solid #1a1a1a;
                    padding: 1.1rem 1.25rem;
                    background: #fafafa;
                    border-radius: 0 8px 8px 0;
                ">
                    <div style="font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;
                                text-transform: uppercase; color: #888; margin-bottom: 0.4rem;">
                        One-time setup
                    </div>
                    <div style="font-size: 1rem; font-weight: 600; color: #1a1a1a; margin-bottom: 0.35rem;">
                        Make every future run stronger
                    </div>
                    <div style="font-size: 0.875rem; color: #555; line-height: 1.6;">
                        Save your experience once. The optimizer will draw on your full background
                        automatically — no copy-pasting between runs.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
            profile_col1, profile_col2 = st.columns([1, 1], gap="medium")
            with profile_col1:
                if primary_button("Set up Career Profile", use_container_width=True, key="success-build-profile"):
                    st.session_state.is_first_optimization = False
                    st.session_state.screen = "profile_welcome"
                    st.rerun()
            with profile_col2:
                if secondary_button("Maybe later", use_container_width=True, key="success-skip-profile"):
                    st.session_state.is_first_optimization = False
                    logger.info("User declined profile building prompt on first optimization")
        return

    # ===== DETAILED REVIEW MODE (show_review_changes = True) =====
    if st.button("Back to Summary", key="review-back-button"):
        logger.info("User returned from detailed review to success snapshot")
        st.session_state.show_review_changes = False
        st.rerun()

    st.subheader("Review All Changes")
    st.caption("Expand sections to see every edit.")

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
                on_click=lambda: logger.info(
                    "Optimized resume downloaded from detail view: filename=%s",
                    st.session_state.output_filename,
                ),
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
    logger.info("Streamlit app started")
    st.set_page_config(page_title="Resume OTG", layout="wide")
    init_session_state()

    # ── Auth gate (hosted web only) ──────────────────────────────────────────
    if is_hosted_web():
        st.session_state.hosted_web_mode = True
        load_auth_into_session()
        if not is_authenticated():
            apply_apple_theme()
            render_auth_screen()
            st.stop()

    init_profile_db()
    init_tracker_tables()
    handle_step_navigation_request()
    apply_apple_theme()

    # ── First-run detection ──────────────────────────────────────────────────
    # If onboarding hasn't been completed, redirect to the wizard before
    # rendering sidebar or routing — so a new user never sees the main app first.
    #
    # Grace condition: if the profile already has meaningful data (name + career
    # stage set, or prior sources exist), the user pre-dates the onboarding feature —
    # auto-complete it silently so they are never shown the wizard.
    _profile_for_ob = create_or_get_profile()
    if not _profile_for_ob.onboarding_complete:
        from profile_store import list_profile_sources as _lps, complete_onboarding as _co
        _has_existing_data = bool(
            (_profile_for_ob.full_name.strip() and _profile_for_ob.career_stage.strip())
            or _lps()
        )
        if _has_existing_data:
            # Existing user — silently mark done, never show the wizard
            _co()
        elif st.session_state.get("screen") != "onboarding":
            st.session_state.screen = "onboarding"
            st.rerun()

    _in_onboarding = st.session_state.get("screen") == "onboarding"

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<p style="font-size:0.95rem;font-weight:700;margin:0 0 1rem 0.25rem;'
            'letter-spacing:-0.01em;">Resume OTG</p>',
            unsafe_allow_html=True,
        )

        if _in_onboarding:
            if secondary_button("Skip setup", key="ob-sidebar-skip", use_container_width=True):
                from profile_store import complete_onboarding as _co
                _co()
                st.session_state.screen = "landing"
                st.rerun()
        else:
            # ── Primary nav ──────────────────────────────────────────────
            if secondary_button("Home", use_container_width=True, key="sidebar-home"):
                st.session_state.screen = "landing"
                st.rerun()
            if secondary_button("Career Profile", use_container_width=True, key="sidebar-profile"):
                st.session_state.screen = "profile"
                st.rerun()
            if secondary_button("Job Tracker", use_container_width=True, key="sidebar-job-tracker"):
                st.session_state.screen = "job_tracker"
                st.rerun()
            if secondary_button("Need Help", use_container_width=True, key="sidebar-need-help"):
                st.session_state.screen = "help"
                st.rerun()
            if secondary_button("Settings", use_container_width=True, key="sidebar-settings"):
                st.session_state.screen = "settings"
                st.session_state.settings_open_help = False
                st.rerun()

            # ── Footer: user + support ────────────────────────────────
            st.markdown(
                '<hr style="border:none;border-top:1px solid var(--line,#e5e5e5);margin:0.5rem 0;">',
                unsafe_allow_html=True,
            )
            if is_hosted_web():
                user_email = st.session_state.get("auth_user_email", "")
                if user_email:
                    st.markdown(
                        f'<p style="font-size:0.78rem;color:#888;margin:0.25rem 0.25rem 0.4rem;'
                        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                        f'{user_email}</p>',
                        unsafe_allow_html=True,
                    )
                if secondary_button("Sign Out", use_container_width=True, key="sidebar-sign-out"):
                    sign_out()
                    st.rerun()
            render_support_button()
            components.html(
                """
                <script>
                const doc = window.parent && window.parent.document ? window.parent.document : document;

                const hideSidebarArtifacts = () => {
                  const candidates = Array.from(doc.querySelectorAll("button, div, span"));
                  candidates.forEach((node) => {
                    const text = (node.innerText || node.textContent || "").trim();
                    if (!text || !text.includes("keyboard_double_arrow_right")) return;
                    const clickable = node.closest("button, [role='button'], [data-testid='collapsedControl'], [data-testid='stSidebarCollapseButton']");
                    const target = clickable || node;
                    if (target instanceof HTMLElement) {
                      target.style.display = "none";
                      const wrapper = target.parentElement;
                      if (wrapper && wrapper.childElementCount === 1) {
                        wrapper.style.display = "none";
                      }
                    }
                  });
                };

                const CLAUDE_CORAL = "#d97757";
                const CLAUDE_CORAL_HOVER = "#c9683f";

                const applyCoralStyle = (btn) => {
                  if (btn.closest("[data-testid='stSidebar']")) return;
                  btn.style.setProperty("background-color", CLAUDE_CORAL, "important");
                  btn.style.setProperty("background", CLAUDE_CORAL, "important");
                  btn.style.setProperty("color", "#ffffff", "important");
                  btn.style.setProperty("border-color", CLAUDE_CORAL, "important");
                  btn.querySelectorAll("p, span, div").forEach((el) => {
                    el.style.setProperty("color", "#ffffff", "important");
                  });
                  if (!btn._coralHooked) {
                    btn._coralHooked = true;
                    btn.addEventListener("mouseenter", () => {
                      btn.style.setProperty("background-color", CLAUDE_CORAL_HOVER, "important");
                      btn.style.setProperty("background", CLAUDE_CORAL_HOVER, "important");
                    });
                    btn.addEventListener("mouseleave", () => {
                      btn.style.setProperty("background-color", CLAUDE_CORAL, "important");
                      btn.style.setProperty("background", CLAUDE_CORAL, "important");
                    });
                  }
                };

                const applyButtonStyles = () => {
                  // All primary/secondary wrappers — includes st.button and st.download_button
                  doc.querySelectorAll(
                    ".apple-primary button, .apple-primary a[download], " +
                    ".apple-secondary button, .apple-secondary a[download], " +
                    ".apple-primary [data-testid='stDownloadButton'] button, " +
                    ".apple-secondary [data-testid='stDownloadButton'] button"
                  ).forEach(applyCoralStyle);

                  // Also target stDownloadButton directly when inside our wrappers
                  doc.querySelectorAll(
                    ".apple-primary [data-testid='stDownloadButton'], " +
                    ".apple-secondary [data-testid='stDownloadButton']"
                  ).forEach((wrapper) => {
                    wrapper.querySelectorAll("button, a").forEach(applyCoralStyle);
                  });
                };

                const runFixes = () => {
                  hideSidebarArtifacts();
                  applyButtonStyles();
                };

                // Run immediately and after Streamlit renders
                runFixes();
                setTimeout(runFixes, 100);
                setTimeout(runFixes, 400);
                setTimeout(runFixes, 1200);

                // Watch for DOM changes (Streamlit re-renders buttons dynamically)
                const observer = new MutationObserver(() => applyButtonStyles());
                observer.observe(doc.body, { childList: true, subtree: true });
                </script>
                """,
                height=0,
            )

    screen = st.session_state.screen
    # NOTE: _prev_rendered_screen is updated at the END of the routing block so that
    # render functions can read it and see the *previous* screen, not the current one.

    if screen == "onboarding":
        render_onboarding_screen()
    elif screen == "landing":
        render_landing()
    elif screen in ("onboarding_welcome", "onboarding_questions"):
        # Legacy keys — redirect to new unified wizard
        st.session_state.screen = "onboarding"
        st.rerun()
    elif screen == "profile":
        render_profile_screen()
    # Legacy profile screens kept as fallback (reached only via direct nav or Local AI flow)
    elif screen == "profile_welcome":
        render_profile_screen()  # redirect legacy key to new home
    elif screen == "profile_import":
        render_profile_screen()  # redirect legacy key to new home
    elif screen == "profile_review":
        render_profile_review_screen()  # kept: used by Local AI extraction flow
    elif screen == "profile_dashboard":
        render_profile_screen()  # redirect legacy key to new home
    elif screen == "profile_add_item":
        render_profile_screen()  # redirect legacy key to new home
    elif screen == "profile_build_resume_prompt":
        render_profile_build_resume_prompt_screen()
    elif screen == "application_match":
        render_application_match_screen()
    elif screen == "job_tracker":
        render_job_tracker_screen()
    elif screen == "job_detail":
        render_job_tracker_detail_screen()
    elif screen == "application_workspace":
        render_application_workspace_screen()
    elif screen == "optimization_history":
        render_optimization_history_screen()
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
    elif screen == "local_ai_setup":
        if show_private_mode():
            render_local_ai_setup_screen()
        else:
            st.session_state.screen = "landing"
            st.rerun()
    elif screen == "local_ai_run":
        if show_private_mode():
            render_local_ai_run_screen()
        else:
            st.session_state.screen = "landing"
            st.rerun()
    elif screen == "settings":
        render_settings_screen()
    elif screen == "help":
        render_help_screen()
    elif screen == "manual":
        render_manual_screen()
    elif screen == "api":
        render_api_screen()
    elif screen == "review":
        render_review_screen()

    # Update the previous-screen tracker after routing so render functions
    # can detect fresh navigation vs. in-screen reruns on the next pass.
    st.session_state._prev_rendered_screen = screen


if __name__ == "__main__":
    main()
