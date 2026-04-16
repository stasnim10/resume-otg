"""
Chunking helpers for local evidence retrieval.
"""
from __future__ import annotations

from llm_core.schemas import EvidenceChunk


def chunk_text(source_type: str, source_id: str, text: str, section: str, chunk_size: int = 500) -> list[EvidenceChunk]:
    """Split text into simple fixed-size chunks."""
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[EvidenceChunk] = []
    for index in range(0, len(normalized), chunk_size):
        snippet = normalized[index:index + chunk_size].strip()
        if snippet:
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"{source_type}:{source_id}:{section}:{index // chunk_size}",
                    source_type=source_type,
                    source_id=source_id,
                    section=section,
                    text=snippet,
                )
            )
    return chunks
