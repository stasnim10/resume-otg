"""
Generate human-readable improvement summaries for redesign Phase 1.

Analyzes before/after optimization results and creates compelling explanations
for why each change improves the resume-to-job match.
"""
from __future__ import annotations

import re
from typing import Any


# Common weak verbs to strong verb mappings
VERB_UPGRADES = {
    "managed": ["led", "directed", "coordinated", "spearheaded"],
    "worked": ["contributed", "collaborated", "partnered", "delivered"],
    "helped": ["enabled", "supported", "facilitated", "accelerated"],
    "made": ["created", "developed", "built", "designed"],
    "good": ["excellent", "outstanding", "superior", "exceptional"],
    "did": ["executed", "implemented", "completed", "delivered"],
}

STRONG_VERBS = {
    "accelerated", "achieved", "analyzed", "automated", "built",
    "collaborated", "created", "delivered", "designed", "developed",
    "directed", "discovered", "elevated", "enabled", "engineered",
    "enhanced", "established", "exceeded", "executed", "expanded",
    "facilitated", "founded", "generated", "grew", "guided",
    "implemented", "improved", "increased", "innovated", "instituted",
    "launched", "led", "leveraged", "maximized", "optimized",
    "pioneered", "produced", "programmed", "proposed", "reduced",
    "refined", "restructured", "revolutionized", "scaled", "solved",
    "sparked", "spearheaded", "streamlined", "strengthened", "succeeded",
    "surpassed", "synthesized", "transformed", "unveiled", "won",
}


def _extract_verb(text: str) -> str | None:
    """Extract the first verb from a sentence."""
    words = text.split()
    if not words:
        return None
    # First word is often the verb in resume bullets
    return words[0].lower()


def _has_quantified_impact(text: str) -> bool:
    """Check if text contains numbers/percentages/metrics indicating quantified impact."""
    return bool(re.search(r'\d+\s*(%|k|m|b|year|month|week|day|hour)', text, re.IGNORECASE)) or \
           bool(re.search(r'\$\d+', text)) or \
           bool(re.search(r'\b(percent|percentage|times|growth|increase|decrease|improvement)\b', text, re.IGNORECASE))


def _count_keywords_in_text(keywords: list[str], text: str) -> int:
    """Count how many keywords appear in text."""
    text_lower = text.lower()
    count = 0
    for keyword in keywords:
        if keyword.lower() in text_lower:
            count += 1
    return count


def categorize_change(before: str, after: str) -> str:
    """
    Categorize the type of change made to a resume section.

    Returns one of: "stronger_verb", "quantified_impact", "keyword_addition",
                    "clarity_improved", "restructured"
    """
    before_lower = before.lower()
    after_lower = after.lower()

    # Check for verb upgrade
    before_verb = _extract_verb(before)
    after_verb = _extract_verb(after)

    if before_verb and after_verb and before_verb != after_verb:
        if after_verb in STRONG_VERBS and before_verb not in STRONG_VERBS:
            return "stronger_verb"

    # Check for quantified impact addition
    before_quantified = _has_quantified_impact(before)
    after_quantified = _has_quantified_impact(after)

    if not before_quantified and after_quantified:
        return "quantified_impact"

    # Check for keyword addition (after is longer and contains new terms)
    if len(after) > len(before) * 1.2:  # 20% longer
        return "keyword_addition"

    # Check for clarity improvement (better wording)
    if len(after) > len(before):
        return "clarity_improved"

    if len(after) < len(before):
        return "restructured"

    return "clarity_improved"


def generate_why_context(
    change_type: str,
    before: str,
    after: str,
    jd_text: str = ""
) -> str:
    """
    Generate a human-readable explanation for why this change improves the resume.

    Args:
        change_type: Type of change (see categorize_change)
        before: Original text
        after: Optimized text
        jd_text: Job description (for keyword relevance checking)

    Returns:
        str: Human-readable explanation
    """
    if change_type == "stronger_verb":
        before_verb = _extract_verb(before) or "verb"
        after_verb = _extract_verb(after) or "verb"
        return (
            f"'{after_verb.title()}' is a stronger action verb than '{before_verb}' "
            f"and signals more leadership and impact. Recruiters notice the difference."
        )

    elif change_type == "quantified_impact":
        return (
            "Numbers make impact tangible and memorable to both ATS and recruiters. "
            "This quantification tells a specific story instead of a vague claim."
        )

    elif change_type == "keyword_addition":
        # Extract new keywords added
        before_words = set(before.lower().split())
        after_words = set(after.lower().split())
        new_words = after_words - before_words

        if jd_text:
            jd_lower = jd_text.lower()
            relevant_new = [w for w in new_words if w in jd_lower and len(w) > 3]
            if relevant_new:
                keyword = relevant_new[0]
                jd_count = jd_text.lower().count(keyword)
                return (
                    f"The job mentions '{keyword}' explicitly. "
                    f"Adding it increases keyword match and helps ATS match your resume to the role."
                )

        return (
            "Adding relevant keywords and technical terms improves ATS matching "
            "and shows you understand the role's requirements."
        )

    elif change_type == "clarity_improved":
        return (
            "This phrasing is clearer and more compelling. "
            "Recruiters can quickly understand your contribution and impact."
        )

    elif change_type == "restructured":
        return (
            "This reorganization makes the key information stand out. "
            "Your strongest accomplishments are now more prominent."
        )

    return "This change improves how your experience aligns with this role."


def assess_impact(before: str, after: str, jd_text: str = "") -> str:
    """
    Assess how significantly this change improves the resume-to-job match.

    Returns: "low", "medium", "high", "very_high"
    """
    change_type = categorize_change(before, after)

    # Keyword additions that match JD are always high impact
    if change_type == "keyword_addition" and jd_text:
        before_words = set(before.lower().split())
        after_words = set(after.lower().split())
        new_words = after_words - before_words
        jd_lower = jd_text.lower()
        jd_keyword_matches = sum(1 for w in new_words if w in jd_lower and len(w) > 3)
        if jd_keyword_matches >= 2:
            return "very_high"
        elif jd_keyword_matches == 1:
            return "high"

    # Verb upgrades are always high impact
    if change_type == "stronger_verb":
        return "high"

    # Quantified impact is always high
    if change_type == "quantified_impact":
        return "high"

    # Clarity and restructuring are medium
    if change_type in ["clarity_improved", "restructured"]:
        return "medium"

    return "medium"


def generate_improvements_summary(
    optimized_replacements: list[dict],
    jd_text: str = "",
    max_improvements: int = 5,
    min_impact: str = "medium"
) -> list[dict]:
    """
    Generate human-readable improvement summaries from optimization output.

    Args:
        optimized_replacements: List of {match_anchor, replacement_text} dicts from prompt output
        jd_text: Job description (for context)
        max_improvements: Maximum number of improvements to return
        min_impact: Minimum impact threshold to include ("low", "medium", "high", "very_high")

    Returns:
        list of dicts with:
        {
            "type": "stronger_verb" | "quantified_impact" | "keyword_addition" | "clarity_improved" | "restructured",
            "before": str,
            "after": str,
            "why": str,
            "impact": str
        }
    """
    # Define impact rank for filtering
    impact_ranks = {"low": 0, "medium": 1, "high": 2, "very_high": 3}
    min_rank = impact_ranks.get(min_impact, 1)

    improvements = []

    for replacement in optimized_replacements:
        before_text = replacement.get("match_anchor", "")
        after_text = replacement.get("replacement_text", "")

        if not before_text or not after_text or before_text == after_text:
            continue

        # Categorize and assess
        change_type = categorize_change(before_text, after_text)
        impact = assess_impact(before_text, after_text, jd_text)
        why_context = generate_why_context(change_type, before_text, after_text, jd_text)

        # Filter by impact threshold
        if impact_ranks.get(impact, 0) < min_rank:
            continue

        improvements.append({
            "type": change_type,
            "before": before_text,
            "after": after_text,
            "why": why_context,
            "impact": impact
        })

    # Sort by impact (high first)
    impact_order = {"very_high": 0, "high": 1, "medium": 2, "low": 3}
    improvements.sort(key=lambda x: impact_order.get(x["impact"], 99))

    # Return top N
    return improvements[:max_improvements]


# Example usage for testing:
if __name__ == "__main__":
    # Test with sample improvements
    test_replacements = [
        {
            "match_anchor": "Managed supply chain operations",
            "replacement_text": "Led supply chain operations strategy"
        },
        {
            "match_anchor": "Coordinated shipments",
            "replacement_text": "Coordinated 500+ monthly shipments"
        },
        {
            "match_anchor": "Some basic analytics work",
            "replacement_text": "Developed Tableau dashboards for real-time analytics"
        }
    ]

    test_jd = "We need someone with Tableau experience and leadership in supply chain."

    results = generate_improvements_summary(test_replacements, test_jd)
    for r in results:
        print(f"\nType: {r['type']}")
        print(f"Before: {r['before']}")
        print(f"After: {r['after']}")
        print(f"Why: {r['why']}")
        print(f"Impact: {r['impact']}")
