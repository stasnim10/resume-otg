"""
Typed schemas for the Career Profile foundation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def utc_now_iso() -> str:
    """Return an ISO timestamp string."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class CareerProfile:
    """Top-level persistent candidate profile."""

    id: int | None = None
    user_id: str = "local-user"
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    headline: str = ""
    career_stage: str = "Student"
    summary: str = ""
    target_roles: list[str] = field(default_factory=list)
    target_industries: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    work_authorization: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProfileSource:
    """Imported source document or manual note."""

    id: int | None = None
    user_id: str = "local-user"
    source_type: str = "manual_notes"
    source_name: str = ""
    file_path: str = ""
    raw_text: str = ""
    parsed_status: str = "pending"
    parsed_payload_json: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProfileItem:
    """Reusable evidence item linked to a profile."""

    id: int | None = None
    user_id: str = "local-user"
    profile_id: int | None = None
    source_id: int | None = None
    item_type: str = "experience"
    title: str = ""
    organization: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    is_current: bool = False
    description: str = ""
    bullets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    industry_tags: list[str] = field(default_factory=list)
    function_tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    confidence_score: float = 0.5
    verification_status: str = "suggested"
    visibility: str = "active"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Application:
    """A saved target job / application workspace."""

    id: int | None = None
    user_id: str = "local-user"
    job_title: str = ""
    company: str = ""
    job_description: str = ""
    role_family: str = ""
    industry: str = ""
    job_url: str = ""
    status: str = "draft"
    selected_profile_item_ids: list[int] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResumeAsset:
    """A saved resume output tied to an application or profile workflow."""

    id: int | None = None
    user_id: str = "local-user"
    application_id: int | None = None
    source_kind: str = "optimized_resume"
    category: str = "general"
    title: str = ""
    target_role: str = ""
    company: str = ""
    file_name: str = ""
    file_bytes: bytes = b""
    notes: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
