"""Run with python mcp_server.py; stdout is reserved for the MCP protocol."""
from mcp.server.fastmcp import FastMCP

from mcp_resume_service import export_resume, prepare_resume, read_export

mcp = FastMCP("Resume OTG")


@mcp.tool()
def prepare_resume_for_job(job: str) -> dict:
    """Start here: paste a job URL or description to tailor the user's saved Word resume.

    Follow the returned optimization instructions to generate replacement JSON,
    then call export_tailored_resume. No separate AI API key is needed.
    """
    return prepare_resume(job)


@mcp.tool()
def export_tailored_resume(payload: dict, resume_sha256: str) -> dict:
    """Apply grounded replacement JSON and save a Word download.

    Use the source hash from prepare_resume_for_job. Return the file path and
    resource URI to the user. Preserve facts; review wording before applying.
    """
    return export_resume(payload, resume_sha256)


@mcp.resource("resume-otg://exports/{export_id}", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
def download_resume(export_id: str) -> bytes:
    """Download an exported resume as a binary DOCX resource."""
    return read_export(export_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
