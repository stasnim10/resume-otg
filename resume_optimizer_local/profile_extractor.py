"""
First-pass profile extraction from imported candidate materials.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from profile_schema import ProfileItem


SECTION_HEADERS = {
    "about": "general",
    "summary": "general",
    "profile": "general",
    "education": "education",
    "experience": "experience",
    "experiences": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "projects": "project",
    "academic projects": "project",
    "leadership": "leadership",
    "leadership experience": "leadership",
    "activities": "activity",
    "extracurriculars": "activity",
    "certifications": "certification",
    "licenses & certifications": "certification",
    "licenses and certifications": "certification",
    "courses": "certification",
    "skills": "skills",
    "technical skills": "skills",
}

DATE_PATTERN = re.compile(
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|"
    r"\b\d{4}\s*[-–]\s*(?:present|\d{4})\b|"
    r"\b\d{4}\b",
    flags=re.IGNORECASE,
)

CONTACT_LINE_PATTERN = re.compile(
    r"@|linkedin\.com|github\.com|portfolio|www\.|https?://|"
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}",
    flags=re.IGNORECASE,
)


def _normalize_lines(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.replace("\r", "").split("\n")]
    return [line for line in lines if line]


def _extract_contact_basics(lines: list[str]) -> dict[str, str]:
    basics = {
        "full_name": lines[0] if lines else "",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
    }
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_pattern = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")

    for line in lines[:8]:
        if not basics["email"]:
            email_match = email_pattern.search(line)
            if email_match:
                basics["email"] = email_match.group(0)
        if not basics["phone"]:
            phone_match = phone_pattern.search(line)
            if phone_match:
                basics["phone"] = phone_match.group(0)
        if not basics["linkedin"] and "linkedin.com" in line.lower():
            linkedin_match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/\S+", line, flags=re.IGNORECASE)
            basics["linkedin"] = linkedin_match.group(0).rstrip(".,)") if linkedin_match else line.strip()
        if not basics["location"] and "," in line and len(line.split()) <= 6 and not email_pattern.search(line):
            basics["location"] = line.strip()
        if not basics["location"] and "|" in line:
            for part in [part.strip() for part in line.split("|")]:
                if "," in part and not _looks_like_contact_line(part) and len(part.split()) <= 6:
                    basics["location"] = part
                    break
    return basics


def _looks_like_contact_line(line: str) -> bool:
    return bool(CONTACT_LINE_PATTERN.search(line))


def _looks_like_date_line(line: str) -> bool:
    return bool(DATE_PATTERN.search(line))


def _choose_headline(lines: list[str], full_name: str) -> str:
    for line in lines[1:8]:
        if line == full_name or _looks_like_contact_line(line):
            continue
        if "," in line and len(line.split()) <= 6:
            continue
        if len(line) <= 90:
            return line
    return full_name


def _split_sections(lines: list[str]) -> OrderedDict[str, list[str]]:
    sections: OrderedDict[str, list[str]] = OrderedDict()
    current = "general"
    sections[current] = []
    for line in lines:
        lowered = line.lower().strip(":")
        if lowered in SECTION_HEADERS:
            current = SECTION_HEADERS[lowered]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _extract_skills(lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in lines:
        parts = re.split(r"[,\u2022|/]", line)
        skills.extend([part.strip() for part in parts if part.strip()])
    unique: list[str] = []
    for skill in skills:
        if skill not in unique:
            unique.append(skill)
    return unique[:30]


def _extract_keywords(chunk: list[str]) -> list[str]:
    keyword_source = " ".join(chunk).lower()
    keywords = [word for word in re.findall(r"[a-zA-Z]{4,}", keyword_source)]
    unique: list[str] = []
    for keyword in keywords:
        if keyword not in unique:
            unique.append(keyword)
    return unique[:12]


def _guess_organization(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    for line in lines[:2]:
        if " at " in line.lower():
            parts = re.split(r"\s+[Aa][Tt]\s+", line, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                return parts[1].strip()
        if "|" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) >= 2:
                return parts[1]
        if " - " in line:
            parts = [part.strip() for part in line.split(" - ") if part.strip()]
            if len(parts) >= 2 and parts[0] != title:
                return parts[0]
        if (
            line != title
            and len(line.split()) <= 8
            and not _looks_like_contact_line(line)
            and not _looks_like_date_line(line)
            and not line.startswith(("-", "*", "\u2022"))
        ):
            linkedin_company = line.split(" · ")[0].strip()
            return linkedin_company
    return ""


def _extract_dates(lines: list[str]) -> str:
    for line in lines[:4]:
        if _looks_like_date_line(line):
            return line.strip()
    return ""


def _strip_metadata_lines(lines: list[str], organization: str, dates: str) -> list[str]:
    stripped: list[str] = []
    for line in lines:
        normalized_line = line.strip()
        if organization and (normalized_line == organization or normalized_line.startswith(f"{organization} ·")):
            continue
        if dates and normalized_line == dates:
            continue
        if _looks_like_contact_line(normalized_line):
            continue
        stripped.append(normalized_line)
    return stripped


def _chunk_items(lines: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        clean_line = line.strip()
        if re.match(r"^[-\u2022*]\s+", line):
            current.append(re.sub(r"^[-\u2022*]\s+", "", line).strip())
            continue

        line_could_be_title = (
            bool(re.match(r"^[A-Z][A-Za-z0-9&,'()./ -]{2,}$", clean_line))
            and not _looks_like_date_line(clean_line)
            and " · " not in clean_line
            and not _looks_like_contact_line(clean_line)
            and len(clean_line.split()) <= 10
        )
        current_has_completed_shape = (
            len(current) >= 3
            and (
                any(_looks_like_date_line(existing_line) for existing_line in current)
                or any(len(existing_line.split()) >= 7 for existing_line in current[2:])
            )
        )

        if current and line_could_be_title and current_has_completed_shape:
            chunks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _build_generic_item(item_type: str, chunk: list[str]) -> ProfileItem:
    title = chunk[0] if chunk else ""
    organization = _guess_organization(title, chunk[1:])
    dates = _extract_dates(chunk[1:])
    detail_lines = _strip_metadata_lines(chunk[1:], organization, dates)
    description = "\n".join(detail_lines).strip()
    bullets = [line for line in detail_lines if len(line.split()) > 2][:6]
    keywords = _extract_keywords(chunk)
    return ProfileItem(
        item_type=item_type,
        title=title,
        organization=organization,
        start_date=dates,
        description=description,
        bullets=bullets,
        keywords=keywords,
        confidence_score=0.75 if organization and description else 0.55 if description else 0.4,
    )


def _dedupe_profile_items(items: list[ProfileItem]) -> list[ProfileItem]:
    merged_items: list[ProfileItem] = []
    seen_by_key: dict[tuple[str, str, str], ProfileItem] = {}
    for item in items:
        key = (
            item.item_type.lower(),
            re.sub(r"[^a-z0-9]+", " ", item.title.lower()).strip(),
            re.sub(r"[^a-z0-9]+", " ", item.organization.lower()).strip(),
        )
        if key not in seen_by_key or not key[1]:
            seen_by_key[key] = item
            merged_items.append(item)
            continue
        existing = seen_by_key[key]
        if item.description and item.description not in existing.description:
            existing.description = "\n".join(part for part in [existing.description, item.description] if part)
        for bullet in item.bullets:
            if bullet not in existing.bullets:
                existing.bullets.append(bullet)
        for skill in item.skills:
            if skill not in existing.skills:
                existing.skills.append(skill)
        for keyword in item.keywords:
            if keyword not in existing.keywords:
                existing.keywords.append(keyword)
        existing.keywords = existing.keywords[:12]
        existing.bullets = existing.bullets[:8]
        existing.confidence_score = max(existing.confidence_score, item.confidence_score)
    return merged_items


def extract_profile_items_from_text(raw_text: str) -> tuple[dict[str, str], list[ProfileItem]]:
    """Return inferred profile basics and reusable profile items."""
    lines = _normalize_lines(raw_text)
    sections = _split_sections(lines)

    basics: dict[str, str] = _extract_contact_basics(lines)
    basics.update({"headline": _choose_headline(lines, basics.get("full_name", "")), "summary": ""})
    if "general" in sections and sections["general"]:
        general_lines = sections["general"][:3]
        basics["summary"] = " ".join(general_lines[:2]).strip()

    items: list[ProfileItem] = []
    for section_name, section_lines in sections.items():
        if not section_lines:
            continue
        if section_name == "skills":
            extracted_skills = _extract_skills(section_lines)
            if extracted_skills:
                items.append(
                    ProfileItem(
                        item_type="skills",
                        title="Skills Bank",
                        description=", ".join(extracted_skills),
                        skills=extracted_skills,
                        keywords=extracted_skills[:12],
                        confidence_score=0.7,
                    )
                )
            continue
        if section_name == "general":
            continue

        for chunk in _chunk_items(section_lines):
            item_type = section_name if section_name != "project" else "project"
            item = _build_generic_item(item_type, chunk)
            if section_name == "education":
                item.organization = chunk[0]
            items.append(item)

    return basics, _dedupe_profile_items(items)
