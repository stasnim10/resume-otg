"""
Structured task logging helpers.
"""
from __future__ import annotations

import logging
from time import perf_counter


logger = logging.getLogger("resume_optimizer.llm_core")


class TaskTimer:
    """Small timer used to capture workflow latency."""

    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed_ms(self) -> int:
        return int((perf_counter() - self._start) * 1000)


def log_task_event(task_name: str, stage: str, **extra) -> None:
    """Log a structured event for a task."""
    logger.info("task=%s stage=%s extra=%s", task_name, stage, extra)
