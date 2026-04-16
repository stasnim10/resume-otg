"""
Guarded first-resume builder workflow.
"""
from __future__ import annotations

from json_parser import parse_builder_payload
from llm_core.guardrails.input_guards import validate_builder_input
from llm_core.guardrails.output_guards import validate_builder_payload_output
from llm_core.guardrails.repair import build_repair_prompt
from llm_core.logging import TaskTimer, log_task_event
from llm_core.providers import run_text_generation
from llm_core.retrieval.indexers import index_job_description, index_profile_items
from llm_core.retrieval.queries import get_relevant_profile_items, get_role_guidance
from llm_core.schemas import BuilderPayload, GuardedTaskResult
from prompt_engine import build_builder_prompt


def _compose_builder_text(payload: dict) -> str:
    parts = [
        payload.get("full_name", ""),
        payload.get("contact_info", ""),
        payload.get("education", ""),
        payload.get("experience_dump", ""),
        payload.get("activities", ""),
        payload.get("skills", ""),
    ]
    return "\n".join(part for part in parts if part).strip()


def run_builder_workflow(payload: dict) -> GuardedTaskResult:
    """Run the first-resume builder workflow."""
    timer = TaskTimer()
    combined_input = _compose_builder_text(payload)
    validate_builder_input(combined_input)

    full_name = payload.get("full_name", "")
    contact_info = payload.get("contact_info", "")
    education = payload.get("education", "")
    experience_dump = payload.get("experience_dump", "")
    activities = payload.get("activities", "")
    skills = payload.get("skills", "")
    job_description = payload.get("job_description", "")
    career_stage = payload.get("career_stage", "Student")
    target_role = payload.get("target_role", "the target role")
    model_name = payload.get("model_name", "")
    base_url = payload.get("base_url", "")

    if job_description:
        index_job_description(job_description)
    if combined_input:
        index_profile_items(combined_input, source_id="builder_input")
    evidence = get_relevant_profile_items(target_role or combined_input[:120], limit=3) + get_role_guidance(target_role or job_description[:120], limit=2)

    prompt = build_builder_prompt(
        full_name=full_name,
        contact_info=contact_info,
        education=education,
        experience_dump=experience_dump,
        activities=activities,
        skills=skills,
        job_description=job_description,
        career_stage=career_stage,
        target_role=target_role,
    )
    if evidence:
        prompt += "\n\nRETRIEVED SUPPORTING EVIDENCE\n" + "\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in evidence[:5])

    log_task_event("draft_first_resume", "draft_start", evidence_count=len(evidence))
    raw_output = run_text_generation(prompt=prompt, model_name=model_name, base_url=base_url, json_mode=True)
    repair_attempted = False
    validation_errors: list[str] = []
    try:
        parsed = parse_builder_payload(raw_output)
        result = BuilderPayload(payload=parsed, source_evidence_refs=[chunk.chunk_id for chunk in evidence])
        validate_builder_payload_output(result)
    except Exception as error:  # noqa: BLE001
        repair_attempted = True
        validation_errors.append(str(error))
        repair_prompt = build_repair_prompt(prompt, raw_output, validation_errors)
        repaired = run_text_generation(prompt=repair_prompt, model_name=model_name, base_url=base_url, temperature=0.0, json_mode=True)
        parsed = parse_builder_payload(repaired)
        result = BuilderPayload(payload=parsed, source_evidence_refs=[chunk.chunk_id for chunk in evidence])
        validate_builder_payload_output(result)

    log_task_event("draft_first_resume", "completed", repair_attempted=repair_attempted, latency_ms=timer.elapsed_ms())
    return GuardedTaskResult(
        status="success",
        payload=result,
        validation_errors=validation_errors,
        repair_attempted=repair_attempted,
        model_name=model_name,
        latency_ms=timer.elapsed_ms(),
        retrieved_evidence=evidence,
    )
