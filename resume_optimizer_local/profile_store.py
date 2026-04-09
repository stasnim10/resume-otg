"""
SQLite-backed persistence for Career Profile foundation.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from profile_schema import Application, CareerProfile, ProfileItem, ProfileSource, utc_now_iso


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "career_profile.db"


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_profile_db() -> None:
    """Create required tables if missing."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS career_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                linkedin TEXT NOT NULL DEFAULT '',
                headline TEXT NOT NULL DEFAULT '',
                career_stage TEXT NOT NULL DEFAULT 'Student',
                summary TEXT NOT NULL DEFAULT '',
                target_roles_json TEXT NOT NULL DEFAULT '[]',
                target_industries_json TEXT NOT NULL DEFAULT '[]',
                preferred_locations_json TEXT NOT NULL DEFAULT '[]',
                work_authorization TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                file_path TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL DEFAULT '',
                parsed_status TEXT NOT NULL DEFAULT 'pending',
                parsed_payload_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                profile_id INTEGER,
                source_id INTEGER,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                organization TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                is_current INTEGER NOT NULL DEFAULT 0,
                description TEXT NOT NULL DEFAULT '',
                bullets_json TEXT NOT NULL DEFAULT '[]',
                skills_json TEXT NOT NULL DEFAULT '[]',
                tools_json TEXT NOT NULL DEFAULT '[]',
                industry_tags_json TEXT NOT NULL DEFAULT '[]',
                function_tags_json TEXT NOT NULL DEFAULT '[]',
                keywords_json TEXT NOT NULL DEFAULT '[]',
                confidence_score REAL NOT NULL DEFAULT 0.5,
                verification_status TEXT NOT NULL DEFAULT 'suggested',
                visibility TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                job_title TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                job_description TEXT NOT NULL DEFAULT '',
                role_family TEXT NOT NULL DEFAULT '',
                industry TEXT NOT NULL DEFAULT '',
                job_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS application_profile_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                profile_item_id INTEGER NOT NULL,
                selected_by TEXT NOT NULL DEFAULT 'user',
                rank_score REAL NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                selection_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(application_id, profile_item_id)
            );
            """
        )
        _ensure_profile_columns(conn)


def _ensure_profile_columns(conn: sqlite3.Connection) -> None:
    """Apply additive migrations for career_profiles."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(career_profiles)").fetchall()}
    expected_columns = {
        "full_name": "TEXT NOT NULL DEFAULT ''",
        "email": "TEXT NOT NULL DEFAULT ''",
        "phone": "TEXT NOT NULL DEFAULT ''",
        "location": "TEXT NOT NULL DEFAULT ''",
        "linkedin": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_type in expected_columns.items():
        if column_name not in columns:
            conn.execute(f"ALTER TABLE career_profiles ADD COLUMN {column_name} {column_type}")


def _decode_json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _application_from_row(row: sqlite3.Row, selected_ids: list[int] | None = None) -> Application:
    return Application(
        id=row["id"],
        user_id=row["user_id"],
        job_title=row["job_title"],
        company=row["company"],
        job_description=row["job_description"],
        role_family=row["role_family"],
        industry=row["industry"],
        job_url=row["job_url"],
        status=row["status"],
        selected_profile_item_ids=selected_ids or [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_or_get_profile(user_id: str = "local-user") -> CareerProfile:
    """Return the single local profile, creating it if missing."""
    init_profile_db()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM career_profiles WHERE user_id = ? ORDER BY id LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            return CareerProfile(
                id=row["id"],
                user_id=row["user_id"],
                full_name=row["full_name"],
                email=row["email"],
                phone=row["phone"],
                location=row["location"],
                linkedin=row["linkedin"],
                headline=row["headline"],
                career_stage=row["career_stage"],
                summary=row["summary"],
                target_roles=_decode_json_list(row["target_roles_json"]),
                target_industries=_decode_json_list(row["target_industries_json"]),
                preferred_locations=_decode_json_list(row["preferred_locations_json"]),
                work_authorization=row["work_authorization"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        profile = CareerProfile(user_id=user_id)
        conn.execute(
            """
            INSERT INTO career_profiles (
                user_id, full_name, email, phone, location, linkedin,
                headline, career_stage, summary,
                target_roles_json, target_industries_json, preferred_locations_json,
                work_authorization, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.user_id,
                profile.full_name,
                profile.email,
                profile.phone,
                profile.location,
                profile.linkedin,
                profile.headline,
                profile.career_stage,
                profile.summary,
                json.dumps(profile.target_roles),
                json.dumps(profile.target_industries),
                json.dumps(profile.preferred_locations),
                profile.work_authorization,
                profile.created_at,
                profile.updated_at,
            ),
        )
        profile.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return profile


def save_profile_basics(
    full_name: str,
    email: str,
    phone: str,
    location: str,
    linkedin: str,
    headline: str,
    career_stage: str,
    summary: str,
    target_roles: list[str],
    target_industries: list[str],
    preferred_locations: list[str],
    work_authorization: str,
    user_id: str = "local-user",
) -> CareerProfile:
    """Persist editable top-level profile fields."""
    profile = create_or_get_profile(user_id)
    updated_at = utc_now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE career_profiles
            SET full_name = ?,
                email = ?,
                phone = ?,
                location = ?,
                linkedin = ?,
                headline = ?,
                career_stage = ?,
                summary = ?,
                target_roles_json = ?,
                target_industries_json = ?,
                preferred_locations_json = ?,
                work_authorization = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                full_name.strip(),
                email.strip(),
                phone.strip(),
                location.strip(),
                linkedin.strip(),
                headline.strip(),
                career_stage.strip() or profile.career_stage,
                summary.strip(),
                json.dumps([item.strip() for item in target_roles if item.strip()]),
                json.dumps([item.strip() for item in target_industries if item.strip()]),
                json.dumps([item.strip() for item in preferred_locations if item.strip()]),
                work_authorization.strip(),
                updated_at,
                profile.id,
            ),
        )
    return create_or_get_profile(user_id)


def save_profile_source(
    source_type: str,
    source_name: str,
    raw_text: str,
    file_path: str = "",
    parsed_status: str = "parsed",
    parsed_payload: dict[str, Any] | None = None,
    user_id: str = "local-user",
) -> int:
    """Persist an imported source and return its id."""
    init_profile_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO profile_sources (
                user_id, source_type, source_name, file_path,
                raw_text, parsed_status, parsed_payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source_type,
                source_name,
                file_path,
                raw_text,
                parsed_status,
                json.dumps(parsed_payload or {}),
                utc_now_iso(),
            ),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def save_profile_items(
    items: list[ProfileItem],
    user_id: str = "local-user",
    replace_existing_for_source: int | None = None,
) -> list[ProfileItem]:
    """Persist extracted profile items."""
    profile = create_or_get_profile(user_id)
    with get_connection() as conn:
        if replace_existing_for_source is not None:
            conn.execute(
                "DELETE FROM profile_items WHERE user_id = ? AND source_id = ?",
                (user_id, replace_existing_for_source),
            )

        saved_items: list[ProfileItem] = []
        for item in items:
            item.user_id = user_id
            item.profile_id = profile.id
            item.created_at = item.created_at or utc_now_iso()
            item.updated_at = utc_now_iso()
            conn.execute(
                """
                INSERT INTO profile_items (
                    user_id, profile_id, source_id, item_type, title, organization, location,
                    start_date, end_date, is_current, description,
                    bullets_json, skills_json, tools_json,
                    industry_tags_json, function_tags_json, keywords_json,
                    confidence_score, verification_status, visibility,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.user_id,
                    item.profile_id,
                    item.source_id,
                    item.item_type,
                    item.title,
                    item.organization,
                    item.location,
                    item.start_date,
                    item.end_date,
                    1 if item.is_current else 0,
                    item.description,
                    json.dumps(item.bullets),
                    json.dumps(item.skills),
                    json.dumps(item.tools),
                    json.dumps(item.industry_tags),
                    json.dumps(item.function_tags),
                    json.dumps(item.keywords),
                    item.confidence_score,
                    item.verification_status,
                    item.visibility,
                    item.created_at,
                    item.updated_at,
                ),
            )
            item.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            saved_items.append(item)
    return saved_items


def list_profile_items(user_id: str = "local-user") -> list[ProfileItem]:
    """Return all stored profile items."""
    init_profile_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM profile_items WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [
        ProfileItem(
            id=row["id"],
            user_id=row["user_id"],
            profile_id=row["profile_id"],
            source_id=row["source_id"],
            item_type=row["item_type"],
            title=row["title"],
            organization=row["organization"],
            location=row["location"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            is_current=bool(row["is_current"]),
            description=row["description"],
            bullets=_decode_json_list(row["bullets_json"]),
            skills=_decode_json_list(row["skills_json"]),
            tools=_decode_json_list(row["tools_json"]),
            industry_tags=_decode_json_list(row["industry_tags_json"]),
            function_tags=_decode_json_list(row["function_tags_json"]),
            keywords=_decode_json_list(row["keywords_json"]),
            confidence_score=float(row["confidence_score"]),
            verification_status=row["verification_status"],
            visibility=row["visibility"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def list_profile_sources(user_id: str = "local-user") -> list[ProfileSource]:
    """Return uploaded/imported sources."""
    init_profile_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM profile_sources WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [
        ProfileSource(
            id=row["id"],
            user_id=row["user_id"],
            source_type=row["source_type"],
            source_name=row["source_name"],
            file_path=row["file_path"],
            raw_text=row["raw_text"],
            parsed_status=row["parsed_status"],
            parsed_payload_json=row["parsed_payload_json"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def update_profile_item_verification(item_id: int, verification_status: str) -> None:
    """Update the verification flag for a profile item."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE profile_items SET verification_status = ?, updated_at = ? WHERE id = ?",
            (verification_status, utc_now_iso(), item_id),
        )


def update_profile_item(item: ProfileItem) -> None:
    """Persist editable fields for an existing profile item."""
    if item.id is None:
        raise ValueError("Profile item id is required for updates.")

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE profile_items
            SET item_type = ?,
                title = ?,
                organization = ?,
                location = ?,
                start_date = ?,
                end_date = ?,
                is_current = ?,
                description = ?,
                bullets_json = ?,
                skills_json = ?,
                tools_json = ?,
                industry_tags_json = ?,
                function_tags_json = ?,
                keywords_json = ?,
                confidence_score = ?,
                verification_status = ?,
                visibility = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                item.item_type,
                item.title,
                item.organization,
                item.location,
                item.start_date,
                item.end_date,
                1 if item.is_current else 0,
                item.description,
                json.dumps(item.bullets),
                json.dumps(item.skills),
                json.dumps(item.tools),
                json.dumps(item.industry_tags),
                json.dumps(item.function_tags),
                json.dumps(item.keywords),
                item.confidence_score,
                item.verification_status,
                item.visibility,
                utc_now_iso(),
                item.id,
            ),
        )


def archive_profile_item(item_id: int, visibility: str = "archived") -> None:
    """Archive or reactivate a stored profile item."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE profile_items SET visibility = ?, updated_at = ? WHERE id = ?",
            (visibility, utc_now_iso(), item_id),
        )


def upsert_application(
    job_title: str,
    company: str,
    job_description: str,
    role_family: str,
    industry: str,
    job_url: str = "",
    status: str = "draft",
    application_id: int | None = None,
    user_id: str = "local-user",
) -> Application:
    """Create or update a saved application workspace."""
    init_profile_db()
    now = utc_now_iso()
    with get_connection() as conn:
        if application_id is not None:
            conn.execute(
                """
                UPDATE applications
                SET job_title = ?,
                    company = ?,
                    job_description = ?,
                    role_family = ?,
                    industry = ?,
                    job_url = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    job_title.strip(),
                    company.strip(),
                    job_description.strip(),
                    role_family.strip(),
                    industry.strip(),
                    job_url.strip(),
                    status.strip() or "draft",
                    now,
                    application_id,
                    user_id,
                ),
            )
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
            return _application_from_row(row, list_application_profile_item_ids(application_id))

        conn.execute(
            """
            INSERT INTO applications (
                user_id, job_title, company, job_description,
                role_family, industry, job_url, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                job_title.strip(),
                company.strip(),
                job_description.strip(),
                role_family.strip(),
                industry.strip(),
                job_url.strip(),
                status.strip() or "draft",
                now,
                now,
            ),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (new_id,)).fetchone()
        return _application_from_row(row)


def list_application_profile_item_ids(application_id: int) -> list[int]:
    """Return selected profile item ids for one application."""
    init_profile_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT profile_item_id
            FROM application_profile_items
            WHERE application_id = ?
            ORDER BY id
            """,
            (application_id,),
        ).fetchall()
    return [int(row["profile_item_id"]) for row in rows]


def link_profile_items_to_application(
    application_id: int,
    profile_item_ids: list[int],
    selected_by: str = "user",
) -> None:
    """Replace application evidence links with the selected profile-item ids."""
    now = utc_now_iso()
    unique_ids = []
    for profile_item_id in profile_item_ids:
        if profile_item_id not in unique_ids:
            unique_ids.append(profile_item_id)
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM application_profile_items WHERE application_id = ?",
            (application_id,),
        )
        for profile_item_id in unique_ids:
            conn.execute(
                """
                INSERT OR REPLACE INTO application_profile_items (
                    application_id, profile_item_id, selected_by, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (application_id, profile_item_id, selected_by, now),
            )


def get_application(application_id: int) -> Application | None:
    """Load one application workspace."""
    init_profile_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if row is None:
        return None
    return _application_from_row(row, list_application_profile_item_ids(application_id))


def list_applications(user_id: str = "local-user") -> list[Application]:
    """Return saved application workspaces, newest first."""
    init_profile_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    applications: list[Application] = []
    for row in rows:
        application = _application_from_row(row, list_application_profile_item_ids(row["id"]))
        applications.append(application)
    return applications
