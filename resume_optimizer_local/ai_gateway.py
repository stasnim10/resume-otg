"""Provider-aware AI gateway for the Streamlit prototype."""
from __future__ import annotations

from typing import Dict, List, Union

import streamlit as st

from json_parser import parse_replacement_payload


PROVIDER_CONFIG: Dict[str, Dict[str, Union[List[str], str]]] = {
    "OpenAI": {
        "key_label": "OpenAI API Key",
        "placeholder": "sk-...",
        "models": ["gpt-5-mini", "gpt-5", "gpt-4.1", "gpt-4o-mini"],
        "description": "Hosted provider. Strong JSON reliability.",
    },
    "Anthropic": {
        "key_label": "Anthropic API Key",
        "placeholder": "sk-ant-...",
        "models": ["claude-sonnet-4-0", "claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest"],
        "description": "Hosted provider. Strong reasoning quality.",
    },
    "Gemini": {
        "key_label": "Google AI API Key",
        "placeholder": "AIza...",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "description": "Hosted provider. Affordable and fast.",
    },
    "Advanced Custom Endpoint": {
        "key_label": "API Key (Optional)",
        "placeholder": "Leave blank for local endpoints that do not require auth",
        "models": ["mistral"],
        "description": "Advanced option for custom OpenAI-compatible endpoints.",
    },
}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _openai_sort_key(model_id: str) -> tuple[int, str]:
    priorities = [
        "gpt-5",
        "gpt-4.1",
        "gpt-4o",
        "o4",
        "o3",
        "o1",
    ]
    lowered = model_id.lower()
    for idx, prefix in enumerate(priorities):
        if lowered.startswith(prefix):
            return (idx, lowered)
    return (len(priorities), lowered)


def _anthropic_sort_key(model_id: str) -> tuple[int, str]:
    priorities = [
        "claude-opus",
        "claude-sonnet",
        "claude-3-7-sonnet",
        "claude-3-5-sonnet",
        "claude-haiku",
    ]
    lowered = model_id.lower()
    for idx, prefix in enumerate(priorities):
        if lowered.startswith(prefix):
            return (idx, lowered)
    return (len(priorities), lowered)


def _gemini_sort_key(model_id: str) -> tuple[int, str]:
    priorities = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0",
        "gemini-1.5",
    ]
    lowered = model_id.lower()
    for idx, prefix in enumerate(priorities):
        if lowered.startswith(prefix):
            return (idx, lowered)
    return (len(priorities), lowered)


def _filter_openai_models(model_ids: list[str]) -> list[str]:
    allowed_prefixes = ("gpt-", "o1", "o3", "o4")
    blocked_fragments = ("audio", "transcribe", "search", "realtime", "image", "vision-preview", "embedding", "moderation")
    filtered = [
        model_id
        for model_id in model_ids
        if model_id.startswith(allowed_prefixes) and not any(fragment in model_id for fragment in blocked_fragments)
    ]
    return sorted(_unique(filtered), key=_openai_sort_key)


def _filter_anthropic_models(model_ids: list[str]) -> list[str]:
    filtered = [model_id for model_id in model_ids if model_id.startswith("claude")]
    return sorted(_unique(filtered), key=_anthropic_sort_key)


def _filter_gemini_models(model_ids: list[str]) -> list[str]:
    filtered = [model_id for model_id in model_ids if model_id.startswith("gemini")]
    return sorted(_unique(filtered), key=_gemini_sort_key)


def list_available_models(provider: str, api_key: str) -> list[str]:
    """Fetch the provider's accessible text models for the current API key."""
    api_key = (api_key or "").strip()
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unsupported provider: {provider}")
    if not api_key:
        return list(PROVIDER_CONFIG[provider]["models"])

    if provider == "OpenAI":
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model_ids = [item.id for item in client.models.list().data]
        filtered = _filter_openai_models(model_ids)
        return filtered or list(PROVIDER_CONFIG[provider]["models"])

    if provider == "Anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        response = client.models.list()
        model_ids = [item.id for item in getattr(response, "data", [])]
        filtered = _filter_anthropic_models(model_ids)
        return filtered or list(PROVIDER_CONFIG[provider]["models"])

    if provider == "Gemini":
        from google import genai

        client = genai.Client(api_key=api_key)
        model_ids: list[str] = []
        for model in client.models.list():
            name = getattr(model, "name", "") or ""
            supported_actions = getattr(model, "supported_actions", None) or []
            if supported_actions and "generateContent" not in supported_actions:
                continue
            model_ids.append(name.replace("models/", ""))
        filtered = _filter_gemini_models(model_ids)
        return filtered or list(PROVIDER_CONFIG[provider]["models"])

    return list(PROVIDER_CONFIG[provider]["models"])


def get_provider_models(provider: str, api_key: str = "") -> list[str]:
    """
    Return the best available model list for a provider.

    Uses live provider discovery when an API key is present, otherwise falls back
    to the curated static list.
    """
    try:
        return list_available_models(provider, api_key)
    except Exception:
        return list(PROVIDER_CONFIG[provider]["models"])


def _parse_output_text(output_text: str) -> dict:
    """Validate provider output against the optimizer schema."""
    if not output_text or not output_text.strip():
        raise ValueError("The model returned an empty response. Try again.")
    return parse_replacement_payload(output_text)


def _is_model_access_error(error: Exception) -> bool:
    message = str(error).lower()
    markers = (
        "model_not_found",
        "does not have access to model",
        "unsupported model",
        "invalid model",
        "model not found",
    )
    return any(marker in message for marker in markers)


def _fallback_models(provider: str, api_key: str, selected_model: str) -> list[str]:
    live_models = get_provider_models(provider, api_key)
    curated_models = list(PROVIDER_CONFIG[provider]["models"])
    candidates = _unique([*live_models, *curated_models])
    return [model for model in candidates if model != selected_model]


def _run_openai(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against OpenAI."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key.strip())
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return _parse_output_text(response.output_text)


def _run_openai_compatible(base_url: str, api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against an OpenAI-compatible endpoint such as Ollama."""
    from openai import OpenAI

    if not base_url or not base_url.strip():
        raise ValueError("Enter the base URL for your local or custom endpoint.")
    if not model or not model.strip():
        raise ValueError("Enter the model name for your local or custom endpoint.")

    client = OpenAI(
        api_key=(api_key.strip() or "ollama"),
        base_url=base_url.strip().rstrip("/"),
    )
    response = client.responses.create(
        model=model.strip(),
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
    base_url: str = "",
) -> dict:
    """Run the optimizer prompt against the selected provider."""
    st.session_state.ai_fallback_notice = ""
    if provider not in PROVIDER_CONFIG:
        raise ValueError(f"Unsupported provider: {provider}")
    if provider != "Advanced Custom Endpoint" and (not api_key or not api_key.strip()):
        raise ValueError(f"Enter your {provider} API key to use API mode.")

    if provider == "OpenAI":
        try:
            return _run_openai(api_key, prompt, model)
        except Exception as error:
            if not _is_model_access_error(error):
                raise
            for fallback_model in _fallback_models(provider, api_key, model):
                try:
                    result = _run_openai(api_key, prompt, fallback_model)
                    st.session_state.ai_fallback_notice = (
                        f'OpenAI could not use "{model}", so Resume OTG automatically switched to "{fallback_model}".'
                    )
                    return result
                except Exception as fallback_error:
                    if _is_model_access_error(fallback_error):
                        continue
                    raise fallback_error
            raise ValueError(
                f'The selected model "{model}" is not available for this OpenAI project, and no fallback model succeeded.'
            ) from error
    if provider == "Anthropic":
        try:
            return _run_anthropic(api_key, prompt, model)
        except Exception as error:
            if not _is_model_access_error(error):
                raise
            for fallback_model in _fallback_models(provider, api_key, model):
                try:
                    result = _run_anthropic(api_key, prompt, fallback_model)
                    st.session_state.ai_fallback_notice = (
                        f'Anthropic could not use "{model}", so Resume OTG automatically switched to "{fallback_model}".'
                    )
                    return result
                except Exception as fallback_error:
                    if _is_model_access_error(fallback_error):
                        continue
                    raise fallback_error
            raise ValueError(
                f'The selected model "{model}" is not available for this Anthropic project, and no fallback model succeeded.'
            ) from error
    if provider == "Gemini":
        try:
            return _run_gemini(api_key, prompt, model)
        except Exception as error:
            if not _is_model_access_error(error):
                raise
            for fallback_model in _fallback_models(provider, api_key, model):
                try:
                    result = _run_gemini(api_key, prompt, fallback_model)
                    st.session_state.ai_fallback_notice = (
                        f'Gemini could not use "{model}", so Resume OTG automatically switched to "{fallback_model}".'
                    )
                    return result
                except Exception as fallback_error:
                    if _is_model_access_error(fallback_error):
                        continue
                    raise fallback_error
            raise ValueError(
                f'The selected model "{model}" is not available for this Gemini project, and no fallback model succeeded.'
            ) from error
    if provider == "Advanced Custom Endpoint":
        return _run_openai_compatible(base_url, api_key, prompt, model)

    raise ValueError(f"Unsupported provider: {provider}")
