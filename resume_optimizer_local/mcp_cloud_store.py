"""Private, account-scoped resume storage shared by Streamlit and remote MCP."""
from __future__ import annotations

import re
from uuid import UUID

BUCKET = "mcp-resumes"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def user_folder(user_id: str) -> str:
    return str(UUID(user_id))


def save_source(client, user_id: str, contents: bytes) -> None:
    client.storage.from_(BUCKET).upload(
        f"{user_folder(user_id)}/source.docx", contents,
        file_options={"content-type": DOCX_MIME, "upsert": "true"},
    )


def read_source(client, user_id: str) -> tuple[dict, bytes]:
    contents = client.storage.from_(BUCKET).download(f"{user_folder(user_id)}/source.docx")
    return {"original_name": "Saved MCP resume.docx"}, contents


def export_path(user_id: str, export_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{32}", export_id):
        raise ValueError("Invalid export ID.")
    return f"{user_folder(user_id)}/exports/{export_id}.docx"


def save_export(client, user_id: str, export_id: str, contents: bytes) -> str:
    path = export_path(user_id, export_id)
    client.storage.from_(BUCKET).upload(path, contents, file_options={"content-type": DOCX_MIME})
    result = client.storage.from_(BUCKET).create_signed_url(path, 600)
    return result["signedURL"]
