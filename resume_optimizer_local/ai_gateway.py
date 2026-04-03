"""
Provider-aware AI gateway for the Streamlit prototype.
"""
from typing import Dict, List, Union

from json_parser import parse_replacement_payload


PROVIDER_CONFIG: Dict[str, Dict[str, Union[List[str], str]]] = {
    "OpenAI": {
        "key_label": "OpenAI API Key",
        "placeholder": "sk-...",
        "models": ["gpt-4o-mini", "gpt-4.1-mini"],
    },
    "Anthropic": {
        "key_label": "Anthropic API Key",
        "placeholder": "sk-ant-...",
        "models": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
    },
    "Gemini": {
        "key_label": "Google AI API Key",
        "placeholder": "AIza...",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
    },
}


def _parse_output_text(output_text: str) -> dict:
    """Validate provider output against the optimizer schema."""
    if not output_text or not output_text.strip():
        raise ValueError("The model returned an empty response. Try again.")
    return parse_replacement_payload(output_text)


def _run_openai(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against OpenAI."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key.strip())
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return _parse_output_text(response.output_text)


def _run_anthropic(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against Anthropic."""
    try:
        from anthropic import Anthropic
    except ImportError as error:
        raise ValueError(
            "Anthropic support is scaffolded, but the `anthropic` package is not installed yet."
        ) from error

    client = Anthropic(api_key=api_key.strip())
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return _parse_output_text("\n".join(parts))


def _run_gemini(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against Gemini."""
    try:
        from google import genai
    except ImportError as error:
        raise ValueError(
            "Gemini support is scaffolded, but the `google-genai` package is not installed yet."
        ) from error

    client = genai.Client(api_key=api_key.strip())
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    output_text = getattr(response, "text", None)
    return _parse_output_text(output_text or "")


def optimize_with_provider(
    provider: str,
    api_key: str,
    prompt: str,
    model: str,
) -> dict:
    """Run the optimizer prompt against the selected provider."""
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unsupported provider: {provider}")
    if not api_key or not api_key.strip():
        raise ValueError(f"Enter your {provider} API key to use API mode.")

    if provider == "OpenAI":
        return _run_openai(api_key, prompt, model)
    if provider == "Anthropic":
        return _run_anthropic(api_key, prompt, model)
    if provider == "Gemini":
        return _run_gemini(api_key, prompt, model)

    raise ValueError(f"Unsupported provider: {provider}")
