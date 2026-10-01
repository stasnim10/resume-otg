"""Private, account-scoped resume storage shared by Streamlit and remote MCP."""
from __future__ import annotations

import re
from uuid import UUID
from filename_utils import _filename_component

BUCKET = "mcp-resumes"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def user_folder(user_id: str) -> str:
    return str(UUID(user_id))


def save_source(client, user_id: str, contents: bytes, original_name: str = "Resume.docx", user_name: str = "", naming_style: str = "uploaded") -> None:
    client.storage.from_(BUCKET).upload(
        f"{user_folder(user_id)}/source.docx", contents,
        file_options={"content-type": DOCX_MIME, "upsert": "true", "metadata": {
            "original_name": original_name, "user_name": user_name, "naming_style": naming_style,
        }},
    )


def read_source(client, user_id: str) -> tuple[dict, bytes]:
    contents = client.storage.from_(BUCKET).download(f"{user_folder(user_id)}/source.docx")
    info = client.storage.from_(BUCKET).info(f"{user_folder(user_id)}/source.docx")
    metadata = info.get("user_metadata") or info.get("userMetadata") or info.get("metadata") or {}
    return {"original_name": "Resume.docx", **metadata}, contents


def export_path(user_id: str, export_id: str, filename: str | None = None) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", export_id):
        raise ValueError("Invalid export ID.")
    suffix = f"--{_filename_component(filename, 'Resume_Optimized.docx', 200)}" if filename else ".docx"
    return f"{user_folder(user_id)}/exports/{export_id}{suffix}"


def save_export(client, user_id: str, export_id: str, contents: bytes, filename: str = "Resume_Optimized.docx") -> str:
    path = export_path(user_id, export_id, filename)
    client.storage.from_(BUCKET).upload(path, contents, file_options={"content-type": DOCX_MIME})
    result = client.storage.from_(BUCKET).create_signed_url(path, 600, {"download": filename})
    return result["signedURL"]


def export_download_name(storage_name: str) -> str:
    match = re.fullmatch(r"[0-9a-f]{32}--(.+\.docx)", storage_name)
    return match.group(1) if match else "Resume_Optimized.docx"


def resolve_export_path(client, user_id: str, export_id: str) -> str:
    legacy = export_path(user_id, export_id)  # Validate before querying storage.
    files = client.storage.from_(BUCKET).list(f"{user_folder(user_id)}/exports", {"search": export_id, "limit": 100})
    for item in files:
        name = item.get("name", "")
        if re.fullmatch(re.escape(export_id) + r"--[^/\\]+\.docx", name):
            return f"{user_folder(user_id)}/exports/{name}"
    return legacy
