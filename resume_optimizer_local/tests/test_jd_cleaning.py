"""
Unit tests for jd_cleaning.py
"""
import pytest
from jd_cleaning import (
    clean_job_description,
    _is_junk_line,
    _merge_broken_lines,
    _trim_at_stop_marker,
    _compress_blank_lines,
    _normalize_typography,
)


class TestIsJunkLine:
    def test_apply_now_is_junk(self):
        assert _is_junk_line("Apply now") is True

    def test_sign_in_is_junk(self):
        assert _is_junk_line("Sign in") is True

    def test_job_content_is_not_junk(self):
        assert _is_junk_line("Manage global supply chain operations") is False

    def test_empty_string_not_junk(self):
        assert _is_junk_line("") is False


class TestMergeBrokenLines:
    def test_merges_continuation_line(self):
        lines = ["The candidate should have experience", "in supply chain management."]
        merged, count = _merge_broken_lines(lines)
        assert count >= 1
        assert "experience" in merged[0] and "supply chain" in merged[0]

    def test_does_not_merge_complete_sentence(self):
        lines = ["First complete sentence.", "Second sentence starts here."]
        merged, count = _merge_broken_lines(lines)
        # First line ends with "." so second should stay separate
        assert len(merged) == 2

    def test_merges_punctuation_only_line(self):
        lines = ["Some text", "."]
        merged, count = _merge_broken_lines(lines)
        assert count == 1
        assert merged[0] == "Some text."


class TestTrimAtStopMarker:
    def test_trims_at_linkedin_marker(self):
        text = "Job description text.\nPeople also viewed\nSome recommendation here"
        trimmed, was_trimmed = _trim_at_stop_marker(text)
        assert was_trimmed is True
        assert "People also viewed" not in trimmed
        assert "Job description text" in trimmed

    def test_no_marker_returns_unchanged(self):
        text = "Regular job description without any markers."
        trimmed, was_trimmed = _trim_at_stop_marker(text)
        assert was_trimmed is False
        assert trimmed == text


class TestCompressBlankLines:
    def test_multiple_blanks_compressed(self):
        lines = ["Line 1", "", "", "Line 2", "", "", "", "Line 3"]
        result = _compress_blank_lines(lines)
        # No two consecutive blank lines
        for i in range(len(result) - 1):
            assert not (result[i] == "" and result[i + 1] == "")

    def test_leading_trailing_blanks_removed(self):
        lines = ["", "", "Content", "", ""]
        result = _compress_blank_lines(lines)
        assert result[0] != ""
        assert result[-1] != ""


class TestNormalizeTypography:
    def test_removes_space_before_comma(self):
        result = _normalize_typography("Hello , world")
        assert "Hello," in result

    def test_fixes_broken_apostrophe(self):
        result = _normalize_typography("don ' t")
        # The function joins broken apostrophes; spaces around the apostrophe are removed.
        assert " ' " not in result  # spaces around apostrophe have been removed


class TestCleanJobDescription:
    def test_returns_required_keys(self):
        result = clean_job_description("We are hiring a supply chain analyst.")
        assert "cleaned_text" in result
        assert "junk_lines_removed" in result
        assert "broken_lines_merged" in result
        assert "confidence_message" in result

    def test_removes_junk_lines(self):
        raw = "Apply now\nWe are looking for an analyst.\nSign in\nSave\n"
        result = clean_job_description(raw)
        assert result["junk_lines_removed"] >= 2
        assert "Apply now" not in result["cleaned_text"]

    def test_trims_linkedin_recommendations(self):
        raw = "Job description here.\nPeople also viewed\nSome other person's profile"
        result = clean_job_description(raw)
        assert "People also viewed" not in result["cleaned_text"]

    def test_empty_input_returns_empty_cleaned_text(self):
        result = clean_job_description("")
        assert result["cleaned_text"] == ""

    def test_clean_jd_unchanged(self):
        jd = "Lead the procurement team. Manage supplier negotiations. Report to CPO."
        result = clean_job_description(jd)
        # Clean text should still contain the meaningful content
        assert "procurement" in result["cleaned_text"]
        assert "supplier" in result["cleaned_text"]
