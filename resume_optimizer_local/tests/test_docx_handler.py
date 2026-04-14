"""
Tests for docx_handler.py — extract_text, replace_paragraph_text, and
replace_exact_paragraph. These functions operate on real .docx objects
so tests create fixtures with python-docx directly.
"""
import pathlib
import tempfile

import pytest
from docx import Document

from docx_handler import (
    extract_text,
    replace_paragraph_text,
    replace_exact_paragraph,
    apply_replacements,
    generate_output_filename,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_docx(paragraphs: list[str], path: pathlib.Path) -> str:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))
    return str(path)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_basic_paragraphs_returned(self, tmp_dir):
        path = _make_docx(["First paragraph.", "Second paragraph."], tmp_dir / "r.docx")
        text = extract_text(path)
        assert "First paragraph." in text
        assert "Second paragraph." in text

    def test_paragraphs_joined_with_newline(self, tmp_dir):
        path = _make_docx(["Line one.", "Line two."], tmp_dir / "r.docx")
        text = extract_text(path)
        lines = [l for l in text.splitlines() if l.strip()]
        assert "Line one." in lines
        assert "Line two." in lines

    def test_empty_paragraphs_preserved_as_blank_lines(self, tmp_dir):
        # python-docx join includes empty paras as blank lines
        path = _make_docx(["Content here.", "", "More content."], tmp_dir / "r.docx")
        text = extract_text(path)
        assert "Content here." in text
        assert "More content." in text

    def test_single_paragraph(self, tmp_dir):
        path = _make_docx(["Only one line."], tmp_dir / "r.docx")
        assert "Only one line." in extract_text(path)

    def test_pdf_extension_triggers_import_error_without_pypdf2(self, tmp_dir):
        fake_pdf = tmp_dir / "resume.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")
        try:
            import PyPDF2  # noqa: F401
            pytest.skip("PyPDF2 is installed; skipping ImportError test")
        except ImportError:
            with pytest.raises((ImportError, RuntimeError)):
                extract_text(str(fake_pdf))


# ---------------------------------------------------------------------------
# replace_paragraph_text
# ---------------------------------------------------------------------------

class TestReplaceParagraphText:
    def test_replaces_text_content(self):
        doc = Document()
        para = doc.add_paragraph("Original text.")
        replace_paragraph_text(para, "New text.")
        assert para.text == "New text."

    def test_preserves_bold_formatting(self):
        doc = Document()
        para = doc.add_paragraph()
        run = para.add_run("Bold text.")
        run.bold = True
        replace_paragraph_text(para, "Still bold.")
        assert para.runs[0].bold is True

    def test_returns_true_on_success(self):
        doc = Document()
        para = doc.add_paragraph("Text.")
        result = replace_paragraph_text(para, "New text.")
        assert result is True

    def test_paragraph_with_no_runs(self):
        doc = Document()
        # Create para without runs (bare paragraph element)
        para = doc.add_paragraph()
        # Remove any default runs
        for run in para.runs:
            run._element.getparent().remove(run._element)
        result = replace_paragraph_text(para, "Added text.")
        assert result is True
        assert para.text == "Added text."


# ---------------------------------------------------------------------------
# replace_exact_paragraph
# ---------------------------------------------------------------------------

class TestReplaceExactParagraph:
    def test_exact_match_replaced(self):
        doc = Document()
        doc.add_paragraph("Managed logistics operations.")
        replace_exact_paragraph(doc, "Managed logistics operations.", "Led end-to-end logistics operations.")
        texts = [p.text for p in doc.paragraphs]
        assert "Led end-to-end logistics operations." in texts
        assert "Managed logistics operations." not in texts

    def test_no_match_raises_value_error(self):
        doc = Document()
        doc.add_paragraph("Some other paragraph.")
        with pytest.raises(ValueError, match="Anchor not found"):
            replace_exact_paragraph(doc, "Does not exist.", "Replacement.")

    def test_duplicate_anchor_raises_value_error(self):
        doc = Document()
        doc.add_paragraph("Duplicate line.")
        doc.add_paragraph("Duplicate line.")
        with pytest.raises(ValueError, match="Multiple matches"):
            replace_exact_paragraph(doc, "Duplicate line.", "New text.")

    def test_whitespace_trimmed_for_matching(self):
        doc = Document()
        doc.add_paragraph("  Leading spaces paragraph.  ")
        # Should match after strip on both sides
        replace_exact_paragraph(doc, "Leading spaces paragraph.", "Replaced.")
        texts = [p.text.strip() for p in doc.paragraphs]
        assert "Replaced." in texts

    def test_returns_success_message(self):
        doc = Document()
        doc.add_paragraph("Target paragraph.")
        msg = replace_exact_paragraph(doc, "Target paragraph.", "Replacement.")
        assert isinstance(msg, str)
        assert len(msg) > 0


# ---------------------------------------------------------------------------
# apply_replacements
# ---------------------------------------------------------------------------

class TestApplyReplacements:
    """
    apply_replacements saves to a new _Optimized file alongside the
    original. Tests load the output path to verify content changes.
    """

    def test_summary_replaced_successfully(self, tmp_dir):
        path = _make_docx(
            ["Old summary text.", "Bullet one.", "Python, Excel"],
            tmp_dir / "resume.docx",
        )
        payload = {
            "summary_replacement": {
                "match_anchor": "Old summary text.",
                "replacement_text": "New summary text.",
            }
        }
        success, msg = apply_replacements(path, payload)
        assert success is True
        output_path = generate_output_filename(path)
        doc = Document(output_path)
        texts = [p.text for p in doc.paragraphs]
        assert "New summary text." in texts

    def test_bullet_replaced_successfully(self, tmp_dir):
        path = _make_docx(
            ["Summary.", "Old bullet point.", "Skills."],
            tmp_dir / "resume.docx",
        )
        payload = {
            "bullet_replacements": [
                {"match_anchor": "Old bullet point.", "replacement_text": "Improved bullet point."}
            ]
        }
        success, msg = apply_replacements(path, payload)
        assert success is True
        output_path = generate_output_filename(path)
        doc = Document(output_path)
        texts = [p.text for p in doc.paragraphs]
        assert "Improved bullet point." in texts

    def test_missing_anchor_returns_failure(self, tmp_dir):
        path = _make_docx(["Only this paragraph."], tmp_dir / "resume.docx")
        payload = {
            "bullet_replacements": [
                {"match_anchor": "Nonexistent anchor.", "replacement_text": "Replacement."}
            ]
        }
        success, msg = apply_replacements(path, payload)
        assert success is False

    def test_multiple_replacements_applied(self, tmp_dir):
        path = _make_docx(
            ["Summary A.", "Bullet A.", "Skills A."],
            tmp_dir / "resume.docx",
        )
        payload = {
            "summary_replacement": {
                "match_anchor": "Summary A.",
                "replacement_text": "Summary B.",
            },
            "bullet_replacements": [
                {"match_anchor": "Bullet A.", "replacement_text": "Bullet B."}
            ],
        }
        success, _msg = apply_replacements(path, payload)
        assert success is True
        output_path = generate_output_filename(path)
        doc = Document(output_path)
        texts = [p.text for p in doc.paragraphs]
        assert "Summary B." in texts
        assert "Bullet B." in texts
