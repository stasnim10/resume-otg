"""
Guarded resume optimization workflow.
"""
from __future__ import annotations

from json_parser import parse_replacement_payload
from llm_core.guardrails.input_guards import validate_resume_drafting_input
from llm_core.guardrails.output_guards import validate_replacement_anchorability, validate_replacement_payload_output
from llm_core.guardrails.repair import build_repair_prompt
from llm_core.logging import TaskTimer, log_task_event
from llm_core.providers import run_text_generation
from llm_core.retrieval.indexers import index_job_description, index_profile_items, index_resume_text, index_validated_optimization
from llm_core.retrieval.queries import (
    get_relevant_profile_items,
    get_relevant_resume_chunks,
    get_role_guidance,
    get_similar_validated_optimizations,
)
from llm_core.schemas import GuardedTaskResult, ReplacementPayload
from prompt_engine import build_optimizer_prompt


def _build_prompt(resume_text: str, job_description: str, career_stage: str, target_role: str, target_industry: str, profile_context: str, evidence_chunks) -> str:
    evidence_block = "\n\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in evidence_chunks[:8])
    base_prompt = build_optimizer_prompt(
        resume_text=resume_text,
        job_description=job_description,
        career_stage=career_stage,
        target_role=target_role,
        target_industry=target_industry,
        profile_context=profile_context,
    )
    return (
        base_prompt
        + "\n\nRETRIEVED SUPPORTING EVIDENCE\n"
        + (evidence_block or "No additional evidence retrieved.")
        + "\n\nIMPORTANT\nUse retrieved evidence only when it supports the uploaded resume text. Do not invent facts."
    )


def run_resume_optimization_workflow(payload: dict) -> GuardedTaskResult:
    """Run the resume optimization workflow."""
    timer = TaskTimer()
    resume_text = payload.get("resume_text", "")
    job_description = payload.get("job_description", "")
    career_stage = payload.get("career_stage", "Early Career")
    target_role = payload.get("target_role", "")
    target_industry = payload.get("target_industry", "")
    profile_context = payload.get("profile_context", "")
    model_name = payload.get("model_name", "")
    base_url = payload.get("base_url", "")

    validate_resume_drafting_input(resume_text, job_description)
    index_resume_text(resume_text)
    index_job_description(job_description)
    if profile_context:
        index_profile_items(profile_context)

    evidence = []
    evidence.extend(get_relevant_resume_chunks(job_description[:240], limit=4))
    evidence.extend(get_relevant_profile_items(target_role or profile_context[:120], limit=2))
    evidence.extend(get_role_guidance(target_role or job_description[:120], limit=2))
    evidence.extend(get_similar_validated_optimizations(target_role or target_industry or "resume optimization", limit=2))

    prompt = _build_prompt(resume_text, job_description, career_stage, target_role, target_industry, profile_context, evidence)
    log_task_event("draft_resume_improvements", "draft_start", evidence_count=len(evidence))

    raw_output = run_text_generation(prompt=prompt, model_name=model_name, base_url=base_url, json_mode=True)
    repair_attempted = False
    validation_errors: list[str] = []
    try:
        parsed = parse_replacement_payload(raw_output)
        result = ReplacementPayload(payload=parsed, source_evidence_refs=[chunk.chunk_id for chunk in evidence])
        validate_replacement_payload_output(result)
        validate_replacement_anchorability(result, resume_text)
    except Exception as error:  # noqa: BLE001
        repair_attempted = True
        validation_errors.append(str(error))
        repair_prompt = build_repair_prompt(prompt, raw_output, validation_errors)
        repaired = run_text_generation(prompt=repair_prompt, model_name=model_name, base_url=base_url, temperature=0.0, json_mode=True)
        parsed = parse_replacement_payload(repaired)
        result = ReplacementPayload(payload=parsed, source_evidence_refs=[chunk.chunk_id for chunk in evidence])
        validate_replacement_payload_output(result)
        validate_replacement_anchorability(result, resume_text)

    index_validated_optimization(str(result.payload))
    log_task_event("draft_resume_improvements", "completed", repair_attempted=repair_attempted, latency_ms=timer.elapsed_ms())
    return GuardedTaskResult(
        status="success",
        payload=result,
        validation_errors=validation_errors,
        repair_attempted=repair_attempted,
        model_name=model_name,
        latency_ms=timer.elapsed_ms(),
        retrieved_evidence=evidence,
    )
