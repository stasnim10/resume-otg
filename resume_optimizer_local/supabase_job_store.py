"""
Supabase-backed implementation of the job tracker store interface.

All public functions match the signatures in job_tracker_store.py so the
routing shim can swap transparently.
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from job_tracker_store import (
    STATUS_COLORS,
    TRACKER_STATUSES,
    _clean_company,
    _clean_title,
    _job_matches_search,
    normalize_status,
)
from profile_schema import utc_now_iso
from supabase_client import get_supabase

logger = logging.getLogger(__name__)


# Re-export constants so importers that do `from job_tracker_store import STATUS_COLORS`
# still work after the module override.
__all__ = [
    "TRACKER_STATUSES",
    "STATUS_COLORS",
    "normalize_status",
    "init_tracker_tables",
    "list_jobs",
    "get_job",
    "add_job_manually",
    "update_job_status",
    "update_job_metadata",
    "update_job_next_action",
    "delete_job",
    "add_note",
    "list_notes",
    "update_note",
    "add_optimization_run",
    "list_optimization_runs",
    "list_timeline_events",
    "list_materials",
    "mark_applied",
    "add_timeline_event",
    "save_material",
    "get_profile_items_for_job",
]


def _uid(user_id: str | None = None) -> str:
    if user_id and user_id not in ("local-user", ""):
        return user_id
    uid = st.session_state.get("auth_user_id", "")
    if not uid:
        raise RuntimeError("User not authenticated.")
    return uid


def _sb():
    return get_supabase()


# ---------------------------------------------------------------------------
# No-op init
# ---------------------------------------------------------------------------


def init_tracker_tables() -> None:
    pass


# ---------------------------------------------------------------------------
# Job list
# ---------------------------------------------------------------------------


def list_jobs(
    user_id: str = "local-user",
    search: str = "",
    status_filter: str = "All",
    sort_by: str = "Last updated",
) -> list[dict]:
    """Return all tracked jobs, enriched with latest run scores and note count."""
    uid = _uid(user_id)
    try:
        resp = (
            _sb()
            .table("tracked_jobs")
            .select("*, job_optimization_runs(match_after, delta, run_at), job_notes(id)")
            .eq("user_id", uid)
            .order("updated_at", desc=True)
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:
        logger.warning("list_jobs failed: %s", exc)
        return []

    jobs: list[dict] = []
    for row in rows:
        runs = row.get("job_optimization_runs") or []
        latest_run = runs[-1] if runs else {}
        note_count = len(row.get("job_notes") or [])

        job: dict[str, Any] = {
            "id": row["id"],
            "job_title": _clean_title(row.get("job_title") or ""),
            "company": _clean_company(row.get("company") or ""),
            "location": (row.get("location") or "").strip(),
            "job_url": (row.get("job_url") or "").strip(),
            "jd_text": row.get("job_description") or "",
            "status": normalize_status(row.get("status") or ""),
            "applied_date": (row.get("applied_date") or ""),
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
            "next_action": (row.get("next_action") or "").strip(),
            "has_run": bool(latest_run),
            "current_fit": latest_run.get("match_after") if latest_run else None,
            "latest_delta": latest_run.get("delta") if latest_run else None,
            "last_run_at": latest_run.get("run_at") if latest_run else None,
            "has_resume": False,
            "has_cover_letter": False,
            "note_count": note_count,
        }
        jobs.append(job)

    # Filter
    if status_filter and status_filter != "All":
        jobs = [j for j in jobs if j["status"] == status_filter]
    if search.strip():
        jobs = [j for j in jobs if _job_matches_search(j, search)]

    # Sort
    if sort_by == "Newest saved":
        jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    elif sort_by == "Date applied":
        jobs.sort(key=lambda j: j.get("applied_date") or "", reverse=True)
    elif sort_by == "Highest fit":
        jobs.sort(key=lambda j: j.get("current_fit") if j.get("current_fit") is not None else -1, reverse=True)
    # Default "Last updated" already sorted by DB query

    return jobs


def get_job(job_id: Any) -> dict | None:
    if not job_id:
        return None
    try:
        resp = (
            _sb()
            .table("tracked_jobs")
            .select("*")
            .eq("id", str(job_id))
            .maybe_single()
            .execute()
        )
        if resp.data:
            row = resp.data
            return {
                "id": row["id"],
                "user_id": row.get("user_id", ""),
                "job_title": _clean_title(row.get("job_title") or ""),
                "company": _clean_company(row.get("company") or ""),
                "location": (row.get("location") or "").strip(),
                "job_url": (row.get("job_url") or "").strip(),
                "jd_text": row.get("job_description") or "",
                "role_family": row.get("role_family") or "",
                "industry": row.get("industry") or "",
                "status": normalize_status(row.get("status") or ""),
                "applied_date": row.get("applied_date") or "",
                "next_action": (row.get("next_action") or "").strip(),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", ""),
                "current_fit": None,
                "latest_delta": None,
                "note_count": 0,
            }
    except Exception as exc:
        logger.warning("get_job failed: %s", exc)
    return None


def add_job_manually(
    user_id: str = "local-user",
    job_title: str = "",
    company: str = "",
    job_url: str = "",
    location: str = "",
    jd_text: str = "",
    status: str = "Bookmarked",
) -> str:
    """Create a new tracked job and return its UUID."""
    uid = _uid(user_id)
    now = utc_now_iso()
    row = {
        "user_id": uid,
        "job_title": job_title.strip(),
        "company": company.strip(),
        "job_url": job_url.strip(),
        "location": location.strip(),
        "job_description": jd_text.strip(),
        "status": normalize_status(status),
        "next_action": "",
        "applied_date": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        resp = _sb().table("tracked_jobs").insert(row).execute()
        if resp.data:
            job_id = resp.data[0]["id"]
            add_timeline_event(job_id, "job_added", "Job added to tracker")
            return job_id
    except Exception as exc:
        logger.warning("add_job_manually failed: %s", exc)
    return ""


def update_job_status(job_id: Any, new_status: str, user_id: str = "local-user") -> None:
    norm = normalize_status(new_status)
    try:
        _sb().table("tracked_jobs").update(
            {"status": norm, "updated_at": utc_now_iso()}
        ).eq("id", str(job_id)).execute()
        add_timeline_event(job_id, "status_changed", f"Status changed to {norm}")
    except Exception as exc:
        logger.warning("update_job_status failed: %s", exc)


def update_job_metadata(job_id: Any, **kwargs: Any) -> None:
    _ALLOWED = {
        "job_title", "company", "location", "job_url",
        "applied_date", "next_action", "status", "jd_text",
    }
    patch: dict[str, Any] = {"updated_at": utc_now_iso()}
    for key, val in kwargs.items():
        if key == "jd_text":
            patch["job_description"] = val
        elif key in _ALLOWED:
            patch[key] = val
    if len(patch) <= 1:
        return
    try:
        _sb().table("tracked_jobs").update(patch).eq("id", str(job_id)).execute()
        add_timeline_event(job_id, "job_updated", "Job details updated")
    except Exception as exc:
        logger.warning("update_job_metadata failed: %s", exc)


def update_job_next_action(job_id: Any, text: str) -> None:
    try:
        _sb().table("tracked_jobs").update(
            {"next_action": text, "updated_at": utc_now_iso()}
        ).eq("id", str(job_id)).execute()
    except Exception as exc:
        logger.warning("update_job_next_action failed: %s", exc)


def mark_applied(job_id: Any, applied_date: str = "") -> None:
    date = applied_date or utc_now_iso()[:10]
    try:
        _sb().table("tracked_jobs").update(
            {"status": "Applied", "applied_date": date, "updated_at": utc_now_iso()}
        ).eq("id", str(job_id)).execute()
        add_timeline_event(job_id, "application_marked_submitted", "Marked as applied")
    except Exception as exc:
        logger.warning("mark_applied failed: %s", exc)


def delete_job(job_id: Any) -> None:
    try:
        _sb().table("tracked_jobs").delete().eq("id", str(job_id)).execute()
    except Exception as exc:
        logger.warning("delete_job failed: %s", exc)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


def add_note(
    job_id: Any,
    content: str,
    note_type: str = "general",
    user_id: str = "local-user",
) -> None:
    uid = _uid(user_id)
    now = utc_now_iso()
    try:
        _sb().table("job_notes").insert({
            "job_id": str(job_id),
            "user_id": uid,
            "note_type": note_type,
            "content": content,
            "created_at": now,
        }).execute()
        add_timeline_event(job_id, "note_added", "Note added")
    except Exception as exc:
        logger.warning("add_note failed: %s", exc)


def list_notes(job_id: Any) -> list[dict]:
    try:
        resp = (
            _sb()
            .table("job_notes")
            .select("*")
            .eq("job_id", str(job_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [
            {
                "id": r["id"],
                "job_id": r["job_id"],
                "content": r.get("content", ""),
                "note_type": r.get("note_type", "general"),
                "created_at": r.get("created_at", ""),
                "updated_at": r.get("created_at", ""),
            }
            for r in (resp.data or [])
        ]
    except Exception as exc:
        logger.warning("list_notes failed: %s", exc)
        return []


def update_note(note_id: Any, content: str) -> None:
    try:
        _sb().table("job_notes").update({"content": content}).eq("id", str(note_id)).execute()
    except Exception as exc:
        logger.warning("update_note failed: %s", exc)


# ---------------------------------------------------------------------------
# Timeline events
# ---------------------------------------------------------------------------


def add_timeline_event(
    job_id: Any,
    event_type: str,
    description: str = "",
    metadata: dict | None = None,
) -> None:
    try:
        _sb().table("job_timeline_events").insert({
            "job_id": str(job_id),
            "event_type": event_type,
            "description": description,
            "metadata_json": metadata or {},
            "created_at": utc_now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("add_timeline_event failed: %s", exc)


def list_timeline_events(job_id: Any) -> list[dict]:
    try:
        resp = (
            _sb()
            .table("job_timeline_events")
            .select("*")
            .eq("job_id", str(job_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [
            {
                "id": r["id"],
                "job_id": r["job_id"],
                "event_type": r.get("event_type", ""),
                "description": r.get("description", ""),
                "created_at": r.get("created_at", ""),
                "metadata_json": r.get("metadata_json") or "{}",
            }
            for r in (resp.data or [])
        ]
    except Exception as exc:
        logger.warning("list_timeline_events failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Materials (stubs — file upload is Phase 2)
# ---------------------------------------------------------------------------


def save_material(
    job_id: Any,
    material_type: str,
    file_path: str,
    metadata: dict | None = None,
) -> None:
    logger.debug("save_material: file storage not yet implemented in Supabase store")


def list_materials(job_id: Any) -> list[dict]:
    return []


# ---------------------------------------------------------------------------
# Optimization runs
# ---------------------------------------------------------------------------


def add_optimization_run(
    job_id: Any,
    match_before: int = 0,
    match_after: int = 0,
    improvements: list | None = None,
    resume_path: str = "",
    cover_letter_path: str = "",
    profile_item_ids: list | None = None,
    user_id: str = "local-user",
) -> str:
    uid = _uid(user_id)
    delta = (match_after or 0) - (match_before or 0)
    now = utc_now_iso()
    row = {
        "job_id": str(job_id),
        "user_id": uid,
        "match_before": match_before or 0,
        "match_after": match_after or 0,
        "delta": delta,
        "improvements": improvements or [],
        "resume_storage_path": resume_path or "",
        "cover_letter_storage_path": cover_letter_path or "",
        "profile_item_ids": [str(i) for i in (profile_item_ids or [])],
        "run_at": now,
    }
    try:
        resp = _sb().table("job_optimization_runs").insert(row).execute()
        _sb().table("tracked_jobs").update({"updated_at": now}).eq("id", str(job_id)).execute()
        add_timeline_event(job_id, "optimization_run_completed", f"Optimization run: {match_after}% match")
        if resp.data:
            return resp.data[0]["id"]
    except Exception as exc:
        logger.warning("add_optimization_run failed: %s", exc)
    return ""


def list_optimization_runs(job_id: Any) -> list[dict]:
    try:
        resp = (
            _sb()
            .table("job_optimization_runs")
            .select("*")
            .eq("job_id", str(job_id))
            .order("run_at", desc=True)
            .execute()
        )
        return [
            {
                "id": r["id"],
                "job_id": r["job_id"],
                "match_before": r.get("match_before", 0),
                "match_after": r.get("match_after", 0),
                "delta": r.get("delta", 0),
                "improvements": r.get("improvements") or [],
                "resume_path": r.get("resume_storage_path", ""),
                "cover_letter_path": r.get("cover_letter_storage_path", ""),
                "profile_item_ids": r.get("profile_item_ids") or [],
                "run_at": r.get("run_at", ""),
            }
            for r in (resp.data or [])
        ]
    except Exception as exc:
        logger.warning("list_optimization_runs failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Profile items for job (best-effort from tracked_jobs.profile_item_ids)
# ---------------------------------------------------------------------------


def get_profile_items_for_job(job_id: Any) -> list[dict]:
    return []
