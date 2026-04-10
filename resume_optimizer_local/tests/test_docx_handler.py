"""
Unit tests for docx_handler.py (resume_optimizer_local).
"""
import io
import pytest
from docx import Document

from tests.conftest import make_docx_file


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_doc(path: str) -> Document:
    return Document(path)


# ── extract_text ──────────────────────────────────────────────────────────────

class TestExtractText:
    def test_returns_paragraph_text(self, tmp_path):
        from docx_handler import extract_text
        path = make_docx_file(tmp_path, ["Hello world", "Second paragraph"])
        text = extract_text(path)
        assert "Hello world" in text
        assert "Second paragraph" in text

    def test_includes_table_content(self, tmp_path):
        from docx_handler import extract_text
        from docx import Document

        doc = Document()
        doc.add_paragraph("Before table")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Cell A"
        table.cell(0, 1).text = "Cell B"
        doc.add_paragraph("After table")
        path = str(tmp_path / "table_resume.docx")
        doc.save(path)

        text = extract_text(path)
        assert "Cell A" in text
        assert "Cell B" in text
        assert "Before table" in text

    def test_empty_doc_returns_empty_string(self, tmp_path):
        from docx_handler import extract_text
        path = make_docx_file(tmp_path, [])
        text = extract_text(path)
        assert text.strip() == ""


# ── replace_paragraph_text ────────────────────────────────────────────────────

class TestReplaceParagraphText:
    def test_replaces_text(self, tmp_path):
        from docx_handler import replace_paragraph_text
        doc = Document()
        para = doc.add_paragraph("Original text")
        replace_paragraph_text(para, "New text")
        assert para.text == "New text"

    def test_preserves_bold(self, tmp_path):
        from docx_handler import replace_paragraph_text
        doc = Document()
        para = doc.add_paragraph()
        run = para.add_run("Bold text")
        run.bold = True
        replace_paragraph_text(para, "Replaced bold")
        assert para.runs[0].bold is True

    def test_paragraph_with_no_runs(self, tmp_path):
        from docx_handler import replace_paragraph_text
        doc = Document()
        para = doc.add_paragraph()
        # Remove any auto-created runs
        for r in list(para.runs):
            r._element.getparent().remove(r._element)
        replace_paragraph_text(para, "Fresh text")
        assert "Fresh text" in para.text


# ── replace_exact_paragraph ───────────────────────────────────────────────────

class TestReplaceExactParagraph:
    def test_successful_replacement(self, tmp_path):
        from docx_handler import replace_exact_paragraph
        doc = Document()
        doc.add_paragraph("Match me exactly")
        doc.add_paragraph("Other paragraph")
        msg = replace_exact_paragraph(doc, "Match me exactly", "Replaced!")
        assert "Replaced" in doc.paragraphs[0].text
        assert "✅" in msg

    def test_not_found_raises_value_error(self, tmp_path):
        from docx_handler import replace_exact_paragraph
        doc = Document()
        doc.add_paragraph("Some paragraph")
        with pytest.raises(ValueError, match="Anchor not found"):
            replace_exact_paragraph(doc, "Missing anchor text", "x")

    def test_duplicate_raises_value_error(self, tmp_path):
        from docx_handler import replace_exact_paragraph
        doc = Document()
        doc.add_paragraph("Duplicate text")
        doc.add_paragraph("Duplicate text")
        with pytest.raises(ValueError, match="Multiple matches"):
            replace_exact_paragraph(doc, "Duplicate text", "x")

    def test_whitespace_normalization(self, tmp_path):
        from docx_handler import replace_exact_paragraph
        doc = Document()
        doc.add_paragraph("  Spaced text  ")
        # Should match even if anchor has different surrounding whitespace
        msg = replace_exact_paragraph(doc, "Spaced text", "Trimmed!")
        assert "Trimmed!" in doc.paragraphs[0].text


# ── apply_replacements ────────────────────────────────────────────────────────

class TestApplyReplacements:
    def _payload(self):
        return {
            "summary_replacement": {
                "match_anchor": "Original summary text",
                "replacement_text": "New summary text",
            },
            "bullet_replacements": [
                {
                    "match_anchor": "Original bullet one",
                    "replacement_text": "Replaced bullet one",
                }
            ],
            "skills_replacements": [
                {
                    "match_anchor": "Original skills line",
                    "replacement_text": "Replaced skills line",
                }
            ],
        }

    def test_successful_application(self, tmp_path):
        from docx_handler import apply_replacements
        path = make_docx_file(
            tmp_path,
            ["Original summary text", "Original bullet one", "Original skills line"],
        )
        success, message = apply_replacements(path, self._payload())
        assert success is True
        assert "Successfully" in message

        # Verify the file was updated
        doc = _load_doc(
            path.replace(".docx", "_Optimized.docx")
        )
        texts = [p.text for p in doc.paragraphs if p.text.strip()]
        assert any("New summary text" in t for t in texts)

    def test_unmatched_anchor_returns_error(self, tmp_path):
        from docx_handler import apply_replacements
        path = make_docx_file(tmp_path, ["Something else entirely"])
        success, message = apply_replacements(path, self._payload())
        assert success is False
        assert "Errors" in message

    def test_empty_payload_no_change(self, tmp_path):
        from docx_handler import apply_replacements
        path = make_docx_file(tmp_path, ["Any paragraph"])
        success, message = apply_replacements(path, {})
        # No replacements requested → should succeed and save output
        assert success is True


# ── generate_output_filename ──────────────────────────────────────────────────

class TestGenerateOutputFilename:
    def test_appends_optimized_suffix(self):
        from docx_handler import generate_output_filename
        result = generate_output_filename("/some/path/My_Resume.docx")
        assert result.endswith("My_Resume_Optimized.docx")

    def test_custom_suffix(self):
        from docx_handler import generate_output_filename
        result = generate_output_filename("/some/path/My_Resume.docx", suffix="_v2")
        assert result.endswith("My_Resume_v2.docx")
