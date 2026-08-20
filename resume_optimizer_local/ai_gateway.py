"""Provider-aware AI gateway for the Streamlit prototype."""
from __future__ import annotations

from typing import Callable, Dict, List, Union

import requests
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


def _build_payload_repair_prompt(original_prompt: str, raw_output: str, error_message: str) -> str:
    """Ask a local/custom model to convert a bad response into the strict replacement schema."""
    return f"""You returned an invalid response for a resume optimization task.

VALIDATION ERROR
{error_message}

YOUR PREVIOUS RESPONSE
{raw_output}

REPAIR TASK
Return only valid JSON that matches exactly this schema. Do not include markdown, prose, comments, analysis, or keys other than these:
{{
  "summary_replacement": {{
    "match_anchor": "Full exact summary paragraph from the resume",
    "replacement_text": "New full summary paragraph"
  }},
  "bullet_replacements": [
    {{
      "match_anchor": "Full exact bullet paragraph from the resume",
      "replacement_text": "New bullet paragraph"
    }}
  ],
  "skills_replacements": [
    {{
      "match_anchor": "Full exact skills paragraph from the resume",
      "replacement_text": "New skills paragraph"
    }}
  ]
}}

Rules:
1. Every match_anchor must be copied exactly from RESUME TEXT in the original task.
2. If you cannot provide an exact match_anchor for a replacement, omit that replacement.
3. Do not return a resume, job summary, sections, or recommendations.
4. Do not use top-level keys like section, content, optimized_resume, analysis, or changes unless changes is converted into bullet_replacements.
5. Return JSON only.

ORIGINAL TASK
{original_prompt}
"""


def _parse_with_repair(
    original_prompt: str,
    raw_output: str,
    generate_repair: Callable[[str], str],
) -> dict:
    """Parse provider output and make one schema-repair attempt when needed."""
    try:
        return _parse_output_text(raw_output)
    except ValueError as error:
        repair_prompt = _build_payload_repair_prompt(original_prompt, raw_output, str(error))
        repaired_output = generate_repair(repair_prompt)
        return _parse_output_text(repaired_output)


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
    def generate(user_prompt: str) -> str:
        response = client.responses.create(
            model=model,
            input=user_prompt,
        )
        return response.output_text or ""

    raw_output = generate(prompt)
    return _parse_with_repair(prompt, raw_output, generate)


def _run_openai_compatible(base_url: str, api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against an OpenAI-compatible endpoint such as Ollama."""
    from openai import OpenAI

    if not base_url or not base_url.strip():
        raise ValueError("Enter the base URL for your local or custom endpoint.")
    if not model or not model.strip():
        raise ValueError("Enter the model name for your local or custom endpoint.")

    normalized_base_url = base_url.strip().rstrip("/")
    is_ollama = "localhost:11434" in normalized_base_url or "127.0.0.1:11434" in normalized_base_url
    if is_ollama:
        native_base_url = normalized_base_url[:-3].rstrip("/") if normalized_base_url.endswith("/v1") else normalized_base_url
        return _run_ollama_native(native_base_url, prompt, model.strip())

    client = OpenAI(
        api_key=(api_key.strip() or "ollama"),
        base_url=normalized_base_url,
    )
    response = client.chat.completions.create(
        model=model.strip(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    output_text = response.choices[0].message.content if response.choices else ""
    try:
        return _parse_output_text(output_text or "")
    except ValueError as error:
        repair_prompt = _build_payload_repair_prompt(prompt, output_text or "", str(error))
        repair_response = client.chat.completions.create(
            model=model.strip(),
            messages=[{"role": "user", "content": repair_prompt}],
            temperature=0.0,
        )
        repaired_text = repair_response.choices[0].message.content if repair_response.choices else ""
        return _parse_output_text(repaired_text or "")


def _run_ollama_native(base_url: str, prompt: str, model: str) -> dict:
    """Run Ollama through its native JSON mode, then repair once if needed."""
    raw_output = _ollama_generate_json(base_url, prompt, model)
    try:
        return _parse_output_text(raw_output)
    except ValueError as error:
        repair_prompt = _build_payload_repair_prompt(prompt, raw_output, str(error))
        repaired_output = _ollama_generate_json(base_url, repair_prompt, model)
        return _parse_output_text(repaired_output)


def _ollama_generate_json(base_url: str, prompt: str, model: str) -> str:
    """Generate one non-streaming JSON-mode response from Ollama."""
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
            },
        },
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload.get("response") or "").strip()


def _run_anthropic(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against Anthropic."""
    try:
        from anthropic import Anthropic
    except ImportError as error:
        raise ValueError(
            "Anthropic support is scaffolded, but the `anthropic` package is not installed yet."
        ) from error

    client = Anthropic(api_key=api_key.strip())
    def generate(user_prompt: str) -> str:
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            messages=[{"role": "user", "content": user_prompt}],
        )

        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts)

    raw_output = generate(prompt)
    return _parse_with_repair(prompt, raw_output, generate)


def _run_gemini(api_key: str, prompt: str, model: str) -> dict:
    """Run the prompt against Gemini."""
    try:
        from google import genai
    except ImportError as error:
        raise ValueError(
            "Gemini support is scaffolded, but the `google-genai` package is not installed yet."
        ) from error

    client = genai.Client(api_key=api_key.strip())
    def generate(user_prompt: str) -> str:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
        )
        return getattr(response, "text", None) or ""

    raw_output = generate(prompt)
    return _parse_with_repair(prompt, raw_output, generate)


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
