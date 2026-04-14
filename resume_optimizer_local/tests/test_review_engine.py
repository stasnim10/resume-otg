"""
Tests for review_engine.py — the anchor-matching layer that validates
a replacement payload against the actual uploaded document before export.

These tests use python-docx to create real .docx fixtures in temp
directories, matching the real call path in the app.
"""
import pathlib
import tempfile

import pytest
from docx import Document

from review_engine import (
    _best_suggestions,
    analyze_payload_against_document,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_docx(paragraphs: list[str], tmp_dir: pathlib.Path) -> str:
    """Create a minimal .docx with the given paragraphs and return its path."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    path = tmp_dir / "test_resume.docx"
    doc.save(str(path))
    return str(path)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


# ---------------------------------------------------------------------------
# _best_suggestions
# ---------------------------------------------------------------------------

class TestBestSuggestions:
    def test_returns_close_match(self):
        paragraphs = ["Led a cross-functional team of 8 engineers"]
        suggestions = _best_suggestions("Led cross-functional team of eight engineers", paragraphs)
        assert len(suggestions) == 1
        assert suggestions[0]["score"] > 0.45

    def test_no_match_below_threshold(self):
        paragraphs = ["Managed quarterly budget forecasting"]
        suggestions = _best_suggestions("Python SQL Tableau", paragraphs)
        assert suggestions == []

    def test_respects_limit(self):
        paragraphs = [
            "Increased revenue by 20%",
            "Increased sales by 20%",
            "Increased output by 20%",
            "Increased efficiency by 20%",
        ]
        suggestions = _best_suggestions("Increased performance by 20%", paragraphs, limit=2)
        assert len(suggestions) <= 2

    def test_sorted_by_score_descending(self):
        paragraphs = [
            "Managed a large team",         # lower similarity
            "Managed a large team of ten",  # higher similarity
        ]
        anchor = "Managed a large team of eight"
        suggestions = _best_suggestions(anchor, paragraphs)
        if len(suggestions) > 1:
            assert suggestions[0]["score"] >= suggestions[1]["score"]

    def test_exact_match_scores_highest(self):
        anchor = "Developed automated testing framework"
        paragraphs = [anchor, "Something completely unrelated"]
        suggestions = _best_suggestions(anchor, paragraphs)
        assert suggestions[0]["score"] == 1.0


# ---------------------------------------------------------------------------
# analyze_payload_against_document
# ---------------------------------------------------------------------------

class TestAnalyzePayloadAgainstDocument:
    def test_all_anchors_matched(self, tmp_dir):
        doc_path = _make_docx(
            [
                "Results-driven analyst with 4 years of experience.",
                "Managed end-to-end supply chain operations.",
                "Python, SQL, Tableau",
            ],
            tmp_dir,
        )
        payload = {
            "summary_replacement": {
                "match_anchor": "Results-driven analyst with 4 years of experience.",
                "replacement_text": "Data-driven analyst with 4 years of cross-functional experience.",
            },
            "bullet_replacements": [
                {
                    "match_anchor": "Managed end-to-end supply chain operations.",
                    "replacement_text": "Owned end-to-end supply chain operations across 3 regions.",
                }
            ],
        }
        result = analyze_payload_against_document(doc_path, payload)

        assert result["stats"]["ready_for_export"] is True
        assert result["stats"]["matched_replacements"] == 2
        assert result["stats"]["unmatched_replacements"] == 0
        assert result["stats"]["duplicate_replacements"] == 0

    def test_unmatched_anchor_blocks_export(self, tmp_dir):
        doc_path = _make_docx(["Only paragraph in this document."], tmp_dir)
        payload = {
            "bullet_replacements": [
                {
                    "match_anchor": "This paragraph does not exist at all.",
                    "replacement_text": "Replacement text.",
                }
            ]
        }
        result = analyze_payload_against_document(doc_path, payload)

        assert result["stats"]["ready_for_export"] is False
        assert result["stats"]["unmatched_replacements"] == 1
        assert len(result["warnings"]) > 0

    def test_duplicate_anchor_blocks_export(self, tmp_dir):
        repeated = "Handled administrative responsibilities."
        doc_path = _make_docx([repeated, repeated, "Other paragraph."], tmp_dir)
        payload = {
            "bullet_replacements": [
                {
                    "match_anchor": repeated,
                    "replacement_text": "Managed administrative operations across two departments.",
                }
            ]
        }
        result = analyze_payload_against_document(doc_path, payload)

        assert result["stats"]["ready_for_export"] is False
        assert result["stats"]["duplicate_replacements"] == 1

    def test_mixed_results_not_ready(self, tmp_dir):
        doc_path = _make_docx(
            ["Exact match paragraph.", "Another paragraph."],
            tmp_dir,
        )
        payload = {
            "bullet_replacements": [
                {"match_anchor": "Exact match paragraph.", "replacement_text": "New text."},
                {"match_anchor": "This one does not exist.", "replacement_text": "New text 2."},
            ]
        }
        result = analyze_payload_against_document(doc_path, payload)

        assert result["stats"]["ready_for_export"] is False
        assert result["stats"]["matched_replacements"] == 1
        assert result["stats"]["unmatched_replacements"] == 1

    def test_unmatched_provides_fuzzy_suggestions(self, tmp_dir):
        doc_path = _make_docx(
            ["Developed Python automation scripts for data pipeline."],
            tmp_dir,
        )
        payload = {
            "bullet_replacements": [
                {
                    "match_anchor": "Developed Python automation script for data pipeline.",
                    "replacement_text": "Built Python automation scripts that cut pipeline runtime by 40%.",
                }
            ]
        }
        result = analyze_payload_against_document(doc_path, payload)

        unmatched_item = next(r for r in result["results"] if r["status"] == "unmatched")
        assert len(unmatched_item["suggestions"]) > 0

    def test_returns_paragraph_list(self, tmp_dir):
        doc_path = _make_docx(["Para one.", "Para two."], tmp_dir)
        result = analyze_payload_against_document(doc_path, {"bullet_replacements": []})
        assert "paragraphs" in result
        assert "Para one." in result["paragraphs"]

    def test_empty_payload_zero_replacements(self, tmp_dir):
        doc_path = _make_docx(["Some content."], tmp_dir)
        result = analyze_payload_against_document(doc_path, {})
        assert result["stats"]["requested_replacements"] == 0
        assert result["stats"]["ready_for_export"] is True

    def test_skills_replacement_section(self, tmp_dir):
        doc_path = _make_docx(["Python, Excel, Word"], tmp_dir)
        payload = {
            "skills_replacements": [
                {"match_anchor": "Python, Excel, Word", "replacement_text": "Python, SQL, Tableau"}
            ]
        }
        result = analyze_payload_against_document(doc_path, payload)
        assert result["stats"]["matched_replacements"] == 1
        result_item = result["results"][0]
        assert result_item["section"] == "Skills"

    def test_result_section_labels(self, tmp_dir):
        doc_path = _make_docx(
            ["Summary text.", "Bullet text.", "Skills text."],
            tmp_dir,
        )
        payload = {
            "summary_replacement": {"match_anchor": "Summary text.", "replacement_text": "New summary."},
            "bullet_replacements": [{"match_anchor": "Bullet text.", "replacement_text": "New bullet."}],
            "skills_replacements": [{"match_anchor": "Skills text.", "replacement_text": "New skills."}],
        }
        result = analyze_payload_against_document(doc_path, payload)
        sections = {r["section"] for r in result["results"]}
        assert sections == {"Summary", "Bullet", "Skills"}
