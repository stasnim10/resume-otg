"""
JSON parsing and validation helpers for the resume optimizer prototype.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Extract the outermost JSON object from pasted text.

    This is intentionally forgiving because users often paste
    conversational text around the JSON returned by an AI tool.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("No pasted content found. Paste the AI response and try again.")

    match = re.search(r"\{[\s\S]*\}\s*$", raw_text.strip())
    if not match:
        raise ValueError("No JSON block found. Paste the AI response that contains the structured payload.")

    json_str = match.group(0)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Invalid JSON format. "
            f"Line {error.lineno}, Column {error.colno}: {error.msg}"
        ) from error


def _validate_replacement_object(
    value: Any,
    label: str,
) -> Tuple[bool, Optional[str]]:
    """Validate a single replacement object."""
    if not isinstance(value, dict):
        return False, f"{label} must be an object."

    match_anchor = value.get("match_anchor")
    replacement_text = value.get("replacement_text")

    if not isinstance(match_anchor, str) or not match_anchor.strip():
        return False, f"{label}.match_anchor must be a non-empty string."
    if not isinstance(replacement_text, str) or not replacement_text.strip():
        return False, f"{label}.replacement_text must be a non-empty string."

    return True, None


def validate_payload(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the optimizer payload structure.

    Supported top-level keys:
    - summary_replacement: object
    - bullet_replacements: list[object]
    - skills_replacements: list[object]
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object."

    supported_keys = {
        "summary_replacement",
        "bullet_replacements",
        "skills_replacements",
    }
    unknown_keys = [key for key in payload.keys() if key not in supported_keys]
    if unknown_keys:
        return False, f"Unsupported top-level key(s): {', '.join(unknown_keys)}."

    if not any(key in payload for key in supported_keys):
        return False, "Add at least one replacement section to continue."

    if "summary_replacement" in payload:
        is_valid, error = _validate_replacement_object(
            payload["summary_replacement"],
            "summary_replacement",
        )
        if not is_valid:
            return False, error

    list_sections = ("bullet_replacements", "skills_replacements")
    for section_name in list_sections:
        if section_name not in payload:
            continue
        section_value = payload[section_name]
        if not isinstance(section_value, list):
            return False, f"{section_name} must be an array."
        for index, item in enumerate(section_value):
            is_valid, error = _validate_replacement_object(item, f"{section_name}[{index}]")
            if not is_valid:
                return False, error

    return True, None


def collect_replacements(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Flatten supported payload sections into a single replacement list."""
    replacements: List[Dict[str, str]] = []

    if "summary_replacement" in payload:
        replacements.append(payload["summary_replacement"])

    for section_name in ("bullet_replacements", "skills_replacements"):
        replacements.extend(payload.get(section_name, []))

    return replacements


def build_validation_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create UI-friendly validation summary stats for the payload."""
    summary_count = 1 if "summary_replacement" in payload else 0
    bullet_count = len(payload.get("bullet_replacements", []))
    skills_count = len(payload.get("skills_replacements", []))
    total_count = summary_count + bullet_count + skills_count

    return {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {
            "requested_replacements": total_count,
            "summary_replacements": summary_count,
            "bullet_replacements": bullet_count,
            "skills_replacements": skills_count,
        },
    }


def parse_replacement_payload(raw_text: str) -> Dict[str, Any]:
    """
    Extract and validate a replacement payload.

    Raises ValueError when the payload is missing or invalid.
    """
    payload = extract_json_from_text(raw_text)
    is_valid, error_message = validate_payload(payload)
    if not is_valid:
        raise ValueError(error_message)
    return payload
