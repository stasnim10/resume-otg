"""
Task registry definitions.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDefinition:
    """Metadata for a guarded LLM task."""

    name: str
    workflow: str
    input_guard: str
    output_guard: str
    retrieval_query: str


TASK_REGISTRY: dict[str, TaskDefinition] = {
    "process_job_description": TaskDefinition(
        name="process_job_description",
        workflow="jd_processing_graph",
        input_guard="validate_job_description_input",
        output_guard="validate_job_brief_output",
        retrieval_query="get_role_guidance",
    ),
    "extract_or_create_profile": TaskDefinition(
        name="extract_or_create_profile",
        workflow="profile_graph",
        input_guard="validate_profile_input",
        output_guard="validate_profile_output",
        retrieval_query="get_relevant_profile_items",
    ),
    "draft_resume_improvements": TaskDefinition(
        name="draft_resume_improvements",
        workflow="resume_optimization_graph",
        input_guard="validate_resume_drafting_input",
        output_guard="validate_replacement_payload_output",
        retrieval_query="get_relevant_resume_chunks",
    ),
    "draft_first_resume": TaskDefinition(
        name="draft_first_resume",
        workflow="builder_graph",
        input_guard="validate_builder_input",
        output_guard="validate_builder_payload_output",
        retrieval_query="get_role_guidance",
    ),
}
