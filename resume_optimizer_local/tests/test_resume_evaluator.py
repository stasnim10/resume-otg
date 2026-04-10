"""
Unit tests for resume_evaluator.py
"""
import pytest
from resume_evaluator import (
    evaluate_resume_fit,
    _tokenize,
    _top_keywords,
    _extract_skills,
    _resume_bullets,
    _count_quantified_bullets,
    _count_action_bullets,
    _section_presence,
    _score_bullets,
)

SAMPLE_RESUME = """
Jane Doe | jane@example.com | (555) 555-5555 | New York, NY

SUMMARY
Results-driven analyst with 4 years of experience in supply chain analytics.

EXPERIENCE
Senior Analyst, Acme Corp, Jan 2021 - Present
- Led a team of 5 analysts to improve reporting dashboards
- Reduced supply chain costs by $500K through process optimization
- Managed inventory forecasting models using SQL and Excel

EDUCATION
B.S. Business Analytics, State University, May 2020

SKILLS
SQL, Excel, Tableau, Python, Forecasting, Inventory Management
"""

SAMPLE_JD = """
We are looking for a Supply Chain Analyst with experience in:
- SQL and data analytics
- Inventory management and forecasting
- Dashboard development in Tableau or Power BI
- Cross-functional stakeholder collaboration
- Process improvement and cost reduction initiatives
"""


class TestEvaluateResumeFit:
    def test_returns_required_keys(self):
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD)
        required_keys = {
            "overall_score", "ats_score", "keyword_score", "skill_score",
            "bullet_score", "evidence_score", "matched_keywords",
            "missing_keywords", "matched_skills", "missing_skills",
            "bullet_count", "quantified_bullet_count", "action_verb_bullet_count",
            "warnings", "recommendations", "verdict",
        }
        assert required_keys.issubset(result.keys())

    def test_score_range(self):
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD)
        for key in ("overall_score", "ats_score", "keyword_score", "skill_score", "bullet_score"):
            assert 0 <= result[key] <= 100, f"{key} out of range: {result[key]}"

    def test_good_resume_scores_above_threshold(self):
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD)
        assert result["overall_score"] >= 40

    def test_empty_resume_returns_low_score(self):
        result = evaluate_resume_fit("", SAMPLE_JD)
        assert result["overall_score"] < 60

    def test_verdict_is_string(self):
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD)
        assert isinstance(result["verdict"], str)
        assert len(result["verdict"]) > 0

    def test_matched_keywords_subset_of_job_keywords(self):
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD)
        matched = set(result["matched_keywords"])
        missing = set(result["missing_keywords"])
        assert matched & missing == set(), "matched and missing keywords must be disjoint"

    def test_with_profile_items(self):
        from profile_schema import ProfileItem
        item = ProfileItem(
            item_type="experience",
            title="Supply Chain Analyst",
            organization="Test Co",
            description="Managed inventory and SQL reporting",
            bullets=["Reduced costs by 20%"],
            skills=["SQL", "Excel"],
            keywords=["inventory", "sql"],
        )
        result = evaluate_resume_fit(SAMPLE_RESUME, SAMPLE_JD, selected_profile_items=[item])
        assert result["evidence_score"] > 0
        assert len(result["selected_evidence_titles"]) > 0


class TestTokenize:
    def test_filters_stopwords(self):
        tokens = _tokenize("we are working with them")
        assert "with" not in tokens
        assert "them" not in tokens

    def test_minimum_length(self):
        tokens = _tokenize("a ab abc abcd")
        assert "a" not in tokens
        assert "ab" not in tokens
        # "abc" and "abcd" should pass (length >= 3 after the regex)


class TestTopKeywords:
    def test_returns_at_most_limit(self):
        text = "analytics dashboard kpi reporting metrics forecasting analytics analytics"
        keywords = _top_keywords(text, limit=5)
        assert len(keywords) <= 5

    def test_most_common_first(self):
        text = "analytics analytics analytics dashboard dashboard kpi"
        keywords = _top_keywords(text, limit=3)
        assert keywords[0] == "analytics"


class TestExtractSkills:
    def test_finds_listed_skills(self):
        skills = _extract_skills("Requirements: Excel, SQL, Tableau")
        assert "excel" in skills
        assert "sql" in skills
        assert "tableau" in skills

    def test_no_false_positives(self):
        skills = _extract_skills("We need communication skills and leadership")
        # "communication" is not in COMMON_SKILLS
        assert "communication" not in skills


class TestResumeBullets:
    def test_identifies_bullet_lines(self):
        text = "• Led a team of 10\n- Managed budget of $1M\nRandom sentence"
        bullets = _resume_bullets(text)
        assert any("Led" in b for b in bullets)

    def test_identifies_action_verb_sentences(self):
        text = "Managed a cross-functional team of eight people across three continents"
        bullets = _resume_bullets(text)
        assert len(bullets) > 0


class TestCountBullets:
    def test_quantified_bullets(self):
        bullets = [
            "Led a team of 10 engineers",
            "Reduced costs by $500K",
            "Improved efficiency",
        ]
        assert _count_quantified_bullets(bullets) == 2

    def test_action_verb_bullets(self):
        bullets = [
            "Led a global team",
            "Managed supply chain operations",
            "worked on various projects",
        ]
        assert _count_action_bullets(bullets) == 2


class TestSectionPresence:
    def test_detects_experience(self):
        p = _section_presence("Experience\nSoftware Engineer at Acme 2020-2023")
        assert p["experience"] is True

    def test_detects_email(self):
        p = _section_presence("Name | email@example.com | phone")
        assert p["contact"] is True

    def test_missing_sections(self):
        p = _section_presence("Just some random text without standard sections")
        assert p["experience"] is False
        assert p["contact"] is False


class TestScoreBullets:
    def test_empty_bullets_returns_low_score(self):
        assert _score_bullets([]) == 35

    def test_strong_bullets_score_high(self):
        bullets = [
            "Led cost reduction of $2M annually",
            "Managed team of 15, improving efficiency by 40%",
            "Reduced supply chain costs by 25% through optimization",
            "Implemented forecasting model saving $500K",
        ]
        score = _score_bullets(bullets)
        assert score >= 50
