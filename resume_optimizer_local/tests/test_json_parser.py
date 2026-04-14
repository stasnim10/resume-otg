from __future__ import annotations

import pytest

from json_parser import (
    build_validation_summary,
    collect_replacements,
    extract_json_from_text,
    parse_builder_payload,
    parse_replacement_payload,
    validate_builder_payload,
    validate_payload,
)


def _valid_replacement_payload() -> dict:
    return {
        "summary_replacement": {"match_anchor": "Old summary", "replacement_text": "New summary"},
        "bullet_replacements": [{"match_anchor": "Old bullet", "replacement_text": "New bullet"}],
        "skills_replacements": [{"match_anchor": "Old skills", "replacement_text": "New skills"}],
    }


def _valid_builder_payload() -> dict:
    return {
        "basics": {
            "full_name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-0100",
            "location": "NYC",
            "linkedin": "linkedin.com/in/jane",
        },
        "summary": "Impact-focused analyst with strong execution.",
        "education": [
            {
                "school": "State University",
                "degree": "BS Business",
                "graduation_date": "2024",
                "details": ["Honors"],
            }
        ],
        "experience": [
            {
                "title": "Analyst",
                "organization": "Acme",
                "location": "NY",
                "dates": "2023-2024",
                "bullets": ["Improved KPI by 12%"],
            }
        ],
        "projects": [{"name": "Capstone", "details": ["Built dashboard"]}],
        "skills": ["SQL", "Excel"],
    }


def test_extract_json_from_text_with_prose_wrapper() -> None:
    raw = "Here you go:\n{\"summary_replacement\": {\"match_anchor\": \"A\", \"replacement_text\": \"B\"}}"
    parsed = extract_json_from_text(raw)
    assert parsed["summary_replacement"]["match_anchor"] == "A"


def test_extract_json_from_text_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="No pasted content found"):
        extract_json_from_text("  ")


def test_extract_json_from_text_rejects_when_no_json_block() -> None:
    with pytest.raises(ValueError, match="No JSON block found"):
        extract_json_from_text("no structured payload present")


def test_extract_json_from_text_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="Invalid JSON format"):
        extract_json_from_text("{\"summary_replacement\": {\"match_anchor\": \"A\",}}")


def test_validate_payload_accepts_all_supported_sections() -> None:
    is_valid, error = validate_payload(_valid_replacement_payload())
    assert is_valid is True
    assert error is None


def test_validate_payload_rejects_non_object_payload() -> None:
    is_valid, error = validate_payload([])  # type: ignore[arg-type]
    assert is_valid is False
    assert error == "Payload must be a JSON object."


def test_validate_payload_rejects_unknown_top_level_key() -> None:
    is_valid, error = validate_payload({"foo": "bar"})
    assert is_valid is False
    assert "Unsupported top-level key(s): foo." == error


def test_validate_payload_requires_at_least_one_section() -> None:
    is_valid, error = validate_payload({})
    assert is_valid is False
    assert error == "Add at least one replacement section to continue."


def test_validate_payload_rejects_invalid_summary_replacement_type() -> None:
    is_valid, error = validate_payload({"summary_replacement": "bad"})  # type: ignore[dict-item]
    assert is_valid is False
    assert error == "summary_replacement must be an object."


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ({"replacement_text": "new"}, "summary_replacement.match_anchor must be a non-empty string."),
        ({"match_anchor": "", "replacement_text": "new"}, "summary_replacement.match_anchor must be a non-empty string."),
        ({"match_anchor": "old"}, "summary_replacement.replacement_text must be a non-empty string."),
        ({"match_anchor": "old", "replacement_text": " "}, "summary_replacement.replacement_text must be a non-empty string."),
    ],
)
def test_validate_payload_rejects_invalid_summary_fields(summary: dict, expected: str) -> None:
    is_valid, error = validate_payload({"summary_replacement": summary})
    assert is_valid is False
    assert error == expected


def test_validate_payload_rejects_non_list_bullet_section() -> None:
    is_valid, error = validate_payload({"bullet_replacements": {}})  # type: ignore[dict-item]
    assert is_valid is False
    assert error == "bullet_replacements must be an array."


def test_validate_payload_rejects_non_list_skills_section() -> None:
    is_valid, error = validate_payload({"skills_replacements": {}})  # type: ignore[dict-item]
    assert is_valid is False
    assert error == "skills_replacements must be an array."


def test_validate_payload_rejects_invalid_bullet_item() -> None:
    is_valid, error = validate_payload({"bullet_replacements": [{"match_anchor": "old"}]})
    assert is_valid is False
    assert error == "bullet_replacements[0].replacement_text must be a non-empty string."


def test_validate_payload_rejects_invalid_skills_item() -> None:
    is_valid, error = validate_payload({"skills_replacements": [{"replacement_text": "new"}]})
    assert is_valid is False
    assert error == "skills_replacements[0].match_anchor must be a non-empty string."


def test_collect_replacements_preserves_expected_order() -> None:
    payload = {
        "summary_replacement": {"match_anchor": "s", "replacement_text": "S"},
        "bullet_replacements": [
            {"match_anchor": "b1", "replacement_text": "B1"},
            {"match_anchor": "b2", "replacement_text": "B2"},
        ],
        "skills_replacements": [{"match_anchor": "k1", "replacement_text": "K1"}],
    }
    result = collect_replacements(payload)
    assert [item["match_anchor"] for item in result] == ["s", "b1", "b2", "k1"]


def test_collect_replacements_returns_empty_for_empty_payload() -> None:
    assert collect_replacements({}) == []


def test_build_validation_summary_computes_stats() -> None:
    summary = build_validation_summary(_valid_replacement_payload())
    assert summary["valid"] is True
    assert summary["stats"] == {
        "requested_replacements": 3,
        "summary_replacements": 1,
        "bullet_replacements": 1,
        "skills_replacements": 1,
    }


def test_validate_builder_payload_accepts_valid_payload() -> None:
    is_valid, error = validate_builder_payload(_valid_builder_payload())
    assert is_valid is True
    assert error is None


def test_validate_builder_payload_rejects_non_object_payload() -> None:
    is_valid, error = validate_builder_payload([])  # type: ignore[arg-type]
    assert is_valid is False
    assert error == "Payload must be a JSON object."


def test_validate_builder_payload_rejects_missing_required_key() -> None:
    payload = _valid_builder_payload()
    del payload["skills"]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert "Missing required top-level key(s): skills." == error


def test_validate_builder_payload_rejects_invalid_basics() -> None:
    payload = _valid_builder_payload()
    payload["basics"] = "bad"  # type: ignore[assignment]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "basics must be an object."


def test_validate_builder_payload_requires_basics_full_name() -> None:
    payload = _valid_builder_payload()
    payload["basics"]["full_name"] = ""
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "basics.full_name is required."


def test_validate_builder_payload_requires_summary() -> None:
    payload = _valid_builder_payload()
    payload["summary"] = ""
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "summary is required."


def test_validate_builder_payload_rejects_non_list_education() -> None:
    payload = _valid_builder_payload()
    payload["education"] = {}  # type: ignore[assignment]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "education must be an array."


def test_validate_builder_payload_rejects_invalid_education_details() -> None:
    payload = _valid_builder_payload()
    payload["education"][0]["details"] = ["good", ""]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "education[0].details[1] must be a non-empty string."


def test_validate_builder_payload_rejects_non_list_experience() -> None:
    payload = _valid_builder_payload()
    payload["experience"] = {}  # type: ignore[assignment]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "experience must be an array."


def test_validate_builder_payload_rejects_invalid_experience_bullets() -> None:
    payload = _valid_builder_payload()
    payload["experience"][0]["bullets"] = ["ok", 3]  # type: ignore[list-item]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "experience[0].bullets[1] must be a non-empty string."


def test_validate_builder_payload_rejects_non_list_projects() -> None:
    payload = _valid_builder_payload()
    payload["projects"] = {}  # type: ignore[assignment]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "projects must be an array."


def test_validate_builder_payload_rejects_project_without_name() -> None:
    payload = _valid_builder_payload()
    payload["projects"][0]["name"] = ""
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "projects[0].name is required."


def test_validate_builder_payload_rejects_non_list_skills() -> None:
    payload = _valid_builder_payload()
    payload["skills"] = {}  # type: ignore[assignment]
    is_valid, error = validate_builder_payload(payload)
    assert is_valid is False
    assert error == "skills must be an array."


def test_parse_replacement_payload_returns_payload_for_valid_input() -> None:
    raw = """
    Here:
    {"summary_replacement": {"match_anchor": "Old", "replacement_text": "New"}}
    """
    parsed = parse_replacement_payload(raw)
    assert parsed["summary_replacement"]["replacement_text"] == "New"


def test_parse_replacement_payload_raises_for_invalid_input() -> None:
    with pytest.raises(ValueError, match="No JSON block found"):
        parse_replacement_payload("invalid")


def test_parse_builder_payload_returns_payload_for_valid_input() -> None:
    payload = _valid_builder_payload()
    parsed = parse_builder_payload(f"prefix\n{payload}".replace("'", '"'))
    assert parsed["basics"]["full_name"] == "Jane Doe"


def test_parse_builder_payload_raises_for_invalid_builder_payload() -> None:
    with pytest.raises(ValueError, match="Missing required top-level key"):
        parse_builder_payload('{"basics": {}, "summary": "x"}')
