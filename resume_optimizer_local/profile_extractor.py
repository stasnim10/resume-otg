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
    "contact": "general",
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
    "honors-awards": "award",
    "honors and awards": "award",
    "awards": "award",
    "top skills": "skills",
    "languages": "skills",
    "skills": "skills",
    "technical skills": "skills",
}

DATE_PATTERN = re.compile(
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|"
    r"\b\d{4}\s*[-–]\s*(?:present|\d{4})\b|"
    r"\b\d{4}\b",
    flags=re.IGNORECASE,
)
DATE_RANGE_PATTERN = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|\d{4})"
    r"\s*[-–]\s*"
    r"(?P<end>present|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}|\d{4})",
    flags=re.IGNORECASE,
)
DURATION_LINE_PATTERN = re.compile(r"^\d+\s+(?:year|years|month|months)\b(?:\s+\d+\s+(?:month|months))?$", flags=re.IGNORECASE)

CONTACT_LINE_PATTERN = re.compile(
    r"@|linkedin\.com|github\.com|portfolio|www\.|https?://|"
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}",
    flags=re.IGNORECASE,
)

ROLE_WORDS = {
    "analyst", "manager", "engineer", "consultant", "founder", "leader", "specialist",
    "director", "associate", "coordinator", "intern", "developer", "designer", "executive",
    "officer", "strategist", "researcher", "student", "advisor", "assistant", "president",
    "coach", "partner", "owner", "developer", "product", "transport", "logistics", "project",
}

ORG_HINT_WORDS = {
    "university", "school", "college", "institute", "program", "console", "ltd", "limited",
    "inc", "llc", "corp", "corporation", "business", "studio", "technologies", "technology",
}

COMMON_LOCATION_VALUES = {
    "united states", "bangladesh", "france", "india", "cambodia", "ethiopia", "sri lanka",
    "rochester", "new york", "remote",
}


def _normalize_lines(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.replace("\r", "").split("\n")]
    cleaned = [line for line in lines if line]
    return _restructure_linkedin_pdf_lines(cleaned)


def _looks_like_name(line: str) -> bool:
    clean = line.strip()
    lowered = clean.lower().strip(":")
    if not clean or len(clean) > 60:
        return False
    if lowered in SECTION_HEADERS:
        return False
    if lowered in {"top skills", "contact", "languages", "certifications", "honors-awards", "honors and awards", "awards"}:
        return False
    if any(token in clean.lower() for token in ["linkedin", "portfolio", "page ", "@", "summary", "experience", "education"]):
        return False
    role_words = {
        "analyst", "manager", "engineer", "consultant", "founder", "leader", "specialist",
        "director", "associate", "coordinator", "intern", "developer", "designer", "executive",
        "officer", "strategist", "researcher", "student", "advisor", "assistant", "president",
    }
    organization_words = {
        "logistics", "university", "school", "college", "institute", "technologies", "technology",
        "solutions", "systems", "consulting", "group", "company", "corp", "corporation", "inc",
        "llc", "ltd", "labs", "ventures", "capital", "partners", "studio", "agency",
    }
    tokens = re.findall(r"[A-Za-z]+", clean.lower())
    if any(token in role_words for token in tokens):
        return False
    if any(token in organization_words for token in tokens):
        return False
    if not re.match(r"^[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}$", clean):
        return False
    return True


def _restructure_linkedin_pdf_lines(lines: list[str]) -> list[str]:
    """Normalize LinkedIn PDF exports where the contact block appears before the name."""
    if not lines:
        return lines

    page_filtered = [line for line in lines if not re.match(r"^Page\s+\d+\s+of\s+\d+$", line, flags=re.IGNORECASE)]
    linkedin_markers = {"contact", "top skills", "languages", "certifications", "honors-awards", "honors and awards", "awards", "summary"}
    if not any(line.lower().strip(":") in linkedin_markers for line in page_filtered[:40]):
        return page_filtered
    summary_index = next(
        (index for index, line in enumerate(page_filtered[:120]) if line.lower().strip(":") == "summary"),
        None,
    )
    name_index = None
    if summary_index is not None:
        for index in range(summary_index + 1, min(len(page_filtered), summary_index + 7)):
            if _looks_like_name(page_filtered[index]):
                name_index = index
                break
    if summary_index is not None and name_index is None:
        for index in range(max(0, summary_index - 8), summary_index):
            if _looks_like_name(page_filtered[index]):
                name_index = index
                break
    if name_index is None:
        name_index = next((index for index, line in enumerate(page_filtered[:80]) if _looks_like_name(line)), None)
    if name_index is None or name_index == 0:
        return page_filtered

    preamble = page_filtered[:name_index]
    main_lines = page_filtered[name_index:]

    contact_lines: list[str] = []
    skills_lines: list[str] = []
    certifications_lines: list[str] = []
    awards_lines: list[str] = []

    current_block: str | None = None
    for line in preamble:
        lowered = line.lower().strip(":")
        if lowered in {"contact", "top skills", "languages", "certifications", "honors-awards", "honors and awards", "awards"}:
            current_block = lowered
            continue
        if lowered == "summary":
            current_block = None
            continue

        if current_block == "contact":
            contact_lines.append(line)
        elif current_block in {"top skills", "languages"}:
            skills_lines.append(line)
        elif current_block == "certifications":
            certifications_lines.append(line)
        elif current_block in {"honors-awards", "honors and awards", "awards"}:
            awards_lines.append(line)

    rebuilt = main_lines[:]
    insertion_blocks: list[str] = []
    if contact_lines:
        insertion_blocks.extend(["Contact", *contact_lines])
    if skills_lines:
        insertion_blocks.extend(["Skills", *skills_lines])
    if certifications_lines:
        insertion_blocks.extend(["Certifications", *certifications_lines])
    if awards_lines:
        insertion_blocks.extend(["Awards", *awards_lines])

    return rebuilt + insertion_blocks if insertion_blocks else rebuilt


def _extract_contact_basics(lines: list[str]) -> dict[str, str]:
    full_name = lines[0] if lines else ""
    if full_name and not _looks_like_name(full_name):
        full_name = ""
        for candidate in lines[:30]:
            if _looks_like_name(candidate):
                full_name = candidate
                break

    basics = {
        "full_name": full_name,
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
    }
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_pattern = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")

    in_contact_block = False
    for line in lines:
        lowered = line.lower().strip(":")
        if lowered in SECTION_HEADERS and lowered != "contact":
            in_contact_block = False
        if lowered == "contact":
            in_contact_block = True
            continue
        if not in_contact_block:
            continue

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
        if (
            not basics["location"]
            and "," in line
            and "|" not in line
            and len(line.split()) <= 8
            and not email_pattern.search(line)
            and "linkedin" not in line.lower()
        ):
            basics["location"] = line.strip()

    for line in lines:
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
        if (
            not basics["location"]
            and "," in line
            and "|" not in line
            and len(line.split()) <= 8
            and not email_pattern.search(line)
            and "linkedin" not in line.lower()
        ):
            basics["location"] = line.strip()
    return basics


def _looks_like_contact_line(line: str) -> bool:
    return bool(CONTACT_LINE_PATTERN.search(line))


def _looks_like_date_line(line: str) -> bool:
    return bool(DATE_PATTERN.search(line))


def _looks_like_location_only(line: str) -> bool:
    clean = line.strip().strip(".")
    lowered = clean.lower()
    if not clean:
        return False
    if lowered in COMMON_LOCATION_VALUES:
        return True
    if "," in clean:
        parts = [part.strip() for part in clean.split(",") if part.strip()]
        if parts and len(parts) <= 5 and all(part[:1].isupper() for part in parts if part):
            return True
    if len(clean.split()) <= 4 and all(token[:1].isupper() for token in clean.split() if token):
        return lowered in COMMON_LOCATION_VALUES or clean in {"United States", "Bangladesh"}
    return False


def _looks_like_sentence_fragment(line: str) -> bool:
    clean = line.strip()
    if not clean:
        return False
    tokens = re.findall(r"[A-Za-z]+", clean)
    if len(tokens) < 5:
        return False
    lower_ratio = sum(1 for token in tokens[1:] if token.islower()) / max(1, len(tokens) - 1)
    return lower_ratio > 0.45 or clean.endswith(".")


def _looks_like_item_heading(line: str) -> bool:
    clean = line.strip()
    lowered = clean.lower()
    if (
        not clean
        or len(clean) > 90
        or _looks_like_date_line(clean)
        or _looks_like_contact_line(clean)
        or _looks_like_location_only(clean)
        or _looks_like_sentence_fragment(clean)
        or lowered.startswith(("page ", "key responsibilities", "key contributions", "selected for"))
    ):
        return False
    if clean.startswith(("-", "*", "\u2022")):
        return False
    tokens = re.findall(r"[A-Za-z0-9&+'()/-]+", clean)
    if not tokens or len(tokens) > 10:
        return False
    capital_like = sum(1 for token in tokens if token[:1].isupper() or token.isupper() or token.isdigit())
    return (capital_like / len(tokens)) >= 0.65


def _looks_like_role_title(line: str) -> bool:
    clean = line.strip()
    lowered = clean.lower()
    if not clean or _looks_like_location_only(clean) or _looks_like_sentence_fragment(clean):
        return False
    tokens = re.findall(r"[A-Za-z]+", lowered)
    if any(token in ROLE_WORDS for token in tokens):
        return True
    return _looks_like_item_heading(clean)


def _looks_like_organization_name(line: str) -> bool:
    clean = line.strip()
    lowered = clean.lower()
    if not clean or _looks_like_location_only(clean):
        return False
    tokens = re.findall(r"[A-Za-z]+", lowered)
    if any(token in ORG_HINT_WORDS for token in tokens):
        return True
    return _looks_like_item_heading(clean) and not any(token in ROLE_WORDS for token in tokens)


def _choose_headline(lines: list[str], full_name: str) -> str:
    if not full_name:
        return ""
    start_index = 1
    if full_name in lines:
        start_index = lines.index(full_name) + 1
    for line in lines[start_index:start_index + 8]:
        if line == full_name or _looks_like_contact_line(line):
            continue
        if "," in line and len(line.split()) <= 6:
            continue
        if len(line) <= 90:
            return line
    return full_name


def _extract_summary_from_lines(lines: list[str]) -> str:
    """Pull a cleaner summary block, especially for LinkedIn-style imports."""
    for index, line in enumerate(lines):
        if line.lower().strip(":") == "summary":
            collected: list[str] = []
            for next_line in lines[index + 1:]:
                lowered = next_line.lower().strip(":")
                if lowered in SECTION_HEADERS and lowered != "summary":
                    break
                if next_line.lower().startswith("where am i now"):
                    break
                if _looks_like_contact_line(next_line):
                    continue
                collected.append(next_line)
                if len(" ".join(collected)) > 600:
                    break
            summary_text = " ".join(collected[:8]).strip()
            if summary_text:
                return summary_text

    if len(lines) >= 3:
        collected: list[str] = []
        for next_line in lines[2:14]:
            lowered = next_line.lower().strip(":")
            if lowered in SECTION_HEADERS:
                break
            if next_line.lower().startswith("where am i now"):
                break
            if _looks_like_contact_line(next_line):
                continue
            collected.append(next_line)
            if len(" ".join(collected)) > 450:
                break
        summary_text = " ".join(collected[:5]).strip()
        if summary_text:
            return summary_text
    return ""


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


def _parse_date_range(date_text: str) -> tuple[str, str, bool]:
    """Split a detected date range into start, end, and current flag."""
    if not date_text:
        return "", "", False
    match = DATE_RANGE_PATTERN.search(date_text)
    if match:
        start_date = match.group("start").strip()
        end_date = match.group("end").strip()
        is_current = end_date.lower() == "present"
        return start_date, end_date, is_current
    clean = date_text.strip()
    return clean, "", False


def _guess_location(lines: list[str], organization: str, dates: str) -> str:
    """Best-effort location extraction from a chunk."""
    for line in lines[:4]:
        normalized = line.strip()
        if not normalized or normalized == organization or normalized == dates:
            continue
        if _looks_like_contact_line(normalized) or _looks_like_date_line(normalized):
            continue
        if normalized.startswith(("-", "*", "\u2022")):
            continue
        if "|" in normalized:
            parts = [part.strip() for part in normalized.split("|") if part.strip()]
            for part in parts:
                if (
                    "," in part
                    and len(part.split()) <= 10
                    and not _looks_like_date_line(part)
                    and "linkedin" not in part.lower()
                ):
                    return part
        if "," in normalized and len(normalized.split()) <= 10:
            return normalized
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

        line_could_be_title = _looks_like_item_heading(clean_line) and " · " not in clean_line
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


def _build_experience_item(chunk: list[str]) -> ProfileItem:
    header_lines: list[str] = []
    details_start = 0
    for index, line in enumerate(chunk):
        if _looks_like_date_line(line):
            details_start = index
            break
        header_lines.append(line.strip())
    else:
        details_start = len(header_lines)

    clean_headers = [line for line in header_lines if not DURATION_LINE_PATTERN.match(line.strip())]

    title = clean_headers[0] if clean_headers else (header_lines[0] if header_lines else "")
    organization = ""
    if len(clean_headers) >= 2:
        first_line, second_line = clean_headers[0], clean_headers[1]
        if _looks_like_role_title(second_line) and (_looks_like_organization_name(first_line) or second_line != first_line):
            title = second_line
            organization = first_line
        elif _looks_like_role_title(first_line):
            title = first_line
            organization = second_line if not _looks_like_location_only(second_line) else ""
        else:
            title = first_line
            organization = second_line
    elif clean_headers:
        title = clean_headers[0]

    date_text = chunk[details_start].strip() if details_start < len(chunk) and _looks_like_date_line(chunk[details_start]) else ""
    start_date, end_date, is_current = _parse_date_range(date_text)

    remainder = chunk[details_start + 1:] if date_text else chunk[len(header_lines):]
    location = ""
    if remainder and _looks_like_location_only(remainder[0].strip()):
        location = remainder[0].strip()
        remainder = remainder[1:]

    detail_lines = [line.strip() for line in remainder if line.strip()]
    description = "\n".join(detail_lines).strip()
    bullets = [line for line in detail_lines if len(line.split()) > 2][:8]
    keywords = _extract_keywords([title, organization, *detail_lines])

    return ProfileItem(
        item_type="experience",
        title=title,
        organization=organization,
        location=location,
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
        description=description,
        bullets=bullets,
        keywords=keywords,
        confidence_score=0.82 if title and (organization or start_date or bullets) else 0.6,
    )


def _build_education_item(chunk: list[str]) -> ProfileItem:
    school = chunk[0].strip() if chunk else ""
    date_text = _extract_dates(chunk[1:])
    start_date, end_date, is_current = _parse_date_range(date_text)
    detail_lines = _strip_metadata_lines(chunk[1:], "", date_text)
    title = detail_lines[0] if detail_lines else school
    description_lines = detail_lines[1:] if detail_lines else []
    description = "\n".join(description_lines).strip()
    bullets = [line for line in description_lines if len(line.split()) > 2][:4]
    keywords = _extract_keywords(chunk)
    return ProfileItem(
        item_type="education",
        title=title,
        organization=school,
        location="",
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
        description=description,
        bullets=bullets,
        keywords=keywords,
        confidence_score=0.8 if school and title else 0.55,
    )


def _build_generic_item(item_type: str, chunk: list[str]) -> ProfileItem:
    if item_type == "experience":
        return _build_experience_item(chunk)
    if item_type == "education":
        return _build_education_item(chunk)

    title = chunk[0] if chunk else ""
    organization = _guess_organization(title, chunk[1:])
    dates = _extract_dates(chunk[1:])
    start_date, end_date, is_current = _parse_date_range(dates)
    location = _guess_location(chunk[1:], organization, dates)
    detail_lines = _strip_metadata_lines(chunk[1:], organization, dates)
    description = "\n".join(detail_lines).strip()
    bullets = [line for line in detail_lines if len(line.split()) > 2][:6]
    keywords = _extract_keywords(chunk)
    return ProfileItem(
        item_type=item_type,
        title=title,
        organization=organization,
        location=location,
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
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


def _is_noise_profile_item(item: ProfileItem) -> bool:
    title = item.title.strip()
    if not title:
        return True
    if title.lower().startswith(("page ", "key responsibilities", "key contributions")):
        return True
    if _looks_like_location_only(title) and item.item_type != "education":
        return True
    if _looks_like_sentence_fragment(title) and not item.organization and not item.start_date:
        return True
    if item.item_type == "experience":
        if not (item.organization or item.start_date or item.bullets):
            return True
        if len(title.split()) > 10:
            return True
    if item.item_type in {"award", "certification"} and len(title) < 4:
        return True
    return False


def extract_profile_items_from_text(raw_text: str) -> tuple[dict[str, str], list[ProfileItem]]:
    """Return inferred profile basics and reusable profile items."""
    lines = _normalize_lines(raw_text)
    sections = _split_sections(lines)

    basics: dict[str, str] = _extract_contact_basics(lines)
    basics.update({"headline": _choose_headline(lines, basics.get("full_name", "")), "summary": ""})
    extracted_summary = _extract_summary_from_lines(lines)
    if extracted_summary:
        basics["summary"] = extracted_summary
    elif "general" in sections and sections["general"]:
        general_lines = [
            line for line in sections["general"]
            if line != basics.get("full_name", "")
            and line != basics.get("headline", "")
            and not _looks_like_contact_line(line)
            and not _looks_like_name(line)
        ]
        basics["summary"] = " ".join(general_lines[:4]).strip()

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

    deduped_items = [item for item in _dedupe_profile_items(items) if not _is_noise_profile_item(item)]
    if not basics.get("full_name"):
        basics["headline"] = ""
        if not (basics.get("email") or basics.get("phone") or basics.get("linkedin")):
            basics["summary"] = ""
            basics["location"] = ""

    return basics, deduped_items
