"""
JSON parsing and validation helpers for the resume optimizer prototype.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

COMMON_TOP_LEVEL_WRAPPERS = (
    "result",
    "data",
    "output",
    "payload",
    "response",
)

REPLACEMENT_ANCHOR_KEYS = (
    "match_anchor",
    "current_text",
    "original_text",
    "source_text",
    "before_text",
    "original",
    "anchor",
)

REPLACEMENT_TEXT_KEYS = (
    "replacement_text",
    "optimized_text",
    "revised_text",
    "updated_text",
    "after_text",
    "rewrite",
    "replacement",
    "improved_text",
)


def _strip_common_wrappers(raw_text: str) -> str:
    """Remove common non-JSON wrappers models add around structured output."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"<\|channel\|>thought[\s\S]*?<\|/channel\|>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<\|channel\|>thought[\s\S]*?<channel\|>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_balanced_json_object(text: str) -> Optional[str]:
    """Find the first balanced top-level JSON object in text."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        start = text.find("{", start + 1)
    return None


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Extract the outermost JSON object from pasted text.

    This is intentionally forgiving because users often paste
    conversational text around the JSON returned by an AI tool.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("No pasted content found. Paste the AI response and try again.")

    cleaned_text = _strip_common_wrappers(raw_text)
    json_str = _extract_balanced_json_object(cleaned_text)
    if not json_str:
        raise ValueError("No JSON block found. Paste the AI response that contains the structured payload.")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Invalid JSON format. "
            f"Line {error.lineno}, Column {error.colno}: {error.msg}"
        ) from error


def _unwrap_common_payload_wrappers(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unwrap common single-key envelopes produced by local models.

    Some models return the real schema inside a top-level key such as
    ``result`` or ``data`` even when prompted not to. We recover from
    that here so downstream validation still applies to the actual task
    payload rather than failing on a harmless wrapper.
    """
    current: Any = payload
    for _ in range(3):
        if not isinstance(current, dict) or len(current) != 1:
            break

        wrapper_key = next(iter(current.keys()))
        if wrapper_key not in COMMON_TOP_LEVEL_WRAPPERS:
            break

        inner_payload = current.get(wrapper_key)
        if not isinstance(inner_payload, dict):
            break

        current = inner_payload

    return current if isinstance(current, dict) else payload


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


def _pick_first_non_empty_string(source: Dict[str, Any], keys: tuple[str, ...]) -> str:
    """Return the first non-empty string for any of the provided keys."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _coerce_replacement_object(value: Any) -> Optional[Dict[str, str]]:
    """Map common model response variants into the expected replacement shape."""
    if not isinstance(value, dict):
        return None

    match_anchor = _pick_first_non_empty_string(value, REPLACEMENT_ANCHOR_KEYS)
    replacement_text = _pick_first_non_empty_string(value, REPLACEMENT_TEXT_KEYS)
    if not match_anchor or not replacement_text:
        return None

    return {
        "match_anchor": match_anchor,
        "replacement_text": replacement_text,
    }


def _normalize_replacement_collection(value: Any) -> List[Dict[str, str]]:
    """Normalize a replacement collection into validated replacement objects."""
    if isinstance(value, dict):
        normalized = _coerce_replacement_object(value)
        return [normalized] if normalized else []

    if not isinstance(value, list):
        return []

    items: List[Dict[str, str]] = []
    for raw_item in value:
        normalized = _coerce_replacement_object(raw_item)
        if normalized:
            items.append(normalized)
    return items


def _normalize_replacement_payload_shape(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recover from common alternate draft schemas returned by local models.

    Gemma sometimes returns semantically useful structures such as
    ``optimized_sections`` or ``action_items`` even when we asked for the
    replacement schema. This function translates those variants into the
    strict payload the rest of the app expects.
    """
    if not isinstance(payload, dict):
        return payload

    supported_keys = {"summary_replacement", "bullet_replacements", "skills_replacements"}
    if any(key in payload for key in supported_keys):
        normalized: Dict[str, Any] = {}
        if "summary_replacement" in payload:
            summary_replacement = _coerce_replacement_object(payload.get("summary_replacement"))
            if summary_replacement:
                normalized["summary_replacement"] = summary_replacement
        for section_name in ("bullet_replacements", "skills_replacements"):
            replacements = _normalize_replacement_collection(payload.get(section_name))
            if replacements:
                normalized[section_name] = replacements
        return normalized or payload

    normalized_payload: Dict[str, Any] = {}

    summary_candidate = _coerce_replacement_object(payload.get("summary"))
    if summary_candidate:
        normalized_payload["summary_replacement"] = summary_candidate

    bullet_replacements: List[Dict[str, str]] = []
    skills_replacements: List[Dict[str, str]] = []

    for collection_key in ("optimized_sections", "action_items", "replacements", "changes"):
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            continue
        for raw_item in collection:
            normalized_item = _coerce_replacement_object(raw_item)
            if not normalized_item:
                continue

            section_hint = str(
                raw_item.get("section")
                or raw_item.get("section_type")
                or raw_item.get("target_section")
                or raw_item.get("type")
                or ""
            ).lower()

            if "skill" in section_hint:
                skills_replacements.append(normalized_item)
            elif "summary" in section_hint or "headline" in section_hint or "profile" in section_hint:
                normalized_payload.setdefault("summary_replacement", normalized_item)
            else:
                bullet_replacements.append(normalized_item)

    if bullet_replacements:
        normalized_payload["bullet_replacements"] = bullet_replacements
    if skills_replacements:
        normalized_payload["skills_replacements"] = skills_replacements

    return normalized_payload or payload


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


def _validate_string_field(value: Any, label: str, required: bool = False) -> Tuple[bool, Optional[str]]:
    """Validate a JSON string field."""
    if value is None or value == "":
        if required:
            return False, f"{label} is required."
        return True, None
    if not isinstance(value, str):
        return False, f"{label} must be a string."
    return True, None


def _validate_string_list(value: Any, label: str) -> Tuple[bool, Optional[str]]:
    """Validate a list of strings."""
    if not isinstance(value, list):
        return False, f"{label} must be an array."
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            return False, f"{label}[{index}] must be a non-empty string."
    return True, None


def validate_builder_payload(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the first-resume builder payload structure."""
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object."

    required_keys = {"basics", "summary", "education", "experience", "projects", "skills"}
    missing_keys = [key for key in required_keys if key not in payload]
    if missing_keys:
        return False, f"Missing required top-level key(s): {', '.join(sorted(missing_keys))}."

    basics = payload.get("basics")
    if not isinstance(basics, dict):
        return False, "basics must be an object."
    for key in ("full_name", "email", "phone", "location", "linkedin"):
        is_valid, error = _validate_string_field(basics.get(key), f"basics.{key}", required=(key == "full_name"))
        if not is_valid:
            return False, error

    is_valid, error = _validate_string_field(payload.get("summary"), "summary", required=True)
    if not is_valid:
        return False, error

    education = payload.get("education")
    if not isinstance(education, list):
        return False, "education must be an array."
    for index, item in enumerate(education):
        if not isinstance(item, dict):
            return False, f"education[{index}] must be an object."
        for key in ("school", "degree", "graduation_date"):
            is_valid, error = _validate_string_field(item.get(key), f"education[{index}].{key}", required=True)
            if not is_valid:
                return False, error
        details = item.get("details", [])
        is_valid, error = _validate_string_list(details, f"education[{index}].details")
        if not is_valid:
            return False, error

    experience = payload.get("experience")
    if not isinstance(experience, list):
        return False, "experience must be an array."
    for index, item in enumerate(experience):
        if not isinstance(item, dict):
            return False, f"experience[{index}] must be an object."
        for key in ("title", "organization", "location", "dates"):
            is_valid, error = _validate_string_field(item.get(key), f"experience[{index}].{key}", required=True)
            if not is_valid:
                return False, error
        bullets = item.get("bullets", [])
        is_valid, error = _validate_string_list(bullets, f"experience[{index}].bullets")
        if not is_valid:
            return False, error

    projects = payload.get("projects")
    if not isinstance(projects, list):
        return False, "projects must be an array."
    for index, item in enumerate(projects):
        if not isinstance(item, dict):
            return False, f"projects[{index}] must be an object."
        is_valid, error = _validate_string_field(item.get("name"), f"projects[{index}].name", required=True)
        if not is_valid:
            return False, error
        details = item.get("details", [])
        is_valid, error = _validate_string_list(details, f"projects[{index}].details")
        if not is_valid:
            return False, error

    skills = payload.get("skills")
    is_valid, error = _validate_string_list(skills, "skills")
    if not is_valid:
        return False, error

    return True, None


def build_builder_validation_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create UI-friendly stats for the builder path."""
    return {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {
            "education_items": len(payload.get("education", [])),
            "experience_items": len(payload.get("experience", [])),
            "project_items": len(payload.get("projects", [])),
            "skills_items": len(payload.get("skills", [])),
        },
    }


def parse_replacement_payload(raw_text: str) -> Dict[str, Any]:
    """
    Extract and validate a replacement payload.

    Raises ValueError when the payload is missing or invalid.
    """
    payload = _normalize_replacement_payload_shape(
        _unwrap_common_payload_wrappers(extract_json_from_text(raw_text))
    )
    is_valid, error_message = validate_payload(payload)
    if not is_valid:
        raise ValueError(error_message)
    return payload


def parse_builder_payload(raw_text: str) -> Dict[str, Any]:
    """Extract and validate a builder payload."""
    payload = _unwrap_common_payload_wrappers(extract_json_from_text(raw_text))
    is_valid, error_message = validate_builder_payload(payload)
    if not is_valid:
        raise ValueError(error_message)
    return payload
