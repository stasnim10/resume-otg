"""
Supabase-backed store for user_settings (provider, model, API key).

API keys are stored base64-encoded as a temporary measure.
Replace with Supabase Vault / Edge Function encryption before public launch.
"""
from __future__ import annotations

import base64
import logging

import streamlit as st

from supabase_client import get_supabase

logger = logging.getLogger(__name__)

_EMPTY_SETTINGS: dict = {
    "preferred_provider": "OpenAI",
    "default_model": "",
    "api_key_encrypted": "",
    "api_key_last4": "",
    "api_key_valid": False,
    "api_key_validation_message": "",
}

# Maps provider display name → column prefix in user_settings
_PROVIDER_COL: dict[str, str] = {
    "OpenAI": "openai",
    "Anthropic": "anthropic",
    "Gemini": "gemini",
}


def _uid() -> str:
    uid = st.session_state.get("auth_user_id", "")
    if not uid:
        raise RuntimeError("Not authenticated")
    return uid


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_user_settings() -> dict:
    """Return the current user's settings, or defaults if not yet saved."""
    try:
        resp = (
            get_supabase()
            .table("user_settings")
            .select("*")
            .eq("user_id", _uid())
            .maybe_single()
            .execute()
        )
        if resp.data:
            return resp.data
    except Exception as exc:
        logger.warning("get_user_settings failed: %s", exc)
    return dict(_EMPTY_SETTINGS)


def get_decrypted_api_key() -> str:
    """Return the stored API key (decoded from base64), or empty string."""
    settings = get_user_settings()
    encoded = settings.get("api_key_encrypted", "")
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def save_api_key(provider: str, model: str, api_key: str) -> None:
    """Persist provider selection and API key (base64-encoded)."""
    encoded = base64.b64encode(api_key.encode()).decode() if api_key else ""
    last4 = api_key[-4:] if len(api_key) >= 4 else ""
    _upsert({
        "preferred_provider": provider,
        "default_model": model,
        "api_key_encrypted": encoded,
        "api_key_last4": last4,
        "api_key_valid": False,
        "api_key_validation_message": "Not yet validated",
    })


def mark_api_key_valid(valid: bool, message: str = "") -> None:
    """Update the validity status after a test connection."""
    try:
        get_supabase().table("user_settings").update({
            "api_key_valid": valid,
            "api_key_validation_message": message,
        }).eq("user_id", _uid()).execute()
    except Exception as exc:
        logger.warning("mark_api_key_valid failed: %s", exc)


def save_provider_model(provider: str, model: str) -> None:
    """Update just the provider and model (keep existing key)."""
    _upsert({"preferred_provider": provider, "default_model": model})


def clear_api_key() -> None:
    """Remove the stored API key."""
    try:
        get_supabase().table("user_settings").update({
            "api_key_encrypted": "",
            "api_key_last4": "",
            "api_key_valid": False,
            "api_key_validation_message": "",
        }).eq("user_id", _uid()).execute()
    except Exception as exc:
        logger.warning("clear_api_key failed: %s", exc)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _upsert(data: dict) -> None:
    try:
        get_supabase().table("user_settings").upsert(
            {"user_id": _uid(), **data},
            on_conflict="user_id",
        ).execute()
    except Exception as exc:
        logger.warning("user_settings upsert failed: %s", exc)


# ---------------------------------------------------------------------------
# Per-provider key operations
# ---------------------------------------------------------------------------


def save_provider_api_key(provider: str, model: str, api_key: str) -> None:
    """Save an API key for a specific provider (base64-encoded)."""
    col = _PROVIDER_COL.get(provider)
    if not col:
        return
    encoded = base64.b64encode(api_key.encode()).decode() if api_key else ""
    last4 = api_key[-4:] if len(api_key) >= 4 else ""
    _upsert({
        f"{col}_key_encrypted": encoded,
        f"{col}_key_last4": last4,
        f"{col}_key_valid": False,
        "preferred_provider": provider,
        "default_model": model,
    })


def get_provider_api_key(provider: str) -> str:
    """Return the decrypted API key for a provider, or empty string."""
    col = _PROVIDER_COL.get(provider)
    if not col:
        return ""
    settings = get_user_settings()
    encoded = settings.get(f"{col}_key_encrypted", "")
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return ""


def get_provider_key_info(provider: str) -> dict:
    """Return last4 and valid status for a provider's saved key."""
    col = _PROVIDER_COL.get(provider)
    if not col:
        return {"last4": "", "valid": False}
    settings = get_user_settings()
    return {
        "last4": settings.get(f"{col}_key_last4", ""),
        "valid": settings.get(f"{col}_key_valid", False),
    }


def get_all_provider_key_info() -> dict[str, dict]:
    """Return key status for all known providers in one DB call."""
    settings = get_user_settings()
    return {
        provider: {
            "last4": settings.get(f"{col}_key_last4", ""),
            "valid": settings.get(f"{col}_key_valid", False),
        }
        for provider, col in _PROVIDER_COL.items()
    }


def mark_provider_key_valid(provider: str, valid: bool) -> None:
    """Update validity flag for a provider's key after a test call."""
    col = _PROVIDER_COL.get(provider)
    if not col:
        return
    try:
        get_supabase().table("user_settings").update(
            {f"{col}_key_valid": valid}
        ).eq("user_id", _uid()).execute()
    except Exception as exc:
        logger.warning("mark_provider_key_valid failed: %s", exc)


def clear_provider_api_key(provider: str) -> None:
    """Remove the saved key for a specific provider."""
    col = _PROVIDER_COL.get(provider)
    if not col:
        return
    try:
        get_supabase().table("user_settings").update({
            f"{col}_key_encrypted": "",
            f"{col}_key_last4": "",
            f"{col}_key_valid": False,
        }).eq("user_id", _uid()).execute()
    except Exception as exc:
        logger.warning("clear_provider_api_key failed: %s", exc)
