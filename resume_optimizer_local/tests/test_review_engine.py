from __future__ import annotations

from pathlib import Path

from docx import Document

from review_engine import _best_suggestions, analyze_payload_against_document


def _write_doc(path: Path, paragraphs: list[str]) -> str:
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)
    return str(path)


def _base_payload() -> dict:
    return {
        "summary_replacement": {"match_anchor": "Summary A", "replacement_text": "Summary B"},
        "bullet_replacements": [{"match_anchor": "Bullet A", "replacement_text": "Bullet B"}],
        "skills_replacements": [{"match_anchor": "Skills A", "replacement_text": "Skills B"}],
    }


def test_best_suggestions_filters_by_threshold() -> None:
    suggestions = _best_suggestions("Data analysis", ["Unrelated text", "Data analytics"], limit=5)
    assert all(item["score"] > 0.45 for item in suggestions)


def test_best_suggestions_respects_limit() -> None:
    suggestions = _best_suggestions("Anchor", ["Anchor", "Anchor plus", "Anchor extra", "Anchor more"], limit=2)
    assert len(suggestions) == 2


def test_best_suggestions_sorted_descending() -> None:
    suggestions = _best_suggestions("Alpha", ["Alphabeta", "A", "Alpha"], limit=3)
    scores = [item["score"] for item in suggestions]
    assert scores == sorted(scores, reverse=True)


def test_best_suggestions_exact_match_scores_one() -> None:
    suggestions = _best_suggestions("Exact text", ["Exact text"], limit=1)
    assert suggestions[0]["score"] == 1.0


def test_analyze_payload_all_matched(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "all-matched.docx", ["Summary A", "Bullet A", "Skills A"])
    report = analyze_payload_against_document(doc_path, _base_payload())
    assert report["stats"]["matched_replacements"] == 3
    assert report["stats"]["ready_for_export"] is True
    assert report["warnings"] == []


def test_analyze_payload_unmatched_item(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "unmatched.docx", ["Summary A", "Bullet A"])
    payload = _base_payload()
    report = analyze_payload_against_document(doc_path, payload)
    assert report["stats"]["unmatched_replacements"] == 1
    assert report["stats"]["ready_for_export"] is False


def test_analyze_payload_duplicate_anchor(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "duplicate.docx", ["Summary A", "Summary A", "Bullet A", "Skills A"])
    payload = _base_payload()
    report = analyze_payload_against_document(doc_path, payload)
    assert report["stats"]["duplicate_replacements"] == 1
    summary_row = [row for row in report["results"] if row["section"] == "Summary"][0]
    assert summary_row["status"] == "duplicate"


def test_analyze_payload_mixed_results(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "mixed.docx", ["Summary A", "Summary A", "Bullet A"])
    payload = _base_payload()
    report = analyze_payload_against_document(doc_path, payload)
    assert report["stats"]["matched_replacements"] == 1
    assert report["stats"]["duplicate_replacements"] == 1
    assert report["stats"]["unmatched_replacements"] == 1


def test_analyze_payload_surfaces_fuzzy_suggestions_for_unmatched(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "suggestions.docx", ["Summary A", "Bullet A", "Skills A-like"])
    payload = _base_payload()
    report = analyze_payload_against_document(doc_path, payload)
    skills_row = [row for row in report["results"] if row["section"] == "Skills"][0]
    assert skills_row["status"] == "unmatched"
    assert skills_row["suggestions"]


def test_analyze_payload_handles_empty_payload(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "empty-payload.docx", ["Paragraph 1"])
    report = analyze_payload_against_document(doc_path, {})
    assert report["stats"]["requested_replacements"] == 0
    assert report["stats"]["ready_for_export"] is True
    assert report["results"] == []


def test_analyze_payload_keeps_section_labels(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "labels.docx", ["Summary A", "Bullet A", "Skills A"])
    report = analyze_payload_against_document(doc_path, _base_payload())
    labels = [row["section"] for row in report["results"]]
    assert labels == ["Summary", "Bullet", "Skills"]


def test_analyze_payload_includes_warning_for_unmatched(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "warning-unmatched.docx", ["Summary A", "Bullet A"])
    report = analyze_payload_against_document(doc_path, _base_payload())
    assert any("could not be matched exactly" in warning for warning in report["warnings"])


def test_analyze_payload_includes_warning_for_duplicate(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "warning-duplicate.docx", ["Summary A", "Summary A", "Bullet A", "Skills A"])
    report = analyze_payload_against_document(doc_path, _base_payload())
    assert any("matched multiple paragraphs" in warning for warning in report["warnings"])


def test_analyze_payload_counts_paragraphs(tmp_path: Path) -> None:
    doc_path = _write_doc(tmp_path / "paragraph-count.docx", ["A", "B", "C", "D"])
    report = analyze_payload_against_document(doc_path, {})
    assert report["paragraph_count"] == 4
