"""
Unit tests for json_parser.py
"""
import pytest
from json_parser import (
    extract_json_from_text,
    validate_payload,
    parse_replacement_payload,
    parse_builder_payload,
    validate_builder_payload,
    collect_replacements,
    build_validation_summary,
)


# ── extract_json_from_text ────────────────────────────────────────────────────

class TestExtractJsonFromText:
    def test_clean_json(self):
        raw = '{"summary_replacement": {"match_anchor": "a", "replacement_text": "b"}}'
        result = extract_json_from_text(raw)
        assert result["summary_replacement"]["match_anchor"] == "a"

    def test_json_wrapped_in_prose(self):
        raw = 'Here is your payload:\n{"summary_replacement": {"match_anchor": "x", "replacement_text": "y"}}'
        result = extract_json_from_text(raw)
        assert "summary_replacement" in result

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="No pasted content"):
            extract_json_from_text("")

    def test_no_json_block_raises(self):
        with pytest.raises(ValueError, match="No JSON block"):
            extract_json_from_text("just plain text without any braces")

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            extract_json_from_text("{bad json:}")


# ── validate_payload ──────────────────────────────────────────────────────────

class TestValidatePayload:
    def _summary(self):
        return {"match_anchor": "old text", "replacement_text": "new text"}

    def test_valid_summary_only(self):
        ok, err = validate_payload({"summary_replacement": self._summary()})
        assert ok is True
        assert err is None

    def test_valid_bullets_only(self):
        payload = {"bullet_replacements": [self._summary()]}
        ok, err = validate_payload(payload)
        assert ok is True

    def test_valid_skills_only(self):
        payload = {"skills_replacements": [self._summary()]}
        ok, err = validate_payload(payload)
        assert ok is True

    def test_valid_all_sections(self):
        payload = {
            "summary_replacement": self._summary(),
            "bullet_replacements": [self._summary()],
            "skills_replacements": [self._summary()],
        }
        ok, err = validate_payload(payload)
        assert ok is True

    def test_empty_dict_fails(self):
        ok, err = validate_payload({})
        assert ok is False
        assert "at least one" in err.lower()

    def test_unknown_key_fails(self):
        payload = {"unknown_key": {"match_anchor": "a", "replacement_text": "b"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "unsupported" in err.lower()

    def test_missing_match_anchor_fails(self):
        payload = {"summary_replacement": {"replacement_text": "b"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "match_anchor" in err

    def test_missing_replacement_text_fails(self):
        payload = {"summary_replacement": {"match_anchor": "a"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "replacement_text" in err

    def test_bullet_not_list_fails(self):
        payload = {"bullet_replacements": {"match_anchor": "a", "replacement_text": "b"}}
        ok, err = validate_payload(payload)
        assert ok is False
        assert "array" in err.lower()

    def test_empty_anchor_string_fails(self):
        payload = {"summary_replacement": {"match_anchor": "   ", "replacement_text": "b"}}
        ok, err = validate_payload(payload)
        assert ok is False

    def test_not_a_dict_fails(self):
        ok, err = validate_payload([])
        assert ok is False


# ── parse_replacement_payload ─────────────────────────────────────────────────

class TestParseReplacementPayload:
    def test_round_trip(self):
        raw = '{"summary_replacement": {"match_anchor": "old", "replacement_text": "new"}}'
        payload = parse_replacement_payload(raw)
        assert payload["summary_replacement"]["replacement_text"] == "new"

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_replacement_payload("{}")


# ── collect_replacements ──────────────────────────────────────────────────────

class TestCollectReplacements:
    def _item(self, anchor="a", text="b"):
        return {"match_anchor": anchor, "replacement_text": text}

    def test_collects_all_sections(self):
        payload = {
            "summary_replacement": self._item("s", "S"),
            "bullet_replacements": [self._item("b1", "B1"), self._item("b2", "B2")],
            "skills_replacements": [self._item("sk", "SK")],
        }
        replacements = collect_replacements(payload)
        assert len(replacements) == 4
        assert replacements[0]["match_anchor"] == "s"
        assert replacements[1]["match_anchor"] == "b1"

    def test_empty_payload(self):
        payload = {"summary_replacement": self._item()}
        replacements = collect_replacements(payload)
        assert len(replacements) == 1


# ── build_validation_summary ──────────────────────────────────────────────────

class TestBuildValidationSummary:
    def test_counts(self):
        payload = {
            "summary_replacement": {"match_anchor": "a", "replacement_text": "b"},
            "bullet_replacements": [{"match_anchor": "x", "replacement_text": "y"}] * 3,
            "skills_replacements": [{"match_anchor": "p", "replacement_text": "q"}] * 2,
        }
        summary = build_validation_summary(payload)
        assert summary["stats"]["requested_replacements"] == 6
        assert summary["stats"]["summary_replacements"] == 1
        assert summary["stats"]["bullet_replacements"] == 3
        assert summary["stats"]["skills_replacements"] == 2


# ── validate_builder_payload ──────────────────────────────────────────────────

VALID_BUILDER = {
    "basics": {
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-555-5555",
        "location": "New York, NY",
        "linkedin": "linkedin.com/in/janedoe",
    },
    "summary": "A motivated professional.",
    "education": [
        {
            "school": "State U",
            "degree": "B.S. Computer Science",
            "graduation_date": "May 2024",
            "details": ["GPA: 3.9"],
        }
    ],
    "experience": [
        {
            "title": "Software Engineer",
            "organization": "Acme",
            "location": "NYC",
            "dates": "Jan 2023 - Present",
            "bullets": ["Built APIs", "Reduced latency by 30%"],
        }
    ],
    "projects": [
        {
            "name": "Resume Optimizer",
            "details": ["Open-source Python tool"],
        }
    ],
    "skills": ["Python", "SQL", "Docker"],
}


class TestValidateBuilderPayload:
    def test_valid(self):
        ok, err = validate_builder_payload(VALID_BUILDER)
        assert ok is True
        assert err is None

    def test_missing_basics(self):
        payload = {k: v for k, v in VALID_BUILDER.items() if k != "basics"}
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "basics" in err

    def test_missing_full_name(self):
        import copy
        payload = copy.deepcopy(VALID_BUILDER)
        del payload["basics"]["full_name"]
        ok, err = validate_builder_payload(payload)
        assert ok is False
        assert "full_name" in err

    def test_skills_not_list_fails(self):
        import copy
        payload = copy.deepcopy(VALID_BUILDER)
        payload["skills"] = "Python, SQL"
        ok, err = validate_builder_payload(payload)
        assert ok is False

    def test_parse_builder_payload_round_trip(self):
        import json
        raw = json.dumps(VALID_BUILDER)
        result = parse_builder_payload(raw)
        assert result["basics"]["full_name"] == "Jane Doe"
