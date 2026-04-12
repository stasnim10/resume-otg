"""
Deterministic resume / job fit evaluator.

This module intentionally avoids paid AI calls. It gives the app a fast,
explainable first opinion before the user spends time running an optimization.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from profile_schema import ProfileItem


STOPWORDS = {
    "about",
    "above",
    "across",
    "after",
    "again",
    "against",
    "also",
    "and",
    "another",
    "apply",
    "are",
    "because",
    "been",
    "being",
    "candidate",
    "company",
    "description",
    "during",
    "each",
    "from",
    "have",
    "help",
    "into",
    "including",
    "include",
    "included",
    "includes",
    "more",
    "must",
    "our",
    "own",
    "position",
    "preferred",
    "required",
    "requirements",
    "responsibilities",
    "role",
    "should",
    "team",
    "that",
    "their",
    "them",
    "they",
    "this",
    "through",
    "using",
    "with",
    "will",
    "work",
    "you",
    "your",
}

ACTION_VERBS = {
    "accelerated",
    "achieved",
    "analyzed",
    "automated",
    "built",
    "collaborated",
    "created",
    "delivered",
    "designed",
    "developed",
    "drove",
    "enabled",
    "executed",
    "improved",
    "increased",
    "launched",
    "led",
    "managed",
    "optimized",
    "owned",
    "reduced",
    "resolved",
    "saved",
    "scaled",
    "shipped",
    "streamlined",
    "supported",
}

COMMON_SKILLS = [
    "excel",
    "sql",
    "python",
    "tableau",
    "power bi",
    "salesforce",
    "sap",
    "erp",
    "forecasting",
    "analytics",
    "dashboard",
    "inventory",
    "logistics",
    "procurement",
    "operations",
    "project management",
    "stakeholder",
    "financial modeling",
    "market research",
    "data analysis",
    "process improvement",
]


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z+\-]{2,}", text.lower())
    return [token for token in tokens if token not in STOPWORDS]


def _top_keywords(text: str, limit: int = 22) -> list[str]:
    counts = Counter(_tokenize(text))
    return [word for word, _count in counts.most_common(limit)]


def _extract_skills(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        if re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", lowered):
            found.append(skill)
    return found


def _resume_bullets(resume_text: str) -> list[str]:
    bullet_lines = []
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if re.match(r"^[•\-\*\u2023\u25e6]\s+", cleaned):
            bullet_lines.append(re.sub(r"^[•\-\*\u2023\u25e6]\s+", "", cleaned).strip())
        elif len(cleaned.split()) >= 8 and cleaned.split()[0].lower().rstrip(",:;") in ACTION_VERBS:
            bullet_lines.append(cleaned)
    return bullet_lines


def _count_quantified_bullets(bullets: list[str]) -> int:
    return sum(1 for bullet in bullets if re.search(r"(\d+|%|\$|million|thousand|hours?|days?|weeks?|months?)", bullet.lower()))


def _count_action_bullets(bullets: list[str]) -> int:
    count = 0
    for bullet in bullets:
        words = _tokenize(bullet)
        if words and words[0].lower().rstrip(",:;") in ACTION_VERBS:
            count += 1
    return count


def _section_presence(resume_text: str) -> dict[str, bool]:
    lowered = resume_text.lower()
    return {
        "experience": any(marker in lowered for marker in ["experience", "employment", "work history"]),
        "education": "education" in lowered,
        "skills": any(marker in lowered for marker in ["skills", "technical skills", "tools"]),
        "contact": bool(re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", resume_text)) or bool(re.search(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}", resume_text)),
    }


def _score_ratio(matched_count: int, total_count: int, floor_when_empty: int = 65) -> int:
    if total_count == 0:
        return floor_when_empty
    return round(100 * matched_count / total_count)


def _score_bullets(bullets: list[str]) -> int:
    if not bullets:
        return 35
    quantified_ratio = _score_ratio(_count_quantified_bullets(bullets), len(bullets), 40)
    action_ratio = _score_ratio(_count_action_bullets(bullets), len(bullets), 45)
    bullet_count_score = min(100, 45 + len(bullets) * 6)
    return round(0.42 * quantified_ratio + 0.36 * action_ratio + 0.22 * bullet_count_score)


def _score_ats(resume_text: str, bullets: list[str]) -> tuple[int, list[str]]:
    sections = _section_presence(resume_text)
    warnings = []
    score = 100

    if not sections["contact"]:
        score -= 18
        warnings.append("Add an email or phone number so recruiters can contact you quickly.")
    if not sections["experience"]:
        score -= 18
        warnings.append("Make the experience section easy to find with a standard section heading.")
    if not sections["education"]:
        score -= 12
        warnings.append("Add a clear education section.")
    if not sections["skills"]:
        score -= 10
        warnings.append("Add a compact skills section with tools and role-specific capabilities.")
    if len(resume_text.split()) > 950:
        score -= 8
        warnings.append("Your resume may be long for a one-page resume. Consider trimming lower-relevance detail.")
    if len(bullets) < 4:
        score -= 10
        warnings.append("Add more achievement-focused bullets. Short resumes can under-sell your evidence.")

    return max(0, score), warnings


def _score_profile_evidence(selected_profile_items: list[ProfileItem], job_keywords: set[str]) -> tuple[int, list[str]]:
    if not selected_profile_items:
        return 0, []

    evidence_tokens: set[str] = set()
    evidence_titles: list[str] = []
    for item in selected_profile_items:
        evidence_titles.append(item.title or item.item_type.title())
        evidence_tokens.update(
            _tokenize(
                " ".join(
                    [
                        item.title,
                        item.organization,
                        item.description,
                        " ".join(item.bullets),
                        " ".join(item.skills),
                        " ".join(item.keywords),
                    ]
                )
            )
        )
    overlap = sorted(evidence_tokens & job_keywords)
    score = min(100, 45 + len(overlap) * 7 + len(selected_profile_items) * 4)
    return score, evidence_titles[:4]


def evaluate_resume_fit(
    resume_text: str,
    job_description: str,
    selected_profile_items: list[ProfileItem] | None = None,
) -> dict[str, Any]:
    """Return an explainable fit report for resume + job + optional profile evidence."""
    selected_profile_items = selected_profile_items or []
    resume_keywords = set(_tokenize(resume_text))
    job_keywords_list = _top_keywords(job_description)
    job_keywords = set(job_keywords_list)

    matched_keywords = [keyword for keyword in job_keywords_list if keyword in resume_keywords]
    missing_keywords = [keyword for keyword in job_keywords_list if keyword not in resume_keywords]

    job_skills = _extract_skills(job_description)
    resume_skills = set(_extract_skills(resume_text))
    matched_skills = [skill for skill in job_skills if skill in resume_skills]
    missing_skills = [skill for skill in job_skills if skill not in resume_skills]

    bullets = _resume_bullets(resume_text)
    quantified_bullet_count = _count_quantified_bullets(bullets)
    action_verb_bullet_count = _count_action_bullets(bullets)

    keyword_score = _score_ratio(len(matched_keywords), len(job_keywords_list))
    skill_score = _score_ratio(len(matched_skills), len(job_skills), floor_when_empty=70)
    bullet_score = _score_bullets(bullets)
    ats_score, warnings = _score_ats(resume_text, bullets)
    evidence_score, selected_evidence_titles = _score_profile_evidence(selected_profile_items, job_keywords)

    weighted_scores = [
        (keyword_score, 0.32),
        (skill_score, 0.22),
        (bullet_score, 0.2),
        (ats_score, 0.18),
    ]
    if selected_profile_items:
        weighted_scores.append((evidence_score, 0.08))
        weight_total = sum(weight for _score, weight in weighted_scores)
        overall_score = round(sum(score * weight for score, weight in weighted_scores) / weight_total)
    else:
        overall_score = round(sum(score * weight for score, weight in weighted_scores) / 0.92)

    recommendations = []
    if missing_keywords:
        recommendations.append(f"Consider adding honest evidence for: {', '.join(missing_keywords[:6])}.")
    if missing_skills:
        recommendations.append(f"The job mentions these tools/skills that are not obvious yet: {', '.join(missing_skills[:5])}.")
    if quantified_bullet_count < max(2, len(bullets) // 3):
        recommendations.append("Strengthen bullets with numbers, scope, frequency, savings, revenue, speed, volume, or quality impact.")
    if selected_profile_items and evidence_score < 70:
        recommendations.append("Select more profile evidence that directly overlaps with the target job before generating the prompt.")

    if overall_score >= 82:
        verdict = "Strong fit. You have a solid base; focus the optimization on precision and impact."
    elif overall_score >= 65:
        verdict = "Promising fit. A targeted rewrite should make the resume feel much closer to the role."
    elif overall_score >= 48:
        verdict = "Partial fit. Optimize carefully and consider adding stronger adjacent evidence from your profile."
    else:
        verdict = "Low visible fit. Before optimizing, decide whether you have missing experience in your profile that should be surfaced."

    if overall_score >= 80 and keyword_score >= 72 and skill_score >= 65:
        apply_signal = "Strong apply"
        apply_confidence = "High confidence"
        improvement_priority = "Polish and tailor"
    elif overall_score >= 62:
        apply_signal = "Worth targeting"
        apply_confidence = "Moderate confidence"
        improvement_priority = "Optimize before applying"
    elif overall_score >= 45:
        apply_signal = "Borderline"
        apply_confidence = "Cautious confidence"
        improvement_priority = "Only continue if you can surface stronger relevant evidence"
    else:
        apply_signal = "Probably not worth the time yet"
        apply_confidence = "Low confidence"
        improvement_priority = "Either change target roles or add missing evidence before investing more effort"

    total_gap_count = len(missing_keywords) + len(missing_skills)
    if overall_score >= 80 and total_gap_count <= 5:
        gap_severity = "Low"
    elif overall_score >= 62 and total_gap_count <= 10:
        gap_severity = "Moderate"
    elif overall_score >= 45:
        gap_severity = "High"
    else:
        gap_severity = "Critical"

    if apply_signal == "Strong apply":
        opportunity_worthiness = "Pursue now"
        recommendation_strength = "Strong recommendation"
    elif apply_signal == "Worth targeting":
        opportunity_worthiness = "Pursue after revision"
        recommendation_strength = "Good opportunity if you tighten the resume first"
    elif apply_signal == "Borderline":
        opportunity_worthiness = "Stretch target"
        recommendation_strength = "Proceed only if you can surface stronger evidence"
    else:
        opportunity_worthiness = "Skip for now"
        recommendation_strength = "Low recommendation"

    strongest_area_name, strongest_area_score = max(
        [
            ("Keywords", keyword_score),
            ("Skills", skill_score),
            ("Bullets", bullet_score),
            ("ATS / Clarity", ats_score),
            ("Profile Evidence", evidence_score if selected_profile_items else 0),
        ],
        key=lambda item: item[1],
    )
    weakest_area_name, weakest_area_score = min(
        [
            ("Keywords", keyword_score),
            ("Skills", skill_score),
            ("Bullets", bullet_score),
            ("ATS / Clarity", ats_score),
        ],
        key=lambda item: item[1],
    )

    focus_areas: list[str] = []
    if weakest_area_name == "Keywords" and missing_keywords:
        focus_areas.append(f"Surface honest evidence for: {', '.join(missing_keywords[:4])}.")
    if weakest_area_name == "Skills" and missing_skills:
        focus_areas.append(f"Clarify tools or hard skills such as: {', '.join(missing_skills[:4])}.")
    if weakest_area_name == "Bullets":
        focus_areas.append("Strengthen bullets with clearer action + measurable outcomes.")
    if weakest_area_name == "ATS / Clarity":
        focus_areas.append("Tighten structure, section labels, and contact basics for easier scanning.")
    if selected_profile_items and evidence_score < 70:
        focus_areas.append("Pull in stronger saved profile evidence before you finalize the application.")
    if not focus_areas:
        focus_areas.append("Stay focused on tailoring language and preserving the strongest role-specific evidence.")

    return {
        "overall_score": overall_score,
        "ats_score": ats_score,
        "keyword_score": keyword_score,
        "skill_score": skill_score,
        "bullet_score": bullet_score,
        "evidence_score": evidence_score,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "bullet_count": len(bullets),
        "quantified_bullet_count": quantified_bullet_count,
        "action_verb_bullet_count": action_verb_bullet_count,
        "warnings": warnings,
        "recommendations": recommendations,
        "verdict": verdict,
        "apply_signal": apply_signal,
        "apply_confidence": apply_confidence,
        "improvement_priority": improvement_priority,
        "gap_severity": gap_severity,
        "opportunity_worthiness": opportunity_worthiness,
        "recommendation_strength": recommendation_strength,
        "strongest_area": strongest_area_name,
        "strongest_area_score": strongest_area_score,
        "weakest_area": weakest_area_name,
        "weakest_area_score": weakest_area_score,
        "focus_areas": focus_areas,
        "total_gap_count": total_gap_count,
        "selected_evidence_titles": selected_evidence_titles,
    }
