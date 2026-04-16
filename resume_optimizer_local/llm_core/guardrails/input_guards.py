"""
Input validation for guarded LLM tasks.
"""
from __future__ import annotations

from llm_core.errors import GuardrailFailure
from llm_core.guardrails.policy import BLOCKED_PATTERNS


def _ensure_not_injected(text: str, label: str) -> None:
    lowered = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in lowered:
            raise GuardrailFailure(f"{label} contains instructions that should not be followed by the model.")


def validate_job_description_input(raw_text: str) -> None:
    """Validate JD task input."""
    if not raw_text or len(raw_text.strip()) < 40:
        raise GuardrailFailure("Add a fuller job description before running Local AI.")
    _ensure_not_injected(raw_text, "Job description")


def validate_profile_input(resume_text: str) -> None:
    """Validate profile extraction input."""
    if not resume_text or len(resume_text.strip()) < 40:
        raise GuardrailFailure("Upload a richer resume before extracting a profile.")
    _ensure_not_injected(resume_text, "Resume")


def validate_resume_drafting_input(resume_text: str, job_description: str) -> None:
    """Validate resume drafting input."""
    validate_profile_input(resume_text)
    validate_job_description_input(job_description)


def validate_builder_input(text: str) -> None:
    """Validate builder notes input."""
    if not text or len(text.strip()) < 20:
        raise GuardrailFailure("Add more background before creating a first resume.")
    _ensure_not_injected(text, "Builder input")
