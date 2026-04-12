"""
Unit tests for profile_extractor.py
"""
from profile_extractor import extract_profile_items_from_text


LINKEDIN_PDF_TEXT = """
Contact
14623, Rochester, New York, United States
tasnimsimum@gmail.com
+1 585-625-7752
www.linkedin.com/in/simum-tasnim
Top Skills
Supply Chain
Strategy
Product
Languages
English
Summary
Simum Tasnim
MBA 2026 | Consultant | Product & Strategy | Supply Chain
Where am I going?
I am pursuing my MBA at Simon Business School to deepen my ability to solve ambiguous business problems and to build products, systems, and teams that scale. My long-term goal is to work at the intersection of product, operations, and strategy.
Where am I now?
I bring experience across logistics, consulting-style problem solving, and entrepreneurial work.
Experience
Founder
So Good Wigs
Jan 2025 - Present
- Built the e-commerce infrastructure and backend logistics to enable a scalable launch.
- Conducted customer discovery and translated insights into actionable product improvements.
Country Project Leader
Decathlon
Jun 2023 - Jun 2024
- Led cross-functional projects and improved sourcing and logistics operations.
Education
Simon Business School, University of Rochester
Master of Business Administration (MBA), Technology & Operations Consulting
2025 - 2026
BRAC University
Bachelor of Business Administration, Marketing
2018 - 2022
Certifications
Google Project Management
Awards
Dean's Scholarship
"""


class TestProfileExtractorLinkedInPdf:
    def test_extracts_clean_linkedin_basics(self):
        basics, items = extract_profile_items_from_text(LINKEDIN_PDF_TEXT)

        assert basics["full_name"] == "Simum Tasnim"
        assert basics["email"] == "tasnimsimum@gmail.com"
        assert basics["phone"] == "+1 585-625-7752"
        assert basics["location"] == "14623, Rochester, New York, United States"
        assert basics["linkedin"] == "www.linkedin.com/in/simum-tasnim"
        assert "MBA 2026" in basics["headline"]
        assert basics["summary"].startswith("Where am I going?")
        assert "Where am I now?" not in basics["summary"]
        assert items

    def test_creates_skills_bank_from_top_skills_block(self):
        _, items = extract_profile_items_from_text(LINKEDIN_PDF_TEXT)

        skills_items = [item for item in items if item.item_type == "skills"]
        assert len(skills_items) == 1
        skills_item = skills_items[0]
        assert skills_item.title == "Skills Bank"
        assert "Supply Chain" in skills_item.skills
        assert "Strategy" in skills_item.skills
        assert "Product" in skills_item.skills

    def test_extracts_major_section_items(self):
        _, items = extract_profile_items_from_text(LINKEDIN_PDF_TEXT)

        item_types = {item.item_type for item in items}
        assert "experience" in item_types
        assert "education" in item_types
        assert "certification" in item_types
        assert "award" in item_types

    def test_splits_date_ranges_for_experience_items(self):
        _, items = extract_profile_items_from_text(LINKEDIN_PDF_TEXT)

        founder_item = next(item for item in items if item.title == "Founder")
        assert founder_item.start_date == "Jan 2025"
        assert founder_item.end_date == "Present"
        assert founder_item.is_current is True

        leader_item = next(item for item in items if item.title == "Country Project Leader")
        assert leader_item.start_date == "Jun 2023"
        assert leader_item.end_date == "Jun 2024"
        assert leader_item.is_current is False


GENERIC_LOCATION_TEXT = """
Experience
Operations Analyst
Acme Logistics
Boston, Massachusetts
Jan 2024 - Jun 2025
- Improved reporting and reduced turnaround time.
"""


class TestProfileExtractorMetadata:
    def test_extracts_location_from_chunk(self):
        basics, items = extract_profile_items_from_text(GENERIC_LOCATION_TEXT)
        experience_item = next(item for item in items if item.title == "Operations Analyst")
        assert basics["full_name"] == ""
        assert basics["headline"] == ""
        assert basics["summary"] == ""
        assert basics["location"] == ""
        assert experience_item.organization == "Acme Logistics"
        assert experience_item.location == "Boston, Massachusetts"
        assert experience_item.start_date == "Jan 2024"
        assert experience_item.end_date == "Jun 2025"
