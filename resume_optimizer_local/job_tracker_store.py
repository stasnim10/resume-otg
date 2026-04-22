"""
Job Tracker persistence layer.

All tracker-related CRUD operations.  The primary record is a row in
`applications` — every `applications.id` is a `job_id` throughout this module.
New tables added here (job_notes, job_timeline_events, job_materials,
job_optimization_runs) always reference `applications.id` via `job_id`.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from profile_schema import utc_now_iso
from profile_store import get_connection, init_profile_db

logger = logging.getLogger(__name__)

# Columns permitted in dynamic UPDATE clauses — guards against SQL injection.
_ALLOWED_UPDATE_COLUMNS: frozenset[str] = frozenset({
    "job_title", "company", "location", "job_url",
    "applied_date", "next_action", "status", "job_description", "updated_at",
})

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

TRACKER_STATUSES = [
    "Bookmarked",
    "Preparing",
    "Applied",
    "Interviewing",
    "Offer",
    "Rejected",
    "Archived",
]

_LEGACY_STATUS_MAP: dict[str, str] = {
    "completed":   "Preparing",
    "draft":       "Bookmarked",
    "in_progress": "Preparing",
    "active":      "Preparing",
}

STATUS_COLORS: dict[str, str] = {
    "Bookmarked":  "var(--muted)",
    "Preparing":   "var(--blue)",
    "Applied":     "var(--green)",
    "Interviewing":"#a78bfa",      # soft purple — not in existing vars
    "Offer":       "var(--green)",
    "Rejected":    "var(--danger)",
    "Archived":    "var(--muted)",
}


def _has_identity(job_title: str | None = None, company: str | None = None) -> bool:
    """Return whether at least one user-meaningful identity field is present."""
    return bool((job_title or "").strip() or (company or "").strip())


def normalize_status(raw: str) -> str:
    """Map legacy / unknown statuses to a valid tracker status."""
    if raw in TRACKER_STATUSES:
        return raw
    return _LEGACY_STATUS_MAP.get(raw, "Bookmarked")


# ---------------------------------------------------------------------------
# Schema initialisation + migration
# ---------------------------------------------------------------------------

_tracker_initialized: bool = False


def init_tracker_tables() -> None:
    """Create tracker tables if missing. Idempotent — only runs DDL once per process."""
    global _tracker_initialized
    if _tracker_initialized:
        return
    init_profile_db()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS job_notes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      INTEGER NOT NULL,
                content     TEXT NOT NULL DEFAULT '',
                note_type   TEXT NOT NULL DEFAULT 'general',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_timeline_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id        INTEGER NOT NULL,
                event_type    TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS job_materials (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id        INTEGER NOT NULL,
                material_type TEXT NOT NULL,
                file_path     TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                saved_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_optimization_runs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id            INTEGER NOT NULL,
                match_before      INTEGER NOT NULL DEFAULT 0,
                match_after       INTEGER NOT NULL DEFAULT 0,
                delta             INTEGER NOT NULL DEFAULT 0,
                improvements      TEXT NOT NULL DEFAULT '[]',
                resume_path       TEXT NOT NULL DEFAULT '',
                cover_letter_path TEXT NOT NULL DEFAULT '',
                profile_item_ids  TEXT NOT NULL DEFAULT '[]',
                run_at            TEXT NOT NULL
            );
            """
        )
        _ensure_applications_tracker_columns(conn)
        _migrate_existing_applications(conn)
    _tracker_initialized = True


def _ensure_applications_tracker_columns(conn: sqlite3.Connection) -> None:
    """Add tracker-specific columns to the existing applications table."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(applications)").fetchall()}
    new_cols = {
        "next_action":  "TEXT NOT NULL DEFAULT ''",
        "applied_date": "TEXT NOT NULL DEFAULT ''",
        "location":     "TEXT NOT NULL DEFAULT ''",
    }
    for col, col_type in new_cols.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {col} {col_type}")


def _migrate_existing_applications(conn: sqlite3.Connection) -> None:
    """
    One-time migration: for every completed applications row that has no
    corresponding job_optimization_runs row, create the initial run record
    and a job_added timeline event.
    """
    rows = conn.execute(
        """
        SELECT a.id, a.match_before, a.match_after, a.improvements, a.optimized_at
        FROM applications a
        WHERE a.optimized_at IS NOT NULL
          AND a.optimized_at != ''
          AND NOT EXISTS (
              SELECT 1 FROM job_optimization_runs r WHERE r.job_id = a.id
          )
        """
    ).fetchall()

    for row in rows:
        delta = (row["match_after"] or 0) - (row["match_before"] or 0)
        conn.execute(
            """
            INSERT INTO job_optimization_runs
                (job_id, match_before, match_after, delta, improvements,
                 resume_path, cover_letter_path, profile_item_ids, run_at)
            VALUES (?, ?, ?, ?, ?, '', '', '[]', ?)
            """,
            (
                row["id"],
                row["match_before"] or 0,
                row["match_after"] or 0,
                delta,
                row["improvements"] or "[]",
                row["optimized_at"],
            ),
        )

    # Ensure every application row has a job_added timeline event
    app_rows = conn.execute(
        """
        SELECT a.id, a.created_at FROM applications a
        WHERE NOT EXISTS (
            SELECT 1 FROM job_timeline_events t
            WHERE t.job_id = a.id AND t.event_type = 'job_added'
        )
        """
    ).fetchall()
    for row in app_rows:
        conn.execute(
            """
            INSERT INTO job_timeline_events (job_id, event_type, description, created_at, metadata_json)
            VALUES (?, 'job_added', 'Job added to tracker', ?, '{}')
            """,
            (row["id"], row["created_at"]),
        )


# ---------------------------------------------------------------------------
# Job list  (the main tracker view)
# ---------------------------------------------------------------------------

def _clean_title(raw: str) -> str:
    """Normalise legacy sentinel strings to empty so the UI shows 'missing'."""
    if not raw:
        return ""
    lw = raw.strip().lower()
    if lw in ("untitled role", "untitled", "untitled job"):
        return ""
    return raw.strip()


def _clean_company(raw: str) -> str:
    """Normalise legacy sentinel strings to empty so the UI shows 'missing'."""
    if not raw:
        return ""
    lw = raw.strip().lower()
    if lw in ("untitled company", "untitled", "unknown company"):
        return ""
    return raw.strip()


def _normalize_search_text(raw: str) -> str:
    """Lowercase and collapse internal whitespace for predictable matching."""
    return " ".join((raw or "").lower().split())


def _job_matches_search(job: dict[str, Any], query: str) -> bool:
    """Match only against role title or company, never description text."""
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return True
    title = _normalize_search_text(job.get("job_title", ""))
    company = _normalize_search_text(job.get("company", ""))
    return normalized_query in title or normalized_query in company


def list_jobs(
    user_id: str = "local-user",
    search: str = "",
    status_filter: str = "All",
    sort_by: str = "Last updated",
) -> list[dict]:
    """
    Return all tracked jobs enriched with latest-run scores and note counts.
    Single query — no N+1 per-job fetches. Filtering and sorting happen in
    Python after the DB fetch.
    """
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.id, a.user_id, a.job_title, a.company, a.job_description,
                a.job_url, a.status, a.created_at, a.updated_at,
                a.location, a.applied_date, a.next_action,
                r.match_after        AS run_match_after,
                r.delta              AS run_delta,
                r.resume_path        AS run_resume_path,
                r.cover_letter_path  AS run_cover_letter_path,
                r.run_at             AS run_run_at,
                COALESCE(nc.note_count, 0) AS note_count
            FROM applications a
            LEFT JOIN job_optimization_runs r ON r.id = (
                SELECT id FROM job_optimization_runs
                WHERE job_id = a.id ORDER BY run_at DESC LIMIT 1
            )
            LEFT JOIN (
                SELECT job_id, COUNT(*) AS note_count
                FROM job_notes GROUP BY job_id
            ) nc ON nc.job_id = a.id
            WHERE a.user_id = ?
            ORDER BY a.updated_at DESC
            """,
            (user_id,),
        ).fetchall()

    jobs: list[dict] = []
    for row in rows:
        has_run = row["run_run_at"] is not None
        job: dict[str, Any] = {
            "id":              row["id"],
            "job_title":       _clean_title(row["job_title"] or ""),
            "company":         _clean_company(row["company"] or ""),
            "location":        (row["location"] or "").strip(),
            "job_url":         (row["job_url"] or "").strip(),
            "jd_text":         row["job_description"] or "",
            "status":          normalize_status(row["status"]),
            "applied_date":    (row["applied_date"] or "").strip(),
            "created_at":      row["created_at"],
            "updated_at":      row["updated_at"],
            "next_action":     (row["next_action"] or "").strip(),
            "current_fit":     row["run_match_after"]       if has_run else None,
            "latest_delta":    row["run_delta"]             if has_run else None,
            "last_run_at":     row["run_run_at"]            if has_run else None,
            "has_resume":      bool(has_run and row["run_resume_path"]),
            "has_cover_letter":bool(has_run and row["run_cover_letter_path"]),
            "note_count":      row["note_count"],
        }
        jobs.append(job)

    # ── Search ────────────────────────────────────────────────────────────────
    if search.strip():
        jobs = [j for j in jobs if _job_matches_search(j, search)]

    # ── Status filter ─────────────────────────────────────────────────────────
    if status_filter and status_filter != "All":
        jobs = [j for j in jobs if j["status"] == status_filter]

    # ── Sort ──────────────────────────────────────────────────────────────────
    if sort_by == "Date applied":
        jobs.sort(key=lambda j: j["applied_date"] or "", reverse=True)
    elif sort_by == "Highest fit":
        jobs.sort(key=lambda j: j["current_fit"] if j["current_fit"] is not None else -1, reverse=True)
    elif sort_by == "Newest saved":
        jobs.sort(key=lambda j: j["created_at"], reverse=True)
    else:  # Last updated (default)
        jobs.sort(key=lambda j: j["updated_at"], reverse=True)

    return jobs


def get_job(job_id: int) -> dict | None:
    """Return a single job dict, or None if not found."""
    init_tracker_tables()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                a.id, a.user_id, a.job_title, a.company, a.job_description,
                a.job_url, a.role_family, a.industry, a.status,
                a.created_at, a.updated_at,
                a.location, a.applied_date, a.next_action,
                r.match_after        AS run_match_after,
                r.delta              AS run_delta,
                COALESCE(nc.note_count, 0) AS note_count
            FROM applications a
            LEFT JOIN job_optimization_runs r ON r.id = (
                SELECT id FROM job_optimization_runs
                WHERE job_id = a.id ORDER BY run_at DESC LIMIT 1
            )
            LEFT JOIN (
                SELECT job_id, COUNT(*) AS note_count
                FROM job_notes GROUP BY job_id
            ) nc ON nc.job_id = a.id
            WHERE a.id = ?
            """,
            (job_id,),
        ).fetchone()
    if row is None:
        return None
    has_run = row["run_match_after"] is not None
    return {
        "id":           row["id"],
        "job_title":    _clean_title(row["job_title"] or ""),
        "company":      _clean_company(row["company"] or ""),
        "location":     (row["location"] or "").strip(),
        "job_url":      row["job_url"]          or "",
        "jd_text":      row["job_description"]  or "",
        "role_family":  row["role_family"]       or "",
        "industry":     row["industry"]          or "",
        "status":       normalize_status(row["status"]),
        "applied_date": (row["applied_date"] or "").strip(),
        "created_at":   row["created_at"],
        "updated_at":   row["updated_at"],
        "next_action":  (row["next_action"] or "").strip(),
        "current_fit":  row["run_match_after"] if has_run else None,
        "latest_delta": row["run_delta"]       if has_run else None,
        "note_count":   row["note_count"],
    }


# ---------------------------------------------------------------------------
# Job mutations
# ---------------------------------------------------------------------------

def add_job_manually(
    job_title: str,
    company: str,
    location: str = "",
    job_url: str = "",
    jd_text: str = "",
    applied_date: str = "",
    status: str = "Bookmarked",
    user_id: str = "local-user",
) -> int:
    """Create a new tracked job without an optimization run. Returns job_id."""
    init_tracker_tables()
    if not _has_identity(job_title, company):
        raise ValueError("Add at least a role title or company before saving this job.")
    now = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO applications
                (user_id, job_title, company, job_description, role_family, industry,
                 job_url, status, location, applied_date, next_action, created_at, updated_at)
            VALUES (?, ?, ?, ?, '', '', ?, ?, ?, ?, '', ?, ?)
            """,
            (user_id, job_title.strip(), company.strip(), jd_text.strip(),
             job_url.strip(), status, location.strip(), applied_date.strip(), now, now),
        )
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    add_timeline_event(job_id, "job_added", f"Job added manually: {job_title} at {company}")
    return job_id


def update_job_status(job_id: int, new_status: str, user_id: str = "local-user") -> None:
    """Update a job's tracker status and create a timeline event."""
    init_tracker_tables()
    now = utc_now_iso()
    with get_connection() as conn:
        old_row = conn.execute("SELECT status FROM applications WHERE id = ?", (job_id,)).fetchone()
        old_status = normalize_status(old_row["status"]) if old_row else "Bookmarked"
        conn.execute(
            "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, job_id),
        )
    if old_status != new_status:
        add_timeline_event(
            job_id,
            "status_changed",
            f"Status changed from {old_status} to {new_status}",
            {"from": old_status, "to": new_status},
        )


def update_job_metadata(
    job_id: int,
    job_title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    job_url: str | None = None,
    applied_date: str | None = None,
    next_action: str | None = None,
    status: str | None = None,
    jd_text: str | None = None,
) -> None:
    """
    Update any editable metadata field on a tracked job.
    Only fields explicitly passed (not None) are written.
    """
    init_tracker_tables()
    with get_connection() as conn:
        old_row = conn.execute("SELECT * FROM applications WHERE id = ?", (job_id,)).fetchone()
    if old_row is None:
        raise ValueError("This job could not be found.")

    old_title = (old_row["job_title"] or "").strip()
    old_company = (old_row["company"] or "").strip()
    candidate_title = job_title.strip() if job_title is not None else old_title
    candidate_company = company.strip() if company is not None else old_company
    if not _has_identity(candidate_title, candidate_company):
        raise ValueError("Keep at least a role title or company on this job.")

    updates: list[tuple[str, str]] = []
    if job_title is not None:
        updates.append(("job_title", job_title.strip()))
    if company is not None:
        updates.append(("company", company.strip()))
    if location is not None:
        updates.append(("location", location.strip()))
    if job_url is not None:
        updates.append(("job_url", job_url.strip()))
    if applied_date is not None:
        updates.append(("applied_date", applied_date.strip()))
    if next_action is not None:
        updates.append(("next_action", next_action.strip()))
    if status is not None:
        updates.append(("status", status))
    if jd_text is not None:
        updates.append(("job_description", jd_text.strip()))
    if not updates:
        return
    old_status = normalize_status(old_row["status"] or "")
    changed_fields = [
        col for col, value in updates
        if col != "updated_at" and str(old_row[col] or "").strip() != str(value).strip()
    ]
    updates.append(("updated_at", utc_now_iso()))
    for col, _ in updates:
        if col not in _ALLOWED_UPDATE_COLUMNS:
            raise ValueError(f"Unexpected column name: {col!r}")
    set_clause = ", ".join(f"{col} = ?" for col, _ in updates)
    values = [v for _, v in updates] + [job_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE applications SET {set_clause} WHERE id = ?", values)
    if status is not None and normalize_status(status) != old_status:
        add_timeline_event(
            job_id,
            "status_changed",
            f"Status changed from {old_status} to {normalize_status(status)}",
            {"from": old_status, "to": normalize_status(status)},
        )
    non_status_fields = [field for field in changed_fields if field != "status"]
    if non_status_fields:
        labels = ", ".join(field.replace("_", " ") for field in non_status_fields)
        add_timeline_event(
            job_id,
            "job_updated",
            f"Updated job details: {labels}",
            {"fields": non_status_fields},
        )
    _touch_job(job_id)


def update_job_next_action(job_id: int, text: str) -> None:
    """Update the next-action freeform field inline (no timeline event needed)."""
    init_tracker_tables()
    with get_connection() as conn:
        conn.execute(
            "UPDATE applications SET next_action = ?, updated_at = ? WHERE id = ?",
            (text.strip(), utc_now_iso(), job_id),
        )


def mark_applied(job_id: int, applied_date: str = "") -> None:
    """Set the applied date and move status to Applied."""
    init_tracker_tables()
    date = applied_date or utc_now_iso()[:10]
    with get_connection() as conn:
        conn.execute(
            "UPDATE applications SET applied_date = ?, status = ?, updated_at = ? WHERE id = ?",
            (date, "Applied", utc_now_iso(), job_id),
        )
    add_timeline_event(job_id, "application_marked_submitted", f"Marked as applied on {date}")


def delete_job(job_id: int) -> None:
    """Permanently remove a tracked job and all related tracker data."""
    init_tracker_tables()
    with get_connection() as conn:
        conn.execute("DELETE FROM job_notes WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM job_timeline_events WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM job_materials WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM job_optimization_runs WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM application_profile_items WHERE application_id = ?", (job_id,))
        conn.execute("DELETE FROM applications WHERE id = ?", (job_id,))


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def add_note(
    job_id: int,
    content: str,
    note_type: str = "general",
) -> int:
    """Add a note and create a paired timeline event. Returns note_id."""
    init_tracker_tables()
    now = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_notes (job_id, content, note_type, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, content.strip(), note_type, now, now),
        )
        note_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    add_timeline_event(
        job_id, "note_added",
        f"Note added ({note_type})",
        {"note_id": note_id, "preview": content[:80]},
    )
    _touch_job(job_id)
    return note_id


def list_notes(job_id: int) -> list[dict]:
    """Return all notes for a job, newest first."""
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_notes WHERE job_id = ? ORDER BY created_at DESC",
            (job_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_note(note_id: int, content: str) -> None:
    """Edit a note's content."""
    init_tracker_tables()
    with get_connection() as conn:
        row = conn.execute("SELECT job_id FROM job_notes WHERE id = ?", (note_id,)).fetchone()
        conn.execute(
            "UPDATE job_notes SET content = ?, updated_at = ? WHERE id = ?",
            (content.strip(), utc_now_iso(), note_id),
        )
    if row:
        _touch_job(row["job_id"])


# ---------------------------------------------------------------------------
# Timeline events
# ---------------------------------------------------------------------------

def add_timeline_event(
    job_id: int,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    """Append a timeline event for a job."""
    init_tracker_tables()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_timeline_events
                (job_id, event_type, description, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, event_type, description, utc_now_iso(), json.dumps(metadata or {})),
        )


def list_timeline_events(job_id: int) -> list[dict]:
    """Return all events for a job, newest first."""
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_timeline_events WHERE job_id = ? ORDER BY created_at DESC",
            (job_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            logger.debug("Failed to parse metadata_json for row %s", d.get("id"), exc_info=True)
            d["metadata"] = {}
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def save_material(
    job_id: int,
    material_type: str,
    file_path: str = "",
    metadata: dict | None = None,
) -> int:
    """Attach a material artifact to a job. Returns material_id."""
    init_tracker_tables()
    now = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_materials (job_id, material_type, file_path, metadata_json, saved_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, material_type, file_path, json.dumps(metadata or {}), now),
        )
        mat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    add_timeline_event(
        job_id, "material_saved",
        f"{material_type.replace('_', ' ').title()} saved",
        {"material_type": material_type, "file_path": file_path},
    )
    _touch_job(job_id)
    return mat_id


def list_materials(job_id: int) -> list[dict]:
    """Return all materials for a job."""
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_materials WHERE job_id = ? ORDER BY saved_at DESC",
            (job_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            logger.debug("Failed to parse metadata_json for row %s", d.get("id"), exc_info=True)
            d["metadata"] = {}
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Optimization runs
# ---------------------------------------------------------------------------

def add_optimization_run(
    job_id: int,
    match_before: int,
    match_after: int,
    improvements: list,
    resume_path: str = "",
    cover_letter_path: str = "",
    profile_item_ids: list[int] | None = None,
) -> int:
    """Record a completed optimization run for a job. Returns run_id."""
    init_tracker_tables()
    now  = utc_now_iso()
    delta = match_after - match_before
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_optimization_runs
                (job_id, match_before, match_after, delta, improvements,
                 resume_path, cover_letter_path, profile_item_ids, run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, match_before, match_after, delta,
                json.dumps(improvements or []),
                resume_path, cover_letter_path,
                json.dumps(profile_item_ids or []),
                now,
            ),
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    add_timeline_event(
        job_id, "optimization_run_completed",
        f"Optimization run: {match_before}% → {match_after}% (Δ{delta:+d}%)",
        {"run_id": run_id, "match_before": match_before, "match_after": match_after, "delta": delta},
    )
    _touch_job(job_id)
    return run_id


def list_optimization_runs(job_id: int) -> list[dict]:
    """Return all optimization runs for a job, newest first."""
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM job_optimization_runs WHERE job_id = ? ORDER BY run_at DESC",
            (job_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["improvements_list"] = json.loads(d.get("improvements") or "[]")
            d["improvements_count"] = len(d["improvements_list"])
        except Exception:
            logger.debug("Failed to parse improvements JSON for run %s", d.get("id"), exc_info=True)
            d["improvements_list"] = []
            d["improvements_count"] = 0
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_latest_run_raw(job_id: int) -> dict | None:
    """Return the most recent optimization run dict, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT match_before, match_after, delta, resume_path,
                   cover_letter_path, run_at
            FROM job_optimization_runs
            WHERE job_id = ?
            ORDER BY run_at DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def _count_notes(job_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM job_notes WHERE job_id = ?", (job_id,)
        ).fetchone()
    return row["n"] if row else 0


def _touch_job(job_id: int) -> None:
    """Update the job's updated_at timestamp."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE applications SET updated_at = ? WHERE id = ?",
            (utc_now_iso(), job_id),
        )


def get_profile_items_for_job(job_id: int) -> list[dict]:
    """
    Return profile items linked to a job via application_profile_items.
    Returns list of dicts with id, item_type, title, organization.
    """
    init_tracker_tables()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pi.id, pi.item_type, pi.title, pi.organization
            FROM application_profile_items api
            JOIN profile_items pi ON pi.id = api.profile_item_id
            WHERE api.application_id = ?
            ORDER BY pi.item_type, pi.title
            """,
            (job_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Hosted-web routing (Supabase) ─────────────────────────────────────────────


def _is_hosted() -> bool:
    try:
        import streamlit as st
        import os

        value = st.secrets.get("HOSTED_WEB")
        if value is None:
            value = os.environ.get("HOSTED_WEB", "false")
        return str(value).lower() == "true"
    except Exception:
        import os

        return str(os.environ.get("HOSTED_WEB", "false")).lower() == "true"


def _apply_supabase_override() -> None:
    if not _is_hosted():
        return
    try:
        import sys
        import supabase_job_store as _sb
        _mod = sys.modules[__name__]
        _public = [n for n in dir(_sb) if not n.startswith("_") and callable(getattr(_sb, n))]
        for name in _public:
            setattr(_mod, name, getattr(_sb, name))
        logger.info("job_tracker_store: Supabase override applied (%d functions)", len(_public))
    except Exception as exc:
        logger.warning(
            "job_tracker_store: Supabase override failed — falling back to SQLite: %s", exc
        )


_apply_supabase_override()
