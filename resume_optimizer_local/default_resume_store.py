"""
Local single-default resume persistence.

This intentionally stores one .docx on the user's device for faster repeat
optimization. It does not implement a resume library.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from profile_schema import utc_now_iso


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RESUME_DIR = BASE_DIR / "saved_resumes"
DEFAULT_RESUME_PATH = DEFAULT_RESUME_DIR / "default_resume.docx"
DEFAULT_RESUME_META_PATH = DEFAULT_RESUME_DIR / "default_resume.json"


def _metadata_for(original_name: str, resume_bytes: bytes) -> dict[str, Any]:
    return {
        "original_name": original_name,
        "size_bytes": len(resume_bytes),
        "sha256": hashlib.sha256(resume_bytes).hexdigest(),
        "saved_at": utc_now_iso(),
    }


def get_default_resume_metadata() -> dict[str, Any] | None:
    """Return metadata for the saved default resume, if one exists."""
    if not DEFAULT_RESUME_PATH.exists() or not DEFAULT_RESUME_META_PATH.exists():
        return None
    try:
        metadata = json.loads(DEFAULT_RESUME_META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(metadata, dict):
        return None
    return metadata


def save_default_resume(original_name: str, resume_bytes: bytes) -> dict[str, Any]:
    """Persist one default resume and return its metadata."""
    DEFAULT_RESUME_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_RESUME_PATH.write_bytes(resume_bytes)
    metadata = _metadata_for(original_name, resume_bytes)
    DEFAULT_RESUME_META_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def read_default_resume() -> tuple[dict[str, Any], bytes]:
    """Read the saved default resume metadata and .docx bytes."""
    metadata = get_default_resume_metadata()
    if metadata is None:
        raise FileNotFoundError("No saved default resume is available yet.")
    return metadata, DEFAULT_RESUME_PATH.read_bytes()


def delete_default_resume() -> None:
    """Remove the saved default resume and metadata."""
    DEFAULT_RESUME_PATH.unlink(missing_ok=True)
    DEFAULT_RESUME_META_PATH.unlink(missing_ok=True)
