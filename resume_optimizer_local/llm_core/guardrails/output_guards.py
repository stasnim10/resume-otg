"""
Output validation for guarded LLM tasks.
"""
from __future__ import annotations

from llm_core.errors import GuardrailFailure
from llm_core.guardrails.policy import ALLOWED_SENIORITY
from json_parser import collect_replacements, validate_builder_payload, validate_payload
from llm_core.schemas import BuilderPayload, JobBrief, ProfileSuggestionResult, ReplacementPayload


def validate_job_brief_output(job_brief: JobBrief) -> None:
    """Validate structured JD output."""
    if not job_brief.normalized_role_title.strip():
        raise GuardrailFailure("Job brief is missing a normalized role title.")
    if job_brief.seniority not in ALLOWED_SENIORITY:
        raise GuardrailFailure("Job brief seniority is invalid.")
    if len(job_brief.required_skills) > 12:
        raise GuardrailFailure("Job brief returned too many skills.")


def validate_profile_output(profile_result: ProfileSuggestionResult) -> None:
    """Validate profile extraction output."""
    for item in profile_result.suggested_items:
        if item.confidence_score < 0 or item.confidence_score > 1:
            raise GuardrailFailure("Profile suggestion confidence must be between 0 and 1.")
        if not item.source_evidence_refs:
            raise GuardrailFailure("Profile suggestions must include source evidence references.")


def validate_replacement_payload_output(payload: ReplacementPayload) -> None:
    """Validate replacement payload wrapper."""
    raw_payload = payload.payload
    is_valid, error = validate_payload(raw_payload)
    if not is_valid:
        raise GuardrailFailure(error or "Replacement payload is invalid.")


def validate_builder_payload_output(payload) -> None:
    """Placeholder builder payload output validation."""
    if not isinstance(payload, BuilderPayload):
        raise GuardrailFailure("Builder payload is empty.")
    is_valid, error = validate_builder_payload(payload.payload)
    if not is_valid:
        raise GuardrailFailure(error or "Builder payload is invalid.")


def validate_replacement_anchorability(payload: ReplacementPayload, resume_text: str) -> None:
    """Ensure every replacement anchor appears exactly once in the current resume text."""
    paragraphs = [paragraph.strip() for paragraph in resume_text.splitlines() if paragraph.strip()]
    for replacement in collect_replacements(payload.payload):
        anchor = replacement.get("match_anchor", "").strip()
        match_count = sum(1 for paragraph in paragraphs if paragraph == anchor)
        if match_count != 1:
            raise GuardrailFailure(
                f"Replacement anchor must match exactly one resume paragraph. Found {match_count} matches for: {anchor[:80]}"
            )
