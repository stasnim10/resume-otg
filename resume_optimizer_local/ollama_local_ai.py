"""
Helpers for the guided Local AI experience backed by Ollama.
"""
from __future__ import annotations

import json
import platform
from typing import Generator

import requests


OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_LOCAL_AI_MODEL = "gemma4:e4b"
DEFAULT_LOCAL_AI_LABEL = "Gemma 4 (Recommended)"
REQUEST_TIMEOUT_SECONDS = 8


def get_ollama_download_url() -> str:
    """Return the best public Ollama install page for the current OS."""
    system_name = platform.system().lower()
    if system_name == "darwin":
        return "https://ollama.com/download/mac"
    if system_name == "windows":
        return "https://ollama.com/download/windows"
    return "https://ollama.com/download"


def get_platform_label() -> str:
    """Return a friendly platform label."""
    system_name = platform.system().lower()
    if system_name == "darwin":
        return "macOS"
    if system_name == "windows":
        return "Windows"
    if system_name == "linux":
        return "Linux"
    return "your computer"


def check_ollama_status(base_url: str = OLLAMA_BASE_URL) -> dict:
    """Return whether Ollama is reachable."""
    try:
        response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=REQUEST_TIMEOUT_SECONDS)
        reachable = response.status_code == 200
        return {
            "reachable": reachable,
            "status_code": response.status_code,
            "message": "Local AI engine is available." if reachable else "Local AI engine was detected but did not respond correctly.",
        }
    except requests.RequestException:
        return {
            "reachable": False,
            "status_code": None,
            "message": "Local AI engine is not running yet.",
        }


def list_installed_models(base_url: str = OLLAMA_BASE_URL) -> list[str]:
    """Return installed Ollama model names."""
    response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    return [model.get("name", "") for model in payload.get("models", []) if model.get("name")]


def is_model_installed(model_name: str, base_url: str = OLLAMA_BASE_URL) -> bool:
    """Return whether the requested model exists locally."""
    try:
        return model_name in list_installed_models(base_url=base_url)
    except requests.RequestException:
        return False


def pull_model_stream(
    model_name: str,
    base_url: str = OLLAMA_BASE_URL,
) -> Generator[dict, None, None]:
    """Stream model download progress from Ollama."""
    response = requests.post(
        f"{base_url.rstrip('/')}/api/pull",
        json={"name": model_name, "stream": True},
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if not line:
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue

        total = int(event.get("total", 0) or 0)
        completed = int(event.get("completed", 0) or 0)
        percent = int((completed / total) * 100) if total > 0 else None
        yield {
            "status": event.get("status", "Preparing download"),
            "digest": event.get("digest", ""),
            "completed": completed,
            "total": total,
            "percent": percent,
        }


def generate_text(
    prompt: str,
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    temperature: float = 0.2,
    json_mode: bool = False,
) -> str:
    """Run a non-streaming generation request against Ollama."""
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    body = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 64,
        },
    }
    if json_mode:
        body["format"] = "json"

    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json=body,
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    return (payload.get("response") or "").strip()


def run_readiness_check(
    model_name: str = DEFAULT_LOCAL_AI_MODEL,
    base_url: str = OLLAMA_BASE_URL,
) -> dict:
    """Confirm Ollama is reachable and the model can answer a tiny JSON prompt."""
    status = check_ollama_status(base_url=base_url)
    if not status["reachable"]:
        return {
            "ready": False,
            "message": status["message"],
        }

    if not is_model_installed(model_name, base_url=base_url):
        return {
            "ready": False,
            "message": "Local AI engine is running, but the recommended model still needs to be downloaded.",
        }

    smoke_prompt = (
        'Return only this JSON object and nothing else: {"status":"ok","task":"readiness_check"}'
    )
    try:
        response_text = generate_text(smoke_prompt, model_name=model_name, base_url=base_url, temperature=0.0)
    except requests.RequestException as error:
        return {
            "ready": False,
            "message": f"Local AI engine is running, but the readiness test failed: {error}",
        }

    ready = False
    normalized = response_text.strip()
    try:
        payload = json.loads(normalized)
        ready = payload.get("status") == "ok"
    except json.JSONDecodeError:
        ready = '"status":"ok"' in normalized.replace(" ", "").replace("\n", "")
    return {
        "ready": ready,
        "message": "Local AI is ready." if ready else "Local AI responded, but the readiness check returned an unexpected result.",
        "raw_response": response_text,
    }
