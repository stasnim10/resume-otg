"""
First-run onboarding wizard.

Shown exactly once — when a new user opens the app for the first time and
`profile.onboarding_complete` is False. After the user finishes (or explicitly
skips the whole wizard), `complete_onboarding()` is called and the wizard
never appears again.

Five steps, one focus each:
  1. Welcome / Name       — who are you?
  2. Career Stage         — visual card-picker
  3. What You're After    — target roles + industries
  4. Add Documents        — upload/paste → extract suggestions → review
  5. All Set              — summary card + adaptive CTA
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from ui_helpers import primary_button, secondary_button
from docx_handler import extract_text
from profile_extractor import extract_profile_items_from_text
from profile_schema import ProfileItem
from profile_extractor import extract_profile_basics as extract_profile_basics_from_resume
from profile_store import (
    complete_onboarding,
    create_or_get_profile,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    start_onboarding,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOTAL_STEPS = 5

_CAREER_STAGES: list[tuple[str, str, str]] = [
    ("Student",       "📚", "In school or recently graduated"),
    ("Early Career",  "🌱", "0–3 years of work experience"),
    ("Mid-Level",     "⚡", "3–8 years, growing in your field"),
    ("Manager",       "🎯", "Leading teams or moving into management"),
    ("Executive",     "🏔", "Senior leadership or C-suite"),
    ("Career Pivot",  "🔄", "Switching industries or role type"),
    ("Not Sure Yet",  "💭", "Still figuring it out — that's fine"),
]

# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _init() -> None:
    defaults: dict = {
        "ob_step":               1,
        "ob_first_name":         "",
        "ob_full_name":          "",
        "ob_email":              "",
        "ob_location":           "",
        "ob_career_stage":       "",
        "ob_target_roles":       "",
        "ob_target_industries":  "",
        "ob_docs_added":         False,
        "ob_pending_basics":     {},
        "ob_pending_items":      [],
        "ob_pending_source":     "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _go(step: int) -> None:
    st.session_state.ob_step = step
    st.rerun()


def _next() -> None:
    _go(st.session_state.ob_step + 1)


def _back() -> None:
    _go(max(1, st.session_state.ob_step - 1))


# ---------------------------------------------------------------------------
# Shared UI primitives
# ---------------------------------------------------------------------------

def _step_indicator(current: int, total: int) -> None:
    dots = []
    for i in range(1, total + 1):
        if i < current:
            # completed
            dots.append(
                '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                'background:var(--muted);margin:0 5px;vertical-align:middle;opacity:0.55;"></span>'
            )
        elif i == current:
            # active
            dots.append(
                '<span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
                'background:var(--text);margin:0 5px;vertical-align:middle;"></span>'
            )
        else:
            # future
            dots.append(
                '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                'border:1.5px solid var(--line-strong);margin:0 5px;vertical-align:middle;opacity:0.4;"></span>'
            )
    st.markdown(
        f'<div style="text-align:center;margin-bottom:2.5rem;">{"".join(dots)}</div>',
        unsafe_allow_html=True,
    )


def _heading(headline: str, sub: str = "", step_label: str = "") -> None:
    step_html = (
        f'<div style="font-size:0.78rem;font-weight:600;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:var(--muted);margin-bottom:0.6rem;">'
        f'Step {step_label} of {TOTAL_STEPS}</div>'
        if step_label else ""
    )
    sub_html = (
        f'<div style="color:var(--muted);font-size:0.97rem;line-height:1.65;margin-top:0.5rem;'
        f'margin-bottom:2rem;">{sub}</div>'
        if sub else '<div style="height:1.5rem;"></div>'
    )
    st.markdown(
        f'{step_html}'
        f'<div style="font-size:clamp(1.5rem,3vw,2.1rem);font-weight:700;letter-spacing:-0.022em;'
        f'line-height:1.2;">{headline}</div>'
        f'{sub_html}',
        unsafe_allow_html=True,
    )


def _nav_row(
    *,
    show_back: bool = True,
    next_label: str = "Continue →",
    next_key: str = "ob-next",
    next_disabled: bool = False,
    show_skip: bool = True,
    skip_label: str = "Skip",
    skip_key: str = "ob-skip",
) -> tuple[bool, bool]:
    """Render Back / Continue / Skip row. Returns (next_clicked, skip_clicked)."""
    cols = st.columns([1, 3, 1] if show_back else [3, 1], gap="large")
    idx = 0

    if show_back:
        with cols[idx]:
            if secondary_button("← Back", key=f"{next_key}-back", use_container_width=True):
                _back()
        idx += 1

    with cols[idx]:
        nxt = primary_button(next_label, key=next_key,
                             disabled=next_disabled, use_container_width=True)
    idx += 1

    skp = False
    if show_skip:
        with cols[idx]:
            skp = secondary_button(skip_label, key=skip_key, use_container_width=True)

    return nxt, skp


# ---------------------------------------------------------------------------
# Step 1 — Welcome / Name
# ---------------------------------------------------------------------------

def _step1_welcome() -> None:
    _heading(
        "Hi there! What should I call you?",
        "We'll use your name to personalise the experience and pre-fill your resume drafts.",
        step_label="1",
    )

    with st.form("ob-step1"):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            first_name = st.text_input(
                "First name ✱",
                value=st.session_state.ob_first_name,
                placeholder="Sarah",
            )
            full_name = st.text_input(
                "Full name",
                value=st.session_state.ob_full_name,
                placeholder="Sarah Johnson",
                help="Used on your resume — can be added later",
            )
        with c2:
            email = st.text_input(
                "Email",
                value=st.session_state.ob_email,
                placeholder="sarah@example.com",
            )
            location = st.text_input(
                "Location",
                value=st.session_state.ob_location,
                placeholder="New York, NY  ·  Remote",
            )

        submitted = st.form_submit_button("Continue →", use_container_width=True)

    if submitted:
        if not first_name.strip():
            st.error("Just a first name is enough — we need something to call you!")
            return
        st.session_state.ob_first_name    = first_name.strip()
        st.session_state.ob_full_name     = full_name.strip() or first_name.strip()
        st.session_state.ob_email         = email.strip()
        st.session_state.ob_location      = location.strip()
        _next()


# ---------------------------------------------------------------------------
# Step 2 — Career Stage
# ---------------------------------------------------------------------------

def _step2_career_stage() -> None:
    name = st.session_state.ob_first_name or "there"
    _heading(
        f"Nice to meet you, {name}! Where are you in your career?",
        "Helps us aim resume advice and job suggestions at where you actually are — not a generic template.",
        step_label="2",
    )

    selected = st.session_state.ob_career_stage

    # 3-column card grid
    for row_idx in range(0, len(_CAREER_STAGES), 3):
        chunk = _CAREER_STAGES[row_idx : row_idx + 3]
        cols = st.columns(len(chunk), gap="medium")
        for col, (label, icon, desc) in zip(cols, chunk):
            with col:
                is_sel = selected == label
                border = "2px solid var(--text)" if is_sel else "1px solid var(--line)"
                bg     = "var(--surface-muted)" if is_sel else "transparent"
                check  = "✓ " if is_sel else ""
                st.markdown(
                    f'<div style="border:{border};background:{bg};border-radius:12px;'
                    f'padding:1rem 0.6rem;text-align:center;margin-bottom:0.4rem;">'
                    f'<div style="font-size:1.7rem;margin-bottom:0.3rem;">{icon}</div>'
                    f'<div style="font-weight:600;font-size:0.88rem;margin-bottom:0.15rem;">'
                    f'{check}{label}</div>'
                    f'<div style="font-size:0.76rem;color:var(--muted);line-height:1.45;">'
                    f'{desc}</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Selected ✓" if is_sel else "Select",
                    key=f"ob-stage-{label}",
                    use_container_width=True,
                ):
                    st.session_state.ob_career_stage = label
                    st.rerun()

    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)
    nxt, skp = _nav_row(
        next_label="Continue →",
        next_key="ob-step2-next",
        next_disabled=not selected,
        skip_key="ob-step2-skip",
    )
    if nxt or skp:
        _go(3)


# ---------------------------------------------------------------------------
# Step 3 — What You're After
# ---------------------------------------------------------------------------

def _step3_direction() -> None:
    _heading(
        "What kinds of roles are you targeting?",
        "The more direction you give us, the better we can aim every resume draft. "
        "You can always update this later.",
        step_label="3",
    )

    with st.form("ob-step3"):
        target_roles = st.text_input(
            "Target roles",
            value=st.session_state.ob_target_roles,
            placeholder="Operations Analyst, Supply Chain Manager, Project Lead…",
            help="Comma-separated is fine",
        )
        st.caption(
            "💡 Be as specific or broad as you like. "
            "We use this to surface the most relevant parts of your profile."
        )
        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
        target_industries = st.text_input(
            "Industries you're interested in",
            value=st.session_state.ob_target_industries,
            placeholder="Supply Chain, Technology, Finance, Healthcare…",
            help="Comma-separated is fine",
        )

        c1, c2, c3 = st.columns([1, 3, 1], gap="large")
        with c1:
            back_btn = st.form_submit_button("← Back", use_container_width=True)
        with c2:
            next_btn = st.form_submit_button("Continue →", use_container_width=True)
        with c3:
            skip_btn = st.form_submit_button("Skip", use_container_width=True)

    if back_btn:
        _go(2)
    if next_btn:
        st.session_state.ob_target_roles      = target_roles.strip()
        st.session_state.ob_target_industries = target_industries.strip()
        _go(4)
    if skip_btn:
        _go(4)


# ---------------------------------------------------------------------------
# Step 4 — Add Documents
# ---------------------------------------------------------------------------

def _step4_documents() -> None:
    # If suggestions are already waiting from a prior extract, show the review panel
    if st.session_state.ob_pending_basics or st.session_state.ob_pending_items:
        _step4_review_suggestions()
        return

    _heading(
        "Let's build your profile faster.",
        "Upload a resume or paste your LinkedIn About text. We'll extract what we can and "
        "show you everything before saving a single thing — nothing goes into your profile silently.",
        step_label="4",
    )

    up_col, notes_col = st.columns([1, 1], gap="large")
    with up_col:
        uploaded = st.file_uploader(
            "Upload files",
            type=["docx", "pdf", "txt", "md"],
            accept_multiple_files=True,
            key="ob-doc-upload",
            label_visibility="collapsed",
            help="Supports .docx, .pdf, .txt, .md",
        )
    with notes_col:
        notes = st.text_area(
            "Or paste text",
            height=140,
            placeholder="Paste your LinkedIn About section, resume content, or career notes…",
            key="ob-doc-notes",
            label_visibility="collapsed",
        )

    has_input = bool(uploaded or (notes and notes.strip()))
    st.markdown('<div style="height:0.75rem;"></div>', unsafe_allow_html=True)

    col_back, col_extract, col_skip = st.columns([1, 3, 1], gap="large")
    with col_back:
        if secondary_button("← Back", key="ob-docs-back", use_container_width=True):
            _go(3)
    with col_extract:
        extract_clicked = primary_button(
            "Extract my profile →",
            key="ob-extract-btn",
            disabled=not has_input,
            use_container_width=True,
        )
    with col_skip:
        if secondary_button("Skip →", key="ob-docs-skip", use_container_width=True):
            _go(5)

    if extract_clicked:
        _run_extraction(uploaded, notes or "")


def _run_extraction(uploaded: object, notes: str) -> None:
    """Read files + notes, extract, store in session state for review."""
    try:
        with st.spinner("Reading your documents and extracting profile information…"):
            raw_parts: list[str] = []
            source_names: list[str] = []

            if uploaded:
                files = uploaded if isinstance(uploaded, list) else [uploaded]
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
                    source_names.append("Manual notes")

            raw_text = "\n\n".join(p for p in raw_parts if p.strip())
            if not raw_text.strip():
                st.error("No readable content found — try a different file or paste some text.")
                return

            source_name = ", ".join(source_names) or "Uploaded documents"
            basics = extract_profile_basics_from_resume(raw_text)
            _extra, profile_items = extract_profile_items_from_text(raw_text)
            for k, v in _extra.items():
                if v and not basics.get(k):
                    basics[k] = v

            save_profile_source(
                source_type="resume" if uploaded else "manual_notes",
                source_name=source_name,
                raw_text=raw_text,
                parsed_payload={"type": "onboarding"},
            )

        st.session_state.ob_pending_basics  = basics
        st.session_state.ob_pending_items   = [item.to_dict() for item in profile_items]
        st.session_state.ob_pending_source  = source_name
        st.session_state.ob_docs_added      = True
        st.rerun()

    except Exception as err:
        st.error(str(err))


def _step4_review_suggestions() -> None:
    """Review panel shown after extraction — nothing saved until user confirms."""
    basics      = st.session_state.ob_pending_basics
    item_dicts  = st.session_state.ob_pending_items
    source_name = st.session_state.ob_pending_source or "your document"

    _heading(
        "Here's what we found.",
        f"From **{source_name}**. Nothing is saved yet — review below, then save what fits.",
        step_label="4",
    )

    profile = create_or_get_profile()

    # Personal info block
    if basics:
        with st.container(border=True):
            st.markdown("**Personal information extracted:**")
            field_labels = [
                ("Name",     "full_name"),
                ("Email",    "email"),
                ("Phone",    "phone"),
                ("Location", "location"),
                ("LinkedIn", "linkedin"),
                ("Headline", "headline"),
            ]
            for label, key in field_labels:
                if basics.get(key):
                    st.markdown(
                        f'<div style="display:flex;gap:0.75rem;padding:0.3rem 0;font-size:0.93rem;">'
                        f'<span style="color:var(--muted);min-width:6rem;">{label}</span>'
                        f'<span style="font-weight:500;">{basics[key]}</span></div>',
                        unsafe_allow_html=True,
                    )

    # Career items block
    items = [ProfileItem(**d) for d in item_dicts]
    by_type: dict[str, list[tuple[int, ProfileItem]]] = {}
    for idx, item in enumerate(items):
        by_type.setdefault(item.item_type, []).append((idx, item))

    if items:
        with st.container(border=True):
            st.markdown(f"**{len(items)} career items found — select what to save:**")
            for type_key, indexed_items in by_type.items():
                st.markdown(
                    f'<div style="font-weight:600;font-size:0.83rem;margin:0.75rem 0 0.2rem;'
                    f'text-transform:capitalize;color:var(--muted);">{type_key}</div>',
                    unsafe_allow_html=True,
                )
                for idx, item in indexed_items:
                    label = item.title or "Untitled"
                    if item.organization:
                        label += f" · {item.organization}"
                    st.checkbox(label, value=True, key=f"ob_item_{idx}")

    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)
    col_save, col_discard = st.columns(2, gap="large")

    with col_save:
        if primary_button("Save & Continue →", key="ob-sugg-save", use_container_width=True):
            _persist_suggestions(profile, basics, items, by_type)
            st.session_state.ob_pending_basics = {}
            st.session_state.ob_pending_items  = []
            _go(5)

    with col_discard:
        if secondary_button("Discard & Continue →", key="ob-sugg-discard", use_container_width=True):
            st.session_state.ob_pending_basics = {}
            st.session_state.ob_pending_items  = []
            _go(5)


def _persist_suggestions(profile, basics: dict, items: list, by_type: dict) -> None:
    """Save reviewed basics + checked items. Respects data already entered in steps 1–3."""
    # Basics: step 1–3 data wins; fill any gaps from the document
    if basics:
        save_profile_basics(
            full_name          = st.session_state.ob_full_name     or basics.get("full_name",  ""),
            email              = st.session_state.ob_email          or basics.get("email",      ""),
            phone              = basics.get("phone",    ""),
            location           = st.session_state.ob_location       or basics.get("location",  ""),
            linkedin           = basics.get("linkedin", ""),
            headline           = basics.get("headline", ""),
            career_stage       = st.session_state.ob_career_stage   or "Student",
            summary            = basics.get("summary",  ""),
            target_roles       = _csv_list(st.session_state.ob_target_roles)      or profile.target_roles,
            target_industries  = _csv_list(st.session_state.ob_target_industries) or profile.target_industries,
            preferred_locations= profile.preferred_locations,
            work_authorization = profile.work_authorization,
        )

    # Items: save only the checked ones
    to_save = [
        item
        for type_key, indexed_items in by_type.items()
        for idx, item in indexed_items
        if st.session_state.get(f"ob_item_{idx}", True)
    ]
    for item in to_save:
        item.profile_id         = profile.id
        item.verification_status = "verified"
    if to_save:
        save_profile_items(to_save)


def _csv_list(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


# ---------------------------------------------------------------------------
# Step 5 — All Set
# ---------------------------------------------------------------------------

def _step5_all_set() -> None:
    name       = st.session_state.ob_first_name or "there"
    docs_added = st.session_state.ob_docs_added

    _heading(
        f"You're all set, {name}! 🎉",
        "Here's a summary of what we captured. Everything can be edited anytime in your profile.",
    )

    # Save steps 1–3 data now (if not already saved in step 4)
    _save_basics_from_steps()

    # Summary card
    with st.container(border=True):
        rows = [
            ("Name",          st.session_state.ob_full_name     or "—"),
            ("Career Stage",  st.session_state.ob_career_stage  or "—"),
            ("Target Roles",  st.session_state.ob_target_roles  or "—"),
            ("Industries",    st.session_state.ob_target_industries or "—"),
            ("Documents",     "✓ Extracted and reviewed" if docs_added else "None added yet"),
        ]
        for label, value in rows:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                f'padding:0.42rem 0;border-bottom:1px solid var(--line);font-size:0.94rem;">'
                f'<span style="color:var(--muted);min-width:9rem;">{label}</span>'
                f'<span style="font-weight:500;text-align:right;">{value}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:1.75rem;"></div>', unsafe_allow_html=True)

    # Adaptive CTA
    if docs_added:
        cta_label = "Go to my profile →"
        cta_dest  = "profile"
        cta_hint  = "Your profile has been seeded from your documents. Review and fill in any gaps."
    elif st.session_state.ob_full_name:
        cta_label = "Build my first resume →"
        cta_dest  = "input"
        cta_hint  = "We have enough to get started. You can always enrich your profile later."
    else:
        cta_label = "Take me to the app →"
        cta_dest  = "landing"
        cta_hint  = ""

    if cta_hint:
        st.caption(cta_hint)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    if primary_button(cta_label, key="ob-finish", use_container_width=True):
        _finish(cta_dest)

    # Secondary: go to profile regardless
    if cta_dest != "profile":
        st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
        if secondary_button("Go to my profile", key="ob-finish-profile", use_container_width=True):
            _finish("profile")


def _save_basics_from_steps() -> None:
    """
    Persist steps 1–3 data into the profile.
    Called at step 5 entry. Safe to call multiple times — uses `or` merge so
    if data was already saved during step 4's suggestion review it won't overwrite.
    """
    profile = create_or_get_profile()
    # Only write if we actually collected something
    if not any([
        st.session_state.ob_full_name,
        st.session_state.ob_career_stage,
        st.session_state.ob_target_roles,
        st.session_state.ob_target_industries,
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
        target_roles       = _csv_list(st.session_state.ob_target_roles)      or profile.target_roles,
        target_industries  = _csv_list(st.session_state.ob_target_industries) or profile.target_industries,
        preferred_locations= profile.preferred_locations,
        work_authorization = profile.work_authorization,
    )


def _finish(dest: str) -> None:
    """Mark onboarding complete, clear wizard session state, and route."""
    complete_onboarding()
    for key in [k for k in st.session_state if k.startswith("ob_")]:
        del st.session_state[key]
    st.session_state.screen = dest
    st.rerun()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_onboarding_screen() -> None:
    """Render the active onboarding step inside a centred column."""
    _init()
    start_onboarding()  # no-op if already started

    step = st.session_state.ob_step

    # Centre the wizard in a narrow column for focus
    _, center, _ = st.columns([1, 4, 1])
    with center:
        _step_indicator(step, TOTAL_STEPS)

        if step == 1:
            _step1_welcome()
        elif step == 2:
            _step2_career_stage()
        elif step == 3:
            _step3_direction()
        elif step == 4:
            _step4_documents()
        elif step == 5:
            _step5_all_set()
        else:
            _go(1)
