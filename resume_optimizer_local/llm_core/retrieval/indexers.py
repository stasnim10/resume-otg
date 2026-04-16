"""
Index-building helpers.
"""
from __future__ import annotations

from llm_core.retrieval.chunking import chunk_text
from llm_core.retrieval.store import put_chunks


def index_resume_text(resume_text: str, source_id: str = "current_resume") -> None:
    """Index current resume text."""
    put_chunks("resume_chunks", chunk_text("resume", source_id, resume_text, "resume"))


def index_job_description(job_text: str, source_id: str = "current_job") -> None:
    """Index current job description text."""
    put_chunks("job_briefs", chunk_text("job_description", source_id, job_text, "job_description"))


def index_profile_items(text: str, source_id: str = "current_profile") -> None:
    """Index profile-related text."""
    put_chunks("profile_items", chunk_text("profile", source_id, text, "profile"))


def index_validated_optimization(text: str, source_id: str = "current_optimization") -> None:
    """Index validated optimization text snippets."""
    put_chunks("validated_optimizations", chunk_text("optimization", source_id, text, "optimization"))
