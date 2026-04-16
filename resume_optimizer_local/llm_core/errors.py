"""
Typed error classes for the LLM core.
"""


class LLMCoreError(Exception):
    """Base class for llm_core failures."""


class TaskValidationError(LLMCoreError):
    """Raised when a task input or output fails validation."""


class GuardrailFailure(LLMCoreError):
    """Raised when guardrails reject a task."""


class RetrievalFailure(LLMCoreError):
    """Raised when retrieval does not produce required evidence."""


class ModelExecutionFailure(LLMCoreError):
    """Raised when the model fails to produce a usable answer."""
