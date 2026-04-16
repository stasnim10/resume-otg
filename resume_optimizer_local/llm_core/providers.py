"""
Model provider wrappers.
"""
from __future__ import annotations

from ollama_local_ai import DEFAULT_LOCAL_AI_MODEL, OLLAMA_BASE_URL, generate_text


def run_text_generation(
    prompt: str,
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """Run text generation against the configured Local AI provider."""
    return generate_text(
        prompt=prompt,
        model_name=model_name or DEFAULT_LOCAL_AI_MODEL,
        base_url=base_url or OLLAMA_BASE_URL,
        temperature=temperature,
        json_mode=json_mode,
    )
