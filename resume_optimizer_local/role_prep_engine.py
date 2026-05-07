"""
Build a copy-ready role prep kit from a saved job and Career Profile.

This module is intentionally pure Python: no Streamlit, no persistence, no LLM
calls. The UI can render the returned RolePrepKit however it wants.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from profile_matcher import extract_key_signals, rank_profile_items
from profile_schema import CareerProfile, ProfileItem


MAX_TOP_ITEMS = 8
MIN_TOP_ITEMS = 3
MATCH_THRESHOLD = 6.0
MIN_MEANINGFUL_TERMS = 2

GENERIC_MATCH_WORDS = {
    "ability",
    "able",
    "across",
    "advanced",
    "analysis",
    "apply",
    "based",
    "build",
    "building",
    "business",
    "capacity",
    "chain",
    "change",
    "collaborate",
    "company",
    "complex",
    "cross",
    "data",
    "deliver",
    "design",
    "development",
    "drive",
    "ensure",
    "environment",
    "excellent",
    "execute",
    "experience",
    "functional",
    "global",
    "high",
    "impact",
    "improve",
    "including",
    "key",
    "lead",
    "leading",
    "management",
    "manager",
    "multiple",
    "new",
    "operations",
    "partners",
    "process",
    "program",
    "project",
    "role",
    "skills",
    "stakeholders",
    "strategic",
    "strategy",
    "strong",
    "support",
    "systems",
    "team",
    "teams",
    "using",
    "work",
    "working",
    "years",
}


@dataclass
class RolePrepKit:
    """Prepared evidence and prompts for one tracked job."""

    job_title: str
    company: str
    jd_signals: dict[str, Any]
    top_items: list[dict[str, Any]]
    gap_signals: dict[str, Any]
    markdown_block: str
    prompts: dict[str, str]
    is_thin: bool


def _date_range(item: ProfileItem) -> str:
    end = item.end_date or ("Present" if item.is_current else "")
    return " - ".join(part for part in [item.start_date, end] if part)


def _item_text(item: ProfileItem) -> str:
    parts = [
        item.title,
        item.organization,
        item.location,
        item.description,
        " ".join(item.bullets),
        " ".join(item.skills),
        " ".join(item.tools),
        " ".join(item.keywords),
        " ".join(item.industry_tags),
        " ".join(item.function_tags),
    ]
    return " ".join(part for part in parts if part)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z+\-]{2,}", text.lower())
        if token not in GENERIC_MATCH_WORDS
    }


def _top_matching_bullets(item: ProfileItem, jd_keywords: set[str], limit: int = 3) -> list[str]:
    scored: list[tuple[int, str]] = []
    for bullet in item.bullets:
        tokens = {token.lower().strip(".,;:()[]{}") for token in bullet.split()}
        score = len(tokens & jd_keywords)
        scored.append((score, bullet))
    scored.sort(key=lambda row: (-row[0], item.bullets.index(row[1]) if row[1] in item.bullets else 0))
    matches = [bullet for score, bullet in scored if score > 0][:limit]
    if matches:
        return matches
    return item.bullets[:limit]


def _meaningful_terms(item: ProfileItem, jd_keywords: set[str]) -> list[str]:
    item_tokens = _tokenize(_item_text(item))
    terms = sorted(item_tokens & jd_keywords)
    return terms[:8]


def _matched_skills(item: ProfileItem, jd_keywords: set[str]) -> list[str]:
    matched: list[str] = []
    for skill in item.skills + item.tools + item.keywords:
        skill_tokens = _tokenize(skill)
        if skill_tokens & jd_keywords:
            matched.append(skill)
    return list(dict.fromkeys(matched))[:8]


def _display_title(item: ProfileItem) -> str:
    title_bits = [part.strip() for part in [item.organization, item.title] if part and part.strip()]
    if title_bits:
        return " - ".join(title_bits)
    if item.item_type == "skills":
        skills = [skill for skill in item.skills + item.tools if skill.strip()]
        if skills:
            return f"Skills: {', '.join(skills[:4])}"
        return ""
    if item.description.strip():
        return item.description.strip().split(".")[0][:80]
    return ""


def _match_label(score: float, linked: bool, meaningful_terms: list[str], matched_skills: list[str]) -> str:
    if linked or score >= 10 or len(meaningful_terms) >= 5 or len(matched_skills) >= 3:
        return "Strong match"
    if score >= 7 or len(meaningful_terms) >= 3 or len(matched_skills) >= 2:
        return "Good match"
    return "Partial match"


def _plain_reason(linked: bool, meaningful_terms: list[str], matched_skills: list[str]) -> str:
    if linked:
        return "You already selected this evidence for this job."
    signals = matched_skills[:3] or [term.replace("-", " ") for term in meaningful_terms[:3]]
    if signals:
        return f"Relevant because it connects to {', '.join(signals)}."
    return "Potentially relevant, but review it before using it."


def _has_enough_relevance(
    score: float,
    linked: bool,
    meaningful_terms: list[str],
    matched_skills: list[str],
) -> bool:
    if linked:
        return True
    if score < MATCH_THRESHOLD:
        return False
    if matched_skills:
        return True
    return len(meaningful_terms) >= MIN_MEANINGFUL_TERMS


def _ranked_top_items(
    ranked_results: list[dict[str, Any]],
    linked_item_ids: set[str],
    jd_keywords: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    enriched: list[dict[str, Any]] = []
    for result in ranked_results:
        item: ProfileItem = result["item"]
        score = float(result.get("score") or 0)
        linked = str(item.id) in linked_item_ids
        meaningful_terms = _meaningful_terms(item, jd_keywords)
        matched_skills = _matched_skills(item, jd_keywords)
        display_title = _display_title(item)
        if linked:
            score += 2.0
        if not display_title:
            continue
        if not _has_enough_relevance(score, linked, meaningful_terms, matched_skills):
            continue
        enriched.append(
            {
                "item": item,
                "score": score,
                "display_title": display_title,
                "match_label": _match_label(score, linked, meaningful_terms, matched_skills),
                "plain_reason": _plain_reason(linked, meaningful_terms, matched_skills),
                "meaningful_terms": meaningful_terms,
                "matched_bullets": _top_matching_bullets(item, jd_keywords),
                "matched_skills": matched_skills,
            }
        )

    enriched.sort(
        key=lambda row: (
            -row["score"],
            str(row["item"].id) not in linked_item_ids,
            row["item"].item_type,
            row["item"].title.lower(),
        )
    )
    selected = enriched[:MAX_TOP_ITEMS]
    return selected[:MAX_TOP_ITEMS], len(selected) < MIN_TOP_ITEMS


def _profile_heading(profile: CareerProfile) -> str:
    name = profile.full_name.strip() or "Candidate"
    headline = profile.headline.strip()
    if headline:
        return f"# {name} - Role Prep Context\n\n**Headline:** {headline}"
    return f"# {name} - Role Prep Context"


def _build_markdown(
    profile: CareerProfile,
    job: dict[str, Any],
    top_items: list[dict[str, Any]],
    gap_signals: dict[str, Any],
    is_thin: bool,
) -> str:
    job_title = (job.get("job_title") or "Target role").strip()
    company = (job.get("company") or "Target company").strip()
    lines: list[str] = [
        _profile_heading(profile),
        "",
        "## Target Role",
        f"- Role: {job_title}",
        f"- Company: {company}",
    ]
    if job.get("role_family"):
        lines.append(f"- Role family: {job['role_family']}")
    if job.get("industry"):
        lines.append(f"- Industry: {job['industry']}")

    if profile.summary:
        lines.extend(["", "## Profile Summary", profile.summary.strip()])

    if profile.target_roles:
        lines.extend(["", "## Target Roles", ", ".join(profile.target_roles)])

    lines.extend(["", "## Most Relevant Evidence"])
    if not top_items:
        lines.append("- No saved profile evidence found yet.")
    for idx, result in enumerate(top_items, start=1):
        item: ProfileItem = result["item"]
        title = result.get("display_title") or _display_title(item) or item.item_type.title()
        date = _date_range(item)
        lines.extend(["", f"### {idx}. {title}"])
        if date:
            lines.append(f"Dates: {date}")
        if result.get("match_label"):
            lines.append(f"Relevance: {result['match_label']}")
        if item.description:
            lines.append(f"Context: {item.description.strip()}")
        bullets = result.get("matched_bullets") or item.bullets[:3]
        if bullets:
            lines.append("Evidence:")
            for bullet in bullets:
                lines.append(f"- {bullet}")
        skills = result.get("matched_skills") or item.skills[:8]
        if skills:
            lines.append(f"Relevant skills/tools: {', '.join(skills)}")
        if result.get("plain_reason"):
            lines.append(f"Why this matters: {result['plain_reason']}")

    gaps = gap_signals.get("gaps") or []
    if gaps:
        lines.extend(["", "## Possible Gaps To Address"])
        for gap in gaps:
            lines.append(f"- {gap.get('signal', 'Missing signal')}")
    if is_thin:
        lines.extend(
            [
                "",
                "## Evidence Note",
                "The saved profile has limited high-confidence overlap with this job. Add or verify more examples before finalizing application materials.",
            ]
        )

    lines.extend(
        [
            "",
            "## Instructions for AI",
            "- Use only the facts in this profile unless I provide more information.",
            "- Prioritize evidence that matches the target role and job description.",
            "- Preserve metrics, scope, dates, employers, and titles accurately.",
            "- If a requirement is not supported by the profile, call it out instead of inventing experience.",
        ]
    )
    return "\n".join(lines).strip()


def _prompt(task: str, markdown_block: str, job_description: str) -> str:
    return (
        "Here is my role-specific career context:\n\n"
        f"{markdown_block}\n\n"
        "Here is the job description:\n\n"
        f"{job_description.strip()}\n\n"
        f"Task:\n{task}\n"
    ).strip()


def _build_prompts(markdown_block: str, job_description: str) -> dict[str, str]:
    return {
        "Cover Letter": _prompt(
            "- Write a concise, compelling cover letter for this role.\n"
            "- Make it specific to the company and job requirements.\n"
            "- Use the strongest matching evidence and impact metrics from my profile.\n"
            "- Keep the tone confident, warm, and direct. Aim for 3 short paragraphs.",
            markdown_block,
            job_description,
        ),
        "Interview": _prompt(
            "- Prepare behavioral interview talking points for this role.\n"
            "- Create STAR-style stories using my real profile evidence.\n"
            "- Include the 5 most likely interview questions with concise answer outlines.\n"
            "- Flag any gaps where I need to prepare an honest explanation.",
            markdown_block,
            job_description,
        ),
        "Recruiter Outreach": _prompt(
            "- Write a concise outreach message to a recruiter or hiring manager at this company.\n"
            "- Keep it under 150 words.\n"
            "- Reference the specific role and why I am a strong fit.\n"
            "- Use a confident but not pushy tone.\n"
            "- Make it suitable for a LinkedIn message or a cold email.",
            markdown_block,
            job_description,
        ),
        "Portfolio": _prompt(
            "- Using my career profile, generate content for a professional portfolio page.\n"
            "- Write an About section, an Experience section highlighting my top 3 roles, "
            "a Skills section, and a Projects section if applicable.\n"
            "- Format it cleanly so I can paste it directly into Notion, a personal website, "
            "or LinkedIn's Featured section.\n"
            "- Keep the language active and impact-focused.",
            markdown_block,
            job_description,
        ),
    }


def build_role_prep(
    job: dict[str, Any],
    items: list[ProfileItem],
    profile: CareerProfile,
    linked_item_ids: set[str] | None = None,
) -> RolePrepKit:
    """Assemble a role-specific prep kit from existing profile and job data."""
    job_description = (job.get("jd_text") or "").strip()
    linked_ids = linked_item_ids or set()
    active_items = [item for item in items if item.visibility == "active"]
    job_signals, ranked_results = rank_profile_items(
        active_items,
        job_description,
        target_role=job.get("job_title") or job.get("role_family") or "",
        target_industry=job.get("industry") or "",
    )
    jd_keywords = set(job_signals.get("token_set") or set())
    top_items, is_thin = _ranked_top_items(ranked_results, linked_ids, jd_keywords)
    assembled_profile_text = "\n\n".join(_item_text(row["item"]) for row in top_items)
    gap_signals = extract_key_signals(assembled_profile_text, job_description)
    markdown_block = _build_markdown(profile, job, top_items, gap_signals, is_thin)
    prompts = _build_prompts(markdown_block, job_description)
    return RolePrepKit(
        job_title=(job.get("job_title") or "").strip(),
        company=(job.get("company") or "").strip(),
        jd_signals=job_signals,
        top_items=top_items,
        gap_signals=gap_signals,
        markdown_block=markdown_block,
        prompts=prompts,
        is_thin=is_thin,
    )
