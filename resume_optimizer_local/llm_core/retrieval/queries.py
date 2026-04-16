"""
Query helpers for task-bounded retrieval.
"""
from __future__ import annotations

from llm_core.retrieval.store import search_chunks
from llm_core.schemas import EvidenceChunk


def get_relevant_resume_chunks(query: str, limit: int = 5) -> list[EvidenceChunk]:
    return search_chunks("resume_chunks", query, limit=limit)


def get_relevant_profile_items(query: str, limit: int = 5) -> list[EvidenceChunk]:
    return search_chunks("profile_items", query, limit=limit)


def get_role_guidance(query: str, limit: int = 5) -> list[EvidenceChunk]:
    return search_chunks("job_briefs", query, limit=limit)


def get_similar_validated_optimizations(query: str, limit: int = 5) -> list[EvidenceChunk]:
    return search_chunks("validated_optimizations", query, limit=limit)
