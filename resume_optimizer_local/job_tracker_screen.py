"""
Job Tracker — simplified list view.

Entry point: render_job_tracker_screen()
"""
from __future__ import annotations

import datetime
import html

import streamlit as st

from job_tracker_store import (
    STATUS_COLORS,
    TRACKER_STATUSES,
    add_job_manually,
    add_note,
    delete_job,
    list_jobs,
    update_job_metadata,
    update_job_status,
)
from ui_helpers import primary_button


def _inject_jt_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --jt-card-bg: #ffffff;
            --jt-card-border: #e6e8ec;
            --jt-text-strong: #111111;
            --jt-text-muted: #7a7a7a;
            --jt-text-faint: #b4b4bb;
            --jt-divider: #eceef2;
            --jt-coral: #d97757;
            --jt-coral-hover: #c9683f;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px !important;
            border: 1px solid var(--jt-card-border) !important;
            box-shadow: none !important;
            background: var(--jt-card-bg) !important;
            padding: 0.5rem 0.25rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }

        .jt-toolbar-row {
            margin-bottom: 1rem !important;
        }
        .jt-toolbar-row [data-testid="column"] {
            display: flex !important;
            align-items: flex-start !important;
        }

        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"] {
            width: 100% !important;
            margin-top: 0 !important;
            padding-top: 0 !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] > div > div {
            border-radius: 10px !important;
            border: 1.5px solid rgba(0,0,0,0.10) !important;
            background: #ffffff !important;
            font-size: 0.85rem !important;
            min-height: 44px !important;
            height: 44px !important;
            box-sizing: border-box !important;
            margin: 0 !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: var(--jt-coral) !important;
            box-shadow: 0 0 0 3px rgba(217,119,87,0.12) !important;
        }

        .jt-selection-copy,
        .jt-visible-copy {
            color: #8b8b93;
            font-size: 0.8rem;
            font-weight: 600;
            padding-bottom: 0.5rem;
        }

        /* ✨ INLINE FORM BUTTON ALIGNMENT (SAVE, CANCEL, DELETE) ✨ */
        .jt-form-actions [data-testid="column"] {
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
        }
        .jt-form-actions button,
        .jt-form-actions [data-testid^="stBaseButton"] button {
            height: 40px !important;
            min-height: 40px !important;
            margin: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 16px !important;
            width: 100% !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            border-radius: 999px !important;
            box-sizing: border-box !important;
            line-height: 1 !important;
        }

        .jt-inline-tool button,
        .jt-inline-tool-danger button {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            min-height: 0 !important;
            height: auto !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            text-decoration: none !important;
        }
        .jt-inline-tool button { color: #5a5a5f !important; }
        .jt-inline-tool button:hover { color: #111111 !important; text-decoration: underline !important; }
        .jt-inline-tool-danger button { color: #c0392b !important; }
        .jt-inline-tool-danger button:hover { text-decoration: underline !important; }

        /* ✨ FIX: STRICT 40x40 CIRCLES ✨ */
        .jt-icon,
        .jt-icon-active {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: 40px !important;
        }

        .jt-icon button,
        .jt-icon-active button,
        .jt-icon [data-testid^="stBaseButton"] button,
        .jt-icon-active [data-testid^="stBaseButton"] button {
            width: 40px !important;
            height: 40px !important;
            min-width: 40px !important;
            max-width: 40px !important;
            aspect-ratio: 1 / 1 !important;
            border-radius: 50% !important;
            padding: 0 !important;
            margin: auto !important;
            border: none !important;
            box-shadow: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: var(--jt-coral) !important;
            color: #111111 !important;
            flex-shrink: 0 !important;
        }
        .jt-icon button:hover,
        .jt-icon [data-testid^="stBaseButton"] button:hover {
            background: var(--jt-coral-hover) !important;
        }
        .jt-icon-active button,
        .jt-icon-active [data-testid^="stBaseButton"] button {
            background: var(--jt-coral-hover) !important;
            border: 2px solid #111111 !important;
        }
        .jt-icon button p,
        .jt-icon-active button p {
            margin: 0 !important;
            padding: 0 !important;
            color: #111111 !important;
            font-size: 1.15rem !important;
            line-height: 0 !important;
        }

        /* ✨ EXPLICIT COLUMN TYPOGRAPHY ✨ */
        .jt-title-link {
            color: #111111 !important;
            font-size: 17px !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
        }
        .jt-row-company {
            color: #111111 !important;
            font-size: 17px !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
        }
        .jt-card-meta-text {
            color: #8b8b93 !important;
            font-size: 12px !important;
            margin-top: 0.15rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
        }

        /* ✨ ALIGN TOGGLE WITH ICONS ✨ */
        .jt-toggle-wrapper {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: 40px !important;
        }
        .jt-toggle-wrapper [data-testid="stWidgetLabel"] {
            display: none !important;
        }

        .jt-inline-panel {
            border-top: 1px solid var(--jt-divider);
            margin-top: 0.75rem;
            padding-top: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_pill(status: str) -> str:
    color = STATUS_COLORS.get(status, "#888")
    return (
        f'<div style="display:flex;align-items:center;justify-content:center;height:28px;'
        f'padding:0 12px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:0.04em;'
        f'text-transform:uppercase;background:{color};color:#fff;line-height:1;white-space:nowrap;">'
        f'{html.escape(status.upper())}</div>'
    )


def _title_display(title: str, company: str) -> tuple[str, str]:
    normalized_title = (title or "").strip() or "Role title missing"
    normalized_company = (company or "").strip() or "Company missing"
    return normalized_title, normalized_company


def _nav(screen: str, **extra: object) -> None:
    for key, value in extra.items():
        st.session_state[key] = value
    st.session_state.screen = screen
    st.rerun()


def _init_state() -> None:
    defaults: dict[str, object] = {
        "jt_search": "",
        "jt_filter": "All statuses",
        "jt_add_open": False,
        "jt_status_editing": None,
        "jt_note_editing": None,
        "jt_edit_open": None,
        "jt_delete_confirm": None,
        "jt_selected_ids": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _toggle_job_selection(job_id: int) -> None:
    selected = list(st.session_state.get("jt_selected_ids", []))
    checked = bool(st.session_state.get(f"jt-select-{job_id}", False))
    if checked and job_id not in selected:
        selected.append(job_id)
    if not checked and job_id in selected:
        selected.remove(job_id)
    st.session_state.jt_selected_ids = selected


def _selected_ids_for_visible_jobs(jobs: list[dict]) -> list[int]:
    visible_ids = {job["id"] for job in jobs}
    return [job_id for job_id in st.session_state.get("jt_selected_ids", []) if job_id in visible_ids]


def _jt_icon_button(label: str, key: str, active: bool = False, **kwargs) -> bool:
    kwargs.pop("use_container_width", None)
    cls = "jt-icon-active" if active else "jt-icon"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, type="primary", **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def _jt_inline_tool_button(label: str, key: str, danger: bool = False, **kwargs) -> bool:
    cls = "jt-inline-tool-danger" if danger else "jt-inline-tool"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    clicked = st.button(label, key=key, type="primary", **kwargs)
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


def _inline_divider() -> None:
    st.markdown('<div class="jt-inline-panel">', unsafe_allow_html=True)


def _close_inline_divider() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def _render_add_job_form() -> None:
    st.markdown(
        '<div style="margin:0.5rem 0 1rem;">'
        '<div style="font-size:1rem;font-weight:700;color:#111111;margin-bottom:1rem;">Add a Job</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Job Title *", key="jt-add-title", placeholder="e.g. Product Manager")
        with c2:
            company = st.text_input("Company *", key="jt-add-company", placeholder="e.g. Acme Corp")
        c3, c4 = st.columns(2)
        with c3:
            location = st.text_input("Location", key="jt-add-location", placeholder="e.g. New York, NY")
        with c4:
            job_url = st.text_input("Job URL", key="jt-add-url", placeholder="https://…")

        add_status = st.selectbox("Initial status", TRACKER_STATUSES, index=0, key="jt-add-status")
        jd_text = st.text_area(
            "Job Description (optional)",
            key="jt-add-jd",
            placeholder="Paste the job description.",
            height=90,
        )
        applied_date = ""
        if add_status == "Applied":
            picked = st.date_input(
                "Applied Date",
                value=datetime.date.today(),
                max_value=datetime.date.today(),
                key="jt-add-applied-date",
            )
            applied_date = picked.strftime("%Y-%m-%d") if picked else ""

        st.markdown('<div class="jt-form-actions">', unsafe_allow_html=True)
        a1, a2, _ = st.columns([1.5, 1.5, 4])
        with a1:
            if primary_button(
                "Save Job",
                key="jt-add-save",
                use_container_width=True,
                disabled=not (title.strip() or company.strip()),
            ):
                add_job_manually(
                    job_title=title.strip(),
                    company=company.strip(),
                    location=location.strip(),
                    job_url=job_url.strip(),
                    jd_text=jd_text.strip(),
                    applied_date=applied_date.strip(),
                    status=add_status,
                )
                st.session_state.jt_add_open = False
                st.rerun()
        with a2:
            if st.button("Cancel", key="jt-add-cancel", use_container_width=True):
                st.session_state.jt_add_open = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_edit_form(job: dict) -> None:
    job_id = job["id"]
    c1, c2 = st.columns(2)
    with c1:
        new_title = st.text_input("Job Title", value=job["job_title"], key=f"jt-edit-title-{job_id}")
    with c2:
        new_company = st.text_input("Company", value=job["company"], key=f"jt-edit-company-{job_id}")
    c3, c4 = st.columns(2)
    with c3:
        new_location = st.text_input("Location", value=job["location"], key=f"jt-edit-location-{job_id}")
    with c4:
        new_url = st.text_input("Job URL", value=job["job_url"], key=f"jt-edit-url-{job_id}")
    c5, c6 = st.columns(2)
    with c5:
        status_index = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
        new_status = st.selectbox("Status", TRACKER_STATUSES, index=status_index, key=f"jt-edit-status-{job_id}")
    with c6:
        existing_date = None
        try:
            if job["applied_date"]:
                existing_date = datetime.date.fromisoformat(job["applied_date"])
        except ValueError:
            existing_date = None
        picked = st.date_input("Applied Date", value=existing_date, max_value=datetime.date.today(), key=f"jt-edit-applied-{job_id}")
        new_applied = picked.strftime("%Y-%m-%d") if picked else ""

    st.markdown('<div class="jt-form-actions">', unsafe_allow_html=True)
    a1, a2, a3, _ = st.columns([1.5, 1.5, 1.5, 3.5])
    with a1:
        if primary_button("Save", key=f"jt-edit-save-{job_id}", use_container_width=True):
            update_job_metadata(
                job_id,
                job_title=new_title or None,
                company=new_company or None,
                location=new_location,
                job_url=new_url,
                applied_date=new_applied,
                status=new_status,
            )
            st.session_state.jt_edit_open = None
            st.rerun()
    with a2:
        if st.button("Cancel", key=f"jt-edit-cancel-{job_id}", use_container_width=True):
            st.session_state.jt_edit_open = None
            st.rerun()
    with a3:
        if st.button("Delete", key=f"jt-edit-delete-{job_id}", use_container_width=True):
            st.session_state.jt_delete_confirm = job_id
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_empty_state() -> None:
    st.info("No matching jobs found. Try adjusting your search or filters.")


def _render_job_card(job: dict) -> None:
    job_id = job["id"]
    display_title, display_company = _title_display(job["job_title"], job["company"])

    status_active = st.session_state.get("jt_status_editing") == job_id
    note_active = st.session_state.get("jt_note_editing") == job_id
    edit_active = st.session_state.get("jt_edit_open") == job_id
    selected = job_id in st.session_state.get("jt_selected_ids", [])

    sub_parts: list[str] = []
    location = (job.get("location") or "").strip()
    if location and location.lower() != "unknown":
        sub_parts.append(html.escape(location))
    if job.get("applied_date"):
        try:
            d = datetime.date.fromisoformat(job["applied_date"][:10])
            sub_parts.append(f"Applied {d.strftime('%b')} {d.day}, {d.year}")
        except Exception:
            sub_parts.append(f"Applied {html.escape(job['applied_date'][:10])}")
    else:
        sub_parts.append("Not yet applied")
    note_count = int(job.get("note_count") or 0)
    if note_count:
        sub_parts.append(f"{note_count} note{'s' if note_count != 1 else ''}")
    if job.get("current_fit") is not None:
        score = int(job["current_fit"])
        color = "#16a34a" if score >= 75 else ("#d97757" if score >= 50 else "#888")
        sub_parts.append(f"FIT <span style='color:{color};font-weight:700;'>{score}%</span>")
    subline = " · ".join(sub_parts)

    with st.container(border=True):
        # ✨ 4 Distinct Columns perfectly centered vertically ✨
        c_pill, c_title, c_company, c_actions = st.columns([1.3, 3.5, 2.5, 3.8], gap="small", vertical_alignment="center")

        with c_pill:
            st.markdown(_status_pill(job["status"]), unsafe_allow_html=True)

        with c_title:
            st.markdown(
                f'<div class="jt-title-link" title="{html.escape(display_title)}">{html.escape(display_title)}</div>'
                f'<div class="jt-card-meta-text">{subline}</div>',
                unsafe_allow_html=True,
            )

        with c_company:
            st.markdown(f'<div class="jt-row-company" title="{html.escape(display_company)}">{html.escape(display_company)}</div>', unsafe_allow_html=True)

        with c_actions:
            a1, a2, a3, a4, a5 = st.columns([1, 1, 1, 1, 1.2], gap="small", vertical_alignment="center")
            with a1:
                if _jt_icon_button(":material/open_in_new:", key=f"jt-open-{job_id}"):
                    _nav("job_detail", active_job_detail_id=job_id)
            with a2:
                if _jt_icon_button(":material/published_with_changes:", key=f"jt-status-{job_id}", active=status_active):
                    st.session_state.jt_status_editing = None if status_active else job_id
                    if not status_active:
                        st.session_state.jt_note_editing = None
                        st.session_state.jt_edit_open = None
                    st.rerun()
            with a3:
                if _jt_icon_button(":material/sticky_note_2:", key=f"jt-note-{job_id}", active=note_active):
                    st.session_state.jt_note_editing = None if note_active else job_id
                    if not note_active:
                        st.session_state.jt_status_editing = None
                        st.session_state.jt_edit_open = None
                    st.rerun()
            with a4:
                if _jt_icon_button(":material/edit:", key=f"jt-edit-{job_id}", active=edit_active):
                    st.session_state.jt_edit_open = None if edit_active else job_id
                    if not edit_active:
                        st.session_state.jt_status_editing = None
                        st.session_state.jt_note_editing = None
                    st.rerun()
            with a5:
                st.markdown('<div class="jt-toggle-wrapper">', unsafe_allow_html=True)
                st.toggle(
                    "Select",
                    key=f"jt-select-{job_id}",
                    value=selected,
                    on_change=_toggle_job_selection,
                    args=(job_id,),
                    label_visibility="collapsed",
                )
                st.markdown('</div>', unsafe_allow_html=True)

        if status_active:
            _inline_divider()
            cur_idx = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
            new_status = st.radio(
                "Status",
                TRACKER_STATUSES,
                index=cur_idx,
                key=f"jt-status-radio-{job_id}",
                horizontal=True,
                label_visibility="collapsed",
            )
            st.markdown('<div class="jt-form-actions">', unsafe_allow_html=True)
            s1, s2, _ = st.columns([1.5, 1.5, 6], vertical_alignment="center")
            with s1:
                if primary_button("Save", key=f"jt-status-save-{job_id}", use_container_width=True):
                    update_job_status(job_id, new_status)
                    st.session_state.jt_status_editing = None
                    st.rerun()
            with s2:
                if st.button("Cancel", key=f"jt-status-cancel-{job_id}", use_container_width=True):
                    st.session_state.jt_status_editing = None
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            _close_inline_divider()

        if note_active:
            _inline_divider()
            note_text = st.text_area(
                "Note",
                key=f"jt-note-text-{job_id}",
                placeholder="Add a note about this application…",
                height=70,
                label_visibility="collapsed",
            )
            st.markdown('<div class="jt-form-actions">', unsafe_allow_html=True)
            n1, n2, _ = st.columns([1.5, 1.5, 6], vertical_alignment="center")
            with n1:
                if primary_button("Save", key=f"jt-note-save-{job_id}", use_container_width=True, disabled=not (note_text or "").strip()):
                    add_note(job_id, (note_text or "").strip())
                    st.session_state.jt_note_editing = None
                    st.rerun()
            with n2:
                if st.button("Cancel", key=f"jt-note-cancel-{job_id}", use_container_width=True):
                    st.session_state.jt_note_editing = None
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            _close_inline_divider()

        if edit_active:
            _inline_divider()
            _render_edit_form(job)
            _close_inline_divider()

        if st.session_state.get("jt_delete_confirm") == job_id:
            _inline_divider()
            st.markdown(
                '<div style="font-size:0.84rem;font-weight:600;color:#c0392b;margin-bottom:0.2rem;">Remove this job?</div>'
                '<div style="font-size:0.76rem;color:#7a7a7a;margin-bottom:0.4rem;">Removes job, notes, materials, and history.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="jt-form-actions">', unsafe_allow_html=True)
            d1, d2, _ = st.columns([1.5, 1.5, 6], vertical_alignment="center")
            with d1:
                if primary_button("Delete", key=f"jt-delete-confirm-{job_id}", use_container_width=True):
                    delete_job(job_id)
                    st.session_state.jt_delete_confirm = None
                    if st.session_state.get("active_tracker_job_id") == job_id:
                        st.session_state.active_job_detail_id = None
                    st.rerun()
            with d2:
                if st.button("Cancel", key=f"jt-delete-cancel-{job_id}", use_container_width=True):
                    st.session_state.jt_delete_confirm = None
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            _close_inline_divider()


def render_job_tracker_screen() -> None:
    _init_state()
    _inject_jt_css()

    head1, head2 = st.columns([5.2, 1.2])
    with head1:
        st.markdown(
            '<div style="font-size:2rem;font-weight:800;color:#111111;margin-bottom:0.25rem;">Job Tracker</div>'
            '<div style="font-size:0.9rem;color:#8b8b93;margin-bottom:1rem;">Track applications, update status fast, and keep the list tight and easy to scan.</div>',
            unsafe_allow_html=True,
        )
    with head2:
        if st.button("Add Job", key="jt-add-btn", type="primary", use_container_width=True):
            st.session_state.jt_add_open = not st.session_state.jt_add_open
            st.rerun()

    if st.session_state.jt_add_open:
        _render_add_job_form()

    st.markdown('<div class="jt-toolbar-row">', unsafe_allow_html=True)
    s_col, filter_col = st.columns([3, 1], gap="medium", vertical_alignment="center")
    with s_col:
        search = st.text_input(
            "Search",
            value=st.session_state.jt_search,
            placeholder="Search by role or company…",
            key="jt-search-input",
            label_visibility="collapsed",
        )
        st.session_state.jt_search = search
    filter_opts = ["All statuses", "Bookmarked", "Preparing", "Applied", "Interviewing", "Offer", "Rejected", "Archived"]
    with filter_col:
        selected_filter = st.selectbox(
            "Filter",
            filter_opts,
            index=filter_opts.index(st.session_state.jt_filter) if st.session_state.jt_filter in filter_opts else 0,
            key="jt-filter-select",
            label_visibility="collapsed",
        )
        st.session_state.jt_filter = selected_filter
    st.markdown("</div>", unsafe_allow_html=True)

    status_filter = "All" if st.session_state.jt_filter == "All statuses" else st.session_state.jt_filter
    jobs = list_jobs(search=st.session_state.jt_search, status_filter=status_filter, sort_by="Last updated")

    if jobs:
        selected_ids = _selected_ids_for_visible_jobs(jobs)
        if selected_ids:
            c1, c2, c3, _ = st.columns([1.5, 1, 1.5, 4], vertical_alignment="center")
            with c1:
                st.markdown(f'<div class="jt-selection-copy">{len(selected_ids)} selected</div>', unsafe_allow_html=True)
            with c2:
                if _jt_inline_tool_button("Clear", key="jt-clear-visible"):
                    for job in jobs:
                        st.session_state[f"jt-select-{job['id']}"] = False
                    st.session_state.jt_selected_ids = []
                    st.rerun()
            with c3:
                if _jt_inline_tool_button("Delete selected", key="jt-bulk-delete", danger=True):
                    for job_id in selected_ids:
                        delete_job(job_id)
                        st.session_state[f"jt-select-{job_id}"] = False
                    st.session_state.jt_selected_ids = []
                    st.rerun()
        else:
            st.markdown(
                f'<div class="jt-visible-copy">{len(jobs)} visible job{"s" if len(jobs) != 1 else ""}</div>',
                unsafe_allow_html=True,
            )

        for job in jobs:
            _render_job_card(job)
    else:
        _render_empty_state()
