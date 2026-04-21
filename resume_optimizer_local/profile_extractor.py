"""
First-pass profile extraction from imported candidate materials.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from profile_schema import ProfileItem


SECTION_HEADERS = {
    "about": "general",
    "summary": "general",
    "profile": "general",
    "top skills": "skills",
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
    "volunteer experience": "activity",
    "volunteering": "activity",
    "certifications": "certification",
    "licenses & certifications": "certification",
    "licenses and certifications": "certification",
    "courses": "certification",
    "honors & awards": "award",
    "honors and awards": "award",
    "awards": "award",
    "publications": "general",
    "recommendations": "general",
    "languages": "skills",
    "interests": "general",
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "competencies": "skills",
}

DATE_PATTERN = re.compile(
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|"
    r"\b\d{4}\s*[-–]\s*(?:present|\d{4})\b|"
    r"\b\d{4}\b",
    flags=re.IGNORECASE,
)

_MONTH_ABBR_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

_LINKEDIN_NOISE = re.compile(
    r"^(?:page\s+\d+|linkedin|see\s+(?:all|more|profile|connections)|"
    r"\d+\s+connections?|\d+\s+followers?|message|connect|follow|"
    r"profile\s+strength|all\s+filters|contact\s+info|"
    r"show\s+all\s+\d+|load\s+more|www\.linkedin\.com)$",
    flags=re.IGNORECASE,
)

CONTACT_LINE_PATTERN = re.compile(
    r"@|linkedin\.com|github\.com|portfolio|www\.|https?://|"
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}",
    flags=re.IGNORECASE,
)

_LOCATION_WORDS = {
    "bangladesh", "ethiopia", "france", "sri", "lanka", "india", "cambodia",
    "rochester", "york", "united", "states", "usa", "ny", "singapore",
}
_FILLER_SKILL_WORDS = {
    "outstanding", "performer", "year", "completion", "award", "leveraging",
    "strategic", "insights", "future", "trends", "learning", "project",
    "management", "business", "startup", "transformation", "product",
    "strategy", "consultant",
}
_VERB_HEAVY_WORDS = {
    "audited", "managed", "worked", "created", "improved", "coached", "supported",
    "developed", "led", "built", "drove", "delivered",
}


def _normalize_date(token: str) -> str:
    """Normalize a single date token to MM/YYYY."""
    token = token.strip()
    if not token or token.lower() == "present":
        return token
    if re.match(r"^\d{2}/\d{4}$", token):
        return token
    m = re.match(r"^([A-Za-z]+)\.?\s+(\d{4})$", token)
    if m:
        month_num = _MONTH_ABBR_MAP.get(m.group(1).lower().rstrip("."), "")
        if month_num:
            return f"{month_num}/{m.group(2)}"
    if re.match(r"^\d{4}$", token):
        return token
    return token


def _parse_date_range(date_line: str) -> tuple[str, str, bool]:
    """Parse a date range into (start_date, end_date, is_current).

    Handles: "January 2020 – Present · 4 yrs", "Jan 2020 - Dec 2022",
             "2020 – 2022", "Jun 2022", "(4 months)"
    """
    if not date_line:
        return "", "", False
    # Strip LinkedIn duration noise
    cleaned = re.sub(r"[·•]\s*\d+\s*(?:yrs?|years?|mos?|months?).*$", "", date_line, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\d+\s*(?:yrs?|years?|mos?|months?)[^)]*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip("·•–-—  ")

    is_current = bool(re.search(r"\bpresent\b", cleaned, flags=re.IGNORECASE))
    parts = re.split(r"\s*[–—-]\s*", cleaned, maxsplit=1)
    start_raw = parts[0].strip() if parts else ""
    end_raw   = parts[1].strip() if len(parts) > 1 else ""

    def _first_token(s: str) -> str:
        m = re.search(
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}",
            s, flags=re.IGNORECASE,
        )
        if m:
            return _normalize_date(m.group(0))
        m2 = re.search(r"\b\d{4}\b", s)
        return m2.group(0) if m2 else ""

    start_date = _first_token(start_raw)
    end_date   = "" if is_current else _first_token(end_raw)
    return start_date, end_date, is_current


def _normalize_lines(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.replace("\r", "").split("\n")]
    return [line for line in lines if line and not _LINKEDIN_NOISE.match(line)]


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
        cleaned = re.sub(r"\s+", " ", skill).strip(" -•\t")
        lowered = cleaned.lower()
        token_set = set(re.findall(r"[a-zA-Z]+", lowered))
        if not cleaned or len(cleaned) < 2 or len(cleaned) > 48:
            continue
        if "," in cleaned and cleaned.count(",") >= 2:
            continue
        if lowered in _FILLER_SKILL_WORDS or lowered in _LOCATION_WORDS:
            continue
        if token_set and token_set.issubset(_LOCATION_WORDS | _FILLER_SKILL_WORDS):
            continue
        if token_set & _VERB_HEAVY_WORDS:
            continue
        if re.search(r"\b(linkedin|portfolio|email|phone)\b", lowered):
            continue
        if cleaned not in unique:
            unique.append(cleaned)
    return unique[:30]


def _looks_like_invalid_title(line: str) -> bool:
    cleaned = re.sub(r"\s+", " ", line).strip(" -•\t")
    lowered = cleaned.lower()
    words = re.findall(r"[a-zA-Z]+", lowered)
    token_set = set(words)
    if not cleaned:
        return True
    if cleaned.count(",") >= 2:
        return True
    if token_set and token_set.issubset(_LOCATION_WORDS):
        return True
    if token_set and token_set.issubset(_LOCATION_WORDS | _FILLER_SKILL_WORDS):
        return True
    if token_set & _VERB_HEAVY_WORDS and len(words) > 4:
        return True
    return cleaned.endswith(".")


def _extract_keywords(chunk: list[str]) -> list[str]:
    keyword_source = " ".join(chunk).lower()
    keywords = re.findall(r"[a-zA-Z]{4,}", keyword_source)
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


def _extract_dates(lines: list[str]) -> tuple[str, str, bool]:
    """Return (start_date, end_date, is_current) from the first date-like line."""
    for line in lines[:4]:
        if _looks_like_date_line(line):
            return _parse_date_range(line.strip())
    return "", "", False


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

        # Detect if this line is likely a sentence rather than a job title
        is_sentence = (
            clean_line.endswith('.')
            or clean_line.lower().startswith(('this ', 'these ', 'the ', 'a ', 'an ', 'page '))
            or re.search(r'\b(strengthened|increased|managed|led|developed|worked|created|improved)\b', clean_line.lower())
        )

        line_could_be_title = (
            bool(re.match(r"^[A-Z][A-Za-z0-9&,'()./ -]{2,}$", clean_line))
            and not _looks_like_date_line(clean_line)
            and " · " not in clean_line
            and not _looks_like_contact_line(clean_line)
            and len(clean_line.split()) <= 6  # Reduced from 10 to avoid sentences like "This experience strengthened..."
            and not is_sentence  # Reject obvious prose
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
    if _looks_like_invalid_title(title):
        title = ""
    organization = _guess_organization(title, chunk[1:])
    start_date, end_date, is_current = _extract_dates(chunk[1:])
    date_line = next((ln for ln in chunk[1:4] if _looks_like_date_line(ln)), "")
    detail_lines = _strip_metadata_lines(chunk[1:], organization, date_line)
    description = "\n".join(detail_lines).strip()
    bullets = [line for line in detail_lines if len(line.split()) > 2][:6]
    keywords = _extract_keywords(chunk)

    has_dates = bool(start_date or end_date)
    confidence = 0.4
    if organization:
        confidence += 0.15
    if has_dates:
        confidence += 0.15
    if description and len(description) > 20:
        confidence += 0.15
    if len(bullets) >= 2:
        confidence += 0.1
    if len(keywords) >= 3:
        confidence += 0.1
    if organization and description and (has_dates or len(bullets) >= 2):
        confidence = max(confidence, 0.8)

    return ProfileItem(
        item_type=item_type,
        title=title or (organization if not _looks_like_invalid_title(organization) else ""),
        organization=organization,
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
        description=description,
        bullets=bullets,
        keywords=keywords,
        confidence_score=min(0.95, confidence),
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
            if not item.title and not item.organization:
                continue
            items.append(item)

    return basics, _dedupe_profile_items(items)


_CAREER_STAGES = [
    "Student", "Early Career", "Mid-Level", "Manager", "Executive", "Career Pivot"
]


def extract_profile_basics(resume_text: str) -> dict[str, Any]:
    """Auto-extract profile basics from resume text for pre-filling the profile form.

    Returns a dict with keys: name, email, phone, location, career_stage,
    industries (list[str]), resume_snippet (str).
    """
    lines = resume_text.split("\n")

    # Name — usually the first short, all-alpha line
    name = ""
    for line in lines[:10]:
        clean_line = line.strip()
        if clean_line and len(clean_line) < 50 and len(clean_line.split()) <= 4:
            if not any(char.isdigit() for char in clean_line):
                name = clean_line
                break

    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resume_text)
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(r'(\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', resume_text)
    phone = phone_match.group(0) if phone_match else ""

    location = ""
    location_match = re.search(
        r'(?:Location|City|Based|Address)[:\s]+([A-Z][a-z\s]+(?:,\s*[A-Z]{2})?)',
        resume_text,
        re.IGNORECASE,
    )
    if location_match:
        location = location_match.group(1).strip()

    years_match = re.findall(
        r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|in|project)',
        resume_text,
        re.IGNORECASE,
    )
    years_exp = max((int(m) for m in years_match), default=0)

    if years_exp < 2:
        career_stage = "Student"
    elif years_exp < 5:
        career_stage = "Early Career"
    elif years_exp < 10:
        career_stage = "Mid-Level"
    elif years_exp < 15:
        career_stage = "Manager"
    else:
        career_stage = "Executive"

    industries: set[str] = set()
    job_title_match = re.search(r'(?:Title|Role|Position)[:\s]+([^\n]+)', resume_text, re.IGNORECASE)
    if job_title_match:
        title = job_title_match.group(1).lower()
        if any(w in title for w in ("engineer", "developer", "tech", "software")):
            industries.add("Technology")
        if any(w in title for w in ("data", "analyst", "science")):
            industries.add("Technology")
        if any(w in title for w in ("consult", "adviso")):
            industries.add("Consulting")
        if any(w in title for w in ("finance", "accounting", "cfo")):
            industries.add("Finance")
        if any(w in title for w in ("market", "sales", "business")):
            industries.add("General Business")
    if not industries:
        industries = {"General Business"}

    bullets = re.findall(r'[•\-\*]\s*(.{20,150})', resume_text[:2000])
    resume_snippet = "\n".join(bullets[:3]) if bullets else ""

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "career_stage": career_stage,
        "industries": list(industries),
        "resume_snippet": resume_snippet[:500],
    }
