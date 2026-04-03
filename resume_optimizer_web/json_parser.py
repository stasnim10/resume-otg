"""
JSON parsing and validation for resume optimizer payloads
"""
import json
import re
from typing import Dict, Any


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    r"""
    Extract JSON from text using regex.
    
    Uses: re.search(r'{[\s\S]*}\s*$', raw_text)
    
    Args:
        raw_text: Raw text containing JSON
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        ValueError: If JSON not found or invalid
    """
    match = re.search(r'\{[\s\S]*\}\s*$', raw_text)
    
    if not match:
        raise ValueError("❌ No JSON block found in input. Please paste valid JSON.")
    
    json_str = match.group(0)
    
    try:
        parsed = json.loads(json_str)
        return parsed
    except json.JSONDecodeError as e:
        error_line = e.lineno
        error_col = e.colno
        error_msg = e.msg
        raise ValueError(
            f"❌ Invalid JSON: {error_msg}\n"
            f"   Line {error_line}, Column {error_col}\n"
            f"   Common issues: Missing comma, missing brace, trailing comma in array"
        )


def validate_payload(payload: Dict[str, Any]) -> tuple:
    """
    Validate JSON payload structure.
    
    Expected keys:
    - summary_replacement (optional)
    - bullet_replacements (optional, list)
    - skills_replacement (optional)
    
    Args:
        payload: Parsed JSON dictionary
        
    Returns:
        Tuple of (is_valid: bool, error_message: str or None)
    """
    if not isinstance(payload, dict):
        return False, "❌ Payload must be a JSON object"
    
    # Check summary_replacement
    if "summary_replacement" in payload:
        sr = payload["summary_replacement"]
        if not isinstance(sr, dict):
            return False, "❌ summary_replacement must be an object"
        if "match_anchor" not in sr or "replacement_text" not in sr:
            return False, "❌ summary_replacement must have match_anchor and replacement_text"
    
    # Check bullet_replacements
    if "bullet_replacements" in payload:
        br = payload["bullet_replacements"]
        if not isinstance(br, list):
            return False, "❌ bullet_replacements must be an array"
        for idx, bullet in enumerate(br):
            if not isinstance(bullet, dict):
                return False, f"❌ bullet_replacements[{idx}] must be an object"
            if "match_anchor" not in bullet or "replacement_text" not in bullet:
                return False, f"❌ bullet_replacements[{idx}] must have match_anchor and replacement_text"
    
    # Check skills_replacements
    if "skills_replacements" in payload:
        sr = payload["skills_replacements"]
        if not isinstance(sr, list):
            return False, "❌ skills_replacements must be an array"
        for idx, skill in enumerate(sr):
            if not isinstance(skill, dict):
                return False, f"❌ skills_replacements[{idx}] must be an object"
            if "match_anchor" not in skill or "replacement_text" not in skill:
                return False, f"❌ skills_replacements[{idx}] must have match_anchor and replacement_text"
    
    return True, None


def parse_replacement_payload(raw_text: str) -> Dict[str, Any]:
    """
    Extract and validate replacement payload.
    
    Args:
        raw_text: Raw JSON text
        
    Returns:
        Validated payload dictionary
        
    Raises:
        ValueError: If JSON invalid or structure invalid
    """
    payload = extract_json_from_text(raw_text)
    validate_payload(payload)
    return payload
