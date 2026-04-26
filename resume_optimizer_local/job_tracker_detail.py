"""
Job Tracker — job detail view (3-tab).

Design principles:
  - No emoji in tracker UI
  - Status changes are immediate (no save button needed for single-value radio)
  - Edit metadata is always available in Overview tab
  - History uses neutral symbols, not decorative emoji

Tabs:
  1. Overview  — status, next action, edit metadata, notes
  2. Job & Materials — JD, materials, optimization run history
  3. History   — timeline with expandable opt-run rows

Entry point: render_job_tracker_detail_screen()
"""
from __future__ import annotations

import datetime
import time
import streamlit as st

from job_tracker_store import (
    TRACKER_STATUSES,
    STATUS_COLORS,
    add_note,
    delete_job,
    get_job,
    list_materials,
    list_notes,
    list_optimization_runs,
    list_timeline_events,
    update_job_metadata,
    update_job_next_action,
    update_job_status,
    update_note,
)
from ui_helpers import secondary_button

# ── Constants ──────────────────────────────────────────────────────────────────

_TIMELINE_LABELS: dict[str, str] = {
    "job_added":                    "Job added",
    "job_updated":                  "Job updated",
    "status_changed":               "Status changed",
    "note_added":                   "Note added",
    "material_saved":               "Material saved",
    "optimization_run_completed":   "Optimization run",
    "application_marked_submitted": "Marked as applied",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _status_pill(status: str) -> str:
    color = STATUS_COLORS.get(status, "var(--muted)")
    return (
        f'<span style="display:inline-block;padding:0.2rem 0.65rem;border-radius:999px;'
        f'font-size:0.75rem;font-weight:600;background:{color};color:#fff;">'
        f"{status}</span>"
    )


# ── Tab renders ────────────────────────────────────────────────────────────────

def _render_edit_section(job: dict) -> None:
    """Inline edit form for job metadata, collapsed inside an expander."""
    job_id: int = job["id"]
    with st.expander("Edit job details", expanded=not (job["job_title"] and job["company"])):
        e1, e2 = st.columns(2)
        with e1:
            new_title = st.text_input(
                "Job Title", value=job["job_title"],
                key=f"jt-det-edit-title-{job_id}",
                placeholder="Role title missing — enter to fix",
            )
        with e2:
            new_company = st.text_input(
                "Company", value=job["company"],
                key=f"jt-det-edit-company-{job_id}",
                placeholder="Company missing — enter to fix",
            )
        e3, e4 = st.columns(2)
        with e3:
            new_loc = st.text_input("Location", value=job["location"], key=f"jt-det-edit-loc-{job_id}")
        with e4:
            new_url = st.text_input("Job URL", value=job["job_url"], key=f"jt-det-edit-url-{job_id}")
        e5, e6 = st.columns(2)
        with e5:
            cur_idx = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
            new_status = st.selectbox("Status", TRACKER_STATUSES, index=cur_idx, key=f"jt-det-edit-status-{job_id}")
        with e6:
            _existing_date = None
            try:
                if job["applied_date"]:
                    _existing_date = datetime.date.fromisoformat(job["applied_date"])
            except ValueError:
                pass
            _picked = st.date_input(
                "Applied Date", value=_existing_date,
                max_value=datetime.date.today(), key=f"jt-det-edit-applied-{job_id}",
            )
            new_applied = _picked.strftime("%Y-%m-%d") if _picked else ""

        sa, sb, _ = st.columns([1.5, 1.5, 4])
        with sa:
            if st.button("Save Changes", key=f"jt-det-edit-save-{job_id}", type="primary", use_container_width=True):
                try:
                    _progress = st.progress(0)
                    _status = st.empty()
                    for pct, msg in (
                        (18, "Checking updates..."),
                        (52, "Saving job details..."),
                        (84, "Refreshing tracker record..."),
                    ):
                        _progress.progress(pct)
                        _status.caption(msg)
                        time.sleep(0.12)
                    update_job_metadata(
                        job_id,
                        job_title=new_title or None,
                        company=new_company or None,
                        location=new_loc,
                        job_url=new_url,
                        applied_date=new_applied,
                        status=new_status,
                    )
                    _progress.progress(100)
                    _status.caption("Changes saved.")
                    time.sleep(0.15)
                    st.session_state.jt_detail_flash = "Job details saved."
                    st.rerun()
                except Exception as err:
                    _progress.empty()  # type: ignore[possibly-undefined]
                    _status.empty()  # type: ignore[possibly-undefined]
                    st.error(str(err))
        with sb:
            if st.button("Delete Job", key=f"jt-det-delete-{job_id}", use_container_width=True):
                st.session_state.jt_detail_delete_confirm = job_id
                st.rerun()


def _render_overview_tab(job: dict) -> None:
    job_id: int = job["id"]

    # ── Status radio ──────────────────────────────────────────────────────────
    st.markdown("**Status**")
    cur_idx = TRACKER_STATUSES.index(job["status"]) if job["status"] in TRACKER_STATUSES else 0
    new_status = st.radio(
        "Status", TRACKER_STATUSES, index=cur_idx,
        key="jt-detail-status-radio", horizontal=True, label_visibility="collapsed",
    )
    if new_status != job["status"]:
        update_job_status(job_id, new_status)
        st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
        unsafe_allow_html=True,
    )

    # ── Next action ───────────────────────────────────────────────────────────
    st.markdown("**Next Action**")
    na_val = st.text_input(
        "Next action", value=job["next_action"],
        placeholder="e.g. Follow up with recruiter on Friday",
        key="jt-detail-next-action", label_visibility="collapsed",
    )
    if na_val.strip() != (job["next_action"] or "").strip():
        na_col, _ = st.columns([1.5, 5])
        with na_col:
            if st.button("Save", key="jt-detail-na-save", type="primary", use_container_width=True):
                update_job_next_action(job_id, na_val.strip())
                st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
        unsafe_allow_html=True,
    )

    # ── Edit metadata ─────────────────────────────────────────────────────────
    _render_edit_section(job)

    if st.session_state.get("jt_detail_delete_confirm") == job_id:
        st.warning("Delete this job and all related notes, materials, and optimization runs?")
        dc1, dc2, _ = st.columns([1.2, 1.2, 4])
        with dc1:
            if st.button("Delete Permanently", key="jt-detail-delete-confirm", type="primary", use_container_width=True):
                delete_job(job_id)
                st.session_state.jt_detail_delete_confirm = None
                if st.session_state.get("active_tracker_job_id") == job_id:
                    st.session_state.active_tracker_job_id = None
                st.session_state.screen = "job_tracker"
                st.rerun()
        with dc2:
            if st.button("Keep Job", key="jt-detail-delete-cancel", use_container_width=True):
                st.session_state.jt_detail_delete_confirm = None
                st.rerun()

    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
        unsafe_allow_html=True,
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    st.markdown("**Notes**")
    new_note_val = st.text_area(
        "Add a note", key="jt-detail-new-note",
        placeholder="Interview prep, contacts, reminders, anything useful…",
        height=90, label_visibility="collapsed",
    )
    add_note_col, _ = st.columns([1.5, 5])
    with add_note_col:
        if st.button(
            "Add Note", key="jt-detail-add-note", type="primary", use_container_width=True,
            disabled=not (new_note_val or "").strip(),
        ):
            add_note(job_id, new_note_val.strip())
            st.rerun()

    notes = list_notes(job_id)
    if notes:
        st.markdown("<br>", unsafe_allow_html=True)
        for note in notes:
            edit_key = f"jt-note-editing-{note['id']}"
            with st.container(border=True):
                if st.session_state.get(edit_key):
                    edited = st.text_area(
                        "Edit note", value=note["content"],
                        key=f"jt-note-edit-area-{note['id']}",
                        height=90, label_visibility="collapsed",
                    )
                    ec1, ec2, _ = st.columns([1.2, 1.2, 5])
                    with ec1:
                        if st.button("Save", key=f"jt-note-edit-save-{note['id']}", type="primary", use_container_width=True):
                            update_note(note["id"], edited.strip())
                            st.session_state[edit_key] = False
                            st.rerun()
                    with ec2:
                        if st.button("Cancel", key=f"jt-note-edit-cancel-{note['id']}", use_container_width=True):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    nc_text, nc_btn = st.columns([5, 1])
                    with nc_text:
                        st.markdown(note["content"])
                        st.caption(
                            f"{note['note_type'].replace('_', ' ').title()}"
                            f"  ·  {note['created_at'][:10]}"
                        )
                    with nc_btn:
                        if st.button("Edit", key=f"jt-note-edit-btn-{note['id']}", use_container_width=True):
                            st.session_state[edit_key] = True
                            st.rerun()
    else:
        st.caption("No notes yet — add one above.")


def _render_materials_tab(job: dict) -> None:
    job_id: int = job["id"]

    if job.get("job_url"):
        st.markdown(f"[View Job Posting]({job['job_url']})")
        st.markdown(
            '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
            unsafe_allow_html=True,
        )

    st.markdown("**Job Description**")
    jd = (job.get("jd_text") or "").strip()
    if jd:
        with st.expander("View full job description", expanded=False):
            st.text(jd)
    else:
        st.caption("No job description saved.")

    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
        unsafe_allow_html=True,
    )

    st.markdown("**Saved Materials**")
    materials = list_materials(job_id)
    if materials:
        for mat in materials:
            mat_label = mat["material_type"].replace("_", " ").title()
            with st.container(border=True):
                mc1, mc2 = st.columns([4, 1])
                with mc1:
                    st.markdown(f"**{mat_label}**")
                    if mat.get("file_path"):
                        st.caption(mat["file_path"])
                    st.caption(f"Saved {mat['saved_at'][:10]}")
    else:
        st.caption("No materials saved yet. Run an optimization to generate tailored documents.")

    runs = list_optimization_runs(job_id)
    if runs:
        st.markdown(
            '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
            unsafe_allow_html=True,
        )
        st.markdown(f"**Optimization Runs** — {len(runs)} completed")
        for i, run in enumerate(runs):
            delta_str = f"+{run['delta']}%" if run["delta"] > 0 else (f"{run['delta']}%" if run["delta"] < 0 else "no change")
            label = (
                f"Run {len(runs) - i}  ·  "
                f"{run['match_before']}% → {run['match_after']}%  ({delta_str})"
                f"  ·  {run['run_at'][:10]}"
            )
            with st.expander(label, expanded=(i == 0)):
                if run.get("improvements_list"):
                    st.markdown("**Improvements applied:**")
                    for imp in run["improvements_list"]:
                        st.markdown(f"- {imp}")
                else:
                    st.caption("No improvement details recorded for this run.")


def _render_history_tab(job: dict) -> None:
    job_id: int = job["id"]
    events = list_timeline_events(job_id)

    if not events:
        st.caption("No events yet.")
        return

    runs_by_id: dict[int, dict] = {}
    if any(e["event_type"] == "optimization_run_completed" for e in events):
        for run in list_optimization_runs(job_id):
            runs_by_id[run["id"]] = run

    for ev in events:
        label = _TIMELINE_LABELS.get(ev["event_type"], ev["event_type"].replace("_", " ").title())
        date_str = ev["created_at"][:10]
        time_str = ev["created_at"][11:16] if len(ev["created_at"]) > 10 else ""

        if ev["event_type"] == "optimization_run_completed":
            meta = ev.get("metadata") or {}
            run_id = meta.get("run_id")
            run = runs_by_id.get(run_id) if run_id else None
            exp_label = f"{label}  ·  {ev['description']}  ·  {date_str}"
            with st.expander(exp_label, expanded=False):
                if run and run.get("improvements_list"):
                    st.markdown("**Improvements applied:**")
                    for imp in run["improvements_list"]:
                        st.markdown(f"- {imp}")
                elif run:
                    st.caption("No improvement details recorded.")
                else:
                    st.caption("Run details not found.")
        else:
            st.markdown(
                f'<div style="display:flex;gap:0.5rem;align-items:baseline;'
                f'padding:0.3rem 0;border-bottom:1px solid var(--line);">'
                f'<span style="font-size:0.83rem;flex:1;color:var(--text);">'
                f'{label} — {ev["description"]}</span>'
                f'<span style="font-size:0.7rem;color:var(--muted);white-space:nowrap;">'
                f"{date_str} {time_str}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Main entry point ───────────────────────────────────────────────────────────

def render_job_tracker_detail_screen() -> None:
    """Render the 3-tab job detail view."""
    job_id: int | None = st.session_state.get("active_job_detail_id")

    if not job_id:
        st.error("No job selected.")
        if st.button("Back to Tracker", key="jt-detail-err-back"):
            st.session_state.screen = "job_tracker"
            st.rerun()
        return

    job = get_job(job_id)
    if not job:
        st.error("Job not found.")
        if st.button("Back to Tracker", key="jt-detail-notfound-back"):
            st.session_state.screen = "job_tracker"
            st.rerun()
        return

    # ── Back ──────────────────────────────────────────────────────────────────
    back_col, _ = st.columns([1.5, 6])
    with back_col:
        if secondary_button("Back", key="jt-detail-back", use_container_width=True):
            st.session_state.screen = "job_tracker"
            st.rerun()

    flash_message = st.session_state.pop("jt_detail_flash", "")
    if flash_message:
        st.success(flash_message)

    # ── Header ────────────────────────────────────────────────────────────────
    display_title = job["job_title"] or "Role title missing"
    title_style = (
        "font-size:1.55rem;font-weight:700;margin:0.3rem 0 0.1rem;"
        if job["job_title"]
        else "font-size:1.55rem;font-weight:700;margin:0.3rem 0 0.1rem;color:var(--muted);font-style:italic;"
    )
    st.markdown(f"<h1 style='{title_style}'>{display_title}</h1>", unsafe_allow_html=True)

    sub_parts = [p for p in [job["company"] or ("Company missing" if not job["company"] else ""), job["location"]] if p]
    if sub_parts:
        st.caption("  ·  ".join(sub_parts))

    badge_col, score_col, _ = st.columns([2, 2, 4])
    with badge_col:
        st.markdown(_status_pill(job["status"]), unsafe_allow_html=True)
    with score_col:
        if job["current_fit"] is not None:
            delta = job.get("latest_delta") or 0
            delta_str = (
                f" (+{delta}%)" if delta > 0
                else (f" ({delta}%)" if delta < 0 else "")
            )
            st.markdown(
                f'<p style="margin:0.25rem 0;font-size:0.88rem;">'
                f'Fit: <strong style="color:var(--green);">{job["current_fit"]}%</strong>'
                f'<span style="color:var(--muted);font-size:0.75rem;">{delta_str}</span></p>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--line);margin:0.75rem 0;">',
        unsafe_allow_html=True,
    )

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_overview, tab_materials, tab_history = st.tabs(["Overview", "Job & Materials", "History"])

    with tab_overview:
        _render_overview_tab(job)

    with tab_materials:
        _render_materials_tab(job)

    with tab_history:
        _render_history_tab(job)
