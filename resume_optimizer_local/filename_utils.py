"""Safe, consistent filenames for generated resume downloads."""
from __future__ import annotations

import re


def _filename_component(value: str, fallback: str, max_length: int = 80) -> str:
    """Return a filesystem-safe filename component while preserving spaces."""
    cleaned = re.sub(r'[\x00-\x1f/\\:*?"<>|]+', " ", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    cleaned = cleaned[:max_length].rstrip(" ._")
    return cleaned or fallback


def build_resume_download_filename(user_name: str, role: str) -> str:
    """Build the standard ``User Name_Resume_Role.docx`` download name."""
    safe_name = _filename_component(user_name, "Candidate")
    safe_role = _filename_component(role, "Target Role")
    return f"{safe_name}_Resume_{safe_role}.docx"
