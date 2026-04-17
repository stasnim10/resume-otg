"""
Job Tracker — list view.

Design principles:
  - No emoji in tracker UI — typography, spacing, muted color carry meaning
  - Job identity first: title + company always visible, clearly marked when missing
  - Calm action hierarchy: Open (primary) → Update Status / Add Note (secondary)
    → Edit / Delete
  - Bulk cleanup is available from the list view for multi-job maintenance

Entry point: render_job_tracker_screen()
"""
from __future__ import annotations

import datetime
import streamlit as st

from job_tracker_store import (
    TRACKER_STATUSES,
    STATUS_COLORS,
    add_job_manually,
    add_note,
    delete_job,
    list_jobs,
    update_job_metadata,
    update_job_status,
)
from ui_helpers import primary_button, secondary_button

# ── Constants ──────────────────────────────────────────────────────────────────

_SORT_OPTIONS = ["Last updated", "Newest saved", "Date applied", "Highest fit"]


# ── Private helpers ────────────────────────────────────────────────────────────

def _status_pill(status: str) -> str:
    """Compact, emoji-free HTML status pill."""
    color = STATUS_COLORS.get(status, "var(--muted)")
    return (
        f'<span style="display:inline-block;padding:0.15rem 0.55rem;'
        f'border-radius:999px;font-size:0.68rem;font-weight:600;'
        f'background:{color};color:#fff;letter-spacing:0.02em;">'
        f"{status}</span>"
    )


def _title_display(title: str, company: str) -> tuple[str, str]:
    """Return (display_title, display_company) with 'missing' fallbacks."""
    dt = title if title else "Role title missing"
    dc = company if company else "Company missing"
    return dt, dc


def _nav(screen: str, **extra: object) -> None:
    for k, v in extra.items():
        st.session_state[k] = v
    st.session_state.screen = screen
    st.rerun()


def _init_state() -> None:
    defaults: dict = {
        "jt_search":         "",
        "jt_filter":         "All",
        "jt_sort":           "Last updated",
        "jt_add_open":       False,
        "jt_status_editing": None,
        "jt_note_editing":   None,
        "jt_edit_open":      None,   # job_id with Edit form open
        "jt_delete_confirm": None,
        "jt_selected_ids":   [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _selected_ids_for_visible_jobs(jobs: list[dict]) -> list[int]:
    visible_ids = {job["id"] for job in jobs}
    selected = st.session_state.get("jt_selected_ids", [])
    return [job_id for job_id in selected if job_id in visible_ids]


def _toggle_job_selection(job_id: int) -> None:
    selected = list(st.session_state.get("jt_selected_ids", []))
    checked = bool(st.session_state.get(f"jt-select-{job_id}", False))
    if checked and job_id not in selected:
        selected.append(job_id)
    if not checked and job_id in selected:
        selected.remove(job_id)
    st.session_state.jt_selected_ids = selected


# ── Sub-renders ────────────────────────────────────────────────────────────────

def _render_add_job_form() -> None:
    """Inline form to manually add a new tracked job."""
    with st.container(border=True):
        st.markdown("#### Add a Job")
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
            placeholder="Paste the job description — useful for future optimization.",
            height=100,
        )
        applied_date = ""
        if add_status == "Applied":
            picked = st.date_input(
                "Applied Date", value=datetime.date.today(),
                max_value=datetime.date.today(), key="jt-add-applied-date",
            )
            applied_date = picked.strftime("%Y-%m-%d") if picked else ""

        sa, sb, _ = st.columns([1.2, 1.2, 4])
        with sa:
            if primary_button(
                "Save Job", key="jt-add-save", use_container_width=True,
                disabled=not (title.strip() or company.strip()),
            ):
                try:
                    add_job_manually(
                        job_title=title.strip(), company=company.strip(),
                        location=location.strip(), job_url=job_url.strip(),
                        jd_text=jd_text.strip(), applied_date=applied_date.strip(),
                        status=add_status,
                    )
                    st.session_state.jt_add_open = False
                    st.rerun()
                except Exception as err:
                    st.error(str(err))
        with sb:
            if st.button("Cancel", key="jt-add-cancel", use_container_width=True):
                st.session_state.jt_add_open = False
                st.rerun()


def _render_edit_form(job: dict) -> None:
    """Inline edit form for an existing tracked job."""
    job_id = job["id"]
    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.5rem 0 0.6rem;">',
        unsafe_allow_html=True,
    )
    st.markdown("**Edit Job Details**")
    e1, e2 = st.columns(2)
    with e1:
        new_title = st.text_input(
            "Job Title", value=job["job_title"], key=f"jt-edit-title-{job_id}",
            placeholder="Role title missing — enter to fix",
        )
    with e2:
        new_company = st.text_input(
            "Company", value=job["company"], key=f"jt-edit-company-{job_id}",
            placeholder="Company missing — enter to fix",
        )
    e3, e4 = st.columns(2)
    with e3:
        new_location = st.text_input(
            "Location", value=job["location"], key=f"jt-edit-loc-{job_id}",
        )
    with e4:
        new_url = st.text_input(
            "Job URL", value=job["job_url"], key=f"jt-edit-url-{job_id}",
        )
    e5, e6 = st.columns(2)
    with e5:
        cur_status_idx = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
        new_status = st.selectbox(
            "Status", TRACKER_STATUSES, index=cur_status_idx, key=f"jt-edit-status-{job_id}",
        )
    with e6:
        _existing_date = None
        try:
            if job["applied_date"]:
                _existing_date = datetime.date.fromisoformat(job["applied_date"])
        except ValueError:
            pass
        _picked = st.date_input(
            "Applied Date", value=_existing_date,
            max_value=datetime.date.today(), key=f"jt-edit-applied-{job_id}",
        )
        new_applied = _picked.strftime("%Y-%m-%d") if _picked else ""

    ea, eb, ec, _ = st.columns([1.2, 1.2, 1.2, 4])
    with ea:
        if primary_button("Save Changes", key=f"jt-edit-save-{job_id}", use_container_width=True):
            try:
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
            except Exception as err:
                st.error(str(err))
    with eb:
        if secondary_button("Cancel", key=f"jt-edit-cancel-{job_id}", use_container_width=True):
            st.session_state.jt_edit_open = None
            st.rerun()
    with ec:
        if secondary_button("Delete", key=f"jt-edit-delete-{job_id}", use_container_width=True):
            st.session_state.jt_delete_confirm = job_id
            st.rerun()


def _render_empty_state(is_filtered: bool) -> None:
    with st.container(border=True):
        st.markdown(
            '<div style="text-align:center;padding:2.5rem 1rem;">',
            unsafe_allow_html=True,
        )
        if is_filtered:
            st.markdown("#### No jobs match this filter")
            st.caption('Try switching to "All" or a different status.')
        else:
            st.markdown("#### No tracked jobs yet")
            st.markdown(
                '<p style="color:var(--muted);font-size:0.88rem;margin-bottom:1.25rem;">'
                "Add a job manually or run an optimization — it saves here automatically."
                "</p>",
                unsafe_allow_html=True,
            )
            c1, c2, _ = st.columns([1.6, 1.6, 3])
            with c1:
                if primary_button("Add Job Manually", key="jt-empty-add", use_container_width=True):
                    st.session_state.jt_add_open = True
                    st.rerun()
            with c2:
                if secondary_button("Optimize a Resume", key="jt-empty-opt", use_container_width=True):
                    st.session_state.active_tracker_job_id = None
                    st.session_state.screen = "input"
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def _render_job_card(job: dict) -> None:
    """Render one job card with inline quick-action panels."""
    job_id: int = job["id"]
    display_title, display_company = _title_display(job["job_title"], job["company"])
    title_is_missing  = not job["job_title"]
    company_is_missing = not job["company"]

    with st.container(border=True):
        st.checkbox(
            "Select",
            key=f"jt-select-{job_id}",
            value=job_id in st.session_state.get("jt_selected_ids", []),
            on_change=_toggle_job_selection,
            args=(job_id,),
        )

        # ── Identity row ──────────────────────────────────────────────────────
        col_info, col_score = st.columns([3, 1])

        with col_info:
            # Title
            if title_is_missing:
                st.markdown(
                    f'<p style="margin:0;font-weight:600;font-size:0.95rem;'
                    f'color:var(--muted);font-style:italic;">{display_title}</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"**{display_title}**")

            # Company + location
            sub_parts: list[str] = []
            if company_is_missing:
                sub_parts.append(
                    f'<span style="font-style:italic;color:var(--muted);">{display_company}</span>'
                )
            elif job["company"]:
                sub_parts.append(job["company"])
            if job["location"]:
                sub_parts.append(job["location"])

            if sub_parts:
                st.markdown(
                    f'<p style="margin:0.1rem 0 0;font-size:0.82rem;color:var(--muted);">'
                    f"{'  ·  '.join(sub_parts)}</p>",
                    unsafe_allow_html=True,
                )

        with col_score:
            st.markdown(_status_pill(job["status"]), unsafe_allow_html=True)
            if job["current_fit"] is not None:
                delta = job.get("latest_delta") or 0
                delta_str = (
                    f"&thinsp;(+{delta}%)" if delta > 0
                    else (f"&thinsp;({delta}%)" if delta < 0 else "")
                )
                st.markdown(
                    f'<div style="margin-top:0.35rem;font-weight:700;'
                    f'color:var(--green);font-size:1rem;">{job["current_fit"]}%'
                    f'<span style="font-weight:400;font-size:0.7rem;'
                    f'color:var(--muted);">{delta_str}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="margin-top:0.35rem;font-size:0.72rem;'
                    'color:var(--muted);">Not optimized</div>',
                    unsafe_allow_html=True,
                )

        # ── Secondary context ─────────────────────────────────────────────────
        ctx: list[str] = []
        if job["applied_date"]:
            ctx.append(f"Applied {job['applied_date'][:10]}")
        else:
            ctx.append("Not applied yet")
        if job["has_resume"]:
            ctx.append("Resume saved")
        if job["has_cover_letter"]:
            ctx.append("Cover letter saved")
        if job["note_count"]:
            ctx.append(f"{job['note_count']} note{'s' if job['note_count'] != 1 else ''}")
        st.caption("  ·  ".join(ctx))

        # ── Next action strip ─────────────────────────────────────────────────
        if job["next_action"]:
            st.markdown(
                f'<div style="border-left:2px solid var(--amber);padding-left:0.5rem;'
                f'font-size:0.8rem;margin:0.2rem 0 0.05rem;">Next: {job["next_action"]}</div>',
                unsafe_allow_html=True,
            )

        # ── Primary + secondary actions ───────────────────────────────────────
        action_cols = st.columns([1.1, 1, 1, 1])

        with action_cols[0]:
            if primary_button("Open", key=f"jt-open-{job_id}", use_container_width=True):
                _nav("job_detail", active_job_detail_id=job_id)

        with action_cols[1]:
            status_lbl = "Status" if st.session_state.jt_status_editing != job_id else "Close"
            if secondary_button(status_lbl, key=f"jt-status-{job_id}", use_container_width=True):
                if st.session_state.jt_status_editing == job_id:
                    st.session_state.jt_status_editing = None
                else:
                    st.session_state.jt_status_editing = job_id
                    st.session_state.jt_note_editing = None
                    st.session_state.jt_edit_open = None
                st.rerun()

        with action_cols[2]:
            note_lbl = "Note" if st.session_state.jt_note_editing != job_id else "Close"
            if secondary_button(note_lbl, key=f"jt-note-{job_id}", use_container_width=True):
                if st.session_state.jt_note_editing == job_id:
                    st.session_state.jt_note_editing = None
                else:
                    st.session_state.jt_note_editing = job_id
                    st.session_state.jt_status_editing = None
                    st.session_state.jt_edit_open = None
                st.rerun()

        with action_cols[3]:
            edit_lbl = "Edit" if st.session_state.jt_edit_open != job_id else "Close"
            if secondary_button(edit_lbl, key=f"jt-edit-{job_id}", use_container_width=True):
                if st.session_state.jt_edit_open == job_id:
                    st.session_state.jt_edit_open = None
                else:
                    st.session_state.jt_edit_open = job_id
                    st.session_state.jt_status_editing = None
                    st.session_state.jt_note_editing = None
                st.rerun()

        # ── Inline: status editor ─────────────────────────────────────────────
        if st.session_state.jt_status_editing == job_id:
            st.markdown(
                '<hr style="border:none;border-top:1px solid var(--line);margin:0.5rem 0 0.35rem;">',
                unsafe_allow_html=True,
            )
            cur_idx = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
            new_status = st.radio(
                "Move to", TRACKER_STATUSES, index=cur_idx,
                key=f"jt-status-radio-{job_id}", horizontal=True,
            )
            sv_col, _ = st.columns([1.5, 6])
            with sv_col:
                if primary_button("Save Status", key=f"jt-status-save-{job_id}", use_container_width=True):
                    update_job_status(job_id, new_status)
                    st.session_state.jt_status_editing = None
                    st.rerun()

        # ── Inline: quick note ────────────────────────────────────────────────
        if st.session_state.jt_note_editing == job_id:
            st.markdown(
                '<hr style="border:none;border-top:1px solid var(--line);margin:0.5rem 0 0.35rem;">',
                unsafe_allow_html=True,
            )
            note_text = st.text_area(
                "Add a note", key=f"jt-note-text-{job_id}",
                placeholder="Add a note about this application…",
                height=80, label_visibility="collapsed",
            )
            nn1, nn2, _ = st.columns([1.2, 1.2, 5])
            with nn1:
                if primary_button(
                    "Save Note", key=f"jt-note-save-{job_id}",
                    use_container_width=True,
                    disabled=not (note_text or "").strip(),
                ):
                    add_note(job_id, (note_text or "").strip())
                    st.session_state.jt_note_editing = None
                    st.rerun()
            with nn2:
                if secondary_button("Cancel", key=f"jt-note-cancel-{job_id}", use_container_width=True):
                    st.session_state.jt_note_editing = None
                    st.rerun()

        # ── Inline: edit form ─────────────────────────────────────────────────
        if st.session_state.jt_edit_open == job_id:
            _render_edit_form(job)

        if st.session_state.jt_delete_confirm == job_id:
            st.markdown(
                '<hr style="border:none;border-top:1px solid var(--line);margin:0.5rem 0 0.6rem;">',
                unsafe_allow_html=True,
            )
            st.markdown("**Delete this job?**")
            st.caption("This removes the job card, notes, materials, and optimization history.")
            dc1, dc2, _ = st.columns([1.2, 1.2, 4])
            with dc1:
                if primary_button("Delete Job", key=f"jt-delete-confirm-{job_id}", use_container_width=True):
                    delete_job(job_id)
                    st.session_state.jt_delete_confirm = None
                    if st.session_state.get("active_tracker_job_id") == job_id:
                        st.session_state.active_tracker_job_id = None
                    st.rerun()
            with dc2:
                if secondary_button("Cancel", key=f"jt-delete-cancel-{job_id}", use_container_width=True):
                    st.session_state.jt_delete_confirm = None
                    st.rerun()


# ── Main entry point ───────────────────────────────────────────────────────────

def render_job_tracker_screen() -> None:
    """Render the Job Tracker list view."""
    _init_state()

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_col, add_col = st.columns([5, 1])
    with hdr_col:
        st.title("Job Tracker")
    with add_col:
        add_label = "Close" if st.session_state.jt_add_open else "Add Job"
        if secondary_button(add_label, key="jt-add-btn", use_container_width=True):
            st.session_state.jt_add_open = not st.session_state.jt_add_open
            st.rerun()

    if st.session_state.jt_add_open:
        _render_add_job_form()

    # ── Search + sort ─────────────────────────────────────────────────────────
    s_col, sort_col = st.columns([3, 1])
    with s_col:
        search = st.text_input(
            "Search", value=st.session_state.jt_search,
            placeholder="Search by role or company…",
            key="jt-search-input", label_visibility="collapsed",
        )
        st.session_state.jt_search = search
    with sort_col:
        sort = st.selectbox(
            "Sort", _SORT_OPTIONS,
            index=_SORT_OPTIONS.index(st.session_state.jt_sort)
                  if st.session_state.jt_sort in _SORT_OPTIONS else 0,
            key="jt-sort-sel", label_visibility="collapsed",
        )
        st.session_state.jt_sort = sort

    # ── Filter chips ──────────────────────────────────────────────────────────
    filter_opts = ["All"] + TRACKER_STATUSES
    selected_filter = st.radio(
        "Filter", filter_opts,
        index=filter_opts.index(st.session_state.jt_filter)
              if st.session_state.jt_filter in filter_opts else 0,
        key="jt-filter-radio", horizontal=True, label_visibility="collapsed",
    )
    st.session_state.jt_filter = selected_filter

    # ── Fetch ─────────────────────────────────────────────────────────────────
    jobs = list_jobs(
        search=st.session_state.jt_search,
        status_filter=st.session_state.jt_filter,
        sort_by=st.session_state.jt_sort,
    )
    is_filtered = st.session_state.jt_filter != "All" or bool(st.session_state.jt_search.strip())

    if jobs:
        n = len(jobs)
        lbl = f"{n} job{'s' if n != 1 else ''}"
        if st.session_state.jt_filter != "All":
            lbl += f"  ·  {st.session_state.jt_filter}"
        st.caption(lbl)
        selected_ids = _selected_ids_for_visible_jobs(jobs)
        bulk_col1, bulk_col2, bulk_col3, _ = st.columns([1.2, 1.2, 1.6, 4])
        with bulk_col1:
            if secondary_button("Select Visible", key="jt-select-visible", use_container_width=True):
                selected = set(st.session_state.get("jt_selected_ids", []))
                for job in jobs:
                    st.session_state[f"jt-select-{job['id']}"] = True
                    selected.add(job["id"])
                st.session_state.jt_selected_ids = list(selected)
                st.rerun()
        with bulk_col2:
            if secondary_button("Clear Selection", key="jt-clear-visible", use_container_width=True):
                for job in jobs:
                    st.session_state[f"jt-select-{job['id']}"] = False
                st.session_state.jt_selected_ids = [
                    job_id for job_id in st.session_state.get("jt_selected_ids", [])
                    if job_id not in {job["id"] for job in jobs}
                ]
                st.rerun()
        with bulk_col3:
            delete_label = f"Delete Selected ({len(selected_ids)})" if selected_ids else "Delete Selected"
            if secondary_button(
                delete_label,
                key="jt-bulk-delete",
                use_container_width=True,
                disabled=not selected_ids,
            ):
                for job_id in selected_ids:
                    delete_job(job_id)
                    st.session_state[f"jt-select-{job_id}"] = False
                    if st.session_state.get("active_tracker_job_id") == job_id:
                        st.session_state.active_tracker_job_id = None
                st.session_state.jt_selected_ids = [
                    job_id for job_id in st.session_state.get("jt_selected_ids", [])
                    if job_id not in selected_ids
                ]
                st.rerun()

    if not jobs:
        _render_empty_state(is_filtered)
    else:
        for job in jobs:
            _render_job_card(job)
