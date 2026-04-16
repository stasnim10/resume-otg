"""
Task runner entrypoint.
"""
from __future__ import annotations

from llm_core.errors import TaskValidationError
from llm_core.tasks import TASK_REGISTRY
from llm_core.workflows.builder_graph import run_builder_workflow
from llm_core.workflows.jd_processing_graph import run_jd_processing_workflow
from llm_core.workflows.profile_graph import run_profile_workflow
from llm_core.workflows.resume_optimization_graph import run_resume_optimization_workflow


WORKFLOW_RUNNERS = {
    "jd_processing_graph": run_jd_processing_workflow,
    "profile_graph": run_profile_workflow,
    "resume_optimization_graph": run_resume_optimization_workflow,
    "builder_graph": run_builder_workflow,
}


def run_guarded_task(task_name: str, payload: dict):
    """Run a task through the configured workflow."""
    definition = TASK_REGISTRY.get(task_name)
    if definition is None:
        raise TaskValidationError(f"Unknown task: {task_name}")

    runner = WORKFLOW_RUNNERS.get(definition.workflow)
    if runner is None:
        raise TaskValidationError(f"No workflow runner configured for task: {task_name}")
    return runner(payload)
