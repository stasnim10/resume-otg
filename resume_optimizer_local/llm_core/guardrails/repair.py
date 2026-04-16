"""
Simple repair helpers for one-shot validation repair loops.
"""
from __future__ import annotations


def build_repair_prompt(original_prompt: str, raw_output: str, errors: list[str]) -> str:
    """Return a repair prompt that focuses the model on validation failures."""
    error_block = "\n".join(f"- {error}" for error in errors)
    return (
        "Repair the invalid output below. Return only valid JSON.\n\n"
        f"VALIDATION ERRORS\n{error_block}\n\n"
        f"ORIGINAL TASK\n{original_prompt}\n\n"
        f"INVALID OUTPUT\n{raw_output}"
    )
