"""
Unified Profile screen.

Replaces the six fragmented profile screens:
  - profile_welcome
  - profile_import
  - profile_dashboard
  - profile_add_item
  - profile_build_resume_prompt
  - onboarding_welcome / onboarding_questions

The profile_review screen is preserved as the Local AI extraction review path.

Architecture
------------
One screen. Tabs for each profile section. Documents section at the top.
No stats, no confidence scores, no extraction diagnostics — just the user's data.

Interaction model
-----------------
  • Each section shows saved data in read mode.
  • Empty sections show a simple "Add" button.
  • Pencil/Edit opens an inline form; Save/Cancel returns to read mode.
  • Documents: upload → extract suggestions → user reviews → save.
"""

from __future__ import annotations

import html
import re
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from ui_helpers import primary_button, secondary_button
from docx_handler import extract_text
from profile_extractor import extract_profile_items_from_text
from profile_schema import ProfileItem
from profile_extractor import extract_profile_basics as extract_profile_basics_from_resume
from profile_store import (
    archive_profile_item,
    create_or_get_profile,
    delete_profile_source,
    list_profile_items,
    list_profile_sources,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    update_profile_item,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CAREER_STAGES = [
    "Student",
    "Early Career",
    "Mid-Level",
    "Manager",
    "Executive",
    "Career Pivot",
]

_EXPERIENCE_TYPES = {"experience", "project", "business", "leadership", "volunteering"}
_EDUCATION_TYPES  = {"education", "undergraduate", "masters", "phd", "certificate", "high_school"}
_SKILLS_TYPES     = {"skills", "certification", "award", "activity"}

# Human-readable labels for education degree levels (stored value → display label)
_EDU_TYPE_OPTIONS = [
    ("undergraduate", "Undergraduate / Bachelor's"),
    ("masters",       "Master's / MBA"),
    ("phd",           "PhD / Doctorate"),
    ("certificate",   "Certificate / Bootcamp / Course"),
    ("high_school",   "High School / Secondary"),
    ("education",     "Other / General Education"),
]
_EDU_TYPE_VALUES  = [v for v, _ in _EDU_TYPE_OPTIONS]
_EDU_TYPE_LABELS  = [l for _, l in _EDU_TYPE_OPTIONS]
_EDU_LABEL_BY_VAL = {v: l for v, l in _EDU_TYPE_OPTIONS}

# Human-readable labels for experience subtypes
_EXP_TYPE_OPTIONS = [
    ("experience",    "Work Experience / Role"),
    ("project",       "Project"),
    ("leadership",    "Leadership / Extracurricular"),
    ("volunteering",  "Volunteering / Community"),
    ("business",      "Business / Entrepreneurship"),
]
_EXP_TYPE_VALUES  = [v for v, _ in _EXP_TYPE_OPTIONS]
_EXP_TYPE_LABELS  = [l for _, l in _EXP_TYPE_OPTIONS]
_EXP_LABEL_BY_VAL = {v: l for v, l in _EXP_TYPE_OPTIONS}

_FIELD_LABELS_BY_TYPE = {
    "project": {
        "title": "Project name",
        "organization": "Organization / client (optional)",
        "title_placeholder": "Warehouse automation dashboard",
        "organization_placeholder": "Decathlon, university lab, or personal project",
    },
    "leadership": {
        "title": "Role title",
        "organization": "Organization name",
        "title_placeholder": "Treasurer · Team Lead · Chapter President",
        "organization_placeholder": "Student association, club, or team",
    },
    "volunteering": {
        "title": "Role title",
        "organization": "Organization name",
        "title_placeholder": "Volunteer Coordinator",
        "organization_placeholder": "Community organization or nonprofit",
    },
    "business": {
        "title": "Role / business title",
        "organization": "Company / business name",
        "title_placeholder": "Founder · Operations Lead",
        "organization_placeholder": "Company or venture name",
    },
}


def _item_field_labels(item_type: str, is_edu: bool) -> dict[str, str]:
    """Return labels/placeholders for profile-item identity fields."""
    if is_edu:
        return {
            "title": "Degree / program",
            "organization": "School / institution",
            "title_placeholder": "B.S. Business Administration",
            "organization_placeholder": "University or school name",
        }
    return _FIELD_LABELS_BY_TYPE.get(item_type, {
        "title": "Role title",
        "organization": "Company name",
        "title_placeholder": "Supply Chain Intern",
        "organization_placeholder": "Decathlon",
    })


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

_MONTHS = [
    ("", "Month"),
    ("01", "January"), ("02", "February"), ("03", "March"),
    ("04", "April"), ("05", "May"), ("06", "June"),
    ("07", "July"), ("08", "August"), ("09", "September"),
    ("10", "October"), ("11", "November"), ("12", "December"),
]
_MONTH_LABELS = [l for _, l in _MONTHS]
_MONTH_VALUES = [v for v, _ in _MONTHS]
_MONTH_ABBR = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def _csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


# Pattern 1: digit immediately followed by 3+ lowercase letters (e.g. "50million")
# Pattern 2: 3+ lowercase letters immediately followed by a digit (e.g. "million2")
# Pattern 3: lowercase letter immediately followed by an uppercase letter that starts
#             a word ≥4 chars long — catches "millionLogistics" style PDF run-ons
#             where the extractor preserved capitalisation at word boundaries.
_MISSING_SPACE_RE = re.compile(
    r'(\d)([a-z]{3,})'          # digit → lowercase word
    r'|([a-z]{3,})(\d)'         # lowercase word → digit
    r'|([a-z])([A-Z][a-z]{2,})' # camelCase run-on: lowerUpper (e.g. millionLogistics)
)


def _fix_concat_text(text: str) -> str:
    """Add spaces at obvious word-concatenation points from PDF/text extraction.

    PDF extractors sometimes strip spaces at line-break hyphens, producing
    strings like '$50millionLogisticsTransformation'. This adds spaces at:
      - digit ↔ letter boundaries   (50million → 50 million)
      - camelCase run-on boundaries  (millionLogistics → million Logistics)
    Short tokens like "3PL", "IPv4", "S&P500" are left alone.
    """
    if not text:
        return text

    def _add_space(m: re.Match) -> str:
        if m.group(1):  # digit → lowercase
            return m.group(1) + " " + m.group(2)
        if m.group(3):  # lowercase → digit
            return m.group(3) + " " + m.group(4)
        return m.group(5) + " " + m.group(6)  # camelCase split

    return _MISSING_SPACE_RE.sub(_add_space, text)


def _lines(value: str) -> list[str]:
    return [ln.strip() for ln in value.splitlines() if ln.strip()]


def _parse_date_parts(date_str: str) -> tuple[str, str]:
    """Return (month_num '01'-'12' or '', year '2024' or '') from a date string."""
    if not date_str:
        return "", ""
    m = re.match(r"^(\d{2})/(\d{4})$", date_str.strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([A-Za-z]+)\.?\s+(\d{4})", date_str.strip())
    if m:
        month_num = _MONTH_ABBR.get(m.group(1).lower().rstrip("."), "")
        return month_num, m.group(2)
    m = re.match(r"^(\d{4})$", date_str.strip())
    if m:
        return "", m.group(1)
    return "", ""


def _compose_date(month_num: str, year: str) -> str:
    year = year.strip()
    if month_num and year:
        return f"{month_num}/{year}"
    return year


def _date_range(item: ProfileItem) -> str:
    end = item.end_date or ("Present" if item.is_current else "")
    parts = [p for p in [item.start_date, end] if p]
    return " – ".join(parts)


def _date_sort_value(date_str: str) -> tuple[int, int]:
    """Return sortable (year, month) from profile dates; blanks sort oldest."""
    month, year = _parse_date_parts(date_str)
    try:
        year_num = int(year)
    except ValueError:
        year_num = 0
    try:
        month_num = int(month) if month else 12
    except ValueError:
        month_num = 12
    return year_num, month_num


def _item_recency_key(item: ProfileItem) -> tuple[int, int, int, str]:
    """Sort current and most recent profile items first."""
    end_value = (9999, 12) if item.is_current else _date_sort_value(item.end_date)
    start_value = _date_sort_value(item.start_date)
    return (
        end_value[0],
        end_value[1],
        start_value[0],
        item.updated_at or item.created_at or "",
    )


def _sort_profile_items(items: list[ProfileItem]) -> list[ProfileItem]:
    return sorted(items, key=_item_recency_key, reverse=True)


def _items_for(items: list[ProfileItem], tab: str) -> list[ProfileItem]:
    if tab == "education":
        return _sort_profile_items([i for i in items if i.item_type in _EDUCATION_TYPES])
    if tab == "experience":
        return _sort_profile_items([i for i in items if i.item_type in _EXPERIENCE_TYPES])
    if tab == "skills":
        return [i for i in items if i.item_type in _SKILLS_TYPES]
    return []


def _row(label: str, value: str) -> str:
    """One key/value display row."""
    if not value:
        return ""
    return (
        f'<div style="display:flex; justify-content:space-between; align-items:baseline;'
        f' padding:0.42rem 0; border-bottom:1px solid var(--line); font-size:0.94rem;">'
        f'<span style="color:var(--muted); min-width:9rem;">{label}</span>'
        f'<span style="font-weight:500; text-align:right;">{value}</span>'
        f"</div>"
    )


def _section_header(kicker: str, title: str, copy: str = "") -> None:
    st.markdown(
        f'<div class="apple-kicker">{kicker}</div>'
        f'<div class="apple-section-title">{title}</div>'
        + (f'<div class="apple-section-copy">{copy}</div>' if copy else ""),
        unsafe_allow_html=True,
    )


def _edit_btn(key: str, label: str = "Edit") -> bool:
    col_spacer, col_btn = st.columns([6, 1])
    with col_btn:
        return secondary_button(label, key=key, use_container_width=True)


def _add_btn(key: str, label: str) -> bool:
    return secondary_button(label, key=key)


def _save_cancel(form_key: str) -> tuple[bool, bool]:
    """Two-column Save / Cancel form buttons. Must be called inside a st.form."""
    col_save, col_cancel = st.columns(2, gap="large")
    with col_save:
        saved = st.form_submit_button("Save", use_container_width=True)
    with col_cancel:
        cancelled = st.form_submit_button("Cancel", use_container_width=True)
    return saved, cancelled


def _clear_editing() -> None:
    st.session_state.profile_editing = None


def _render_document_action_styles() -> None:
    """Compact document controls that avoid the global pill button style."""
    st.markdown(
        """
        <style>
          .profile-doc-list {
            margin-top: 0.6rem;
          }

          .profile-doc-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            min-height: 26px;
            padding: 0.05rem 0;
            color: var(--muted);
            font-size: 0.88rem;
            line-height: 1.35;
          }

          .profile-doc-name {
            min-width: 0;
            overflow-wrap: anywhere;
          }

          .stApp .profile-doc-icon-button .stButton,
          .profile-doc-icon-button .stButton {
            display: flex !important;
            justify-content: flex-end !important;
            margin: 0 !important;
          }

          .stApp .profile-doc-icon-button .stButton button,
          .profile-doc-icon-button .stButton button {
            width: 28px !important;
            min-width: 28px !important;
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 !important;
            border-radius: 999px !important;
            border: 1px solid var(--line) !important;
            background: rgba(255,255,255,0.62) !important;
            color: var(--muted) !important;
            font-size: 0.9rem !important;
            font-weight: 700 !important;
            line-height: 1 !important;
            box-shadow: none !important;
          }

          .stApp .profile-doc-icon-button .stButton button:hover,
          .profile-doc-icon-button .stButton button:hover {
            background: var(--surface-muted) !important;
            color: var(--text) !important;
            opacity: 1 !important;
          }

          .stApp .profile-doc-icon-button .stButton button *,
          .profile-doc-icon-button .stButton button * {
            color: inherit !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _document_icon_button(label: str, key: str, help_text: str) -> bool:
    st.markdown('<div class="profile-doc-icon-button">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, help=help_text)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def _render_document_header(editing: bool) -> None:
    title_col, action_col = st.columns([18, 1], gap="small", vertical_alignment="top")
    with title_col:
        st.markdown(
            '<div class="apple-kicker">Documents</div>'
            '<div class="apple-section-title">Your reference library.</div>',
            unsafe_allow_html=True,
        )
    with action_col:
        label = "✓" if editing else "✎"
        help_text = "Done" if editing else "Edit documents"
        if _document_icon_button(label, "profile-doc-edit-toggle", help_text):
            st.session_state.profile_docs_editing = not editing
            st.rerun()


# ---------------------------------------------------------------------------
# Document extraction
# ---------------------------------------------------------------------------

def _extract_from_upload(
    uploaded_files: Any,
    notes_text: str,
) -> tuple[str, str, dict, list[dict]]:
    """Read files + notes, return (raw_text, source_name, basics_dict, item_dicts)."""
    raw_parts: list[str] = []
    source_names: list[str] = []

    if uploaded_files:
        files = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]
        for f in files:
            if f is None:
                continue
            source_names.append(f.name)
            suffix = Path(f.name).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(f.getvalue())
                tmp_path = tmp.name
            try:
                raw_parts.append(extract_text(tmp_path))
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    if notes_text.strip():
        raw_parts.append(notes_text.strip())
        if not source_names:
            source_names.append("Manual notes")

    raw_text = "\n\n".join(p for p in raw_parts if p.strip())
    if not raw_text.strip():
        raise ValueError("Add at least one file or paste some notes before extracting.")

    source_name = ", ".join(source_names) or "Imported materials"
    basics = extract_profile_basics_from_resume(raw_text)
    # extract_profile_items_from_text returns (basics_dict, list[ProfileItem])
    _extra_basics, profile_items = extract_profile_items_from_text(raw_text)
    # Merge any extra basics fields not already captured
    for k, v in _extra_basics.items():
        if v and not basics.get(k):
            basics[k] = v
    item_dicts = [item.to_dict() for item in profile_items]
    return raw_text, source_name, basics, item_dicts


# ---------------------------------------------------------------------------
# Documents section
# ---------------------------------------------------------------------------

def _render_onboarding_extract_ui(profile) -> None:
    """
    First-time setup UI: upload + notes → extract profile basics + items for review.
    Only shown when the user has no prior sources.
    """
    up_col, notes_col = st.columns([1, 1], gap="large")
    with up_col:
        uploaded = st.file_uploader(
            "Upload files",
            type=["docx", "pdf", "txt", "md"],
            accept_multiple_files=True,
            key="profile-doc-upload",
            label_visibility="collapsed",
            help="Supports .docx, .pdf, .txt, .md",
        )
    with notes_col:
        notes = st.text_area(
            "Or paste text",
            height=104,
            placeholder="Paste LinkedIn text, resume content, or career notes…",
            key="profile-doc-notes",
            label_visibility="collapsed",
        )

    has_input = bool(uploaded or (notes and notes.strip()))
    if secondary_button(
        "Extract Profile from Documents",
        key="profile-extract-btn",
        disabled=not has_input,
        use_container_width=True,
    ):
        try:
            with st.spinner("Reading your documents and extracting profile information…"):
                raw_text, source_name, basics, item_dicts = _extract_from_upload(
                    uploaded, notes or ""
                )
            save_profile_source(
                source_type="resume" if uploaded else "manual_notes",
                source_name=source_name,
                raw_text=raw_text,
                parsed_payload={"type": "import"},
            )
            st.session_state.profile_pending_basics = basics
            st.session_state.profile_pending_items = item_dicts
            st.session_state.profile_pending_source = source_name
            st.rerun()
        except Exception as err:
            st.error(str(err))


def _render_reference_upload_ui() -> None:
    """
    Reference library UI: upload files → stored as context, no extraction.
    Shown inside an expander for returning users.
    Works exactly like adding files to a Claude project — stored for the app
    to reference when building resumes, but nothing is parsed or saved to your profile.
    """
    st.caption(
        "Add resumes, cover letters, job descriptions, or any document you want the app "
        "to reference when building your resume. Nothing is extracted or added to your profile — "
        "these are stored as context only."
    )

    ref_uploaded = st.file_uploader(
        "Upload reference files",
        type=["docx", "pdf", "txt", "md"],
        accept_multiple_files=True,
        key="profile-ref-upload",
        label_visibility="collapsed",
        help="Supports .docx, .pdf, .txt, .md",
    )

    has_ref = bool(ref_uploaded)
    if secondary_button(
        "Save to Library",
        key="profile-ref-save-btn",
        disabled=not has_ref,
        use_container_width=True,
    ) and ref_uploaded:
        saved_count = 0
        errors: list[str] = []
        files = ref_uploaded if isinstance(ref_uploaded, list) else [ref_uploaded]
        for f in files:
            if f is None:
                continue
            suffix = Path(f.name).suffix.lower()
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(f.getvalue())
                    tmp_path = tmp.name
                try:
                    raw_text = extract_text(tmp_path)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
                save_profile_source(
                    source_type="reference",
                    source_name=f.name,
                    raw_text=raw_text,
                    parsed_status="stored",
                    parsed_payload={"type": "reference"},
                )
                saved_count += 1
            except Exception as err:
                errors.append(f"{f.name}: {err}")

        if saved_count:
            st.success(
                f"{'1 file' if saved_count == 1 else f'{saved_count} files'} added to your library.",
                icon="✅",
            )
        for e in errors:
            st.error(e)
        if saved_count:
            st.rerun()


def _render_documents(profile) -> None:
    sources = list_profile_sources()
    _render_document_action_styles()

    with st.container(border=True):
        if not sources:
            # ── Onboarding / first-time user ──────────────────────────────
            # Show the full extract flow: upload → extract → review → save to profile.
            _section_header(
                "Documents",
                "Set up your profile from existing documents.",
                "Upload a resume, LinkedIn export, or paste any career notes. "
                "We'll extract what we can and show it to you for review before saving anything.",
            )
            _render_onboarding_extract_ui(profile)
        else:
            # ── Returning user ─────────────────────────────────────────────
            # Documents are a reference library — upload saves to context, no extraction.
            editing_docs = bool(st.session_state.get("profile_docs_editing"))
            _render_document_header(editing_docs)
            if not editing_docs:
                rows: list[str] = []
                for src in sources[:8]:
                    icon = "📎" if getattr(src, "source_type", "") == "reference" else "📄"
                    source_name = html.escape(src.source_name or "Unnamed document")
                    rows.append(
                        '<div class="profile-doc-row">'
                        f'<span class="profile-doc-name">{icon} {source_name}</span>'
                        "</div>"
                    )
                st.markdown(
                    '<div class="profile-doc-list">' + "".join(rows) + "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown('<div class="profile-doc-list">', unsafe_allow_html=True)
                for src in sources[:8]:
                    icon = "📎" if getattr(src, "source_type", "") == "reference" else "📄"
                    name_col, remove_col = st.columns([18, 1], gap="small", vertical_alignment="center")
                    with name_col:
                        st.markdown(
                            '<div class="profile-doc-row">'
                            f'<span class="profile-doc-name">{icon} {html.escape(src.source_name or "Unnamed document")}</span>'
                            "</div>",
                            unsafe_allow_html=True,
                        )
                    with remove_col:
                        if _document_icon_button("×", f"profile-source-remove-{src.id}", "Remove document"):
                            delete_profile_source(src.id)
                            st.toast("Removed from your reference library.")
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            if len(sources) > 8:
                st.caption(f"+{len(sources) - 8} more")

            st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
            with st.expander("Add to library", expanded=False):
                _render_reference_upload_ui()


# ---------------------------------------------------------------------------
# Suggestions review panel
# ---------------------------------------------------------------------------

def _render_suggestions(profile) -> None:
    """Show extracted suggestions inline; user picks what to save."""
    basics: dict = st.session_state.get("profile_pending_basics", {})
    item_dicts: list[dict] = st.session_state.get("profile_pending_items", [])
    source_name: str = st.session_state.get("profile_pending_source", "Uploaded document")

    if not basics and not item_dicts:
        return

    items = [ProfileItem(**d) for d in item_dicts]
    total = len(items) + (1 if basics else 0)

    st.markdown('<div style="height:0.75rem;"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        _section_header(
            "Review Suggestions",
            f'We found suggestions from "{source_name}".',
            "Nothing is saved yet — your existing profile data is safe. "
            "Review what looks right, save what fits, skip the rest.",
        )

        # ---- Personal info ----
        if basics:
            st.markdown("**Personal information extracted:**")
            for label, key in [
                ("Name", "full_name"), ("Email", "email"),
                ("Phone", "phone"), ("Location", "location"), ("LinkedIn", "linkedin"),
            ]:
                if basics.get(key):
                    st.markdown(f"&nbsp;&nbsp;&nbsp;· **{label}:** {basics[key]}")

            st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
            save_basics_col, skip_basics_col = st.columns(2, gap="large")
            with save_basics_col:
                if primary_button("Save Personal Info", key="sugg-save-basics", use_container_width=True):
                    # Merge: only fill in fields the user hasn't set yet (never overwrite)
                    save_profile_basics(
                        full_name=profile.full_name or basics.get("full_name", ""),
                        email=profile.email or basics.get("email", ""),
                        phone=profile.phone or basics.get("phone", ""),
                        location=profile.location or basics.get("location", ""),
                        linkedin=profile.linkedin or basics.get("linkedin", ""),
                        portfolio_url=profile.portfolio_url,
                        photo_path=profile.photo_path,
                        headline=profile.headline or basics.get("headline", ""),
                        career_stage=profile.career_stage,
                        summary=profile.summary or basics.get("summary", ""),
                        target_roles=profile.target_roles,
                        target_industries=profile.target_industries,
                        preferred_locations=profile.preferred_locations,
                        work_authorization=profile.work_authorization,
                    )
                    st.session_state.profile_pending_basics = {}
                    st.rerun()
            with skip_basics_col:
                if secondary_button("Skip Personal Info", key="sugg-skip-basics", use_container_width=True):
                    st.session_state.profile_pending_basics = {}
                    st.rerun()

        # ---- Career items ----
        if items:
            if basics:
                st.markdown(
                    "<hr style='border:none; border-top:1px solid var(--line); margin:1.25rem 0;'>",
                    unsafe_allow_html=True,
                )
            st.markdown(f"**{len(items)} career items found:**")

            # Group by type
            by_type: dict[str, list[tuple[int, ProfileItem]]] = {}
            for idx, item in enumerate(items):
                by_type.setdefault(item.item_type, []).append((idx, item))

            for type_key, indexed_items in by_type.items():
                st.markdown(
                    f'<div style="font-weight:600; font-size:0.9rem; margin:0.75rem 0 0.3rem 0; text-transform:capitalize; color:var(--muted-light);">{type_key}</div>',
                    unsafe_allow_html=True,
                )
                for idx, item in indexed_items:
                    item_label = item.title or "Untitled"
                    if item.organization:
                        item_label += f" @ {item.organization}"
                    date_str = _date_range(item)
                    st.checkbox(
                        f"{item_label}{(' · ' + date_str) if date_str else ''}",
                        value=True,
                        key=f"sugg_item_{idx}",
                    )

            st.markdown('<div style="height:0.75rem;"></div>', unsafe_allow_html=True)
            save_items_col, discard_col = st.columns(2, gap="large")
            with save_items_col:
                if primary_button("Save Selected Items", key="sugg-save-items", use_container_width=True):
                    to_save: list[ProfileItem] = []
                    for type_key, indexed_items in by_type.items():
                        for idx, item in indexed_items:
                            if st.session_state.get(f"sugg_item_{idx}", True):
                                item.profile_id = profile.id
                                item.verification_status = "verified"
                                to_save.append(item)
                    if to_save:
                        save_profile_items(to_save)
                    st.session_state.profile_pending_items = []
                    st.session_state.profile_pending_source = ""
                    st.rerun()
            with discard_col:
                if secondary_button("Discard All Items", key="sugg-discard", use_container_width=True):
                    st.session_state.profile_pending_items = []
                    st.session_state.profile_pending_source = ""
                    st.rerun()


# ---------------------------------------------------------------------------
# Personal tab
# ---------------------------------------------------------------------------

def _row_always(label: str, value: str, empty_text: str = "—") -> str:
    """Key/value row that always renders, showing empty_text when value is blank."""
    display = value if value else f'<span style="color:var(--muted);">{empty_text}</span>'
    return (
        f'<div style="display:flex; justify-content:space-between; align-items:baseline;'
        f' padding:0.42rem 0; border-bottom:1px solid var(--line); font-size:0.94rem;">'
        f'<span style="color:var(--muted); min-width:9rem;">{label}</span>'
        f'<span style="font-weight:500; text-align:right;">{display}</span>'
        f"</div>"
    )


def _render_personal(profile) -> None:
    editing = st.session_state.get("profile_editing") == "personal"

    if not editing:
        if profile.photo_path and Path(profile.photo_path).exists():
            st.image(profile.photo_path, width=108)

        # Name + headline always visible
        name_display = profile.full_name.strip() or '<span style="color:var(--muted);">Name not set</span>'
        headline_display = profile.headline.strip() or ""
        st.markdown(
            f'<div style="font-size:1.5rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:0.2rem;">'
            f"{name_display}</div>"
            + (
                f'<div style="color:var(--muted); font-size:0.95rem; margin-bottom:0.75rem;">'
                f"{headline_display}</div>"
                if headline_display
                else '<div style="height:0.75rem;"></div>'
            ),
            unsafe_allow_html=True,
        )

        # Contact rows — always show all fields so users see what's missing
        contact_rows = "".join([
            _row_always("Email",               profile.email,    "Not set"),
            _row_always("Phone",               profile.phone,    "Not set"),
            _row_always("Location",            profile.location, "Not set"),
            _row_always("LinkedIn",            profile.linkedin, "Not set"),
            _row_always("Portfolio",           profile.portfolio_url, "Not set"),
        ])
        st.markdown(contact_rows, unsafe_allow_html=True)

        if profile.summary:
            # Replace newlines with <br> so Streamlit's markdown parser doesn't
            # convert double-newlines into <p> tags (which inherit Streamlit's
            # default paragraph font-size and override the parent div's 0.95rem).
            _summary_html = _fix_concat_text(profile.summary).replace("\n\n", "<br><br>").replace("\n", "<br>")
            st.markdown(
                f'<div style="margin-top:1rem; font-size:0.95rem; color:var(--muted); line-height:1.72;">'
                f"{_summary_html}</div>",
                unsafe_allow_html=True,
            )

        has_data = bool(profile.full_name or profile.email)
        if _edit_btn("personal-edit-btn", "Edit" if has_data else "Add"):
            st.session_state.profile_editing = "personal"
            st.rerun()

    else:
        with st.form("profile-personal-form"):
            c1, c2 = st.columns(2, gap="large")
            with c1:
                full_name = st.text_input("Full Name", value=profile.full_name, placeholder="Jane Doe")
                email     = st.text_input("Email",     value=profile.email,     placeholder="jane@example.com")
                phone     = st.text_input("Phone",     value=profile.phone,     placeholder="(555) 555-5555")
            with c2:
                location  = st.text_input("Location",          value=profile.location,  placeholder="New York, NY")
                linkedin  = st.text_input("LinkedIn", value=profile.linkedin, placeholder="linkedin.com/in/janedoe")
                portfolio_url = st.text_input("Portfolio", value=profile.portfolio_url, placeholder="https://yourportfolio.com")
            photo_upload = st.file_uploader(
                "Profile Photo",
                type=["png", "jpg", "jpeg", "webp"],
                key="profile-photo-upload",
                help="Optional. Used only inside your profile.",
            )
            headline = st.text_input(
                "Headline", value=profile.headline,
                placeholder="Operations Analyst | Supply Chain | Analytics",
            )
            summary  = st.text_area(
                "Summary", value=profile.summary, height=120,
                placeholder="A brief professional summary. 2–4 sentences.",
            )
            saved, cancelled = _save_cancel("personal")

        if saved:
            photo_path = profile.photo_path
            if photo_upload is not None:
                photo_dir = Path(__file__).resolve().parent / "profile_uploads"
                photo_dir.mkdir(parents=True, exist_ok=True)
                target = photo_dir / f"profile-photo-{profile.id or 'local'}{Path(photo_upload.name).suffix.lower()}"
                target.write_bytes(photo_upload.getbuffer())
                photo_path = str(target)
            save_profile_basics(
                full_name=full_name, email=email, phone=phone,
                location=location,
                linkedin=linkedin,
                portfolio_url=portfolio_url,
                photo_path=photo_path,
                headline=headline,
                career_stage=profile.career_stage, summary=summary,
                target_roles=profile.target_roles,
                target_industries=profile.target_industries,
                preferred_locations=profile.preferred_locations,
                work_authorization=profile.work_authorization,
            )
            _clear_editing(); st.rerun()
        if cancelled:
            _clear_editing(); st.rerun()


# ---------------------------------------------------------------------------
# Education tab
# ---------------------------------------------------------------------------

def _item_type_label(item: ProfileItem) -> str:
    """Return a human-readable label for an item's type."""
    return (
        _EDU_LABEL_BY_VAL.get(item.item_type)
        or _EXP_LABEL_BY_VAL.get(item.item_type)
        or item.item_type.replace("_", " ").title()
    )


def _render_item_card(item: ProfileItem, tab: str) -> None:
    """Read-mode card for one education / experience item."""
    with st.container(border=True):
        top_col, btn_col = st.columns([5, 1])
        with top_col:
            date_str = _date_range(item)
            type_badge = _item_type_label(item)
            if tab == "experience":
                primary = " · ".join(filter(None, [item.organization, item.title])) or type_badge
                secondary_parts = [date_str]
            else:
                primary = item.title or type_badge
                secondary_parts = [item.organization, date_str]
            detail_line = " · ".join(filter(None, secondary_parts))
            st.markdown(
                f'<div style="font-weight:600; font-size:1rem;">{primary}</div>'
                f'<div style="color:var(--muted); font-size:0.9rem; margin-bottom:0.35rem;">'
                f'{detail_line}'
                f'{"  ·  " if detail_line else ""}'
                f'<span style="font-size:0.8rem; background:var(--surface-muted); padding:0.1rem 0.45rem;'
                f' border-radius:999px; border:1px solid var(--line);">{type_badge}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with btn_col:
            if secondary_button("Edit", key=f"edit-{tab}-{item.id}", use_container_width=True):
                st.session_state.profile_editing = f"edit_{tab}_{item.id}"
                st.rerun()

        if item.description:
            desc = _fix_concat_text(item.description)
            st.markdown(
                f'<div style="font-size:0.9rem; color:var(--muted);">'
                f'{desc[:220]}{"…" if len(desc) > 220 else ""}</div>',
                unsafe_allow_html=True,
            )
        for bullet in item.bullets[:3]:
            st.markdown(
                f'<div style="font-size:0.88rem; color:var(--muted); padding-left:0.75rem; margin-top:0.15rem;">• {_fix_concat_text(bullet)}</div>',
                unsafe_allow_html=True,
            )
        if len(item.bullets) > 3:
            st.caption(f"+{len(item.bullets) - 3} more")


def _item_form(
    profile,
    tab: str,
    existing: ProfileItem | None = None,
) -> None:
    """Add / edit form for an education or experience item."""
    is_edu = tab == "education"
    type_values  = _EDU_TYPE_VALUES  if is_edu else _EXP_TYPE_VALUES
    type_labels  = _EDU_TYPE_LABELS  if is_edu else _EXP_TYPE_LABELS
    label_by_val = _EDU_LABEL_BY_VAL if is_edu else _EXP_LABEL_BY_VAL

    form_key = f"item-form-{tab}-{existing.id if existing else 'new'}"

    with st.form(form_key):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            # Find index of existing type, fall back to 0
            existing_type = existing.item_type if existing else ""
            default_idx = (
                type_values.index(existing_type)
                if existing_type in type_values
                else 0
            )
            selected_label = st.selectbox(
                "Degree Level" if is_edu else "Type",
                type_labels,
                index=default_idx,
            )
            item_type = type_values[type_labels.index(selected_label)]
            field_labels = _item_field_labels(item_type, is_edu)
            title = st.text_input(
                field_labels["title"],
                value=existing.title if existing else "",
                placeholder=field_labels["title_placeholder"],
            )
            org = st.text_input(
                field_labels["organization"],
                value=existing.organization if existing else "",
                placeholder=field_labels["organization_placeholder"],
            )
            if not is_edu and item_type == "experience":
                st.caption(
                    "Company name is stored separately from role title. Existing saved items are not changed automatically."
                )
            loc = st.text_input(
                "Location (optional)",
                value=existing.location if existing else "",
            )
        with c2:
            start_m0, start_y0 = _parse_date_parts(existing.start_date if existing else "")
            end_m0, end_y0     = _parse_date_parts(existing.end_date   if existing else "")
            start_idx = _MONTH_VALUES.index(start_m0) if start_m0 in _MONTH_VALUES else 0
            end_idx   = _MONTH_VALUES.index(end_m0)   if end_m0   in _MONTH_VALUES else 0

            st.markdown(
                '<p style="font-size:0.875rem;font-weight:600;margin:0 0 0.25rem;">Start Date</p>',
                unsafe_allow_html=True,
            )
            s1, s2 = st.columns([3, 2])
            with s1:
                start_month_label = st.selectbox(
                    "Start Month", _MONTH_LABELS, index=start_idx,
                    key=f"{form_key}_sm", label_visibility="collapsed",
                )
            with s2:
                start_year = st.text_input(
                    "Start Year", value=start_y0, placeholder="2022",
                    key=f"{form_key}_sy", label_visibility="collapsed",
                )

            st.markdown(
                '<p style="font-size:0.875rem;font-weight:600;margin:0.5rem 0 0.25rem;">End Date</p>',
                unsafe_allow_html=True,
            )
            e1, e2 = st.columns([3, 2])
            with e1:
                end_month_label = st.selectbox(
                    "End Month", _MONTH_LABELS, index=end_idx,
                    key=f"{form_key}_em", label_visibility="collapsed",
                )
            with e2:
                end_year = st.text_input(
                    "End Year", value=end_y0, placeholder="2024",
                    key=f"{form_key}_ey", label_visibility="collapsed",
                )
            is_current = st.checkbox(
                "Currently here",
                value=existing.is_current if existing else False,
            )

        description = st.text_area(
            "Description (optional)",
            value=existing.description if existing else "",
            height=90,
            placeholder="Brief context or what you accomplished here.",
        )
        bullets_raw = st.text_area(
            "Bullet points — one per line",
            value="\n".join(existing.bullets) if existing and existing.bullets else "",
            height=130,
            placeholder="• Led cross-functional team of 8\n• Reduced costs by 18%",
        )

        btn_cols = st.columns([2, 2, 1] if existing else [2, 2])
        with btn_cols[0]:
            saved = st.form_submit_button("Save", use_container_width=True)
        with btn_cols[1]:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)
        deleted = False
        if existing and len(btn_cols) == 3:
            with btn_cols[2]:
                deleted = st.form_submit_button("Remove", use_container_width=True)

    if saved:
        start_m_num = _MONTH_VALUES[_MONTH_LABELS.index(start_month_label)]
        end_m_num   = _MONTH_VALUES[_MONTH_LABELS.index(end_month_label)]
        composed_start = _compose_date(start_m_num, start_year)
        composed_end   = "" if is_current else _compose_date(end_m_num, end_year)
        data = dict(
            item_type=item_type, title=title.strip(), organization=org.strip(),
            location=loc.strip(), start_date=composed_start, end_date=composed_end,
            is_current=is_current, description=description.strip(),
            bullets=_lines(bullets_raw),
            skills=existing.skills if existing else [],
            keywords=existing.keywords if existing else [],
            confidence_score=1.0, verification_status="verified", visibility="active",
        )
        if existing:
            update_profile_item(ProfileItem(**{**existing.__dict__, **data}))
        else:
            save_profile_items([ProfileItem(profile_id=profile.id, **data)])
        _clear_editing(); st.rerun()

    if cancelled:
        _clear_editing(); st.rerun()

    if deleted and existing:
        archive_profile_item(existing.id)
        _clear_editing(); st.rerun()


def _render_education(profile, items: list[ProfileItem]) -> None:
    edu = _items_for(items, "education")
    editing: str = st.session_state.get("profile_editing") or ""

    if editing == "add_education":
        st.markdown('<div class="apple-kicker">Add Education</div>', unsafe_allow_html=True)
        _item_form(profile, "education")
        return

    for item in edu:
        if editing == f"edit_education_{item.id}":
            _item_form(profile, "education", existing=item)
        else:
            _render_item_card(item, "education")

    if not edu:
        st.markdown(
            '<div class="apple-minor-copy" style="margin-bottom:0.75rem;">No education saved yet.</div>',
            unsafe_allow_html=True,
        )

    if editing not in {f"edit_education_{i.id}" for i in edu}:
        if _add_btn("add-edu-btn", "+ Add Education"):
            st.session_state.profile_editing = "add_education"
            st.rerun()


# ---------------------------------------------------------------------------
# Work Experience tab
# ---------------------------------------------------------------------------

def _render_experience(profile, items: list[ProfileItem]) -> None:
    exp = _items_for(items, "experience")
    editing: str = st.session_state.get("profile_editing") or ""

    if editing == "add_experience":
        st.markdown('<div class="apple-kicker">Add Experience</div>', unsafe_allow_html=True)
        _item_form(profile, "experience")
        return

    for item in exp:
        if editing == f"edit_experience_{item.id}":
            _item_form(profile, "experience", existing=item)
        else:
            _render_item_card(item, "experience")

    if not exp:
        st.markdown(
            '<div class="apple-minor-copy" style="margin-bottom:0.75rem;">No work experience saved yet.</div>',
            unsafe_allow_html=True,
        )

    if editing not in {f"edit_experience_{i.id}" for i in exp}:
        if _add_btn("add-exp-btn", "+ Add Experience"):
            st.session_state.profile_editing = "add_experience"
            st.rerun()


# ---------------------------------------------------------------------------
# Skills tab
# ---------------------------------------------------------------------------

def _render_skills(profile, items: list[ProfileItem]) -> None:
    skill_items = [item for item in _items_for(items, "skills") if item.item_type == "skills"]
    all_skills: list[str] = list(
        dict.fromkeys(s for item in skill_items for s in item.skills)
    )
    editing = st.session_state.get("profile_editing") == "skills"

    if not editing:
        if all_skills:
            chips = "".join(
                f'<span style="display:inline-block; padding:0.3rem 0.75rem;'
                f' background:var(--surface-muted); border:1px solid var(--line);'
                f' border-radius:999px; font-size:0.88rem; margin:0.2rem 0.2rem 0 0;">{s}</span>'
                for s in all_skills
            )
            st.markdown(f'<div style="line-height:2.2;">{chips}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="apple-minor-copy" style="margin-bottom:0.75rem;">No skills saved yet.</div>',
                unsafe_allow_html=True,
            )

        if _edit_btn("skills-edit-btn", "Edit" if all_skills else "Add"):
            st.session_state.profile_editing = "skills"
            st.rerun()

    else:
        with st.form("profile-skills-form"):
            skills_input = st.text_area(
                "Skills (comma-separated)",
                value=", ".join(all_skills),
                height=130,
                placeholder="Python, SQL, Excel, Stakeholder Management, Supply Chain…",
            )
            saved, cancelled = _save_cancel("skills")

        if saved:
            new_skills = _csv(skills_input)
            # Non-destructive: update the first existing skills item in place;
            # archive any extras; create fresh only when none existed.
            pure_skill_items = [i for i in skill_items if i.item_type == "skills"]
            other_skill_items = [i for i in skill_items if i.item_type != "skills"]
            if pure_skill_items:
                primary = pure_skill_items[0]
                update_profile_item(ProfileItem(**{
                    **primary.__dict__,
                    "skills": new_skills,
                    "keywords": new_skills[:16],
                    "verification_status": "verified",
                }))
                for extra in pure_skill_items[1:]:
                    archive_profile_item(extra.id)
            elif new_skills:
                save_profile_items([ProfileItem(
                    profile_id=profile.id,
                    item_type="skills",
                    title="Skills",
                    skills=new_skills,
                    keywords=new_skills[:16],
                    confidence_score=1.0,
                    verification_status="verified",
                    visibility="active",
                )])
            # other_skill_items (certifications, awards, etc.) are left untouched
            _ = other_skill_items
            _clear_editing(); st.rerun()
        if cancelled:
            _clear_editing(); st.rerun()


# ---------------------------------------------------------------------------
# Preferences tab
# ---------------------------------------------------------------------------

def _render_preferences(profile) -> None:
    editing = st.session_state.get("profile_editing") == "preferences"

    if not editing:
        rows_html = "".join(filter(None, [
            _row("Career stage",         profile.career_stage or ""),
            _row("Target roles",         ", ".join(profile.target_roles) if profile.target_roles else ""),
            _row("Preferred industries", ", ".join(profile.target_industries) if profile.target_industries else ""),
            _row("Preferred locations",  ", ".join(profile.preferred_locations) if profile.preferred_locations else ""),
            _row("Work authorization",   profile.work_authorization or ""),
        ]))
        if rows_html:
            st.markdown(rows_html, unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="apple-minor-copy" style="margin-bottom:0.75rem;">No preferences saved yet.</div>',
                unsafe_allow_html=True,
            )

        if _edit_btn("prefs-edit-btn", "Edit" if rows_html else "Add"):
            st.session_state.profile_editing = "preferences"
            st.rerun()

    else:
        with st.form("profile-prefs-form"):
            career_stage = st.selectbox(
                "Career Stage",
                _CAREER_STAGES,
                index=_CAREER_STAGES.index(profile.career_stage)
                if profile.career_stage in _CAREER_STAGES else 0,
            )
            target_roles = st.text_input(
                "Target Roles",
                value=", ".join(profile.target_roles),
                placeholder="Operations Analyst, Supply Chain Analyst",
            )
            target_industries = st.text_input(
                "Preferred Industries",
                value=", ".join(profile.target_industries),
                placeholder="Supply Chain / Operations, Technology, Finance",
            )
            preferred_locations = st.text_input(
                "Preferred Locations",
                value=", ".join(profile.preferred_locations),
                placeholder="New York, Boston, Remote",
            )
            work_authorization = st.text_input(
                "Work Authorization",
                value=profile.work_authorization,
                placeholder="U.S. Citizen, OPT, H1-B sponsored",
            )
            saved, cancelled = _save_cancel("prefs")

        if saved:
            save_profile_basics(
                full_name=profile.full_name, email=profile.email,
                phone=profile.phone, location=profile.location,
                linkedin=profile.linkedin,
                portfolio_url=profile.portfolio_url,
                photo_path=profile.photo_path,
                headline=profile.headline,
                career_stage=career_stage, summary=profile.summary,
                target_roles=_csv(target_roles),
                target_industries=_csv(target_industries),
                preferred_locations=_csv(preferred_locations),
                work_authorization=work_authorization,
            )
            _clear_editing(); st.rerun()
        if cancelled:
            _clear_editing(); st.rerun()


# ---------------------------------------------------------------------------
# Optional Info tab  (Equal Employment + demographic)
# ---------------------------------------------------------------------------

_EEO_GENDER = [
    "", "Man", "Woman", "Non-binary / non-conforming",
    "Prefer to self-describe", "Prefer not to say",
]
_EEO_RACE = [
    "", "Asian", "Black or African American", "Hispanic or Latino",
    "Two or more races", "White",
    "American Indian or Alaska Native",
    "Native Hawaiian or Pacific Islander",
    "Prefer not to say",
]
_EEO_VETERAN  = ["", "Not a veteran", "Veteran", "Prefer not to say"]
_EEO_DISABILITY = ["", "No disability", "Has disability", "Prefer not to say"]


def _render_optional(profile) -> None:
    editing = st.session_state.get("profile_editing") == "optional"
    eeo: dict = st.session_state.get("profile_eeo_data", {})

    st.markdown(
        '<div style="font-size:0.88rem; color:var(--muted); margin-bottom:1.1rem; line-height:1.65;">'
        "This information is entirely optional. It is stored locally on your device and is only "
        "used when an application explicitly asks for it."
        "</div>",
        unsafe_allow_html=True,
    )

    if not editing:
        filled = {k: v for k, v in eeo.items() if v}
        if filled:
            label_map = {
                "gender": "Gender identity",
                "race": "Race / Ethnicity",
                "veteran": "Veteran status",
                "disability": "Disability status",
            }
            rows_html = "".join(
                _row(label_map.get(k, k), v) for k, v in filled.items()
            )
            st.markdown(rows_html, unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="apple-minor-copy" style="margin-bottom:0.75rem;">No optional information added.</div>',
                unsafe_allow_html=True,
            )

        if _edit_btn("optional-edit-btn", "Edit" if filled else "Add"):
            st.session_state.profile_editing = "optional"
            st.rerun()

    else:
        def _idx(lst: list, val: str) -> int:
            return lst.index(val) if val in lst else 0

        with st.form("profile-optional-form"):
            st.caption("All fields are optional and voluntary.")
            gender   = st.selectbox("Gender identity (optional)",   _EEO_GENDER,   index=_idx(_EEO_GENDER,   eeo.get("gender", "")))
            race     = st.selectbox("Race / Ethnicity (optional)",   _EEO_RACE,     index=_idx(_EEO_RACE,     eeo.get("race", "")))
            veteran  = st.selectbox("Veteran status (optional)",     _EEO_VETERAN,  index=_idx(_EEO_VETERAN,  eeo.get("veteran", "")))
            disability = st.selectbox("Disability status (optional)", _EEO_DISABILITY, index=_idx(_EEO_DISABILITY, eeo.get("disability", "")))
            saved, cancelled = _save_cancel("optional")

        if saved:
            st.session_state.profile_eeo_data = {
                "gender": gender, "race": race,
                "veteran": veteran, "disability": disability,
            }
            _clear_editing(); st.rerun()
        if cancelled:
            _clear_editing(); st.rerun()


# ---------------------------------------------------------------------------
# Completeness helper
# ---------------------------------------------------------------------------

def _profile_completeness(profile, items: list[ProfileItem]) -> tuple[int, list[str]]:
    """Return (percent_complete, list_of_missing_section_names)."""
    checks = [
        (bool(profile.full_name and profile.email), "Personal info (name + email)"),
        (bool(profile.headline), "Headline"),
        (bool(profile.summary), "Summary"),
        (any(i.item_type in _EDUCATION_TYPES for i in items), "Education"),
        (any(i.item_type in _EXPERIENCE_TYPES for i in items), "Work Experience"),
        (any(i.item_type in _SKILLS_TYPES and i.skills for i in items), "Skills"),
        (bool(profile.career_stage), "Career stage preference"),
    ]
    done = sum(1 for ok, _ in checks if ok)
    missing = [label for ok, label in checks if not ok]
    percent = round(done / len(checks) * 100)
    return percent, missing


# ---------------------------------------------------------------------------
# Post-onboarding verification banner
# ---------------------------------------------------------------------------

def _render_verification_banner(profile, pct: int, missing: list[str]) -> None:
    """
    One-time banner shown immediately after onboarding completes.
    Prompts the user to verify the extracted information is correct and
    highlights any fields that still need attention.
    Dismissed by clicking "Looks good!" or navigating away.
    """
    is_complete = pct == 100

    if is_complete:
        icon    = "✅"
        heading = "Profile complete — you're all set!"
        body    = (
            "Everything looks filled in. You can still edit any field using "
            "the tabs below, but you're ready to start optimising resumes."
        )
        bg      = "#f0fdf4"
        border  = "#bbf7d0"
    else:
        icon    = "👀"
        heading = "Please take a moment to verify your profile"
        missing_str = ", ".join(missing) if missing else "a few fields"
        body    = (
            f"We extracted information from your documents and saved what we found. "
            f"Check each tab below to confirm the details are accurate. "
            f"Still missing: **{missing_str}**."
        )
        bg      = "#fffbeb"
        border  = "#fde68a"

    st.markdown(
        f"""
        <div style="background:{bg}; border:1px solid {border}; border-radius:12px;
                    padding:1.1rem 1.4rem; margin-bottom:1.5rem;">
          <div style="font-size:1.05rem; font-weight:700; margin-bottom:0.35rem;">
            {icon}&nbsp; {heading}
          </div>
          <div style="font-size:0.93rem; line-height:1.65; color:#374151;">
            {body}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    dismiss_col, _ = st.columns([1.5, 4])
    with dismiss_col:
        if primary_button(
            "Looks good! ✓" if is_complete else "Got it — I'll review now",
            key="ob-verify-dismiss",
            use_container_width=True,
        ):
            st.session_state.ob_just_completed = False
            st.rerun()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_profile_screen() -> None:
    """The unified Profile home."""
    # ---- Init session keys ----
    # Reset editing state when arriving from a different screen.
    # This prevents stale edit forms from persisting when the user navigates away and returns.
    _prev_screen = st.session_state.get("_prev_rendered_screen")
    if _prev_screen != "profile":
        st.session_state.profile_editing = None
    _defaults = {
        "profile_editing":        None,
        "profile_pending_basics": {},
        "profile_pending_items":  [],
        "profile_pending_source": "",
        "profile_eeo_data":       {},
    }
    for key, val in _defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    profile = create_or_get_profile()
    items = [i for i in list_profile_items() if i.visibility == "active"]

    # ---- Profile completeness ----
    pct, missing = _profile_completeness(profile, items)

    # ---- Post-onboarding verification banner ----
    if st.session_state.get("ob_just_completed"):
        _render_verification_banner(profile, pct, missing)

    # ---- Page header ----
    display_name     = profile.full_name.strip() or "Your Profile"
    display_subtitle = profile.headline.strip() or "Build your reusable career memory here."

    st.markdown(
        f"""
        <div style="margin-bottom:1.5rem;">
          <div class="apple-eyebrow">Career Profile</div>
          <div style="font-size:clamp(1.8rem,3.5vw,2.6rem); font-weight:700;
                      letter-spacing:-0.022em; margin:0.4rem 0 0.25rem 0;
                      line-height:1.15;">{display_name}</div>
          <div style="color:var(--muted); font-size:1rem; line-height:1.6;">{display_subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Completeness bar ----
    bar_color = "var(--green)" if pct == 100 else ("var(--amber)" if pct >= 60 else "var(--danger)")
    missing_html = (
        ""
        if pct == 100
        else (
            '<div style="margin-top:0.4rem; font-size:0.83rem; color:var(--muted);">'
            "Missing: " + ", ".join(missing) + "</div>"
        )
    )
    st.markdown(
        f"""
        <div style="margin-bottom:1.75rem;">
          <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.3rem;">
            <div style="flex:1; height:6px; background:var(--surface-muted);
                        border-radius:999px; overflow:hidden;">
              <div style="width:{pct}%; height:100%; background:{bar_color};
                          border-radius:999px; transition:width 0.4s ease;"></div>
            </div>
            <span style="font-size:0.85rem; font-weight:600; color:{bar_color};
                         min-width:3rem; text-align:right;">{pct}%</span>
          </div>
          {missing_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Documents section ----
    _render_documents(profile)

    # ---- Suggestions review (appears after extraction) ----
    _render_suggestions(profile)

    # ---- Profile tabs ----
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    (
        tab_personal, tab_edu, tab_exp,
        tab_skills, tab_prefs, tab_optional,
    ) = st.tabs([
        "Personal",
        "Education",
        "Work Experience",
        "Skills",
        "Preferences",
        "Optional Info",
    ])

    with tab_personal:
        _render_personal(profile)

    with tab_edu:
        _render_education(profile, items)

    with tab_exp:
        _render_experience(profile, items)

    with tab_skills:
        _render_skills(profile, items)

    with tab_prefs:
        _render_preferences(profile)

    with tab_optional:
        _render_optional(profile)

    # ---- Footer navigation ----
    st.markdown("<div style='height:2.5rem;'></div>", unsafe_allow_html=True)
    nav_left, nav_right = st.columns(2, gap="large")
    with nav_left:
        if secondary_button("← Back to Home", key="profile-back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
    with nav_right:
        if secondary_button("Start Optimizing →", key="profile-go-optimize", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()
