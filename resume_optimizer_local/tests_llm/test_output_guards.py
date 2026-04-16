from llm_core.errors import GuardrailFailure
from llm_core.guardrails.output_guards import (
    validate_job_brief_output,
    validate_profile_output,
    validate_replacement_anchorability,
)
from llm_core.schemas import JobBrief, ProfileSuggestionItem, ProfileSuggestionResult, ReplacementPayload


def test_validate_job_brief_output_accepts_valid_brief():
    brief = JobBrief(
        normalized_role_title="Data Analyst",
        seniority="Early Career",
        industry_hint="Technology",
        required_skills=["SQL", "Dashboards"],
    )
    validate_job_brief_output(brief)


def test_validate_profile_output_requires_evidence_refs():
    result = ProfileSuggestionResult(
        basics={"full_name": "Jane Doe"},
        suggested_items=[
            ProfileSuggestionItem(
                item_type="experience",
                title="Analyst",
                source_evidence_refs=[],
            )
        ],
    )
    try:
        validate_profile_output(result)
        raise AssertionError("Expected GuardrailFailure")
    except GuardrailFailure:
        pass


def test_validate_replacement_anchorability_requires_exact_match():
    payload = ReplacementPayload(
        payload={
            "summary_replacement": {
                "match_anchor": "Original summary paragraph",
                "replacement_text": "Updated summary paragraph",
            }
        }
    )
    validate_replacement_anchorability(payload, "Original summary paragraph\nAnother paragraph")


def test_validate_replacement_anchorability_rejects_missing_anchor():
    payload = ReplacementPayload(
        payload={
            "summary_replacement": {
                "match_anchor": "Missing summary paragraph",
                "replacement_text": "Updated summary paragraph",
            }
        }
    )
    try:
        validate_replacement_anchorability(payload, "Original summary paragraph\nAnother paragraph")
        raise AssertionError("Expected GuardrailFailure")
    except GuardrailFailure:
        pass
