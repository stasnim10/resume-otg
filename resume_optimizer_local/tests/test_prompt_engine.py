"""
Unit tests for prompt_engine.py
"""
import pytest
from prompt_engine import (
    normalize_role_title,
    build_optimizer_prompt,
    build_builder_prompt,
    _extract_role_specific_priorities,
    _build_prioritization_block,
)


# ── normalize_role_title ──────────────────────────────────────────────────────

class TestNormalizeRoleTitle:
    def test_strips_linkedin_suffix(self):
        assert "Senior Analyst" in normalize_role_title(
            "Senior Analyst | LinkedIn"
        )
        assert "LinkedIn" not in normalize_role_title("Senior Analyst | LinkedIn")

    def test_strips_at_company(self):
        result = normalize_role_title("Product Manager at Acme Corp")
        assert "Product Manager" in result
        assert "Acme" not in result

    def test_strips_remote_suffix(self):
        result = normalize_role_title("Software Engineer - Remote")
        assert "Software Engineer" in result
        assert "Remote" not in result

    def test_strips_location(self):
        result = normalize_role_title("Data Analyst in New York, NY")
        assert "Data Analyst" in result

    def test_strips_hiring_prefix(self):
        result = normalize_role_title("Hiring Senior Product Manager")
        assert "Senior Product Manager" in result
        assert "Hiring" not in result

    def test_empty_string(self):
        assert normalize_role_title("") == ""

    def test_clean_title_unchanged(self):
        assert normalize_role_title("Supply Chain Manager") == "Supply Chain Manager"


# ── _extract_role_specific_priorities ────────────────────────────────────────

class TestExtractRoleSpecificPriorities:
    def test_always_returns_five(self):
        priorities = _extract_role_specific_priorities("some jd", "some role", "some industry")
        assert len(priorities) == 5

    def test_no_duplicates(self):
        priorities = _extract_role_specific_priorities(
            "analytics dashboard kpi supplier procurement cost savings",
            "supply chain analyst",
            "logistics",
        )
        assert len(priorities) == len(set(priorities))

    def test_supply_chain_jd_detects_relevant_priority(self):
        priorities = _extract_role_specific_priorities(
            "Manage supplier relationships and procurement contracts",
            "procurement manager",
            "supply chain",
        )
        assert any("supplier" in p.lower() or "procurement" in p.lower() for p in priorities)

    def test_software_jd_detects_engineering_priority(self):
        priorities = _extract_role_specific_priorities(
            "Backend software development using microservices and cloud APIs",
            "software engineer",
            "technology",
        )
        assert any("software" in p.lower() or "engineering" in p.lower() for p in priorities)

    def test_marketing_jd_detected(self):
        priorities = _extract_role_specific_priorities(
            "Lead marketing campaigns and brand strategy for growth",
            "marketing manager",
            "consumer goods",
        )
        assert any("marketing" in p.lower() or "brand" in p.lower() for p in priorities)

    def test_finance_jd_detected(self):
        priorities = _extract_role_specific_priorities(
            "Financial modeling, DCF valuation, and FP&A budgeting",
            "financial analyst",
            "investment banking",
        )
        assert any("financial" in p.lower() for p in priorities)

    def test_generic_jd_uses_fallbacks(self):
        priorities = _extract_role_specific_priorities("", "", "")
        # Should still return 5 priorities from the fallback list
        assert len(priorities) == 5
        assert any("impact" in p.lower() or "role" in p.lower() for p in priorities)


# ── _build_prioritization_block ───────────────────────────────────────────────

class TestBuildPrioritizationBlock:
    def test_numbered_list(self):
        block = _build_prioritization_block("data analyst", "tech", "sql dashboard reporting")
        lines = [l for l in block.strip().splitlines() if l.strip()]
        assert len(lines) == 5
        assert lines[0].startswith("1.")
        assert lines[4].startswith("5.")


# ── build_optimizer_prompt ────────────────────────────────────────────────────

class TestBuildOptimizerPrompt:
    def _prompt(self, **kwargs):
        defaults = dict(
            resume_text="MBA candidate with experience in supply chain.",
            job_description="Looking for a supply chain analyst with SQL skills.",
            career_stage="Mid-career",
            target_role="Supply Chain Analyst",
            target_industry="Logistics",
        )
        defaults.update(kwargs)
        return build_optimizer_prompt(**defaults)

    def test_contains_resume_text(self):
        p = self._prompt()
        assert "supply chain" in p.lower()

    def test_contains_job_description(self):
        p = self._prompt()
        assert "SQL" in p

    def test_contains_role(self):
        p = self._prompt()
        assert "Supply Chain Analyst" in p

    def test_contains_json_schema(self):
        p = self._prompt()
        assert "summary_replacement" in p
        assert "bullet_replacements" in p

    def test_contains_prioritization_block(self):
        p = self._prompt()
        assert "1." in p  # Numbered priority list

    def test_profile_context_injected_when_provided(self):
        p = self._prompt(profile_context="Relevant project: Managed $50M operations")
        assert "Relevant project" in p

    def test_profile_context_omitted_when_empty(self):
        p = self._prompt(profile_context="")
        assert "PROFILE EVIDENCE" not in p

    def test_normalized_role_in_prompt(self):
        p = self._prompt(target_role="Supply Chain Analyst at Big Corp | LinkedIn")
        # After normalization, "Big Corp" and "LinkedIn" should not appear in the role position
        assert "Big Corp" not in p.split("RESUME TEXT")[0]


# ── build_builder_prompt ──────────────────────────────────────────────────────

class TestBuildBuilderPrompt:
    def _prompt(self, **kwargs):
        defaults = dict(
            full_name="Jane Doe",
            contact_info="jane@example.com | 555-555-5555 | New York, NY",
            education="B.S. Business, State University, May 2024",
            experience_dump="Worked as a barista for two years",
            activities="President of Business Club",
            skills="Excel, SQL, Communication",
            job_description="Looking for a business analyst",
            career_stage="Student",
            target_role="Business Analyst",
        )
        defaults.update(kwargs)
        return build_builder_prompt(**defaults)

    def test_contains_candidate_name(self):
        p = self._prompt()
        assert "Jane Doe" in p

    def test_contains_json_schema(self):
        p = self._prompt()
        assert "basics" in p
        assert "experience" in p

    def test_no_jd_handled_gracefully(self):
        p = self._prompt(job_description="")
        assert "No specific job description" in p

    def test_contains_career_stage(self):
        p = self._prompt()
        assert "Student" in p
