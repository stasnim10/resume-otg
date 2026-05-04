"""
Supabase-backed implementation of the profile store interface.

All public functions match the signatures in profile_store.py so the
routing shim can swap between SQLite and Supabase transparently.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import streamlit as st

from profile_schema import Application, CareerProfile, ProfileItem, ProfileSource, utc_now_iso
from supabase_client import get_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid(user_id: str | None = None) -> str:
    """Resolve the effective user ID — prefer the explicit arg, fall back to session."""
    if user_id and user_id not in ("local-user", ""):
        return user_id
    uid = st.session_state.get("auth_user_id", "")
    if not uid:
        raise RuntimeError("User not authenticated — cannot access Supabase profile store.")
    return uid


def _sb():
    return get_supabase()


def _jl(value) -> list:
    """Safe JSON or passthrough list decode."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return []


def _encode_execution_mode(mode: str) -> str:
    """Store execution mode inside an existing text column without schema changes."""
    normalized = str(mode or "").strip().lower()
    if normalized not in {"api", "local_ai", "manual"}:
        return ""
    return f"meta://execution-mode/{normalized}"


def _decode_execution_mode(value: str) -> str:
    """Recover execution mode from the encoded sentinel value."""
    text = str(value or "").strip()
    prefix = "meta://execution-mode/"
    if not text.startswith(prefix):
        return ""
    return text[len(prefix):]


def _profile_from_row(row: dict) -> CareerProfile:
    return CareerProfile(
        id=row.get("id"),
        user_id=row.get("user_id", ""),
        full_name=row.get("full_name", ""),
        email=row.get("email", ""),
        phone=row.get("phone", ""),
        location=row.get("location", ""),
        linkedin=row.get("linkedin", ""),
        portfolio_url=row.get("portfolio_url", ""),
        photo_path=row.get("photo_path", ""),
        headline=row.get("headline", ""),
        career_stage=row.get("career_stage", "Student"),
        summary=row.get("summary", ""),
        target_roles=_jl(row.get("target_roles", "[]")),
        target_industries=_jl(row.get("target_industries", "[]")),
        preferred_locations=_jl(row.get("preferred_locations", "[]")),
        work_authorization=row.get("work_authorization", ""),
        onboarding_complete=bool(row.get("onboarding_complete", False)),
        onboarding_started_at=row.get("onboarding_started_at") or "",
        created_at=row.get("created_at", utc_now_iso()),
        updated_at=row.get("updated_at", utc_now_iso()),
    )


def _item_from_row(row: dict) -> ProfileItem:
    return ProfileItem(
        id=row.get("id"),
        user_id=row.get("user_id", ""),
        profile_id=None,
        source_id=row.get("source_id"),
        item_type=row.get("item_type", "experience"),
        title=row.get("title", ""),
        organization=row.get("organization", ""),
        location=row.get("location", ""),
        start_date=row.get("start_date", ""),
        end_date=row.get("end_date", ""),
        is_current=bool(row.get("is_current", False)),
        description=row.get("description", ""),
        bullets=_jl(row.get("bullets", "[]")),
        skills=_jl(row.get("skills", "[]")),
        tools=_jl(row.get("tools", "[]")),
        industry_tags=_jl(row.get("industry_tags", "[]")),
        function_tags=_jl(row.get("function_tags", "[]")),
        keywords=_jl(row.get("keywords", "[]")),
        confidence_score=float(row.get("confidence_score", 0.5)),
        verification_status=row.get("verification_status", "suggested"),
        visibility=row.get("visibility", "active"),
        created_at=row.get("created_at", utc_now_iso()),
        updated_at=row.get("updated_at", utc_now_iso()),
    )


def _source_from_row(row: dict) -> ProfileSource:
    return ProfileSource(
        id=row.get("id"),
        user_id=row.get("user_id", ""),
        source_type=row.get("source_type", "manual_notes"),
        source_name=row.get("source_name", ""),
        file_path=row.get("storage_path", ""),
        raw_text=row.get("raw_text", ""),
        parsed_status=row.get("parsed_status", "pending"),
        parsed_payload_json=json.dumps(row.get("parsed_payload_json") or {}),
        created_at=row.get("created_at", utc_now_iso()),
    )


def _app_from_row(row: dict) -> Application:
    return Application(
        id=row.get("id"),
        user_id=row.get("user_id", ""),
        job_title=row.get("job_title", ""),
        company=row.get("company", ""),
        job_description=row.get("job_description", ""),
        role_family=row.get("role_family", ""),
        industry=row.get("industry", ""),
        job_url=row.get("job_url", ""),
        status=row.get("status", "draft"),
        selected_profile_item_ids=_jl(row.get("profile_item_ids", "[]")),
        created_at=row.get("created_at", utc_now_iso()),
        updated_at=row.get("updated_at", utc_now_iso()),
    )


# ---------------------------------------------------------------------------
# No-op init (tables already exist in Supabase)
# ---------------------------------------------------------------------------


def init_profile_db() -> None:
    pass


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


def create_or_get_profile(user_id: str = "local-user") -> CareerProfile:
    """Return the user's profile, creating it if it doesn't exist yet."""
    uid = _uid(user_id)
    try:
        resp = _sb().table("profiles").select("*").eq("id", uid).maybe_single().execute()
        if resp.data:
            return _profile_from_row(resp.data)
    except Exception as exc:
        logger.warning("create_or_get_profile select failed: %s", exc)

    # Create a new profile row keyed to the auth user ID.
    now = utc_now_iso()
    row = {
        "id": uid,
        "full_name": "",
        "email": st.session_state.get("auth_user_email", ""),
        "phone": "",
        "location": "",
        "linkedin": "",
        "portfolio_url": "",
        "photo_path": "",
        "headline": "",
        "career_stage": "Student",
        "summary": "",
        "target_roles": [],
        "target_industries": [],
        "preferred_locations": [],
        "work_authorization": "",
        "onboarding_complete": False,
        "onboarding_started_at": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        resp = _sb().table("profiles").insert(row).execute()
        if resp.data:
            return _profile_from_row(resp.data[0])
    except Exception as exc:
        logger.warning("create_or_get_profile insert failed: %s", exc)

    return CareerProfile(id=uid, user_id=uid, email=st.session_state.get("auth_user_email", ""))


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
    portfolio_url: str = "",
    photo_path: str = "",
    user_id: str = "local-user",
) -> CareerProfile:
    """Persist editable top-level profile fields."""
    uid = _uid(user_id)
    now = utc_now_iso()
    patch = {
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "location": location.strip(),
        "linkedin": linkedin.strip(),
        "portfolio_url": portfolio_url.strip(),
        "photo_path": photo_path.strip(),
        "headline": headline.strip(),
        "career_stage": career_stage.strip() or "Student",
        "summary": summary.strip(),
        "target_roles": [r.strip() for r in target_roles if r.strip()],
        "target_industries": [i.strip() for i in target_industries if i.strip()],
        "preferred_locations": [l.strip() for l in preferred_locations if l.strip()],
        "work_authorization": work_authorization.strip(),
        "updated_at": now,
    }
    try:
        _sb().table("profiles").update(patch).eq("id", uid).execute()
    except Exception as exc:
        logger.warning("save_profile_basics failed: %s", exc)
    return create_or_get_profile(uid)


def start_onboarding(user_id: str = "local-user") -> None:
    uid = _uid(user_id)
    try:
        _sb().table("profiles").update(
            {"onboarding_started_at": utc_now_iso()}
        ).eq("id", uid).is_("onboarding_started_at", "null").execute()
    except Exception as exc:
        logger.warning("start_onboarding failed: %s", exc)


def complete_onboarding(user_id: str = "local-user") -> None:
    uid = _uid(user_id)
    try:
        _sb().table("profiles").update(
            {"onboarding_complete": True, "updated_at": utc_now_iso()}
        ).eq("id", uid).execute()
    except Exception as exc:
        logger.warning("complete_onboarding failed: %s", exc)


# ---------------------------------------------------------------------------
# Profile sources
# ---------------------------------------------------------------------------


def save_profile_source(
    source_type: str,
    source_name: str,
    raw_text: str,
    file_path: str = "",
    parsed_status: str = "parsed",
    parsed_payload: dict[str, Any] | None = None,
    user_id: str = "local-user",
) -> str:
    """Persist an imported source and return its UUID."""
    uid = _uid(user_id)
    row = {
        "user_id": uid,
        "source_type": source_type,
        "source_name": source_name,
        "storage_path": file_path,
        "raw_text": raw_text,
        "parsed_status": parsed_status,
        "parsed_payload_json": parsed_payload or {},
        "created_at": utc_now_iso(),
    }
    try:
        resp = _sb().table("profile_sources").insert(row).execute()
        if resp.data:
            return resp.data[0]["id"]
    except Exception as exc:
        logger.warning("save_profile_source failed: %s", exc)
    return ""


def list_profile_sources(user_id: str = "local-user") -> list[ProfileSource]:
    uid = _uid(user_id)
    try:
        resp = (
            _sb()
            .table("profile_sources")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        return [_source_from_row(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.warning("list_profile_sources failed: %s", exc)
        return []


def delete_profile_source(source_id: Any, user_id: str = "local-user") -> None:
    uid = _uid(user_id)
    try:
        _sb().table("profile_sources").delete().eq("id", str(source_id)).eq("user_id", uid).execute()
    except Exception as exc:
        logger.warning("delete_profile_source failed: %s", exc)


# ---------------------------------------------------------------------------
# Profile items
# ---------------------------------------------------------------------------


def save_profile_items(
    items: list[ProfileItem],
    user_id: str = "local-user",
    replace_existing_for_source: Any = None,
) -> list[ProfileItem]:
    """Persist extracted profile items."""
    uid = _uid(user_id)
    if replace_existing_for_source is not None:
        try:
            _sb().table("profile_items").delete().eq("user_id", uid).eq(
                "source_id", str(replace_existing_for_source)
            ).execute()
        except Exception as exc:
            logger.warning("save_profile_items delete failed: %s", exc)

    saved: list[ProfileItem] = []
    for item in items:
        now = utc_now_iso()
        row = {
            "user_id": uid,
            "source_id": str(item.source_id) if item.source_id else None,
            "item_type": item.item_type,
            "title": item.title,
            "organization": item.organization,
            "location": item.location,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "is_current": item.is_current,
            "description": item.description,
            "bullets": item.bullets,
            "skills": item.skills,
            "tools": item.tools,
            "industry_tags": item.industry_tags,
            "function_tags": item.function_tags,
            "keywords": item.keywords,
            "confidence_score": item.confidence_score,
            "verification_status": item.verification_status,
            "visibility": item.visibility,
            "created_at": item.created_at or now,
            "updated_at": now,
        }
        try:
            resp = _sb().table("profile_items").insert(row).execute()
            if resp.data:
                item.id = resp.data[0]["id"]
                item.user_id = uid
        except Exception as exc:
            logger.warning("save_profile_items insert failed: %s", exc)
        saved.append(item)
    return saved


def list_profile_items(user_id: str = "local-user") -> list[ProfileItem]:
    uid = _uid(user_id)
    try:
        resp = (
            _sb()
            .table("profile_items")
            .select("*")
            .eq("user_id", uid)
            .eq("visibility", "active")
            .order("created_at", desc=True)
            .execute()
        )
        return [_item_from_row(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.warning("list_profile_items failed: %s", exc)
        return []


def update_profile_item(item: ProfileItem) -> None:
    if not item.id:
        return
    patch = {
        "item_type": item.item_type,
        "title": item.title,
        "organization": item.organization,
        "location": item.location,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "is_current": item.is_current,
        "description": item.description,
        "bullets": item.bullets,
        "skills": item.skills,
        "tools": item.tools,
        "industry_tags": item.industry_tags,
        "function_tags": item.function_tags,
        "keywords": item.keywords,
        "confidence_score": item.confidence_score,
        "verification_status": item.verification_status,
        "updated_at": utc_now_iso(),
    }
    try:
        _sb().table("profile_items").update(patch).eq("id", str(item.id)).execute()
    except Exception as exc:
        logger.warning("update_profile_item failed: %s", exc)


def update_profile_item_verification(item_id: Any, verification_status: str) -> None:
    try:
        _sb().table("profile_items").update(
            {"verification_status": verification_status, "updated_at": utc_now_iso()}
        ).eq("id", str(item_id)).execute()
    except Exception as exc:
        logger.warning("update_profile_item_verification failed: %s", exc)


def archive_profile_item(item_id: Any, visibility: str = "archived") -> None:
    try:
        _sb().table("profile_items").update(
            {"visibility": visibility, "updated_at": utc_now_iso()}
        ).eq("id", str(item_id)).execute()
    except Exception as exc:
        logger.warning("archive_profile_item failed: %s", exc)


# ---------------------------------------------------------------------------
# Applications / tracked jobs
# ---------------------------------------------------------------------------


def upsert_application(
    user_id: str,
    job_title: str = "",
    company: str = "",
    job_description: str = "",
    role_family: str = "",
    industry: str = "",
    job_url: str = "",
    status: str = "draft",
    application_id: Any = None,
    match_before: int = 0,
    match_after: int = 0,
    **kwargs: Any,
) -> str:
    """Create or update a tracked job row. Returns the job UUID."""
    uid = _uid(user_id)
    now = utc_now_iso()

    if application_id:
        patch = {
            "job_title": job_title or "",
            "company": company or "",
            "job_description": job_description or "",
            "role_family": role_family or "",
            "industry": industry or "",
            "job_url": job_url or "",
            "status": status,
            "updated_at": now,
        }
        try:
            _sb().table("tracked_jobs").update(patch).eq("id", str(application_id)).execute()
        except Exception as exc:
            logger.warning("upsert_application update failed: %s", exc)
        return str(application_id)

    row = {
        "user_id": uid,
        "job_title": job_title or "",
        "company": company or "",
        "job_description": job_description or "",
        "role_family": role_family or "",
        "industry": industry or "",
        "job_url": job_url or "",
        "status": status,
        "next_action": "",
        "applied_date": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        resp = _sb().table("tracked_jobs").insert(row).execute()
        if resp.data:
            return resp.data[0]["id"]
    except Exception as exc:
        logger.warning("upsert_application insert failed: %s", exc)
    return ""


def get_application(application_id: Any) -> Application | None:
    if not application_id:
        return None
    try:
        resp = (
            _sb()
            .table("tracked_jobs")
            .select("*")
            .eq("id", str(application_id))
            .maybe_single()
            .execute()
        )
        if resp.data:
            return _app_from_row(resp.data)
    except Exception as exc:
        logger.warning("get_application failed: %s", exc)
    return None


def list_applications(user_id: str = "local-user") -> list[Application]:
    uid = _uid(user_id)
    try:
        resp = (
            _sb()
            .table("tracked_jobs")
            .select("*")
            .eq("user_id", uid)
            .order("updated_at", desc=True)
            .execute()
        )
        return [_app_from_row(r) for r in (resp.data or [])]
    except Exception as exc:
        logger.warning("list_applications failed: %s", exc)
        return []


def link_profile_items_to_application(
    application_id: Any,
    profile_item_ids: list[Any],
    user_id: str = "local-user",
) -> None:
    """Store selected profile item IDs on the tracked_jobs row."""
    if not application_id:
        return
    try:
        _sb().table("tracked_jobs").update(
            {"profile_item_ids": [str(i) for i in profile_item_ids]}
        ).eq("id", str(application_id)).execute()
    except Exception as exc:
        logger.warning("link_profile_items_to_application failed: %s", exc)


def list_application_profile_item_ids(application_id: Any) -> list[str]:
    if not application_id:
        return []
    try:
        resp = (
            _sb()
            .table("tracked_jobs")
            .select("profile_item_ids")
            .eq("id", str(application_id))
            .maybe_single()
            .execute()
        )
        if resp.data:
            return _jl(resp.data.get("profile_item_ids", []))
    except Exception as exc:
        logger.warning("list_application_profile_item_ids failed: %s", exc)
    return []


# ---------------------------------------------------------------------------
# Optimization results
# ---------------------------------------------------------------------------


def save_optimization_result(
    user_id: str,
    company_name: str,
    job_title: str,
    job_description: str,
    match_before: int,
    match_after: int,
    improvements: list[dict],
    resume_used_id: str = "",
    application_id: Any = None,
    **kwargs: Any,
) -> str:
    """Record a completed optimization run. Returns the run UUID."""
    uid = _uid(user_id)
    now = utc_now_iso()

    # Ensure the tracked_job row exists.
    job_id = application_id
    if not job_id:
        job_id = upsert_application(
            user_id=uid,
            job_title=job_title,
            company=company_name,
            job_description=job_description,
            status="draft",
        )

    delta = (match_after or 0) - (match_before or 0)
    execution_mode = str(kwargs.get("execution_mode", "") or "").strip()
    row = {
        "job_id": str(job_id),
        "user_id": uid,
        "match_before": match_before or 0,
        "match_after": match_after or 0,
        "delta": delta,
        "improvements": improvements or [],
        "resume_storage_path": resume_used_id or "",
        "cover_letter_storage_path": _encode_execution_mode(execution_mode),
        "profile_item_ids": [],
        "run_at": now,
    }
    try:
        resp = _sb().table("job_optimization_runs").insert(row).execute()
        if resp.data:
            return resp.data[0]["job_id"]
    except Exception as exc:
        logger.warning("save_optimization_result failed: %s", exc)
    return str(job_id) if job_id else ""


def get_optimization_history(user_id: str = "local-user") -> list[dict]:
    """Return recent optimization runs for the dashboard."""
    uid = _uid(user_id)
    try:
        resp = (
            _sb()
            .table("job_optimization_runs")
            .select("*, tracked_jobs(job_title, company)")
            .eq("user_id", uid)
            .order("run_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = resp.data or []
        result = []
        for r in rows:
            job_info = r.get("tracked_jobs") or {}
            result.append({
                "id": r.get("id"),
                "company_name": job_info.get("company", ""),
                "job_title": job_info.get("job_title", ""),
                "match_before": r.get("match_before", 0),
                "match_after": r.get("match_after", 0),
                "delta": r.get("delta", 0),
                "improvements": _jl(r.get("improvements", [])),
                "run_at": r.get("run_at", ""),
                "resume_path": r.get("resume_storage_path", ""),
                "execution_mode": _decode_execution_mode(r.get("cover_letter_storage_path", "")),
            })
        return result
    except Exception as exc:
        logger.warning("get_optimization_history failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Profile extraction helpers (delegated to profile_extractor)
# ---------------------------------------------------------------------------


def extract_profile_basics_from_resume(resume_text: str) -> dict[str, Any]:
    from profile_extractor import extract_profile_basics
    return extract_profile_basics(resume_text)


def create_or_update_profile_from_optimization(
    user_id: str,
    resume_text: str,
    user_id_default: str = "local-user",
) -> str | None:
    uid = _uid(user_id or user_id_default)
    basics = extract_profile_basics_from_resume(resume_text)
    try:
        profile = create_or_get_profile(uid)
        save_profile_basics(
            full_name=basics.get("name", profile.full_name),
            email=basics.get("email", profile.email),
            phone=basics.get("phone", profile.phone),
            location=basics.get("location", profile.location),
            linkedin=profile.linkedin,
            portfolio_url=profile.portfolio_url,
            photo_path=profile.photo_path,
            headline=profile.headline,
            career_stage=basics.get("career_stage", profile.career_stage),
            summary=profile.summary,
            target_roles=profile.target_roles,
            target_industries=basics.get("industries", profile.target_industries),
            preferred_locations=profile.preferred_locations,
            work_authorization=profile.work_authorization,
            user_id=uid,
        )
        return uid
    except Exception as exc:
        logger.warning("create_or_update_profile_from_optimization failed: %s", exc)
        return None
