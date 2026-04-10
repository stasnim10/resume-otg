"""
Shared fixtures for the resume_optimizer_local test suite.
"""
import io
import sys
import os
import pytest

# Ensure the parent package directory is on the path so test modules can
# import the source files without installation.
_SRC = os.path.join(os.path.dirname(__file__), "..")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    """Return the bytes of a minimal .docx file with the given paragraphs."""
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_docx_file(tmp_path, paragraphs: list[str]) -> str:
    """Write a minimal .docx to *tmp_path* and return the file path."""
    path = tmp_path / "test_resume.docx"
    path.write_bytes(make_docx_bytes(paragraphs))
    return str(path)
