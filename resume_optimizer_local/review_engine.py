from __future__ import annotations

"""Review and diagnostics helpers for resume replacement payloads."""
from difflib import SequenceMatcher
from typing import Any, Dict, List

from docx import Document


def extract_paragraphs(doc_path: str) -> List[str]:
    """Return non-empty document paragraphs in source order."""
    doc = Document(doc_path)
    return [para.text.strip() for para in doc.paragraphs if para.text.strip()]


def _best_suggestions(anchor: str, paragraphs: List[str], limit: int = 3) -> List[Dict[str, Any]]:
    """Return the closest paragraph suggestions for a missing anchor."""
    scored = []
    for paragraph in paragraphs:
        score = SequenceMatcher(None, anchor.strip(), paragraph.strip()).ratio()
        if score > 0.45:
            scored.append(
                {
                    "text": paragraph,
                    "score": round(score, 2),
                }
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def _analyze_payload_against_paragraphs(
    paragraphs: List[str],
    payload: Dict[str, Any],
    *,
    ready_for_export: bool,
    warnings: List[str] | None = None,
) -> Dict[str, Any]:
    """Compare requested anchors against a paragraph list."""
    paragraph_counts: Dict[str, int] = {}
    for paragraph in paragraphs:
        paragraph_counts[paragraph] = paragraph_counts.get(paragraph, 0) + 1

    requested_items: List[Dict[str, Any]] = []

    if "summary_replacement" in payload:
        requested_items.append(
            {
                "section": "Summary",
                "match_anchor": payload["summary_replacement"]["match_anchor"],
                "replacement_text": payload["summary_replacement"]["replacement_text"],
            }
        )

    for section_name, label in (
        ("bullet_replacements", "Bullet"),
        ("skills_replacements", "Skills"),
    ):
        for item in payload.get(section_name, []):
            requested_items.append(
                {
                    "section": label,
                    "match_anchor": item["match_anchor"],
                    "replacement_text": item["replacement_text"],
                }
            )

    matched = 0
    unmatched = 0
    duplicate = 0
    results: List[Dict[str, Any]] = []

    for item in requested_items:
        anchor = item["match_anchor"].strip()
        count = paragraph_counts.get(anchor, 0)

        if count == 1:
            status = "matched"
            matched += 1
            suggestions: List[Dict[str, Any]] = []
        elif count > 1:
            status = "duplicate"
            duplicate += 1
            suggestions = []
        else:
            status = "unmatched"
            unmatched += 1
            suggestions = _best_suggestions(anchor, paragraphs)

        results.append(
            {
                "section": item["section"],
                "status": status,
                "match_anchor": item["match_anchor"],
                "replacement_text": item["replacement_text"],
                "match_count": count,
                "suggestions": suggestions,
            }
        )

    warning_list: List[str] = list(warnings or [])
    if unmatched:
        warning_list.append(
            "Some of the AI-generated edits were unclear, so the app could not place them safely."
        )
    if duplicate:
        warning_list.append(
            "Some of the AI-generated edits were unclear, so the app could not place them safely."
        )

    return {
        "paragraph_count": len(paragraphs),
        "results": results,
        "warnings": warning_list,
        "stats": {
            "requested_replacements": len(requested_items),
            "matched_replacements": matched,
            "unmatched_replacements": unmatched,
            "duplicate_replacements": duplicate,
            "ready_for_export": ready_for_export and unmatched == 0 and duplicate == 0,
        },
        "paragraphs": paragraphs,
    }


def analyze_payload_against_document(doc_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare requested anchors against the uploaded document before export.

    This keeps replacement deterministic while still giving the UI
    helpful diagnostics and fuzzy suggestions.
    """
    paragraphs = extract_paragraphs(doc_path)
    return _analyze_payload_against_paragraphs(paragraphs, payload, ready_for_export=True)


def analyze_payload_against_text_paragraphs(paragraphs: List[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare requested anchors against text-only paragraphs.

    Used for PDF uploads where we can review anchors safely, but cannot export
    an in-place optimized .docx from the original file.
    """
    return _analyze_payload_against_paragraphs(
        paragraphs,
        payload,
        ready_for_export=False,
        warnings=[
            "PDF uploads can be reviewed, but exact .docx export requires uploading the original resume as a .docx file."
        ],
    )
