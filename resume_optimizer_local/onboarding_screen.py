"""
Onboarding wizard — 4-stage guided flow.

Stage 1  Welcome      name · career stage · target roles  (conversational)
Stage 2  Upload       resume · LinkedIn · other docs       (explicit + reassuring)
Stage 3  Review       section-by-section confirm / edit   (builds confidence)
Stage 4  Done         adaptive CTA
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from docx_handler import extract_text
from profile_extractor import (
    extract_profile_basics as extract_profile_basics_from_resume,
    extract_profile_items_from_text,
)
from profile_schema import ProfileItem
from profile_store import (
    complete_onboarding,
    create_or_get_profile,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    start_onboarding,
)
from ui_helpers import primary_button, secondary_button
from llm_core.errors import GuardrailFailure
from llm_core.guardrails.input_guards import validate_profile_input

# ── Constants ──────────────────────────────────────────────────────────────────

TOTAL_STEPS = 4

_CAREER_STAGES: list[str] = [
    "Student",
    "Early Career (0–3 yrs)",
    "Mid-Level (3–8 yrs)",
    "Manager / Team Lead",
    "Executive / C-Suite",
    "Career Pivot",
    "Not Sure Yet",
]

_TARGET_ROLES: list[str] = [
    "Software Engineer",
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "DevOps / Platform Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Data Analyst",
    "Product Manager",
    "Product Designer",
    "UX Designer",
    "Business Analyst",
    "Project Manager",
    "Operations Manager",
    "Supply Chain Manager",
    "Financial Analyst",
    "Marketing Manager",
    "Content Writer / Strategist",
    "Account Executive",
    "Sales Manager",
    "Customer Success Manager",
    "HR Manager",
    "Consultant",
    "Research Scientist",
    "Strategy Manager",
]

_TARGET_INDUSTRIES: list[str] = [
    "Technology",
    "Finance & Banking",
    "Healthcare",
    "Education",
    "E-Commerce & Retail",
    "Media & Entertainment",
    "Consulting",
    "Manufacturing",
    "Non-Profit",
    "Government & Public Sector",
    "Energy & Utilities",
    "Real Estate",
    "Legal",
    "Pharmaceuticals & Biotech",
    "Supply Chain & Logistics",
    "Marketing & Advertising",
    "Insurance",
    "Aerospace & Defense",
    "Agriculture",
    "Hospitality & Travel",
]

_EDU_TYPES   = {"education", "undergraduate", "masters", "phd", "certificate", "high_school"}
_EXP_TYPES   = {"experience", "project", "leadership", "volunteering", "business"}
_SKILL_TYPES = {"skills", "certification", "award", "activity"}

_STATUS_CFG: dict[str, tuple[str, str, str]] = {
    "good":    ("Looks good",        "#dcfce7", "#15803d"),
    "review":  ("Check this",        "#fef9c3", "#b45309"),
    "missing": ("Not found yet",     "#f3f4f6", "#6b7280"),
}

_DIVIDER = '<div style="border-top:1px solid #e5e7eb;margin:2rem 0;"></div>'

_ONBOARDING_CSS = """
<style>
    /* Onboarding page chrome */
    .ob-wrap { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }

    /* Radio pill strip */
    div[data-testid="stRadio"] > div {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }
    div[data-testid="stRadio"] > div > label {
        flex: 0 0 auto !important;
        border: 1.5px solid #d1d5db !important;
        border-radius: 999px !important;
        padding: 0.4rem 1rem !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        background: transparent !important;
        color: #374151 !important;
        transition: border-color 150ms, background 150ms !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > div > label:has(input:checked) {
        border-color: #111827 !important;
        background: #111827 !important;
        color: #ffffff !important;
    }
    div[data-testid="stRadio"] > div > label > div:first-child {
        display: none !important;
    }

    /* Step indicator */
    .ob-step-label {
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #9ca3af;
        margin-bottom: 0.5rem;
    }
    .ob-headline {
        font-size: clamp(1.6rem, 3vw, 2.2rem);
        font-weight: 700;
        letter-spacing: -0.025em;
        line-height: 1.2;
        color: #111827;
        margin-bottom: 0.4rem;
    }
    .ob-sub {
        font-size: 0.95rem;
        color: #6b7280;
        line-height: 1.65;
        margin-bottom: 2rem;
    }
    .ob-section-label {
        font-size: 0.875rem;
        font-weight: 600;
        color: #374151;
        margin: 1.5rem 0 0.75rem;
    }
</style>
"""


# ── Session state ──────────────────────────────────────────────────────────────

def _init() -> None:
    defaults: dict = {
        "ob_step":              1,
        "ob_full_name":         "",
        "ob_email":             "",
        "ob_location":          "",
        "ob_career_stage":      "",
        "ob_target_roles":      [],
        "ob_target_industries": [],
        "ob_docs_added":        False,
        "ob_pending_basics":    {},
        "ob_pending_items":     [],
        "ob_pending_source":    "",
        "ob_review_editing":    None,
        "ob_confirmed":         [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── Navigation ─────────────────────────────────────────────────────────────────

def _go(step: int) -> None:
    st.session_state.ob_step = step
    st.rerun()

def _next() -> None: _go(st.session_state.ob_step + 1)
def _back() -> None: _go(max(1, st.session_state.ob_step - 1))


# ── Shared UI primitives ───────────────────────────────────────────────────────

def _step_indicator(current: int, total: int) -> None:
    dots = []
    for i in range(1, total + 1):
        if i < current:
            dots.append(
                '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                'background:#d1d5db;margin:0 4px;vertical-align:middle;"></span>'
            )
        elif i == current:
            dots.append(
                '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
                'background:#111827;margin:0 4px;vertical-align:middle;"></span>'
            )
        else:
            dots.append(
                '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                'border:1.5px solid #d1d5db;margin:0 4px;vertical-align:middle;"></span>'
            )
    st.markdown(
        f'<div style="text-align:center;margin-bottom:2.5rem;">{"".join(dots)}</div>',
        unsafe_allow_html=True,
    )


def _heading(headline: str, sub: str = "", step_label: str = "") -> None:
    step_html = (
        f'<div class="ob-step-label">Step {step_label} of {TOTAL_STEPS}</div>'
        if step_label else ""
    )
    sub_html = (
        f'<div class="ob-sub">{sub}</div>'
        if sub else '<div style="height:0.5rem;"></div>'
    )
    st.markdown(
        f'<div class="ob-wrap">'
        f'{step_html}'
        f'<div class="ob-headline">{headline}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _section_label(text: str) -> None:
    st.markdown(
        f'<div class="ob-section-label">{text}</div>',
        unsafe_allow_html=True,
    )


def _help_hint(label: str, body: str) -> None:
    with st.expander(f"  {label}", expanded=False):
        st.caption(body)


def _status_badge(status: str) -> str:
    label, bg, color = _STATUS_CFG.get(status, _STATUS_CFG["missing"])
    return (
        f'<span style="display:inline-block;background:{bg};color:{color};'
        f'border-radius:999px;padding:0.15rem 0.7rem;font-size:0.78rem;'
        f'font-weight:600;white-space:nowrap;">{label}</span>'
    )


def _first_name() -> str:
    full = st.session_state.get("ob_full_name", "")
    return full.split()[0] if full else "there"


def _csv_list(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


# ── Stage 1 — Welcome ──────────────────────────────────────────────────────────

def _step1_welcome() -> None:
    _heading(
        "Let's get you set up.",
        "Quick answers now — everything can be edited later.",
        step_label="1",
    )

    # ── Name + Contact ─────────────────────────────────────────────────────────
    _section_label("Your name")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        full_name = st.text_input(
            "Full name",
            value=st.session_state.ob_full_name,
            placeholder="Sarah Johnson",
            key="_ob1_full",
        )
        email = st.text_input(
            "Email",
            value=st.session_state.ob_email,
            placeholder="sarah@example.com",
            key="_ob1_email",
        )
    with c2:
        location = st.text_input(
            "Location",
            value=st.session_state.ob_location,
            placeholder="New York, NY  ·  Remote",
            key="_ob1_loc",
        )

    # ── Career Stage ───────────────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    _section_label("Where are you in your career?")

    current_stage = st.session_state.ob_career_stage or None
    stage_index = _CAREER_STAGES.index(current_stage) if current_stage in _CAREER_STAGES else None

    selected_stage = st.radio(
        "Career stage",
        options=_CAREER_STAGES,
        index=stage_index,
        horizontal=True,
        label_visibility="collapsed",
        key="_ob1_stage",
    )

    # ── Target Roles ───────────────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    _section_label("What kind of work are you looking for?")

    current_roles = st.session_state.ob_target_roles
    if isinstance(current_roles, str):
        current_roles = _csv_list(current_roles)

    target_roles = st.multiselect(
        "Target roles",
        options=_TARGET_ROLES,
        default=[r for r in current_roles if r in _TARGET_ROLES],
        placeholder="Choose one or more roles…",
        key="_ob1_roles",
    )

    # Free-text add for roles not in the list
    extra_roles_raw = st.text_input(
        "Other roles not listed above (optional)",
        value=", ".join(r for r in current_roles if r not in _TARGET_ROLES),
        placeholder="e.g. Revenue Operations Lead",
        key="_ob1_roles_extra",
    )

    current_industries = st.session_state.ob_target_industries
    if isinstance(current_industries, str):
        current_industries = _csv_list(current_industries)

    target_industries = st.multiselect(
        "Industries (optional)",
        options=_TARGET_INDUSTRIES,
        default=[i for i in current_industries if i in _TARGET_INDUSTRIES],
        placeholder="Choose industries…",
        key="_ob1_inds",
    )

    extra_industries_raw = st.text_input(
        "Other industries not listed above (optional)",
        value=", ".join(i for i in current_industries if i not in _TARGET_INDUSTRIES),
        placeholder="e.g. Web3 / Crypto",
        key="_ob1_inds_extra",
    )

    st.markdown(
        '<div style="font-size:0.83rem;color:#9ca3af;margin-top:1rem;">'
        'You can update all of this anytime from your profile.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)

    if primary_button("Continue", key="ob-step1-go", use_container_width=True):
        fn = st.session_state.get("_ob1_full", "").strip()
        if not fn:
            st.error("Please enter your name to continue.")
            return

        extra_roles = _csv_list(st.session_state.get("_ob1_roles_extra", ""))
        extra_inds  = _csv_list(st.session_state.get("_ob1_inds_extra", ""))

        st.session_state.ob_full_name         = fn
        st.session_state.ob_email             = st.session_state.get("_ob1_email", "").strip()
        st.session_state.ob_location          = st.session_state.get("_ob1_loc", "").strip()
        st.session_state.ob_career_stage      = selected_stage or ""
        st.session_state.ob_target_roles      = list(target_roles) + extra_roles
        st.session_state.ob_target_industries = list(target_industries) + extra_inds
        _next()


# ── Stage 2 — Upload ───────────────────────────────────────────────────────────

def _step2_upload() -> None:
    name = _first_name()
    _heading(
        f"Let's build your profile, {name}.",
        "",
        step_label="2",
    )

    st.markdown(
        '<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;'
        'padding:0.9rem 1.1rem;margin-bottom:1.5rem;font-size:0.94rem;line-height:1.6;">'
        '<strong>We\'ll use these to build your profile automatically.</strong><br>'
        'Nothing is final until you review it — you\'ll check every section before anything is saved.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Resume upload ──────────────────────────────────────────────────────────
    _section_label("Resume or CV")
    resume_files = st.file_uploader(
        "Upload resume",
        type=["docx", "pdf", "txt", "md"],
        accept_multiple_files=True,
        key="ob-resume-upload",
        label_visibility="collapsed",
        help="Supports .docx, .pdf, .txt, .md",
    )

    _help_hint(
        "What file types work best?",
        "A **.docx** (Word) file preserves the most formatting. **.pdf** works too — "
        "text extraction is automatic. **.txt** or pasted text also work fine.",
    )

    # ── LinkedIn ───────────────────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    _section_label("LinkedIn profile (optional)")

    li_tab, li_paste = st.tabs(["Upload LinkedIn PDF", "Paste LinkedIn text"])

    linkedin_file = None
    linkedin_text = ""

    with li_tab:
        linkedin_file = st.file_uploader(
            "LinkedIn PDF",
            type=["pdf"],
            key="ob-linkedin-pdf",
            label_visibility="collapsed",
        )
        _help_hint(
            "How do I export my LinkedIn profile as a PDF?",
            "1. Go to your LinkedIn profile page.\n"
            "2. Click **More** → **Save to PDF**.\n"
            "3. Upload the downloaded PDF here.",
        )

    with li_paste:
        linkedin_text = st.text_area(
            "Paste LinkedIn text",
            height=120,
            placeholder="Paste your LinkedIn About section, headline, or any profile text…",
            key="ob-linkedin-paste",
            label_visibility="collapsed",
        )

    # ── Other supporting files ─────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    other_files: list = []
    with st.expander("Other supporting documents (optional)", expanded=False):
        st.caption(
            "Cover letters, project write-ups, portfolio descriptions — anything that helps "
            "fill in your skills and experience."
        )
        _uploaded_other = st.file_uploader(
            "Other files",
            type=["docx", "pdf", "txt", "md"],
            accept_multiple_files=True,
            key="ob-other-upload",
            label_visibility="collapsed",
        )
        if _uploaded_other:
            other_files = _uploaded_other

    _help_hint(
        "Why didn't my document parse correctly?",
        "Scanned PDFs (image-only, no selectable text) can't be read automatically. "
        "Try copy-pasting the content into the text box instead, or use a Word (.docx) version.",
    )

    # ── Navigation ─────────────────────────────────────────────────────────────
    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)

    has_files = bool(resume_files or linkedin_file or other_files)
    has_text  = bool((linkedin_text or "").strip())
    has_input = has_files or has_text

    col_back, col_build, col_skip = st.columns([1, 3, 1], gap="large")

    with col_back:
        if secondary_button("Back", key="ob-upload-back", use_container_width=True):
            _back()

    with col_build:
        if primary_button(
            "Build my profile",
            key="ob-build-btn",
            disabled=not has_input,
            use_container_width=True,
        ):
            all_files = list(resume_files or [])
            if linkedin_file:
                all_files.append(linkedin_file)
            all_files += list(other_files or [])
            _run_extraction(all_files, linkedin_text or "")

    with col_skip:
        if secondary_button("Skip", key="ob-upload-skip", use_container_width=True):
            _go(3)


def _run_extraction(files: list, notes: str) -> None:
    """Read files + notes, extract basics + items, store in session state, advance to review."""
    try:
        with st.spinner("Reading your documents and building your profile…"):
            raw_parts: list[str] = []
            source_names: list[str] = []

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

            if notes.strip():
                raw_parts.append(notes.strip())
                if not source_names:
                    source_names.append("Pasted text")

            raw_text = "\n\n".join(p for p in raw_parts if p.strip())
            if not raw_text.strip():
                st.error("No readable content found — try a different file or paste some text.")
                return

            try:
                validate_profile_input(raw_text)
            except GuardrailFailure as gf:
                st.error(str(gf))
                return

            source_name = ", ".join(source_names) or "Uploaded documents"
            basics = extract_profile_basics_from_resume(raw_text)
            _extra, profile_items = extract_profile_items_from_text(raw_text)
            for k, v in _extra.items():
                if v and not basics.get(k):
                    basics[k] = v

            save_profile_source(
                source_type="resume",
                source_name=source_name,
                raw_text=raw_text,
                parsed_payload={"type": "onboarding"},
            )

        st.session_state.ob_pending_basics  = basics
        st.session_state.ob_pending_items   = [item.to_dict() for item in profile_items]
        st.session_state.ob_pending_source  = source_name
        st.session_state.ob_docs_added      = True
        st.session_state.ob_review_editing  = None
        st.session_state.ob_confirmed       = []
        _go(3)

    except Exception as err:
        st.error(f"Extraction failed: {err}")


# ── Stage 3 — Review ───────────────────────────────────────────────────────────

def _section_status(section: str, basics: dict, items: list[ProfileItem]) -> str:
    if section == "personal":
        has_name    = bool(basics.get("full_name") or st.session_state.ob_full_name)
        has_contact = bool(basics.get("email") or st.session_state.ob_email)
        if has_name and has_contact:
            return "good"
        return "review" if has_name else "missing"

    if section == "education":
        return "good" if any(i.item_type in _EDU_TYPES for i in items) else "missing"

    if section == "experience":
        return "good" if any(i.item_type in _EXP_TYPES for i in items) else "missing"

    if section == "skills":
        return "good" if any(i.item_type in _SKILL_TYPES and i.skills for i in items) else "missing"

    if section == "preferences":
        has_stage = bool(st.session_state.ob_career_stage)
        has_roles = bool(st.session_state.ob_target_roles)
        if has_stage and has_roles:
            return "good"
        return "review" if (has_stage or has_roles) else "missing"

    return "missing"


def _section_header_row(title: str, status: str, section_id: str) -> None:
    confirmed = section_id in st.session_state.ob_confirmed
    badge_html = _status_badge("good" if confirmed else status)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.75rem;">'
        f'<span style="font-size:1rem;font-weight:700;">{title}</span>'
        f'{badge_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _confirm_btn(section_id: str, key: str) -> None:
    confirmed = section_id in st.session_state.ob_confirmed
    label = "Confirmed" if confirmed else "Looks good"
    if st.button(label, key=key, disabled=confirmed, use_container_width=True):
        if section_id not in st.session_state.ob_confirmed:
            st.session_state.ob_confirmed.append(section_id)
        st.rerun()


# ── Section: Personal ──────────────────────────────────────────────────────────

def _review_personal(basics: dict) -> None:
    with st.container(border=True):
        status = _section_status("personal", basics, [])
        _section_header_row("Personal", status, "personal")

        name_val     = st.session_state.ob_full_name  or basics.get("full_name",  "")
        email_val    = st.session_state.ob_email       or basics.get("email",     "")
        phone_val    = basics.get("phone",    "")
        loc_val      = st.session_state.ob_location    or basics.get("location",  "")
        linkedin_val = basics.get("linkedin", "")
        headline_val = basics.get("headline", "")

        if st.session_state.ob_review_editing == "personal":
            with st.form("ob-review-personal"):
                c1, c2 = st.columns(2, gap="medium")
                with c1:
                    r_name     = st.text_input("Full name",  value=name_val)
                    r_email    = st.text_input("Email",      value=email_val)
                    r_phone    = st.text_input("Phone",      value=phone_val)
                with c2:
                    r_location = st.text_input("Location",   value=loc_val)
                    r_linkedin = st.text_input("LinkedIn",   value=linkedin_val)
                    r_headline = st.text_input("Headline",   value=headline_val)
                sv, cn = st.columns(2, gap="medium")
                with sv:
                    saved = st.form_submit_button("Save", use_container_width=True)
                with cn:
                    cancelled = st.form_submit_button("Cancel", use_container_width=True)

            if saved:
                st.session_state.ob_full_name = r_name.strip() or name_val
                st.session_state.ob_email     = r_email.strip()
                st.session_state.ob_location  = r_location.strip()
                st.session_state.ob_pending_basics.update({
                    "full_name": r_name.strip(), "email": r_email.strip(),
                    "phone": r_phone.strip(), "location": r_location.strip(),
                    "linkedin": r_linkedin.strip(), "headline": r_headline.strip(),
                })
                st.session_state.ob_review_editing = None
                st.rerun()
            if cancelled:
                st.session_state.ob_review_editing = None
                st.rerun()

        else:
            rows = [
                ("Name",     name_val),
                ("Email",    email_val),
                ("Phone",    phone_val),
                ("Location", loc_val),
                ("LinkedIn", linkedin_val),
                ("Headline", headline_val),
            ]
            preview_html = "".join(
                f'<div style="display:flex;gap:0.6rem;font-size:0.88rem;padding:0.22rem 0;">'
                f'<span style="color:#6b7280;min-width:5.5rem;">{lbl}</span>'
                f'<span style="font-weight:500;">{val}</span></div>'
                for lbl, val in rows if val
            ) or '<div style="font-size:0.87rem;color:#6b7280;">Nothing extracted yet.</div>'
            st.markdown(preview_html, unsafe_allow_html=True)

            btn_col, conf_col = st.columns([1, 1])
            with btn_col:
                if secondary_button("Edit", key="ob-rev-personal-edit", use_container_width=True):
                    st.session_state.ob_review_editing = "personal"
                    st.rerun()
            with conf_col:
                _confirm_btn("personal", "ob-rev-personal-ok")


# ── Section: Education / Experience ───────────────────────────────────────────

def _review_section_items(
    section_id: str,
    title: str,
    items: list[ProfileItem],
    type_filter: set,
) -> None:
    filtered = [i for i in items if i.item_type in type_filter]
    with st.container(border=True):
        status = "good" if filtered else "missing"
        _section_header_row(title, status, section_id)

        if filtered:
            st.markdown(
                '<div style="font-size:0.84rem;color:#6b7280;margin-bottom:0.5rem;">Select what to keep:</div>',
                unsafe_allow_html=True,
            )
            for item in filtered:
                idx        = items.index(item)
                label      = item.title or "Untitled"
                if item.organization:
                    label += f"  ·  {item.organization}"
                date_parts = [p for p in [item.start_date, item.end_date or ("Present" if item.is_current else "")] if p]
                if date_parts:
                    label += f"  ({' – '.join(date_parts)})"
                st.checkbox(label, value=True, key=f"ob_keep_{section_id}_{idx}")

            conf_col, _ = st.columns([1, 2])
            with conf_col:
                _confirm_btn(section_id, f"ob-rev-{section_id}-ok")
        else:
            st.markdown(
                '<div style="font-size:0.87rem;color:#6b7280;">'
                'Nothing found in your documents. You can add this in your profile later.</div>',
                unsafe_allow_html=True,
            )
            _help_hint(
                "How do I add this later?",
                "After finishing setup, open **Career Profile** from the sidebar. "
                "Use the Education / Work Experience tab to add entries manually.",
            )


# ── Section: Skills ────────────────────────────────────────────────────────────

def _review_skills(items: list[ProfileItem]) -> None:
    skill_items = [i for i in items if i.item_type in _SKILL_TYPES and i.skills]
    all_skills  = list(dict.fromkeys(s for i in skill_items for s in i.skills))

    with st.container(border=True):
        status = "good" if all_skills else "missing"
        _section_header_row("Skills", status, "skills")

        if st.session_state.ob_review_editing == "skills":
            current_val = ", ".join(all_skills)
            edited_skills = st.text_area(
                "Edit skills (comma-separated)",
                value=st.session_state.get("_ob_skills_edit", current_val),
                height=100,
                key="_ob_skills_edit",
                label_visibility="collapsed",
            )
            sv_col, cn_col = st.columns(2)
            with sv_col:
                if secondary_button("Save", key="ob-skills-edit-save", use_container_width=True):
                    st.session_state["_ob_skills_edited"] = edited_skills
                    st.session_state.ob_review_editing = None
                    st.rerun()
            with cn_col:
                if secondary_button("Cancel", key="ob-skills-edit-cancel", use_container_width=True):
                    st.session_state.ob_review_editing = None
                    st.rerun()

        elif all_skills:
            chips = "".join(
                f'<span style="display:inline-block;background:#f3f4f6;'
                f'border:1px solid #e5e7eb;border-radius:999px;'
                f'padding:0.18rem 0.65rem;font-size:0.83rem;margin:0.15rem 0.15rem 0 0;">{s}</span>'
                for s in all_skills[:20]
            )
            if len(all_skills) > 20:
                chips += f'<span style="font-size:0.8rem;color:#9ca3af;"> +{len(all_skills)-20} more</span>'
            st.markdown(f'<div style="line-height:2;">{chips}</div>', unsafe_allow_html=True)

            edit_col, conf_col = st.columns([1, 1])
            with edit_col:
                if secondary_button("Edit", key="ob-skills-edit-btn", use_container_width=True):
                    st.session_state["_ob_skills_edit"] = ", ".join(all_skills)
                    st.session_state.ob_review_editing = "skills"
                    st.rerun()
            with conf_col:
                _confirm_btn("skills", "ob-rev-skills-ok")
        else:
            st.markdown(
                '<div style="font-size:0.87rem;color:#6b7280;">'
                'No skills found. You can add them in your profile later.</div>',
                unsafe_allow_html=True,
            )


# ── Section: Preferences ───────────────────────────────────────────────────────

def _review_preferences() -> None:
    with st.container(border=True):
        status = _section_status("preferences", {}, [])
        _section_header_row("Preferences", status, "preferences")

        roles = st.session_state.ob_target_roles
        inds  = st.session_state.ob_target_industries
        roles_str = ", ".join(roles) if isinstance(roles, list) else roles or "—"
        inds_str  = ", ".join(inds)  if isinstance(inds, list)  else inds  or "—"

        rows = [
            ("Career stage",  st.session_state.ob_career_stage or "—"),
            ("Target roles",  roles_str or "—"),
            ("Industries",    inds_str  or "—"),
        ]
        preview_html = "".join(
            f'<div style="display:flex;gap:0.6rem;font-size:0.88rem;padding:0.22rem 0;">'
            f'<span style="color:#6b7280;min-width:7rem;">{lbl}</span>'
            f'<span style="font-weight:500;">{val}</span></div>'
            for lbl, val in rows
        )
        st.markdown(preview_html, unsafe_allow_html=True)
        st.caption("Saved from Step 1 — edit anytime in Career Profile → Preferences.")
        conf_col, _ = st.columns([1, 2])
        with conf_col:
            _confirm_btn("preferences", "ob-rev-prefs-ok")


# ── Review orchestrator ────────────────────────────────────────────────────────

def _step3_review() -> None:
    _heading(
        "Check your profile.",
        "",
        step_label="3",
    )

    st.markdown(
        '<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;'
        'padding:0.85rem 1.1rem;margin-bottom:1.5rem;font-size:0.93rem;line-height:1.6;">'
        '<strong>We filled this in for you.</strong> '
        'Please take a moment to check it before continuing. '
        'Use the <em>Edit</em> button in any section to make corrections.'
        '</div>',
        unsafe_allow_html=True,
    )

    basics = st.session_state.ob_pending_basics or {}
    items  = [ProfileItem(**d) for d in (st.session_state.ob_pending_items or [])]

    _review_personal(basics)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    _review_section_items("education",  "Education",       items, _EDU_TYPES)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    _review_section_items("experience", "Work Experience", items, _EXP_TYPES)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    _review_skills(items)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    _review_preferences()

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    _help_hint(
        "How do I fix wrong extraction?",
        "Click **Edit** in any section to correct names, dates, or details. "
        "For deeper changes (bullet points, descriptions), open **Career Profile** after setup.",
    )
    _help_hint(
        "What if my profile is incomplete?",
        "That's fine — click **Save and continue** now. "
        "You can fill in missing sections anytime from **Career Profile** in the sidebar.",
    )

    st.markdown('<div style="height:1.25rem;"></div>', unsafe_allow_html=True)
    col_back, col_save, col_skip = st.columns([1, 3, 1], gap="large")

    with col_back:
        if secondary_button("Back", key="ob-review-back", use_container_width=True):
            _back()

    with col_save:
        if primary_button("Save and continue", key="ob-review-save", use_container_width=True):
            profile = create_or_get_profile()
            _persist_all(profile, basics, items)
            _go(4)

    with col_skip:
        if secondary_button("Skip", key="ob-review-skip", use_container_width=True):
            _save_basics_from_steps()
            _go(4)


# ── Stage 4 — Done ─────────────────────────────────────────────────────────────

def _step4_done() -> None:
    name       = _first_name()
    docs_added = st.session_state.ob_docs_added

    _heading(f"You're all set, {name}.")

    roles = st.session_state.ob_target_roles
    inds  = st.session_state.ob_target_industries
    roles_str = ", ".join(roles) if isinstance(roles, list) else roles or "—"
    inds_str  = ", ".join(inds)  if isinstance(inds, list)  else inds  or "—"

    with st.container(border=True):
        rows = [
            ("Name",          st.session_state.ob_full_name          or "—"),
            ("Career Stage",  st.session_state.ob_career_stage       or "—"),
            ("Target Roles",  roles_str or "—"),
            ("Industries",    inds_str  or "—"),
            ("Profile",       "Built from documents" if docs_added else "Set up from your answers"),
        ]
        for label, value in rows:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                f'padding:0.4rem 0;border-bottom:1px solid #f3f4f6;font-size:0.93rem;">'
                f'<span style="color:#6b7280;min-width:9rem;">{label}</span>'
                f'<span style="font-weight:500;text-align:right;">{value}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:1.25rem;"></div>', unsafe_allow_html=True)

    st.caption(
        "Your profile is ready to verify. Open it to confirm the details look right "
        "before your first resume optimisation."
    )

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    if primary_button("Verify my profile", key="ob-done-profile", use_container_width=True):
        _finish("profile")

    st.markdown('<div style="height:0.4rem;"></div>', unsafe_allow_html=True)
    if secondary_button("Skip to the app", key="ob-done-skip", use_container_width=True):
        _finish("landing")


# ── Persistence helpers ────────────────────────────────────────────────────────

def _persist_all(profile, basics: dict, items: list[ProfileItem]) -> None:
    """Save reviewed basics + selected items. Step-1 data always wins over extraction."""
    if basics or st.session_state.ob_full_name:
        roles = st.session_state.ob_target_roles
        inds  = st.session_state.ob_target_industries
        if isinstance(roles, str):
            roles = _csv_list(roles)
        if isinstance(inds, str):
            inds = _csv_list(inds)

        save_profile_basics(
            full_name=st.session_state.ob_full_name         or basics.get("full_name",  ""),
            email    =st.session_state.ob_email              or basics.get("email",      ""),
            phone    =basics.get("phone",    ""),
            location =st.session_state.ob_location           or basics.get("location",  ""),
            linkedin =basics.get("linkedin", ""),
            headline =basics.get("headline", ""),
            career_stage=st.session_state.ob_career_stage   or "Student",
            summary  =basics.get("summary",  ""),
            target_roles       =roles or profile.target_roles,
            target_industries  =inds  or profile.target_industries,
            preferred_locations=profile.preferred_locations,
            work_authorization =profile.work_authorization,
        )

    edu_exp_items = [i for i in items if i.item_type in (_EDU_TYPES | _EXP_TYPES)]
    skill_items   = [i for i in items if i.item_type in _SKILL_TYPES]
    other_items   = [i for i in items if i not in edu_exp_items and i not in skill_items]

    to_save: list[ProfileItem] = []

    for section_id, section_items in [
        ("education",  [i for i in edu_exp_items if i.item_type in _EDU_TYPES]),
        ("experience", [i for i in edu_exp_items if i.item_type in _EXP_TYPES]),
    ]:
        for item in section_items:
            idx = items.index(item)
            if st.session_state.get(f"ob_keep_{section_id}_{idx}", True):
                to_save.append(item)

    edited_skills_str = st.session_state.get("_ob_skills_edited")
    if edited_skills_str is not None:
        edited_skills = _csv_list(edited_skills_str)
        if edited_skills:
            to_save.append(ProfileItem(
                profile_id=profile.id,
                item_type="skills",
                title="Skills",
                skills=edited_skills,
                keywords=edited_skills[:16],
                confidence_score=1.0,
                verification_status="verified",
                visibility="active",
            ))
    else:
        for item in skill_items:
            idx = items.index(item)
            if st.session_state.get(f"ob_keep_skills_{idx}", True):
                to_save.append(item)

    to_save += other_items

    for item in to_save:
        item.profile_id          = profile.id
        item.verification_status = "verified"
    if to_save:
        save_profile_items(to_save)


def _save_basics_from_steps() -> None:
    """Persist step-1 data only (called when skipping the review)."""
    profile = create_or_get_profile()
    roles = st.session_state.ob_target_roles
    inds  = st.session_state.ob_target_industries
    if isinstance(roles, str):
        roles = _csv_list(roles)
    if isinstance(inds, str):
        inds = _csv_list(inds)

    if not any([
        st.session_state.ob_full_name,
        st.session_state.ob_career_stage,
        roles,
        st.session_state.ob_email,
        st.session_state.ob_location,
    ]):
        return

    save_profile_basics(
        full_name          = st.session_state.ob_full_name          or profile.full_name,
        email              = st.session_state.ob_email               or profile.email,
        phone              = profile.phone,
        location           = st.session_state.ob_location            or profile.location,
        linkedin           = profile.linkedin,
        headline           = profile.headline,
        career_stage       = st.session_state.ob_career_stage        or profile.career_stage or "Student",
        summary            = profile.summary,
        target_roles       = roles or profile.target_roles,
        target_industries  = inds  or profile.target_industries,
        preferred_locations= profile.preferred_locations,
        work_authorization = profile.work_authorization,
    )


def _finish(dest: str) -> None:
    """Mark onboarding complete, clear wizard state, and route."""
    complete_onboarding()
    st.session_state.ob_just_completed = True
    for key in [k for k in st.session_state if k.startswith("ob_") or k.startswith("_ob")]:
        del st.session_state[key]
    st.session_state.screen = dest
    st.rerun()


# ── Main entry point ───────────────────────────────────────────────────────────

def render_onboarding_screen() -> None:
    """Render the active onboarding stage inside a centred column."""
    st.markdown(_ONBOARDING_CSS, unsafe_allow_html=True)
    _init()
    start_onboarding()

    step = st.session_state.ob_step

    _, center, _ = st.columns([1, 4, 1])
    with center:
        _step_indicator(step, TOTAL_STEPS)

        if step == 1:
            _step1_welcome()
        elif step == 2:
            _step2_upload()
        elif step == 3:
            _step3_review()
        elif step == 4:
            _step4_done()
        else:
            _go(1)
