"""
Deterministic cleanup for fetched job descriptions.

Example:
    raw = '''
    Search by Keyword
    Apply now »
    Botanica
    is a subsidiary of Red Sea Global.
    Coordinate with nurseries and project teams to forecast seasonal plant needs
    .
    '''
    result = clean_job_description(raw)
    # result["cleaned_text"] becomes:
    # Botanica is a subsidiary of Red Sea Global.
    #
    # Coordinate with nurseries and project teams to forecast seasonal plant needs.
"""
from __future__ import annotations

import re
from typing import Dict, List


JUNK_LINE_PATTERNS = [
    r"search by keyword",
    r"show more options",
    r"loading\.{0,3}",
    r"apply now",
    r"^apply$",
    r"^save$",
    r"report this job",
    r"see who .+ has hired for this role",
    r"find similar jobs",
    r"job opportunities",
    r"similar jobs",
    r"related jobs",
    r"show more$",
    r"show less$",
    r"show more jobs like this",
    r"show fewer jobs like this",
    r"show or,\s*, and\.",
    r"sign in",
    r"set alert",
    r"email or phone",
    r"^password$",
    r"forgot password",
    r"join now",
    r"by clicking continue",
    r"referrals increase your chances",
    r"see who you know",
    r"get notified when a new job is posted",
    r"new to linkedin",
    r"user agreement",
    r"privacy policy",
    r"cookie policy",
    r"^department$",
    r"^all$",
]

LINKEDIN_STOP_MARKERS = [
    "People also viewed",
    "Similar Searches",
    "Explore top content on LinkedIn",
    "Show more jobs like this",
    "Show fewer jobs like this",
    "Show or,",
    "View top content",
]

SECTION_HEADERS = {
    "job purpose",
    "key responsibilities",
    "key responsibilities:",
    "procurement strategy & planning",
    "supplier management",
    "procurement execution",
    "cross-functional coordination",
    "risk & cost management",
    "reporting & compliance",
    "policies, systems, processes, procedures, and reports",
    "safety, quality & environment",
    "continuous improvement",
    "internal and external stakeholders",
    "job requirements",
    "skills",
    "skills:",
    "education",
    "experience",
}

PUNCTUATION_ONLY_RE = re.compile(r"^[\.\,\:\;\!\?\-—]+$")
HEADER_PREFIX_RE = re.compile(
    r"^(job purpose|key responsibilities|procurement strategy|supplier management|procurement execution|"
    r"cross-functional coordination|risk & cost management|reporting & compliance|policies, systems|"
    r"safety, quality & environment|continuous improvement|internal and external stakeholders|"
    r"job requirements|skills|education|experience)\b",
    re.IGNORECASE,
)
LABEL_ONLY_RE = re.compile(r"^[A-Z][A-Za-z /&,-]{1,40}:\s*$")


def _is_junk_line(line: str) -> bool:
    normalized = " ".join(line.lower().split())
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in JUNK_LINE_PATTERNS)


def _normalize_lines(raw_text: str) -> List[str]:
    return [line.strip() for line in raw_text.splitlines()]


def _trim_at_stop_marker(text: str) -> tuple[str, bool]:
    """Truncate text once LinkedIn recommendation sections begin."""
    for marker in LINKEDIN_STOP_MARKERS:
        position = text.find(marker)
        if position != -1:
            return text[:position].rstrip(), True
    return text, False


def _merge_broken_lines(lines: List[str]) -> tuple[List[str], int]:
    merged: List[str] = []
    merge_count = 0

    for line in lines:
        if not line:
            if merged and merged[-1] != "":
                merged.append("")
            continue

        if PUNCTUATION_ONLY_RE.match(line):
            if merged:
                merged[-1] = f"{merged[-1]}{line}"
                merge_count += 1
            else:
                merged.append(line)
            continue

        if merged:
            previous = merged[-1]
            if previous and previous != "":
                previous_ends_cleanly = bool(re.search(r"[.:;!?—-]$", previous))
                next_continues_sentence = bool(re.match(r"^[a-z(]", line)) or bool(re.match(r"^[’']", line))
                if not previous_ends_cleanly and next_continues_sentence:
                    merged[-1] = f"{previous} {line}"
                    merge_count += 1
                    continue

        merged.append(line)

    return merged, merge_count


def _recover_section_spacing(lines: List[str]) -> List[str]:
    recovered: List[str] = []
    for line in lines:
        normalized = line.strip().lower()
        is_header = normalized in SECTION_HEADERS or bool(HEADER_PREFIX_RE.match(normalized))
        if is_header and recovered and recovered[-1] != "":
            recovered.append("")
        recovered.append(line)
    return recovered


def _merge_label_value_lines(lines: List[str]) -> tuple[List[str], int]:
    """Convert label-only lines followed by values into one canonical line."""
    merged: List[str] = []
    merge_count = 0
    index = 0
    while index < len(lines):
        current = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        if (
            current
            and next_line
            and LABEL_ONLY_RE.match(current)
            and next_line.strip()
            and next_line.strip() != ""
            and not LABEL_ONLY_RE.match(next_line)
            and not HEADER_PREFIX_RE.match(next_line.strip().lower())
        ):
            merged.append(f"{current.rstrip()} {next_line.strip()}")
            merge_count += 1
            index += 2
            continue

        merged.append(current)
        index += 1

    return merged, merge_count


def _normalize_typography(text: str) -> str:
    """Clean spacing around punctuation and apostrophes."""
    normalized_lines = []
    for line in text.splitlines():
        updated = re.sub(r"\s+([,.;:!?])", r"\1", line)
        updated = re.sub(r"([A-Za-z])\s+[’']\s+([A-Za-z])", r"\1’\2", updated)
        updated = re.sub(r"([A-Za-z])\s+[’']([A-Za-z])", r"\1’\2", updated)
        updated = re.sub(r"([A-Za-z])[’']\s+([A-Za-z])", r"\1’\2", updated)
        updated = re.sub(r"[ \t]{2,}", " ", updated)
        normalized_lines.append(updated.strip())
    return "\n".join(normalized_lines).strip()


def _compress_blank_lines(lines: List[str]) -> List[str]:
    compressed: List[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and previous_blank:
            continue
        compressed.append(line)
        previous_blank = is_blank
    while compressed and compressed[0] == "":
        compressed.pop(0)
    while compressed and compressed[-1] == "":
        compressed.pop()
    return compressed


def clean_job_description(raw_text: str) -> Dict[str, object]:
    """
    Deterministically clean fetched job-description text.

    Returns:
        {
            "cleaned_text": str,
            "junk_lines_removed": int,
            "broken_lines_merged": int,
            "confidence_message": str,
        }
    """
    trimmed_text, trimmed_at_marker = _trim_at_stop_marker(raw_text)
    lines = _normalize_lines(trimmed_text)

    kept_lines: List[str] = []
    junk_removed = 0
    for line in lines:
        if _is_junk_line(line):
            junk_removed += 1
            continue
        kept_lines.append(line.rstrip())

    merged_lines, merged_count = _merge_broken_lines(kept_lines)
    label_merged_lines, label_merge_count = _merge_label_value_lines(merged_lines)
    spaced_lines = _recover_section_spacing(label_merged_lines)
    final_lines = _compress_blank_lines(spaced_lines)
    cleaned_text = _normalize_typography("\n".join(final_lines))

    confidence_parts = [f"Cleaning complete. Removed {junk_removed} lines of page UI."]
    if merged_count:
        confidence_parts.append(f"Repaired {merged_count} broken line joins.")
    else:
        confidence_parts.append("No broken lines needed repair.")
    if label_merge_count:
        confidence_parts.append(f"Standardized {label_merge_count} label/value lines.")
    if trimmed_at_marker:
        confidence_parts.append("Trimmed LinkedIn recommendation sections.")

    return {
        "cleaned_text": cleaned_text,
        "junk_lines_removed": junk_removed,
        "broken_lines_merged": merged_count + label_merge_count,
        "confidence_message": " ".join(confidence_parts),
    }
