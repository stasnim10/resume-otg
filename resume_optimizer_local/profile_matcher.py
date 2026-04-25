"""
Profile-item relevance ranking against a target job description.
"""
from __future__ import annotations

import re
from typing import Any

from profile_schema import ProfileItem


STOPWORDS = {
    "a",
    "an",
    "about",
    "across",
    "all",
    "are",
    "as",
    "after",
    "also",
    "and",
    "any",
    "been",
    "being",
    "by",
    "can",
    "for",
    "from",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "team",
    "the",
    "to",
    "we",
    "who",
    "you",
    "have",
    "into",
    "more",
    "that",
    "their",
    "them",
    "they",
    "this",
    "with",
    "will",
    "your",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z+\-]{2,}", text.lower())
    return [token for token in tokens if token not in STOPWORDS]


def extract_job_signals(job_description: str, target_role: str = "", target_industry: str = "") -> dict[str, Any]:
    """Extract a compact set of job signals for profile-item scoring."""
    source_text = " ".join(part for part in [target_role, target_industry, job_description] if part.strip())
    tokens = _tokenize(source_text)
    keyword_counts: dict[str, int] = {}
    for token in tokens:
        keyword_counts[token] = keyword_counts.get(token, 0) + 1
    sorted_keywords = sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "target_role": target_role.strip(),
        "target_industry": target_industry.strip(),
        "keywords": [keyword for keyword, _ in sorted_keywords[:20]],
        "token_set": set(keyword_counts.keys()),
    }


def score_profile_item(item: ProfileItem, job_signals: dict[str, Any]) -> tuple[float, list[str]]:
    """Return a relevance score and explainable reasons for one item."""
    reasons: list[str] = []
    score = 0.0

    item_tokens = set(
        _tokenize(
            " ".join(
                [
                    item.title,
                    item.organization,
                    item.description,
                    " ".join(item.bullets),
                    " ".join(item.skills),
                    " ".join(item.keywords),
                    " ".join(item.industry_tags),
                    " ".join(item.function_tags),
                ]
            )
        )
    )

    overlap = item_tokens & job_signals["token_set"]
    if overlap:
        keyword_score = min(len(overlap), 6)
        score += keyword_score
        reasons.append(f"Keyword overlap: {', '.join(sorted(list(overlap))[:4])}")

    role_tokens = set(_tokenize(job_signals.get("target_role", "")))
    if role_tokens and role_tokens & item_tokens:
        score += 2.5
        reasons.append("Role family match")

    industry_tokens = set(_tokenize(job_signals.get("target_industry", "")))
    if industry_tokens and industry_tokens & item_tokens:
        score += 2.0
        reasons.append("Industry match")

    if item.skills:
        skill_overlap = set(_tokenize(" ".join(item.skills))) & job_signals["token_set"]
        if skill_overlap:
            score += min(len(skill_overlap), 4) * 1.5
            reasons.append(f"Skills matched: {', '.join(sorted(list(skill_overlap))[:4])}")

    if item.verification_status == "verified":
        score += 1.0
        reasons.append("User verified")

    if item.item_type in {"experience", "project", "leadership", "business"}:
        score += 0.5

    return score, reasons


def rank_profile_items(
    items: list[ProfileItem],
    job_description: str,
    target_role: str = "",
    target_industry: str = "",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rank profile items against the target job and return explainable results."""
    job_signals = extract_job_signals(job_description, target_role=target_role, target_industry=target_industry)
    ranked_results: list[dict[str, Any]] = []
    for item in items:
        score, reasons = score_profile_item(item, job_signals)
        ranked_results.append({"item": item, "score": score, "reasons": reasons})
    ranked_results.sort(
        key=lambda result: (
            -result["score"],
            result["item"].verification_status != "verified",
            result["item"].item_type,
            result["item"].title.lower(),
        )
    )
    return job_signals, ranked_results


def extract_key_signals(resume_text: str, jd_text: str) -> dict[str, Any]:
    """
    Extract key signals for design Phase 1 Screen 3 (pre-optimization match display).

    Analyzes resume vs job description to identify:
    - Matches: Skills/keywords present in resume that are in the JD
    - Gaps: Key skills/keywords from JD that are missing in resume

    Returns: {
        "matches": [
            {"signal": "Supply Chain Management", "strength": "strong"},
            ...
        ],
        "gaps": [
            {"signal": "Advanced Analytics", "reason": "not_mentioned"},
            ...
        ]
    }
    """
    # Extract keywords from both texts
    resume_tokens = set(_tokenize(resume_text))
    jd_tokens = set(_tokenize(jd_text))

    # Get top keywords from JD (these are the must-haves)
    jd_keyword_counts: dict[str, int] = {}
    for token in jd_tokens:
        jd_keyword_counts[token] = jd_keyword_counts.get(token, 0) + 1

    # Sort by frequency (most important keywords appear more often)
    sorted_jd_keywords = sorted(
        jd_keyword_counts.items(),
        key=lambda item: (-item[1], item[0])
    )
    top_jd_keywords = [keyword for keyword, _ in sorted_jd_keywords[:12]]

    # Classify each keyword as match or gap
    matches = []
    gaps = []

    for keyword in top_jd_keywords:
        if keyword in resume_tokens:
            # Determine strength based on frequency in resume
            resume_count = sum(1 for token in _tokenize(resume_text) if token == keyword)
            jd_count = jd_keyword_counts.get(keyword, 1)

            # Strong if mentioned multiple times or in JD
            if resume_count >= 2 or jd_count >= 2:
                strength = "strong"
            elif resume_count >= 1:
                strength = "moderate"
            else:
                strength = "weak"

            matches.append({
                "signal": keyword.replace("_", " ").title(),
                "strength": strength
            })
        else:
            gaps.append({
                "signal": keyword.replace("_", " ").title(),
                "reason": "not_mentioned"
            })

    # Return top 2-3 of each
    return {
        "matches": matches[:3],
        "gaps": gaps[:3]
    }
