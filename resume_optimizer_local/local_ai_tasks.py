"""
Task-oriented Local AI helpers for job processing, profile extraction, and draft generation.
"""
from __future__ import annotations

from typing import Any

from llm_core import run_guarded_task
from ollama_local_ai import DEFAULT_LOCAL_AI_MODEL, OLLAMA_BASE_URL


_LAST_TASK_META: dict[str, dict[str, Any]] = {}


def _record_task_meta(task_name: str, result) -> None:
    """Capture lightweight metadata for UI feedback."""
    evidence_previews = []
    for chunk in result.retrieved_evidence[:4]:
        evidence_previews.append(
            {
                "chunk_id": chunk.chunk_id,
                "source_type": chunk.source_type,
                "section": chunk.section,
                "text": chunk.text,
            }
        )
    _LAST_TASK_META[task_name] = {
        "repair_attempted": result.repair_attempted,
        "validation_errors": list(result.validation_errors),
        "retrieved_evidence_count": len(result.retrieved_evidence),
        "retrieved_evidence_previews": evidence_previews,
        "latency_ms": result.latency_ms,
        "model_name": result.model_name,
        "status": result.status,
    }


def get_last_task_meta(task_name: str) -> dict[str, Any]:
    """Return the last recorded metadata for a task."""
    return dict(_LAST_TASK_META.get(task_name, {}))


def process_job_description(
    raw_job_description: str,
    cleaned_job_description: str,
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> dict[str, Any]:
    """Return structured job signals to guide downstream drafting."""
    result = run_guarded_task(
        "process_job_description",
        {
            "raw_text": raw_job_description,
            "cleaned_text": cleaned_job_description,
            "model_name": model_name,
            "base_url": base_url,
        },
    )
    _record_task_meta("process_job_description", result)
    return result.payload.to_dict()


def extract_or_create_profile(
    resume_text: str,
    existing_profile_summary: str = "",
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> dict[str, Any]:
    """Return deterministic extraction plus Local AI suggestions for profile review."""
    result = run_guarded_task(
        "extract_or_create_profile",
        {
            "resume_text": resume_text,
            "existing_profile_summary": existing_profile_summary,
            "model_name": model_name,
            "base_url": base_url,
        },
    )
    _record_task_meta("extract_or_create_profile", result)
    return result.payload.to_dict()


def draft_resume_improvements(
    resume_text: str,
    job_description: str,
    career_stage: str,
    target_role: str,
    target_industry: str,
    profile_context: str = "",
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> dict[str, Any]:
    """Run the resume drafting task and return a validated replacement payload."""
    result = run_guarded_task(
        "draft_resume_improvements",
        {
            "resume_text": resume_text,
            "job_description": job_description,
            "career_stage": career_stage,
            "target_role": target_role,
            "target_industry": target_industry,
            "profile_context": profile_context,
            "model_name": model_name,
            "base_url": base_url,
        },
    )
    _record_task_meta("draft_resume_improvements", result)
    return result.payload.to_dict()


def draft_first_resume(
    full_name: str,
    contact_info: str,
    education: str,
    experience_dump: str,
    activities: str,
    skills: str,
    job_description: str,
    career_stage: str,
    target_role: str,
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> dict[str, Any]:
    """Run the first-resume builder task and return a validated builder payload."""
    result = run_guarded_task(
        "draft_first_resume",
        {
            "full_name": full_name,
            "contact_info": contact_info,
            "education": education,
            "experience_dump": experience_dump,
            "activities": activities,
            "skills": skills,
            "job_description": job_description,
            "career_stage": career_stage,
            "target_role": target_role,
            "model_name": model_name,
            "base_url": base_url,
        },
    )
    _record_task_meta("draft_first_resume", result)
    return result.payload.to_dict()


def summarize_job_signals_for_ui(job_signals: dict[str, Any]) -> str:
    """Return a short human-friendly summary for the setup/run screen."""
    if not job_signals:
        return ""

    parts = []
    if job_signals.get("normalized_role_title"):
        parts.append(job_signals["normalized_role_title"])
    if job_signals.get("seniority") and job_signals["seniority"] != "Unknown":
        parts.append(job_signals["seniority"])
    if job_signals.get("industry_hint"):
        parts.append(job_signals["industry_hint"])
    return " · ".join(parts)
