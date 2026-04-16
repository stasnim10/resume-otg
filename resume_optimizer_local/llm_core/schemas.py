"""
Typed schemas shared across grounded Local AI tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceChunk:
    """A retrieved chunk of supporting evidence."""

    chunk_id: str
    source_type: str
    source_id: str
    section: str
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobBrief:
    """Structured job description signals."""

    normalized_role_title: str
    seniority: str
    industry_hint: str
    responsibilities: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    domain_hints: list[str] = field(default_factory=list)
    prioritization_signals: list[str] = field(default_factory=list)
    summary: str = ""
    source_evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized_role_title": self.normalized_role_title,
            "seniority": self.seniority,
            "industry_hint": self.industry_hint,
            "responsibilities": self.responsibilities,
            "required_skills": self.required_skills,
            "domain_hints": self.domain_hints,
            "prioritization_signals": self.prioritization_signals,
            "summary": self.summary,
            "source_evidence_refs": self.source_evidence_refs,
        }


@dataclass
class ProfileSuggestionItem:
    """Reusable profile item suggested by the model."""

    item_type: str
    title: str = ""
    organization: str = ""
    description: str = ""
    bullets: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    source_evidence_refs: list[str] = field(default_factory=list)
    llm_reason: str = ""
    confidence_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "title": self.title,
            "organization": self.organization,
            "description": self.description,
            "bullets": self.bullets,
            "keywords": self.keywords,
            "source_evidence_refs": self.source_evidence_refs,
            "llm_reason": self.llm_reason,
            "confidence_score": self.confidence_score,
        }


@dataclass
class ProfileSuggestionResult:
    """Model-assisted profile extraction result."""

    basics: dict[str, Any]
    deterministic_items: list[dict[str, Any]] = field(default_factory=list)
    headline: str = ""
    summary: str = ""
    suggested_items: list[ProfileSuggestionItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "basics": self.basics,
            "deterministic_items": self.deterministic_items,
            "headline": self.headline,
            "summary": self.summary,
            "suggested_items": [item.to_dict() for item in self.suggested_items],
        }


@dataclass
class ReplacementPayload:
    """Validated replacement payload."""

    payload: dict[str, Any]
    source_evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.payload


@dataclass
class BuilderPayload:
    """Validated builder payload wrapper."""

    payload: dict[str, Any]
    source_evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.payload


@dataclass
class GuardedTaskResult:
    """Common result wrapper for guarded workflows."""

    status: str
    payload: Any = None
    validation_errors: list[str] = field(default_factory=list)
    repair_attempted: bool = False
    model_name: str = ""
    latency_ms: int = 0
    retrieved_evidence: list[EvidenceChunk] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload.to_dict() if hasattr(self.payload, "to_dict") else self.payload
        return {
            "status": self.status,
            "payload": payload,
            "validation_errors": self.validation_errors,
            "repair_attempted": self.repair_attempted,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "retrieved_evidence": [chunk.__dict__ for chunk in self.retrieved_evidence],
        }
