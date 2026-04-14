"""
Tests for json_parser.py — the validation layer between raw AI output
and the replacement engine. These are the highest-consequence checks:
a bug here can let malformed payloads reach the user's resume file.
"""
import pytest

from json_parser import (
    extract_json_from_text,
    validate_payload,
    collect_replacements,
    build_validation_summary,
    validate_builder_payload,
    parse_replacement_payload,
)


# ---------------------------------------------------------------------------
# extract_json_from_text
# ---------------------------------------------------------------------------

class TestExtractJsonFromText:
    def test_clean_json_object(self):
        raw = '{"summary_replacement": {"match_anchor": "a", "replacement_text": "b"}}'
        result = extract_json_from_text(raw)
        assert result["summary_replacement"]["match_anchor"] == "a"

    def test_json_embedded_in_prose(self):
        raw = (
            "Here is your optimized payload:\n\n"
            '{"bullet_replacements": [{"match_anchor": "old", "replacement_text": "new"}]}'
        )
        result = extract_json_from_text(raw)
        assert len(result["bullet_replacements"]) == 1

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="No pasted content"):
            extract_json_from_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="No pasted content"):
            extract_json_from_text("   \n  ")

    def test_no_json_block_raises(self):
        with pytest.raises(ValueError, match="No JSON block found"):
            extract_json_from_text("Here is a sentence with no JSON at all.")

    def test_malformed_json_raises_with_position(self):
        # Has matching braces so the regex finds it, but interior is invalid JSON
        with pytest.raises(ValueError, match="Invalid JSON format"):
            extract_json_from_text('{"key": "value", bad: syntax }')  # unquoted key


# ---------------------------------------------------------------------------
# validate_payload
# ---------------------------------------------------------------------------

VALID_SUMMARY = {
    "summary_replacement": {
        "match_anchor": "Experienced professional.",
        "replacement_text": "Results-driven professional with 5 years experience.",
    }
}

VALID_BULLETS = {
    "bullet_replacements": [
        {"match_anchor": "Managed team", "replacement_text": "Led cross-functional team of 8"},
        {"match_anchor": "Handled reports", "replacement_text": "Produced weekly KPI dashboards"},
    ]
}

VALID_SKILLS = {
    "skills_replacements": [
        {"match_anchor": "Python, Excel", "replacement_text": "Python, SQL, Tableau, Excel"},
    ]
}


class TestValidatePayload:
    def test_valid_summary_only(self):
        ok, err = validate_payload(VALID_SUMMARY)
        assert ok is True
        assert err is None

    def test_valid_bullets_only(self):
        ok, err = validate_payload(VALID_BULLETS)
        assert ok is True

    def test_valid_skills_only(self):
        ok, err = validate_payload(VALID_SKILLS)
        assert ok is True

    def test_valid_all_sections(self):
        payload = {**VALID_SUMMARY, **VALID_BULLETS, **VALID_SKILLS}
        ok, err = validate_payload(payload)
        assert ok is True

    def test_not_a_dict_fails(self):
        ok, err = validate_payload(["not", "a", "dict"])
        assert ok is False
        assert "JSON object" in err

    def test_empty_dict_fails(self):
        ok, err = validate_payload({})
        assert ok is False
        assert "at least one" in err.lower()

    def test_unknown_key_fails(self):
        ok, err = validate_payload({"extra_section": {}})
        assert ok is False
        assert "Unsupported" in err

    def test_summary_missing_anchor_fails(self):
        payload = {"summary_replacement": {"replacement_text": "New summary"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "match_anchor" in err

    def test_summary_empty_anchor_fails(self):
        payload = {"summary_replacement": {"match_anchor": "  ", "replacement_text": "text"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "match_anchor" in err

    def test_summary_missing_replacement_fails(self):
        payload = {"summary_replacement": {"match_anchor": "Old summary"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "replacement_text" in err

    def test_summary_empty_replacement_fails(self):
        payload = {"summary_replacement": {"match_anchor": "Old", "replacement_text": ""}}
        ok, err = validate_payload(payload)
        assert ok is False

    def test_bullets_not_a_list_fails(self):
        payload = {"bullet_replacements": {"match_anchor": "x", "replacement_text": "y"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "array" in err

    def test_bullet_item_missing_anchor_fails(self):
        payload = {"bullet_replacements": [{"replacement_text": "New bullet"}]}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "bullet_replacements[0]" in err

    def test_skills_not_a_list_fails(self):
        payload = {"skills_replacements": "Python, SQL"}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "array" in err


# ---------------------------------------------------------------------------
# collect_replacements
# ---------------------------------------------------------------------------

class TestCollectReplacements:
    def test_collects_summary(self):
        items = collect_replacements(VALID_SUMMARY)
        assert len(items) == 1
        assert items[0]["match_anchor"] == "Experienced professional."

    def test_collects_bullets(self):
        items = collect_replacements(VALID_BULLETS)
        assert len(items) == 2

    def test_collects_all_sections_in_order(self):
        payload = {**VALID_SUMMARY, **VALID_BULLETS, **VALID_SKILLS}
        items = collect_replacements(payload)
        # summary first, then bullets (2), then skills (1)
        assert len(items) == 4
        assert items[0]["match_anchor"] == "Experienced professional."

    def test_empty_payload_returns_empty(self):
        assert collect_replacements({}) == []


# ---------------------------------------------------------------------------
# build_validation_summary
# ---------------------------------------------------------------------------

class TestBuildValidationSummary:
    def test_stats_counted_correctly(self):
        payload = {**VALID_SUMMARY, **VALID_BULLETS, **VALID_SKILLS}
        summary = build_validation_summary(payload)
        stats = summary["stats"]
        assert stats["summary_replacements"] == 1
        assert stats["bullet_replacements"] == 2
        assert stats["skills_replacements"] == 1
        assert stats["requested_replacements"] == 4

    def test_no_sections_returns_zero_counts(self):
        summary = build_validation_summary({})
        assert summary["stats"]["requested_replacements"] == 0

    def test_valid_flag_always_true(self):
        # build_validation_summary assumes a pre-validated payload
        assert build_validation_summary(VALID_SUMMARY)["valid"] is True


# ---------------------------------------------------------------------------
# validate_builder_payload
# ---------------------------------------------------------------------------

VALID_BUILDER = {
    "basics": {
        "full_name": "Jane Smith",
        "email": "jane@example.com",
        "phone": "555-0100",
        "location": "New York, NY",
        "linkedin": "linkedin.com/in/janesmith",
    },
    "summary": "Recent CS graduate with internship experience in backend development.",
    "education": [
        {
            "school": "State University",
            "degree": "B.S. Computer Science",
            "graduation_date": "May 2024",
            "details": ["Dean's List 2022–2024"],
        }
    ],
    "experience": [
        {
            "title": "Software Engineering Intern",
            "organization": "Acme Corp",
            "location": "Remote",
            "dates": "Jun–Aug 2023",
            "bullets": ["Built REST API endpoints", "Reduced query time by 30%"],
        }
    ],
    "projects": [
        {
            "name": "Personal Portfolio",
            "details": ["Built with React and Tailwind CSS"],
        }
    ],
    "skills": ["Python", "SQL", "React"],
}


class TestValidateBuilderPayload:
    def test_valid_full_payload(self):
        ok, err = validate_builder_payload(VALID_BUILDER)
        assert ok is True
        assert err is None

    def test_missing_top_level_key_fails(self):
        payload = {k: v for k, v in VALID_BUILDER.items() if k != "summary"}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "summary" in err

    def test_basics_not_dict_fails(self):
        payload = {**VALID_BUILDER, "basics": "Jane Smith"}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "basics" in err

    def test_basics_missing_full_name_fails(self):
        basics = {k: v for k, v in VALID_BUILDER["basics"].items() if k != "full_name"}
        payload = {**VALID_BUILDER, "basics": basics}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "full_name" in err

    def test_education_not_list_fails(self):
        payload = {**VALID_BUILDER, "education": "State University"}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "education" in err

    def test_experience_bullet_not_string_fails(self):
        exp = [
            {
                "title": "Intern",
                "organization": "Co",
                "location": "NY",
                "dates": "2023",
                "bullets": [123],  # not a string
            }
        ]
        payload = {**VALID_BUILDER, "experience": exp}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "bullets" in err


# ---------------------------------------------------------------------------
# parse_replacement_payload (end-to-end)
# ---------------------------------------------------------------------------

class TestParseReplacementPayload:
    def test_valid_raw_text_returns_dict(self):
        raw = (
            'Here is the output:\n'
            '{"summary_replacement": {"match_anchor": "Old summary.", "replacement_text": "New summary."}}'
        )
        result = parse_replacement_payload(raw)
        assert result["summary_replacement"]["replacement_text"] == "New summary."

    def test_invalid_payload_raises(self):
        raw = '{"unknown_key": {}}'
        with pytest.raises(ValueError, match="Unsupported"):
            parse_replacement_payload(raw)

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            parse_replacement_payload("")
