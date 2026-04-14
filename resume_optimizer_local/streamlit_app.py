"""
Streamlit prototype for the Resume Optimizer MVP.
"""
from __future__ import annotations

import io
import json
import logging
import re
import tempfile
from collections import Counter
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ai_gateway import PROVIDER_CONFIG, optimize_with_provider
from docx_handler import apply_replacements, build_resume_from_scratch, extract_text
from jd_cleaning import clean_job_description
from jd_fetcher import fetch_job_description_from_url, looks_like_url
from json_parser import (
    build_builder_validation_summary,
    build_validation_summary,
    collect_replacements,
    parse_builder_payload,
    parse_replacement_payload,
)
from profile_extractor import extract_profile_items_from_text
from profile_matcher import extract_key_signals, rank_profile_items
from profile_schema import ProfileItem
from profile_store import (
    archive_profile_item,
    create_or_get_profile,
    get_application,
    init_profile_db,
    link_profile_items_to_application,
    list_applications,
    list_profile_items,
    list_profile_sources,
    save_profile_basics,
    save_profile_items,
    save_profile_source,
    update_profile_item,
    update_profile_item_verification,
    upsert_application,
    extract_profile_basics_from_resume,
    create_or_update_profile_from_optimization,
    save_optimization_result,
    get_optimization_history,
)
from prompt_engine import build_builder_prompt, build_optimizer_prompt
from resume_evaluator import calculate_match_score, evaluate_resume_fit
from improvements_generator import generate_improvements_summary
from review_engine import analyze_payload_against_document
from optimization_history_ui import render_optimization_history_screen
from screens.ui_helpers import (
    CAREER_STAGES,
    FLOW_STEP_ALIASES,
    FLOW_STEPS,
    INDUSTRIES,
    PROFILE_ITEM_PRIORITY,
    PROFILE_ITEM_TYPES,
    ROLE_KEYWORDS,
    apply_apple_theme,
    build_inline_chip_row,
    build_readiness_rows,
    format_preview_text,
    handle_step_navigation_request,
    render_chip_row,
    render_copy_prompt_button,
    render_instruction_panel,
    render_prompt_block,
    render_replacement_preview,
    render_review_section,
    render_screen_intro,
    render_shell_end,
    render_shell_start,
    sort_profile_items_for_review,
    _group_review_results,
    _section_label,
)
from screens.builder import (
    render_builder_input_screen,
    render_builder_review_screen,
    render_builder_stub_screen,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)






def summarize_fit_recommendation(report: dict) -> tuple[int, str, str, str, str]:
    """Map a fit score to a plain-English recommendation and action."""
    score = int(report.get("overall_score", 0))
    if score >= 75:
        return (
            score,
            "Strong Match",
            "You should apply. Your resume already lines up with most of the role's core signals.",
            "Apply Now",
            "This is a strong match.",
        )
    if score >= 60:
        return (
            score,
            "Promising Match",
            "You should apply after one quick enhancement. The role is within reach, but a few missing signals are still worth tightening.",
            "Review Enhancement",
            "One improvement would boost your chances.",
        )
    return (
        score,
        "Stretch Match",
        "This role looks like a stretch right now. Review the biggest gaps before you spend more time here.",
        "Skip This Role",
        "Major gaps are still visible.",
    )


def build_change_examples(review_results: list[dict], limit: int = 3) -> list[dict[str, str]]:
    """Extract concise before/after examples from replacement review data."""
    examples: list[dict[str, str]] = []
    for result in review_results:
        before_text = (result.get("anchor") or "").strip()
        after_text = (result.get("replacement_text") or "").strip()
        label = result.get("category_label") or result.get("section_label") or "Resume update"
        if before_text and after_text:
            examples.append(
                {
                    "label": label,
                    "before": format_preview_text(before_text, max_len=88),
                    "after": format_preview_text(after_text, max_len=88),
                }
            )
        if len(examples) >= limit:
            break
    return examples


def build_optimization_metrics_summary(before_report: dict, after_report: dict) -> list[dict[str, str | int]]:
    """Create user-facing metric summaries for the success state."""
    before_keyword = int(before_report.get("keyword_score", 0))
    after_keyword = int(after_report.get("keyword_score", 0))
    before_ats = int(before_report.get("ats_score", 0))
    after_ats = int(after_report.get("ats_score", 0))
    before_overall = int(before_report.get("overall_score", 0))
    after_overall = int(after_report.get("overall_score", 0))
    before_action = int(before_report.get("action_verb_bullet_count", 0))
    after_action = int(after_report.get("action_verb_bullet_count", 0))

    return [
        {
            "label": "Keyword Alignment",
            "before": before_keyword,
            "after": after_keyword,
            "delta": after_keyword - before_keyword,
            "suffix": "pts",
        },
        {
            "label": "ATS / Clarity",
            "before": before_ats,
            "after": after_ats,
            "delta": after_ats - before_ats,
            "suffix": "pts",
        },
        {
            "label": "Action-Led Bullets",
            "before": before_action,
            "after": after_action,
            "delta": after_action - before_action,
            "suffix": "bullets",
        },
        {
            "label": "Overall Fit",
            "before": before_overall,
            "after": after_overall,
            "delta": after_overall - before_overall,
            "suffix": "pts",
        },
    ]





def detect_role_title(job_description: str) -> str:
    """Infer a role title from the pasted job description."""
    if not job_description.strip():
        return ""

    top_section = job_description[:700]
    role_suffixes = "|".join(
        [
            "Analyst",
            "Manager",
            "Engineer",
            "Specialist",
            "Consultant",
            "Coordinator",
            "Associate",
            "Intern",
            "Designer",
            "Administrator",
            "Strategist",
            "Recruiter",
            "Marketer",
            "Developer",
            "Scientist",
        ]
    )
    ignore_markers = [
        "requirements",
        "education",
        "years of experience",
        "skills",
        "physical requirements",
        "safety",
        "salary",
        "benefits",
        "preferred",
    ]
    patterns = [
        r"(?im)^\s*(?:job title|title|role|position)\s*[:\-]\s*(.+)$",
        rf"(?im)^\s*([A-Z][A-Za-z/&,\-\s]{{2,80}}(?:{role_suffixes}))\s*$",
        rf"(?i)\bthe\s+([A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes}))\s+(?:plays|is|will|works|supports|leads)\b",
        rf"\b((?:Senior|Lead|Principal|Staff|Junior|Associate|Assistant)\s+[A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes})|[A-Z][A-Za-z/&,\-\s]{{1,80}}(?:{role_suffixes}))\b",
    ]
    for pattern in patterns:
        for text_block in [top_section, job_description]:
            matches = re.findall(pattern, text_block)
            if not matches:
                continue
            for raw_match in matches:
                cleaned_match = " ".join(raw_match.split())
                cleaned_match = re.sub(
                    r"^(?:about the job|job description|job)\s+",
                    "",
                    cleaned_match,
                    flags=re.IGNORECASE,
                ).strip()
                cleaned_match = re.sub(r"^the\s+", "", cleaned_match, flags=re.IGNORECASE).strip()
                cleaned_match = re.sub(r"\s+-\s+remote$", "", cleaned_match, flags=re.IGNORECASE).strip()
                lowered = cleaned_match.lower()
                if any(marker in lowered for marker in ignore_markers):
                    continue
                if len(cleaned_match) > 90:
                    continue
                return cleaned_match

    for line in job_description.splitlines()[:12]:
        cleaned = " ".join(line.split())
        if not cleaned or len(cleaned) > 90:
            continue
        lowered = cleaned.lower()
        if any(marker in lowered for marker in ignore_markers):
            continue
        if any(keyword.lower() in cleaned.lower() for keyword in ROLE_KEYWORDS):
            return cleaned

    return ""


def detect_industry(job_description: str) -> str:
    """Infer an industry bucket from the pasted job description."""
    text = job_description.lower()
    if not text:
        return ""

    keyword_map = {
        "Supply Chain / Operations": [
            "supply chain",
            "logistics",
            "transportation",
            "warehouse",
            "inventory",
            "distribution",
            "carrier",
            "routing",
            "fulfillment",
            "delivery network",
        ],
        "Finance": ["finance", "financial", "fp&a", "banking", "investment", "accounting", "budget", "forecasting"],
        "Consulting": ["consulting", "client engagement", "advisory", "strategy projects"],
        "Technology": ["software", "saas", "cloud", "developer", "product", "tech", "automation platform"],
        "Healthcare": ["healthcare", "clinical", "patient", "medical", "hospital", "pharma"],
        "Marketing": ["marketing", "brand", "campaign", "growth", "content", "seo"],
    }
    scores = {
        industry: sum(text.count(keyword) for keyword in keywords)
        for industry, keywords in keyword_map.items()
    }
    best_industry = max(scores, key=scores.get)
    if scores[best_industry] > 0:
        return best_industry
    return "General Business"


def get_effective_target_role(job_description: str) -> str:
    """Use the manual override when present, otherwise JD detection."""
    return (
        st.session_state.target_role.strip()
        or (st.session_state.jd_role_hint.strip() if st.session_state.jd_source_url else "")
        or detect_role_title(job_description)
        or "the target role"
    )


def get_effective_industry(job_description: str) -> str:
    """Use the manual override when present, otherwise JD detection."""
    return st.session_state.target_industry.strip() or detect_industry(job_description)


def init_session_state() -> None:
    """Initialize expected session keys."""
    defaults = {
        "screen": "landing",
        "resume_name": None,
        "resume_bytes": None,
        "resume_text": None,
        "resume_paragraphs": [],
        "job_description": "",
        "career_stage": CAREER_STAGES[0],
        "target_role": "",
        "target_industry": "",
        "execution_mode": None,
        "selected_provider": "OpenAI",
        "generated_prompt": None,
        "api_prompt_customized": False,
        "api_prompt_override": "",
        "validated_payload": None,
        "validation_summary": None,
        "output_docx_bytes": None,
        "output_filename": None,
        "last_error": None,
        "review_details": None,
        "builder_full_name": "",
        "builder_contact_info": "",
        "builder_education": "",
        "builder_experience_dump": "",
        "builder_activities": "",
        "builder_skills": "",
        "builder_job_description": "",
        "builder_prompt": "",
        "builder_execution_mode": None,
        "builder_payload": None,
        "builder_validation_summary": None,
        "builder_output_docx_bytes": None,
        "builder_output_filename": None,
        "jd_source_url": "",
        "jd_cleaning_result": None,
        "show_review_changes": False,
        "pending_job_description_input": None,
        "jd_role_hint": "",
        "custom_api_base_url": "http://localhost:11434/v1",
        "custom_api_model": "mistral",
        "custom_api_key": "",
        "profile_import_notes": "",
        "profile_import_source_name": "",
        "profile_extracted_basics": {},
        "profile_extracted_items": [],
        "profile_last_source_id": None,
        "profile_last_source_raw_text": "",
        "use_career_profile": False,
        "selected_profile_item_ids": [],
        "profile_job_signals": {},
        "current_application_id": None,
        "current_application_company": "",
        "resume_fit_report": None,
        "baseline_fit_report": None,
        "optimized_fit_report": None,
        "resume_fit_report_signature": "",
        "profile_review_show_all_items": False,
        "show_fit_details": False,
        "optimization_change_examples": [],
        "optimization_metrics_summary": [],
        "is_first_optimization": True,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_flow() -> None:
    """Reset the prototype flow to the landing page."""
    logger.info("Flow reset requested")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()


def save_uploaded_resume(uploaded_file) -> None:
    """Store uploaded resume data and extracted plain text in session state."""
    resume_bytes = uploaded_file.getvalue()

    # Determine file suffix based on uploaded filename
    filename_lower = uploaded_file.name.lower()
    if filename_lower.endswith('.pdf'):
        suffix = ".pdf"
    else:
        suffix = ".docx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(resume_bytes)
        temp_path = temp_file.name

    try:
        resume_text = extract_text(temp_path)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    st.session_state.resume_name = uploaded_file.name
    st.session_state.resume_bytes = resume_bytes
    st.session_state.resume_text = resume_text
    st.session_state.resume_paragraphs = [
        paragraph.strip()
        for paragraph in resume_text.splitlines()
        if paragraph.strip()
    ]
    logger.info(
        "Resume uploaded: filename=%s, paragraphs=%s",
        uploaded_file.name,
        len(st.session_state.resume_paragraphs),
    )


def analyze_payload(payload: dict) -> dict:
    """Run match diagnostics against the uploaded resume."""
    if not st.session_state.resume_bytes or not st.session_state.resume_name:
        raise ValueError("Upload a resume before validating output.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(st.session_state.resume_bytes)
        temp_path = temp_file.name

    try:
        return analyze_payload_against_document(temp_path, payload)
    finally:
        Path(temp_path).unlink(missing_ok=True)


def build_output_docx(payload: dict) -> tuple[bytes, str]:
    """Apply replacements and return the optimized .docx bytes."""
    if not st.session_state.resume_bytes or not st.session_state.resume_name:
        raise ValueError("Upload a resume before exporting.")

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / st.session_state.resume_name
        input_path.write_bytes(st.session_state.resume_bytes)

        success, message = apply_replacements(str(input_path), payload)
        if not success:
            raise ValueError(message)

        output_path = input_path.with_name(f"{input_path.stem}_Optimized{input_path.suffix}")
        if not output_path.exists():
            raise ValueError("The optimized document was not created.")

        return output_path.read_bytes(), message


def _build_optimized_resume_text(payload: dict) -> str:
    """Approximate the post-optimization resume text from exact-match replacements."""
    paragraphs = list(st.session_state.resume_paragraphs or [])
    if not paragraphs:
        return st.session_state.resume_text or ""

    updated_paragraphs = paragraphs[:]
    replacements = collect_replacements(payload)
    for replacement in replacements:
        anchor = replacement["match_anchor"].strip()
        replacement_text = replacement["replacement_text"].strip()
        matching_indexes = [index for index, paragraph in enumerate(updated_paragraphs) if paragraph.strip() == anchor]
        if len(matching_indexes) == 1:
            updated_paragraphs[matching_indexes[0]] = replacement_text

    return "\n".join(updated_paragraphs)


def ensure_export_file_ready() -> None:
    """Generate the optimized output once when export is safe."""
    if st.session_state.output_docx_bytes or not st.session_state.validated_payload:
        return

    output_bytes, _message = build_output_docx(st.session_state.validated_payload)
    original_name = Path(st.session_state.resume_name)
    st.session_state.output_docx_bytes = output_bytes
    st.session_state.output_filename = f"{original_name.stem}_Optimized{original_name.suffix}"


def render_landing() -> None:
    """Landing page."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Resume Optimizer</div>
            <h1>Make resume tailoring feel beautifully simple.</h1>
            <p>Start with your draft, aim it at the role you want, and move through a guided flow that feels calm, clear, and polished from start to download.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(
            """
            <div class="apple-landing-card featured">
              <div>
                <div class="apple-kicker">Most Popular</div>
                <div class="apple-landing-card-title">Optimize an existing resume</div>
                <div class="apple-landing-card-copy">Refine the resume you already have for a specific role, then review the final changes before you export it.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-primary">', unsafe_allow_html=True)
        if st.button("Start Optimizing", use_container_width=True, key="landing-optimize"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            """
            <div class="apple-landing-card">
              <div>
                <div class="apple-kicker">Builder Path</div>
                <div class="apple-landing-card-title">Build your first resume</div>
                <div class="apple-landing-card-copy">Start with a plain-English brain dump and shape it into a clean first draft with more guidance built in.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-landing-actions apple-secondary">', unsafe_allow_html=True)
        if st.button("Build First Resume", use_container_width=True, key="landing-builder"):
            st.session_state.career_stage = "Student"
            st.session_state.screen = "builder_input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    render_shell_end()


def _profile_items_from_session() -> list[ProfileItem]:
    """Convert session-stored dict items back into ProfileItem objects."""
    return [ProfileItem(**item) for item in st.session_state.profile_extracted_items]


def _split_csv_input(value: str) -> list[str]:
    """Turn comma-separated text into a clean list."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _split_line_input(value: str) -> list[str]:
    """Turn multiline text into a clean list of non-empty lines."""
    return [line.strip() for line in value.splitlines() if line.strip()]


def _get_selected_profile_items() -> list[ProfileItem]:
    """Resolve selected profile item ids from session state."""
    selected_ids = set(st.session_state.get("selected_profile_item_ids", []))
    if not selected_ids:
        return []
    items_by_id = {item.id: item for item in list_profile_items() if item.visibility == "active"}
    return [items_by_id[item_id] for item_id in st.session_state.get("selected_profile_item_ids", []) if item_id in items_by_id]


def _build_profile_context(items: list[ProfileItem]) -> str:
    """Convert selected profile items into a compact prompt context block."""
    sections: list[str] = []
    for index, item in enumerate(items, start=1):
        bullet_lines = "\n".join(f"- {bullet}" for bullet in item.bullets[:4])
        skills_line = f"Skills: {', '.join(item.skills[:8])}" if item.skills else ""
        parts = [
            f"{index}. {item.item_type.title()}: {item.title or 'Untitled item'}",
            f"Organization: {item.organization}" if item.organization else "",
            item.description.strip(),
            bullet_lines,
            skills_line,
        ]
        section = "\n".join(part for part in parts if part)
        if section:
            sections.append(section)
    return "\n\n".join(sections)


def _build_optimizer_prompt_from_state() -> str:
    """Build the optimizer prompt, optionally enriched with selected profile evidence."""
    profile_context = _build_profile_context(_get_selected_profile_items()) if st.session_state.get("use_career_profile") else ""
    return build_optimizer_prompt(
        st.session_state.resume_text,
        st.session_state.job_description,
        st.session_state.career_stage,
        get_effective_target_role(st.session_state.job_description),
        get_effective_industry(st.session_state.job_description),
        profile_context=profile_context,
    )


def _resume_fit_signature() -> str:
    """Return a compact signature for the current report inputs."""
    selected_ids = ",".join(str(item_id) for item_id in st.session_state.get("selected_profile_item_ids", []))
    return "|".join(
        [
            str(len(st.session_state.resume_text or "")),
            str(len(st.session_state.job_description or "")),
            selected_ids,
            st.session_state.resume_name or "",
        ]
    )


def _evaluate_current_resume_fit(force: bool = False) -> dict:
    """Evaluate the current resume/JD pair and cache the report."""
    signature = _resume_fit_signature()
    if (
        force
        or not st.session_state.resume_fit_report
        or st.session_state.resume_fit_report_signature != signature
    ):
        report = evaluate_resume_fit(
            st.session_state.resume_text or "",
            st.session_state.job_description or "",
            selected_profile_items=_get_selected_profile_items(),
        )
        st.session_state.resume_fit_report = report
        st.session_state.baseline_fit_report = report
        st.session_state.resume_fit_report_signature = signature
        logger.info(
            "Fit score calculated: overall=%s, keyword=%s, skills=%s, ats=%s",
            int(report.get("overall_score", 0)),
            int(report.get("keyword_score", 0)),
            int(report.get("skill_score", 0)),
            int(report.get("ats_score", 0)),
        )
    return st.session_state.resume_fit_report or {}


def _infer_basics_from_resume_text(resume_text: str) -> tuple[str, str]:
    """Infer a name and contact line from the uploaded resume text when possible."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    full_name = lines[0] if lines else "Candidate Name"
    contact_info = ""
    for line in lines[1:4]:
        if "@" in line or "|" in line or re.search(r"\d{3}[-.)\s]?\d{3}", line):
            contact_info = line
            break
    return full_name, contact_info


def _profile_items_to_builder_inputs(items: list[ProfileItem]) -> dict[str, str]:
    """Convert selected profile items into builder-style source fields."""
    education_chunks: list[str] = []
    experience_chunks: list[str] = []
    activity_chunks: list[str] = []
    skill_bank: list[str] = []

    for item in items:
        heading_parts = [part for part in [item.title, item.organization] if part]
        heading = " | ".join(heading_parts) if heading_parts else item.item_type.title()
        body_parts = [item.description.strip()] if item.description.strip() else []
        if item.bullets:
            body_parts.extend(item.bullets[:5])
        chunk = "\n".join([heading] + [part for part in body_parts if part])

        if item.item_type == "education":
            education_chunks.append(chunk)
        elif item.item_type in {"experience", "business", "volunteering"}:
            experience_chunks.append(chunk)
        else:
            activity_chunks.append(chunk)

        for skill in item.skills:
            if skill not in skill_bank:
                skill_bank.append(skill)

    return {
        "education": "\n\n".join(education_chunks),
        "experience_dump": "\n\n".join(experience_chunks),
        "activities": "\n\n".join(activity_chunks),
        "skills": ", ".join(skill_bank),
    }


def _start_profile_draft_flow() -> None:
    """Seed the builder flow from selected career-profile evidence."""
    selected_items = _get_selected_profile_items()
    if not selected_items:
        raise ValueError("Choose at least one profile item before creating a draft.")

    profile = create_or_get_profile()
    inferred_name, inferred_contact = _infer_basics_from_resume_text(st.session_state.resume_text or "")
    full_name = profile.full_name.strip() or inferred_name
    contact_parts = [profile.email, profile.phone, profile.location, profile.linkedin]
    contact_info = " | ".join([part.strip() for part in contact_parts if part.strip()]) or inferred_contact
    builder_inputs = _profile_items_to_builder_inputs(selected_items)

    st.session_state.builder_full_name = full_name
    st.session_state.builder_contact_info = contact_info
    st.session_state.builder_education = builder_inputs["education"]
    st.session_state.builder_experience_dump = builder_inputs["experience_dump"]
    st.session_state.builder_activities = builder_inputs["activities"]
    st.session_state.builder_skills = builder_inputs["skills"]
    st.session_state.builder_job_description = st.session_state.job_description
    st.session_state.career_stage = profile.career_stage or st.session_state.career_stage
    if profile.target_roles and not st.session_state.target_role.strip():
        st.session_state.target_role = profile.target_roles[0]
    st.session_state.builder_prompt = build_builder_prompt(
        full_name=st.session_state.builder_full_name,
        contact_info=st.session_state.builder_contact_info,
        education=st.session_state.builder_education,
        experience_dump=st.session_state.builder_experience_dump,
        activities=st.session_state.builder_activities,
        skills=st.session_state.builder_skills,
        job_description=st.session_state.builder_job_description,
        career_stage=st.session_state.career_stage,
        target_role=st.session_state.target_role or "the target role",
    )
    st.session_state.builder_execution_mode = None
    st.session_state.builder_payload = None
    st.session_state.builder_validation_summary = None
    st.session_state.builder_output_docx_bytes = None
    st.session_state.builder_output_filename = None
    st.session_state.screen = "builder_stub"


def _save_current_application(status: str = "matched") -> int:
    """Persist the current job target and selected profile evidence."""
    job_description = st.session_state.job_description.strip()
    if not job_description:
        raise ValueError("Add a job description before saving an application workspace.")

    application = upsert_application(
        application_id=st.session_state.get("current_application_id"),
        job_title=get_effective_target_role(job_description),
        company=st.session_state.get("current_application_company", ""),
        job_description=job_description,
        role_family=get_effective_target_role(job_description),
        industry=get_effective_industry(job_description),
        job_url=st.session_state.jd_source_url,
        status=status,
    )
    st.session_state.current_application_id = application.id
    if application.id is not None:
        link_profile_items_to_application(
            application.id,
            [item_id for item_id in st.session_state.get("selected_profile_item_ids", []) if isinstance(item_id, int)],
        )
    logger.info(
        "Application saved: id=%s, job_title=%s, company=%s, status=%s, selected_items=%s",
        application.id,
        application.job_title,
        application.company,
        status,
        len(st.session_state.get("selected_profile_item_ids", [])),
    )
    return application.id or 0


def _load_application_into_session(application_id: int) -> None:
    """Load a saved application into the current Streamlit session."""
    application = get_application(application_id)
    if application is None:
        return
    st.session_state.current_application_id = application.id
    st.session_state.current_application_company = application.company
    st.session_state.job_description = application.job_description
    st.session_state.pending_job_description_input = application.job_description
    st.session_state.target_role = application.job_title
    st.session_state.target_industry = application.industry
    st.session_state.jd_source_url = application.job_url
    st.session_state.selected_profile_item_ids = application.selected_profile_item_ids
    st.session_state.use_career_profile = bool(application.selected_profile_item_ids)


def _extract_profile_from_import(uploaded_file, notes_text: str) -> tuple[str, str, dict, list[dict]]:
    """Extract raw text, source name, profile basics, and item dicts from uploaded material."""
    raw_text_parts: list[str] = []
    source_name = "Manual Notes"

    if uploaded_file is not None:
        source_name = uploaded_file.name
        suffix = Path(uploaded_file.name).suffix.lower()
        file_bytes = uploaded_file.getvalue()
        if suffix == ".docx":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            try:
                raw_text_parts.append(extract_text(temp_path))
            finally:
                Path(temp_path).unlink(missing_ok=True)
        elif suffix in {".txt", ".md"}:
            raw_text_parts.append(file_bytes.decode("utf-8", errors="ignore"))
        else:
            raise ValueError("For now, profile import supports .docx, .txt, or pasted notes.")

    if notes_text.strip():
        raw_text_parts.append(notes_text.strip())

    raw_text = "\n\n".join(part for part in raw_text_parts if part.strip())
    if not raw_text.strip():
        raise ValueError("Upload a source document or paste notes to build the profile.")

    basics, items = extract_profile_items_from_text(raw_text)
    logger.info(
        "Profile import extracted: source=%s, chars=%s, items=%s",
        source_name,
        len(raw_text),
        len(items),
    )
    return raw_text, source_name, basics, [item.to_dict() for item in items]


def render_profile_welcome_screen() -> None:
    """Entry point for Career Profile onboarding."""
    render_shell_start()
    st.markdown(
        """
        <div class="apple-hero-panel">
          <div class="apple-hero">
            <div class="apple-eyebrow">Career Profile</div>
            <h1>Tell us about yourself once.</h1>
            <p>Build a reusable profile the app can draw from for future job applications, instead of starting from scratch every time.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Fast Import</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Import from a resume or notes.</div>', unsafe_allow_html=True)
            st.markdown(
                "<div class=\"apple-choice-copy\">Upload an existing resume or paste detailed notes. We'll extract reusable profile items for you to review.</div>",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Import Materials", use_container_width=True, key="profile-import-entry"):
                st.session_state.screen = "profile_import"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Profile Dashboard</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">View your saved career profile.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Open your stored experience bank, saved sources, and target-role settings. Great for updating your long-term career memory.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Open Profile Dashboard", use_container_width=True, key="profile-dashboard-entry"):
                st.session_state.screen = "profile_dashboard"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    back_col_left, back_col_center, back_col_right = st.columns([1.2, 1.6, 1.2])
    with back_col_center:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Home", use_container_width=True, key="profile-welcome-back"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_import_screen() -> None:
    """Collect source material for first-pass profile extraction."""
    render_shell_start()
    render_screen_intro(
        "input",
        "Career Profile Import",
        "Import your background.",
        "Upload a resume or paste detailed notes. We'll turn them into reusable profile items you can confirm.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Source Material</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Add what you already have.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Use a .docx resume, a plain-text export, or detailed notes from LinkedIn, old resumes, projects, certifications, or activities.</div>',
            unsafe_allow_html=True,
        )
        uploaded_source = st.file_uploader(
            "Upload source file",
            type=["docx", "txt", "md"],
            help="For now, profile import supports .docx, .txt, and .md files.",
            key="profile-import-file",
        )
        notes_text = st.text_area(
            "Notes",
            value=st.session_state.profile_import_notes,
            height=220,
            placeholder="Paste LinkedIn text, old resume content, project notes, certifications, activities, or any other career history here.",
        )
        st.session_state.profile_import_notes = notes_text

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="profile-import-back"):
            st.session_state.screen = "profile_welcome"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Extract Profile", use_container_width=True, key="profile-extract"):
            try:
                logger.info(
                    "Profile import started: has_file=%s, notes_chars=%s",
                    bool(uploaded_source),
                    len(notes_text.strip()),
                )
                raw_text, source_name, basics, item_dicts = _extract_profile_from_import(uploaded_source, notes_text)
                st.session_state.profile_import_source_name = source_name
                st.session_state.profile_extracted_basics = basics
                st.session_state.profile_extracted_items = item_dicts
                st.session_state.profile_last_source_raw_text = raw_text
                st.session_state.profile_review_show_all_items = False
                st.session_state.screen = "profile_review"
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_review_screen() -> None:
    """Review extracted profile basics and items before saving."""
    render_shell_start()
    render_screen_intro(
        "review",
        "Career Profile Review",
        "Review your extracted profile.",
        "Confirm the imported details before saving them as your reusable career profile.",
    )

    basics = st.session_state.profile_extracted_basics or {}
    extracted_items = sort_profile_items_for_review(_profile_items_from_session())
    extracted_type_counts = Counter(item.item_type for item in extracted_items)
    show_all_items = st.session_state.get("profile_review_show_all_items", False)
    prioritized_items = extracted_items[:3]
    hidden_items = extracted_items[3:]
    visible_items = extracted_items if show_all_items else prioritized_items
    logger.info(
        "Profile review opened: total_items=%s, initially_visible=%s, expanded=%s",
        len(extracted_items),
        len(visible_items),
        show_all_items,
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Import Quality</div>', unsafe_allow_html=True)
        st.markdown("<div class=\"apple-section-title\">Here is what we found in your source material.</div>", unsafe_allow_html=True)
        quality_rows = [
            ("Identity detected", basics.get("full_name", "Missing")),
            ("Contact detected", "Yes" if basics.get("email") or basics.get("phone") or basics.get("linkedin") else "Missing"),
            ("Evidence items", str(len(extracted_items))),
            ("Largest category", extracted_type_counts.most_common(1)[0][0].title() if extracted_type_counts else "None yet"),
        ]
        st.markdown(build_readiness_rows(quality_rows), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Basics</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Refine the top-level profile.</div>', unsafe_allow_html=True)
        identity_col1, identity_col2 = st.columns(2, gap="large")
        with identity_col1:
            full_name = st.text_input("Full Name", value=basics.get("full_name", ""), placeholder="Example: Jane Doe")
            email = st.text_input("Email", value=basics.get("email", ""), placeholder="jane@example.com")
            phone = st.text_input("Phone", value=basics.get("phone", ""), placeholder="(555) 555-5555")
        with identity_col2:
            location = st.text_input("Location", value=basics.get("location", ""), placeholder="New York, NY")
            linkedin = st.text_input("LinkedIn", value=basics.get("linkedin", ""), placeholder="linkedin.com/in/janedoe")
        headline = st.text_input("Headline", value=basics.get("headline", ""), placeholder="Example: Supply Chain Analyst | Operations | Analytics")
        summary = st.text_area("Summary", value=basics.get("summary", ""), height=120, placeholder="A concise profile summary.")
        career_stage = st.selectbox(
            "Career Stage",
            CAREER_STAGES,
            index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
            key="profile-review-stage",
        )
        target_roles = st.text_input("Target Roles", value=st.session_state.target_role, placeholder="Example: Operations Analyst, Supply Chain Analyst")
        target_industries = st.text_input("Target Industries", value=st.session_state.target_industry, placeholder="Example: Supply Chain / Operations, Technology")
        preferred_locations = st.text_input("Preferred Locations", value=basics.get("preferred_locations", ""), placeholder="Example: New York, Boston, Remote")
        work_authorization = st.text_input("Work Authorization", value="", placeholder="Example: U.S. Citizen, OPT, No sponsorship needed")

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Extracted Items</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-title">We found {len(extracted_items)} suggested items from your source material.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="apple-section-copy">Review the strongest 3 items first so this feels manageable. You can reveal the rest whenever you want before saving.</div>',
            unsafe_allow_html=True,
        )
        st.success("Import complete. Start by reviewing the three strongest items below.")
        if hidden_items and not show_all_items:
            st.caption(f"{len(hidden_items)} more items are ready when you want them.")

        drafted_items: list[ProfileItem] = []
        included_count = 0
        for index, item in enumerate(visible_items):
            expander_title = f"{index + 1}. {item.item_type.title()} · {item.title or 'Untitled item'}"
            with st.expander(expander_title, expanded=True):
                keep_item = st.checkbox(
                    "Include in career profile",
                    value=item.visibility != "archived",
                    key=f"profile-review-keep-{index}",
                )
                title_col, org_col = st.columns(2, gap="large")
                with title_col:
                    item_type = st.selectbox(
                        "Item Type",
                        PROFILE_ITEM_TYPES,
                        index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                        key=f"profile-review-type-{index}",
                    )
                    title = st.text_input(
                        "Title",
                        value=item.title,
                        placeholder="Example: Operations Analyst Intern",
                        key=f"profile-review-title-{index}",
                    )
                with org_col:
                    organization = st.text_input(
                        "Organization",
                        value=item.organization,
                        placeholder="Example: Amazon or Simon Business School",
                        key=f"profile-review-organization-{index}",
                    )
                    confidence_label = f"{int(item.confidence_score * 100)}% extracted confidence"
                    st.markdown(f'<div class="apple-minor-copy">{confidence_label}</div>', unsafe_allow_html=True)

                description = st.text_area(
                    "Description",
                    value=item.description,
                    height=120,
                    placeholder="What did you do and why does it matter?",
                    key=f"profile-review-description-{index}",
                )
                bullets_text = st.text_area(
                    "Achievement Bullets",
                    value="\n".join(item.bullets),
                    height=120,
                    placeholder="One bullet per line.",
                    key=f"profile-review-bullets-{index}",
                )
                skills_text = st.text_input(
                    "Skills / Keywords",
                    value=", ".join(item.skills or item.keywords),
                    placeholder="SQL, Tableau, stakeholder management",
                    key=f"profile-review-skills-{index}",
                )

                drafted_item = ProfileItem(
                    item_type=item_type,
                    title=title.strip(),
                    organization=organization.strip(),
                    description=description.strip(),
                    bullets=_split_line_input(bullets_text),
                    skills=_split_csv_input(skills_text),
                    keywords=_split_csv_input(skills_text)[:12] or item.keywords,
                    confidence_score=item.confidence_score,
                    verification_status="verified",
                    visibility="active" if keep_item else "archived",
                )
                if keep_item and (drafted_item.title or drafted_item.description or drafted_item.bullets):
                    included_count += 1
                    drafted_items.append(drafted_item)

        for item in hidden_items if not show_all_items else []:
            drafted_item = ProfileItem(
                id=item.id,
                user_id=item.user_id,
                profile_id=item.profile_id,
                source_id=item.source_id,
                item_type=item.item_type,
                title=item.title.strip(),
                organization=item.organization.strip(),
                location=item.location,
                start_date=item.start_date,
                end_date=item.end_date,
                is_current=item.is_current,
                description=item.description.strip(),
                bullets=list(item.bullets),
                skills=list(item.skills),
                tools=list(item.tools),
                industry_tags=list(item.industry_tags),
                function_tags=list(item.function_tags),
                keywords=list(item.keywords),
                confidence_score=item.confidence_score,
                verification_status="verified",
                visibility=item.visibility,
            )
            if drafted_item.visibility != "archived" and (
                drafted_item.title or drafted_item.description or drafted_item.bullets
            ):
                included_count += 1
                drafted_items.append(drafted_item)

        if hidden_items:
            toggle_label = f"Hide {len(hidden_items)} Additional Items" if show_all_items else f"View {len(hidden_items)} More"
            if st.button(toggle_label, use_container_width=True, key="profile-review-toggle-more"):
                st.session_state.profile_review_show_all_items = not show_all_items
                logger.info(
                    "Profile review toggle clicked: expanded=%s, hidden_items=%s",
                    not show_all_items,
                    len(hidden_items),
                )
                st.rerun()

        st.markdown(
            f'<div class="apple-minor-copy" style="margin-top:0.75rem;">{included_count} items will be saved into the reusable profile library.</div>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="profile-review-back"):
            st.session_state.screen = "profile_import"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Save Career Profile", use_container_width=True, key="profile-save"):
            profile = save_profile_basics(
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                linkedin=linkedin,
                headline=headline,
                career_stage=career_stage,
                summary=summary,
                target_roles=[part.strip() for part in target_roles.split(",")],
                target_industries=[part.strip() for part in target_industries.split(",")],
                preferred_locations=[part.strip() for part in preferred_locations.split(",")],
                work_authorization=work_authorization,
            )
            source_type = "manual_notes"
            source_name = st.session_state.profile_import_source_name or "Imported Notes"
            if source_name and source_name != "Manual Notes":
                source_type = "resume"
            source_id = save_profile_source(
                source_type=source_type,
                source_name=source_name,
                raw_text=st.session_state.get("profile_last_source_raw_text", ""),
                parsed_payload={"basics": basics, "item_count": len(drafted_items)},
            )
            for item in drafted_items:
                item.profile_id = profile.id
                item.source_id = source_id
                item.verification_status = "verified"
            saved_items = save_profile_items(drafted_items, replace_existing_for_source=source_id)
            st.session_state.career_stage = career_stage
            if target_roles.strip():
                st.session_state.target_role = target_roles.split(",")[0].strip()
            if target_industries.strip():
                st.session_state.target_industry = target_industries.split(",")[0].strip()
            st.session_state.profile_last_source_id = source_id
            st.session_state.profile_extracted_items = [item.to_dict() for item in saved_items]
            st.session_state.profile_review_show_all_items = False
            logger.info(
                "Career profile saved: source=%s, included_items=%s, stage=%s",
                source_name,
                len(saved_items),
                career_stage,
            )
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_profile_dashboard_screen() -> None:
    """Persistent profile dashboard."""
    render_shell_start()
    profile = create_or_get_profile()
    sources = list_profile_sources()
    items = list_profile_items()
    active_items = [item for item in items if item.visibility == "active"]
    archived_items = [item for item in items if item.visibility == "archived"]
    verification_total = sum(1 for item in active_items if item.verification_status == "verified")
    item_type_counts = Counter(item.item_type for item in active_items)
    top_types = item_type_counts.most_common(3)

    render_screen_intro(
        "complete",
        "Career Profile Dashboard",
        "Your career profile.",
        "This is your reusable source of truth for future applications and resume generation.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Overview</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{profile.full_name or "Set up your profile identity."}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="apple-section-copy">{profile.headline or "Add a headline and preferences so the app understands how to position you."}</div>',
            unsafe_allow_html=True,
        )

        summary_stats = [
            ("Active items", str(len(active_items)), "Reusable evidence"),
            ("Verified items", str(verification_total), "Ready to reuse"),
            ("Source files", str(len(sources)), "Imported materials"),
        ]
        st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
        overview_cols = st.columns(3, gap="large")
        for col, (label, value, caption) in zip(overview_cols, summary_stats):
            with col:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-label">{label}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-value">{value}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="apple-stat-caption">{caption}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    identity_col, targets_col = st.columns(2, gap="large")
    with identity_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Identity</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Who you are.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">These details are used when the app creates profile-driven drafts and application materials.</div>', unsafe_allow_html=True)
            with st.form("profile-identity-form"):
                full_name = st.text_input("Full Name", value=profile.full_name, placeholder="Example: Jane Doe")
                email = st.text_input("Email", value=profile.email, placeholder="jane@example.com")
                phone = st.text_input("Phone", value=profile.phone, placeholder="(555) 555-5555")
                location = st.text_input("Location", value=profile.location, placeholder="New York, NY")
                linkedin = st.text_input("LinkedIn", value=profile.linkedin, placeholder="linkedin.com/in/janedoe")
                headline = st.text_input("Headline", value=profile.headline, placeholder="Supply Chain Analyst | Operations | Analytics")
                summary = st.text_area("Summary", value=profile.summary, height=120, placeholder="A concise career summary.")
                st.markdown(build_readiness_rows([
                    ("Email", profile.email or "Missing"),
                    ("Phone", profile.phone or "Missing"),
                    ("LinkedIn", profile.linkedin or "Missing"),
                ]), unsafe_allow_html=True)
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                identity_saved = st.form_submit_button("Save Identity", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            if identity_saved:
                save_profile_basics(
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    location=location,
                    linkedin=linkedin,
                    headline=headline,
                    career_stage=profile.career_stage,
                    summary=summary,
                    target_roles=profile.target_roles,
                    target_industries=profile.target_industries,
                    preferred_locations=profile.preferred_locations,
                    work_authorization=profile.work_authorization,
                )
                st.rerun()

    with targets_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Targets & Preferences</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">How you want to be positioned.</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-copy">These preferences help the matching and drafting system choose the strongest direction for each application.</div>', unsafe_allow_html=True)
            with st.form("profile-targets-form"):
                career_stage = st.selectbox(
                    "Career Stage",
                    CAREER_STAGES,
                    index=CAREER_STAGES.index(profile.career_stage) if profile.career_stage in CAREER_STAGES else 0,
                )
                work_authorization = st.text_input(
                    "Work Authorization",
                    value=profile.work_authorization,
                    placeholder="OPT, U.S. Citizen, No sponsorship needed",
                )
                target_roles = st.text_input(
                    "Target Roles",
                    value=", ".join(profile.target_roles),
                    placeholder="Operations Analyst, Supply Chain Analyst",
                )
                target_industries = st.text_input(
                    "Target Industries",
                    value=", ".join(profile.target_industries),
                    placeholder="Supply Chain / Operations, Technology",
                )
                preferred_locations = st.text_input(
                    "Preferred Locations",
                    value=", ".join(profile.preferred_locations),
                    placeholder="New York, Boston, Remote",
                )
                st.markdown(build_readiness_rows([
                    ("Career stage", profile.career_stage or "Not set"),
                    ("Target roles", ", ".join(profile.target_roles) if profile.target_roles else "Missing"),
                    ("Preferred locations", ", ".join(profile.preferred_locations) if profile.preferred_locations else "Missing"),
                ]), unsafe_allow_html=True)
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                targets_saved = st.form_submit_button("Save Targets", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            if targets_saved:
                save_profile_basics(
                    full_name=profile.full_name,
                    email=profile.email,
                    phone=profile.phone,
                    location=profile.location,
                    linkedin=profile.linkedin,
                    headline=profile.headline,
                    career_stage=career_stage,
                    summary=profile.summary,
                    target_roles=_split_csv_input(target_roles),
                    target_industries=_split_csv_input(target_industries),
                    preferred_locations=_split_csv_input(preferred_locations),
                    work_authorization=work_authorization,
                )
                st.rerun()

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Source Documents</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">What your profile was built from.</div>', unsafe_allow_html=True)
        if not sources:
            st.markdown('<div class="apple-minor-copy">No source documents yet. Import a resume or notes to start building your profile memory.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="apple-section-copy">These materials helped create and expand your reusable evidence library.</div>', unsafe_allow_html=True)
            for source in sources[:8]:
                with st.container(border=True):
                    source_rows = [
                        ("Type", source.source_type.replace("_", " ").title()),
                        ("Name", source.source_name or "Untitled source"),
                        ("Status", source.parsed_status.title()),
                    ]
                    st.markdown(f"**{source.source_name or 'Untitled source'}**")
                    st.markdown(build_readiness_rows(source_rows), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Profile Library</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(active_items)} active evidence items</div>', unsafe_allow_html=True)
        source_names = ", ".join(source.source_name for source in sources[:4]) if sources else "No imported sources yet"
        st.markdown(f'<div class="apple-section-copy">Recent sources: {source_names}</div>', unsafe_allow_html=True)
        if active_items:
            summary_stats = [
                ("Verified items", str(verification_total), "Ready to reuse"),
                ("Source files", str(len(sources)), "Imported materials"),
                ("Top category", top_types[0][0].title() if top_types else "None yet", f"{top_types[0][1]} items" if top_types else "Add your first item"),
            ]
            st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
            stat_cols = st.columns(3, gap="large")
            for col, (label, value, caption) in zip(stat_cols, summary_stats):
                with col:
                    st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-label">{label}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-value">{value}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="apple-stat-caption">{caption}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if top_types:
                st.markdown(
                    f'<div class="apple-minor-copy" style="margin-top:0.75rem;">Your strongest saved categories right now: {", ".join(f"{name.title()} ({count})" for name, count in top_types)}.</div>',
                    unsafe_allow_html=True,
                )
        if not active_items:
            st.markdown('<div class="apple-minor-copy">Import a resume or notes to start building your reusable experience bank.</div>', unsafe_allow_html=True)
        else:
            grouped_items: dict[str, list[ProfileItem]] = {}
            for item in active_items:
                grouped_items.setdefault(item.item_type, []).append(item)

            for group_name, group_items in grouped_items.items():
                with st.expander(f"{group_name.title()} · {len(group_items)} items", expanded=group_name in {"experience", "project"}):
                    for index, item in enumerate(group_items, start=1):
                        with st.container(border=True):
                            st.markdown(f"**{index}. {item.title or 'Untitled item'}**")
                            st.markdown(f'<div class="apple-minor-copy">{item.organization or "Organization not specified"} · {item.verification_status.title()}</div>', unsafe_allow_html=True)
                            with st.form(key=f"profile-edit-form-{item.id}"):
                                meta_col1, meta_col2 = st.columns(2, gap="large")
                                with meta_col1:
                                    edited_type = st.selectbox(
                                        "Item Type",
                                        PROFILE_ITEM_TYPES,
                                        index=PROFILE_ITEM_TYPES.index(item.item_type) if item.item_type in PROFILE_ITEM_TYPES else 0,
                                        key=f"profile-edit-type-{item.id}",
                                    )
                                    edited_title = st.text_input(
                                        "Title",
                                        value=item.title,
                                        placeholder="Role, project, certification, or activity name",
                                        key=f"profile-edit-title-{item.id}",
                                    )
                                with meta_col2:
                                    edited_org = st.text_input(
                                        "Organization",
                                        value=item.organization,
                                        placeholder="Company, school, club, or organization",
                                        key=f"profile-edit-org-{item.id}",
                                    )
                                    edited_location = st.text_input(
                                        "Location",
                                        value=item.location,
                                        placeholder="Optional location",
                                        key=f"profile-edit-location-{item.id}",
                                    )

                                edited_description = st.text_area(
                                    "Description",
                                    value=item.description,
                                    height=100,
                                    placeholder="What happened here and why does it matter?",
                                    key=f"profile-edit-description-{item.id}",
                                )
                                edited_bullets = st.text_area(
                                    "Achievement Bullets",
                                    value="\n".join(item.bullets),
                                    height=120,
                                    placeholder="One bullet per line.",
                                    key=f"profile-edit-bullets-{item.id}",
                                )
                                edited_skills = st.text_input(
                                    "Skills / Keywords",
                                    value=", ".join(item.skills or item.keywords),
                                    placeholder="SQL, operations, leadership, Tableau",
                                    key=f"profile-edit-skills-{item.id}",
                                )

                                action_col1, action_col2, action_col3 = st.columns([1, 1, 1], gap="large")
                                with action_col1:
                                    save_pressed = st.form_submit_button("Save Changes", use_container_width=True)
                                with action_col2:
                                    verify_pressed = st.form_submit_button("Verify", use_container_width=True)
                                with action_col3:
                                    archive_pressed = st.form_submit_button("Archive", use_container_width=True)

                            if save_pressed or verify_pressed:
                                updated_item = ProfileItem(
                                    id=item.id,
                                    user_id=item.user_id,
                                    profile_id=item.profile_id,
                                    source_id=item.source_id,
                                    item_type=edited_type,
                                    title=edited_title.strip(),
                                    organization=edited_org.strip(),
                                    location=edited_location.strip(),
                                    description=edited_description.strip(),
                                    bullets=_split_line_input(edited_bullets),
                                    skills=_split_csv_input(edited_skills),
                                    keywords=_split_csv_input(edited_skills)[:12] or item.keywords,
                                    confidence_score=item.confidence_score,
                                    verification_status="verified" if verify_pressed else item.verification_status,
                                    visibility=item.visibility,
                                    created_at=item.created_at,
                                    updated_at=item.updated_at,
                                )
                                update_profile_item(updated_item)
                                if verify_pressed and item.verification_status != "verified":
                                    update_profile_item_verification(item.id, "verified")
                                st.rerun()

                            if archive_pressed:
                                archive_profile_item(item.id)
                                st.rerun()

            if archived_items:
                with st.expander(f"Archived Items · {len(archived_items)}", expanded=False):
                    st.markdown('<div class="apple-minor-copy">Archived items stay in memory but are not used as active profile evidence.</div>', unsafe_allow_html=True)
                    for item in archived_items:
                        row_col1, row_col2 = st.columns([4, 1], gap="large")
                        with row_col1:
                            st.markdown(f"**{item.title or 'Untitled item'}**")
                            st.markdown(f'<div class="apple-minor-copy">{item.item_type.title()} · {item.organization or "Organization not specified"}</div>', unsafe_allow_html=True)
                        with row_col2:
                            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                            if st.button("Restore", use_container_width=True, key=f"profile-restore-{item.id}"):
                                archive_profile_item(item.id, visibility="active")
                                st.rerun()
                            st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Import More Materials", use_container_width=True, key="profile-dashboard-import"):
            st.session_state.screen = "profile_import"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Match Profile to Job", use_container_width=True, key="profile-dashboard-match"):
            st.session_state.screen = "application_match"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Application Workspace", use_container_width=True, key="profile-dashboard-workspace"):
            st.session_state.screen = "application_workspace"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Back to Home", use_container_width=True, key="profile-dashboard-home"):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_application_match_screen() -> None:
    """Recommend profile evidence to use for the current application."""
    render_shell_start()
    render_screen_intro(
        "application_match",
        "Career Profile Match",
        "Choose the strongest evidence for this job.",
        "We ranked your saved profile items against the current job description so you can decide what should guide the prompt.",
    )

    active_items = [item for item in list_profile_items() if item.visibility == "active"]
    job_description = st.session_state.job_description.strip()
    resume_loaded = bool(st.session_state.resume_text)

    if not job_description or not active_items:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Not Ready Yet</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">This step needs a job description and active profile items.</div>', unsafe_allow_html=True)
            readiness_rows = [
                ("Resume uploaded", "Yes" if resume_loaded else "Optional for draft mode"),
                ("Job description", "Loaded" if job_description else "Missing"),
                ("Active profile items", str(len(active_items))),
            ]
            st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)
        left_col, right_col = st.columns(2, gap="large")
        with left_col:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Upload", use_container_width=True, key="application-match-back-input"):
                st.session_state.screen = "input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with right_col:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Open Profile Dashboard", use_container_width=True, key="application-match-profile-dashboard"):
                st.session_state.screen = "profile_dashboard"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        render_shell_end()
        return

    target_role = get_effective_target_role(job_description)
    target_industry = get_effective_industry(job_description)
    job_signals, ranked_results = rank_profile_items(active_items, job_description, target_role=target_role, target_industry=target_industry)

    recommended_ids = [result["item"].id for result in ranked_results[:5] if result["score"] > 0 and result["item"].id is not None]
    current_selection = st.session_state.get("selected_profile_item_ids", [])
    if not current_selection:
        st.session_state.selected_profile_item_ids = recommended_ids
        current_selection = recommended_ids

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Job Signals</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">What we detected from the target job.</div>', unsafe_allow_html=True)
        company = st.text_input(
            "Company",
            value=st.session_state.get("current_application_company", ""),
            placeholder="Optional company name",
            key="application-match-company",
        )
        st.session_state.current_application_company = company
        signal_rows = [
            ("Target role", target_role or "Not detected"),
            ("Company", company or "Not set yet"),
            ("Industry", target_industry or "Not detected"),
            ("Top keywords", ", ".join(job_signals.get("keywords", [])[:8]) or "No clear keywords yet"),
        ]
        st.markdown(build_readiness_rows(signal_rows), unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Recommended Evidence</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Select what should guide the tailored resume.</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-copy">The prompt will use these saved items as relevance guidance while still staying anchored to the uploaded resume.</div>', unsafe_allow_html=True)

        selected_ids: list[int] = []
        for index, result in enumerate(ranked_results[:10], start=1):
            item = result["item"]
            item_id = item.id if item.id is not None else -index
            default_selected = item_id in current_selection
            with st.container(border=True):
                include_item = st.checkbox(
                    f"Use item {index}",
                    value=default_selected,
                    key=f"profile-match-include-{item_id}",
                )
                st.markdown(f"**{item.title or 'Untitled item'}**")
                st.markdown(f'<div class="apple-minor-copy">{item.item_type.title()} · {item.organization or "Organization not specified"} · Score {result["score"]:.1f}</div>', unsafe_allow_html=True)
                if item.description:
                    st.markdown(item.description)
                if result["reasons"]:
                    st.markdown(f'<div class="apple-minor-copy">Why selected: {" | ".join(result["reasons"][:3])}</div>', unsafe_allow_html=True)
                if item.skills:
                    st.markdown(f'<div class="apple-minor-copy">Skills: {", ".join(item.skills[:8])}</div>', unsafe_allow_html=True)
                if include_item and item.id is not None:
                    selected_ids.append(item.id)

        st.session_state.selected_profile_item_ids = selected_ids
        st.session_state.profile_job_signals = job_signals

    back_col, optimize_col, draft_col = st.columns([0.8, 1.1, 1.1], gap="large")
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="application-match-back"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with optimize_col:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Optimize Existing Resume", use_container_width=True, key="application-match-continue", disabled=not (selected_ids and resume_loaded)):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_optimize")
            st.session_state.show_fit_details = False
            _evaluate_current_resume_fit(force=True)
            st.session_state.screen = "fit_report"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with draft_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Create Draft from Profile", use_container_width=True, key="application-match-draft", disabled=not selected_ids):
            st.session_state.use_career_profile = True
            _save_current_application(status="ready_to_draft")
            _start_profile_draft_flow()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_application_workspace_screen() -> None:
    """Saved jobs / application workspaces."""
    render_shell_start()
    applications = list_applications()
    render_screen_intro(
        "application_match",
        "Application Workspace",
        "Your saved job targets.",
        "Return to a job, review selected profile evidence, or start a new application from the profile system.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Workspace Summary</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-section-title">{len(applications)} saved applications</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Each application stores the job target, job description, selected career-profile evidence, and current workflow status.</div>',
            unsafe_allow_html=True,
        )
        if not applications:
            st.markdown('<div class="apple-minor-copy">No saved applications yet. Paste a job description, use your Career Profile, and choose evidence to create the first workspace.</div>', unsafe_allow_html=True)

    for application in applications:
        with st.container(border=True):
            title = application.job_title or "Untitled target role"
            company_suffix = f" at {application.company}" if application.company else ""
            st.markdown('<div class="apple-kicker">Saved Application</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="apple-section-title">{title}{company_suffix}</div>', unsafe_allow_html=True)
            rows = [
                ("Company", application.company or "Not set"),
                ("Industry", application.industry or "Not detected"),
                ("Status", application.status.replace("_", " ").title()),
                ("Selected evidence", str(len(application.selected_profile_item_ids))),
                ("Updated", application.updated_at),
            ]
            st.markdown(build_readiness_rows(rows), unsafe_allow_html=True)
            preview = " ".join(application.job_description.split())[:320]
            if preview:
                st.markdown(f'<div class="apple-section-copy">{preview}{"..." if len(preview) == 320 else ""}</div>', unsafe_allow_html=True)

            action_col1, action_col2, action_col3 = st.columns(3, gap="large")
            with action_col1:
                st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                if st.button("Open Evidence Match", use_container_width=True, key=f"application-open-match-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "application_match"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with action_col2:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Optimize / Run", use_container_width=True, key=f"application-open-mode-{application.id}"):
                    _load_application_into_session(application.id)
                    st.session_state.screen = "mode" if st.session_state.resume_text else "application_match"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with action_col3:
                st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                if st.button("Create Profile Draft", use_container_width=True, key=f"application-open-draft-{application.id}", disabled=not application.selected_profile_item_ids):
                    _load_application_into_session(application.id)
                    _start_profile_draft_flow()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Profile", use_container_width=True, key="application-workspace-profile"):
            st.session_state.screen = "profile_dashboard"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Add Job / Upload", use_container_width=True, key="application-workspace-input"):
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Home", use_container_width=True, key="application-workspace-home"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_input_screen() -> None:
    """Resume and job input screen (redesigned for simplicity)."""
    def fetch_and_store_job_description(job_input: str) -> bool:
        """Fetch, clean, and store JD text from a pasted URL."""
        try:
            with st.spinner("Validating link and extracting the job description..."):
                extracted_text, final_url, role_hint = fetch_job_description_from_url(job_input)
            cleaning_result = clean_job_description(extracted_text)
            cleaned_text = cleaning_result["cleaned_text"]
            st.session_state.job_description = cleaned_text
            st.session_state.pending_job_description_input = cleaned_text
            st.session_state.jd_source_url = final_url
            st.session_state.jd_cleaning_result = cleaning_result
            st.session_state.jd_role_hint = role_hint or detect_role_title(cleaned_text)
            st.success("Job description extracted and cleaned successfully. Review the text below before continuing.")
            return True
        except Exception as error:
            st.warning(f"{error} Please paste the job description text manually if the page blocks extraction.")
            return False

    def clean_pasted_job_description(job_input: str) -> bool:
        """Normalize manually pasted JD text so downstream detection is cleaner."""
        cleaned_result = clean_job_description(job_input)
        cleaned_text = cleaned_result["cleaned_text"]
        st.session_state.job_description = cleaned_text
        st.session_state.pending_job_description_input = cleaned_text
        st.session_state.jd_source_url = ""
        st.session_state.jd_cleaning_result = cleaned_result
        st.session_state.jd_role_hint = detect_role_title(cleaned_text)
        st.success("Job description cleaned and ready. Review the text below before continuing.")
        return True

    render_shell_start()
    render_screen_intro(
        "input",
        "Step 1 of 5",
        "Bring in your resume. Then point it at the role you want.",
        "We'll clean the job description, detect the signals that matter, and keep the next step simple.",
    )

    upload_col, jd_col = st.columns([1, 1.15], gap="large")
    with upload_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Upload your resume</div>
                <div class="apple-section-copy">Use a <code>.docx</code> or <code>.pdf</code> file. We preserve the document structure so the finished export still feels like your original resume, just sharper.</div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader("Upload Resume (.docx or .pdf)", type=["docx", "pdf"], label_visibility="collapsed")
            if uploaded_file is not None:
                save_uploaded_resume(uploaded_file)
                st.success(f"Loaded `{uploaded_file.name}`")
                render_chip_row([uploaded_file.name, "Ready for optimization"])

    with jd_col:
        with st.container(border=True):
            st.markdown(
                """
                <div class="apple-section-title">Paste a job description or link</div>
                <div class="apple-section-copy">Use the full posting or a job link. We'll turn it into a cleaner brief for the next step and surface the role signals automatically.</div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.pending_job_description_input is not None:
                st.session_state.job_description_input = st.session_state.pending_job_description_input
                st.session_state.pending_job_description_input = None

            if "job_description_input" not in st.session_state:
                st.session_state.job_description_input = st.session_state.job_description

            job_description = st.text_area(
                "Job Description",
                height=130,
                placeholder="Paste the job description here, or drop in a job-post URL.",
                key="job_description_input",
                label_visibility="collapsed",
            )
            job_description = st.session_state.get("job_description_input", job_description)
            st.markdown(
                "<div class=\"apple-minor-copy\">We'll clean the text, detect the target role, and prepare the prompt inputs for you.</div>",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Process Job Description", use_container_width=True):
                current_input = st.session_state.get("job_description_input", job_description)
                if looks_like_url(current_input):
                    if fetch_and_store_job_description(current_input):
                        st.rerun()
                elif current_input.strip():
                    if clean_pasted_job_description(current_input):
                        st.rerun()
                else:
                    st.info("Paste a job description or job link first.")
            st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.job_description = job_description
    st.session_state.career_stage = "Manager"  # Default to Manager for mode selection
    st.session_state.target_role = ""
    st.session_state.target_industry = ""

    col1, col2, col3 = st.columns([0.7, 0.9, 1.1], gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        active_profile_items = [item for item in list_profile_items() if item.visibility == "active"]
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Use Career Profile", use_container_width=True, disabled=not bool(job_description.strip() and active_profile_items), key="input-use-profile"):
            st.session_state.use_career_profile = True
            st.session_state.screen = "application_match"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
        )
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Continue", use_container_width=True, disabled=not can_continue):
            st.session_state.use_career_profile = False
            st.session_state.selected_profile_item_ids = []
            st.session_state.show_fit_details = False
            if looks_like_url(job_description):
                if fetch_and_store_job_description(job_description):
                    st.rerun()
            else:
                st.session_state.jd_cleaning_result = None
                _evaluate_current_resume_fit(force=True)
                st.session_state.screen = "fit_report"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_score_tile(label: str, score: int, caption: str = "") -> None:
    """Render one compact score tile."""
    st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="apple-kicker">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="apple-stat-value">{score}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_fit_delta_card(before_report: dict, after_report: dict) -> None:
    """Render an honest before/after fit comparison."""
    before_score = int(before_report.get("overall_score", 0))
    after_score = int(after_report.get("overall_score", 0))
    delta = after_score - before_score

    if delta > 0:
        title = f"Estimated fit improved by {delta} point{'s' if delta != 1 else ''}."
    elif delta < 0:
        title = f"Estimated fit dropped by {abs(delta)} point{'s' if abs(delta) != 1 else ''}."
    else:
        title = "Estimated fit stayed flat."

    new_keyword_matches = [
        keyword
        for keyword in after_report.get("matched_keywords", [])
        if keyword not in before_report.get("matched_keywords", [])
    ]

    with st.container(border=True):
        st.markdown('<div class="apple-summary-label">Improvement Report</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-summary-title">{title}</div>', unsafe_allow_html=True)

        score_col1, score_col2, score_col3, score_col4 = st.columns(4, gap="large")
        with score_col1:
            render_score_tile("Before", before_score, "Pre-optimization")
        with score_col2:
            render_score_tile("After", after_score, "Validated replacement draft")
        with score_col3:
            render_score_tile("Change", delta, "Point movement")
        with score_col4:
            render_score_tile(
                "Keyword Gain",
                int(after_report.get("keyword_score", 0)) - int(before_report.get("keyword_score", 0)),
                "Job-language movement",
            )

        readiness_rows = [
            ("Keyword score", f"{before_report.get('keyword_score', 0)} → {after_report.get('keyword_score', 0)}"),
            ("Skill score", f"{before_report.get('skill_score', 0)} → {after_report.get('skill_score', 0)}"),
            ("ATS / clarity", f"{before_report.get('ats_score', 0)} → {after_report.get('ats_score', 0)}"),
            ("New matched keywords", ", ".join(new_keyword_matches[:6]) if new_keyword_matches else "No new keyword wins yet"),
        ]
        st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

        if delta <= 0:
            st.caption("Honest take: this revision may still need stronger evidence or sharper job-language alignment before it is truly better.")


def render_fit_report_screen() -> None:
    """Pre-optimization match report with match % circle and key signals (redesigned)."""
    report = _evaluate_current_resume_fit()
    score = report.get("overall_score", 0)

    # Get match band label
    if score >= 85:
        band = "EXCELLENT MATCH"
        band_color = "#27ae60"  # Green
    elif score >= 70:
        band = "STRONG MATCH"
        band_color = "#2ecc71"  # Lighter green
    elif score >= 50:
        band = "FAIR MATCH"
        band_color = "#f39c12"  # Orange
    else:
        band = "POOR MATCH"
        band_color = "#e74c3c"  # Red

    # Extract key signals
    signals = extract_key_signals(
        st.session_state.resume_text,
        st.session_state.job_description
    )

    job_title = get_effective_target_role(st.session_state.job_description) or "This role"
    company = st.session_state.get("current_application_company", "").strip()

    logger.info(
        "Pre-optimization match shown: score=%s, job_title=%s, company=%s, signals=%s",
        score,
        job_title,
        company or "Unknown",
        len(signals.get("matches", [])) + len(signals.get("gaps", []))
    )

    render_shell_start()
    render_screen_intro(
        "fit_report",
        "Step 2 of 5",
        "Answer the big question first: should you apply?",
        "We show your match score and the key signals. Start with the recommendation, then decide whether to optimize.",
    )

    # Match % Circle Display
    st.markdown("<div style='text-align: center; margin: 2rem 0;'>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display: inline-flex; flex-direction: column; align-items: center;">
        <div style="position: relative; width: 220px; height: 220px; margin: 0 auto;">
            <svg width="220" height="220" viewBox="0 0 220 220" style="transform: rotate(-90deg);">
                <!-- Background circle -->
                <circle cx="110" cy="110" r="100" fill="none" stroke="#e0e0e0" stroke-width="20"/>
                <!-- Progress circle -->
                <circle cx="110" cy="110" r="100" fill="none" stroke="{band_color}" stroke-width="20"
                        stroke-dasharray="{score * 2.09} 628"
                        stroke-linecap="round" style="transition: stroke-dasharray 0.5s;"/>
            </svg>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
                <div style="font-size: 56px; font-weight: bold; color: #333;">{score}%</div>
                <div style="font-size: 14px; color: #666; margin-top: 0.5rem;">{band}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Job Title Context
    st.markdown(f"""
    <div style="text-align: center; margin: 1.5rem 0;">
        <div style="font-size: 18px; font-weight: 600;">{job_title}{f" at {company}" if company else ""}</div>
    </div>
    """, unsafe_allow_html=True)

    # Match Recommendation Section
    with st.container(border=True):
        if score >= 80:
            recommendation = "Strong fit 💪 - Your resume aligns well with this role. Optimize to maximize impact."
            color = "#2ecc71"  # Green
        elif score >= 60:
            recommendation = "Fair fit 🎯 - Potential match. Optimize to improve your chances significantly."
            color = "#f39c12"  # Orange
        else:
            recommendation = "Weak fit ⚠️ - Limited alignment. Optimization might help, but consider if the role is right for you."
            color = "#e74c3c"  # Red

        st.markdown(f"""
        <div style="text-align: center; padding: 1rem; border-left: 4px solid {color};">
            <div style="font-size: 16px; color: {color}; font-weight: 600;">{recommendation}</div>
        </div>
        """, unsafe_allow_html=True)

    # Action Buttons
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    action_col1, action_col2 = st.columns(2, gap="large")

    with action_col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Upload", use_container_width=True, key="fit-back"):
            logger.info("User returned to upload from fit_report: score=%s", score)
            st.session_state.screen = "input"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with action_col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        button_text = "See Details" if score < 50 else "Optimize Now"
        if st.button(button_text, use_container_width=True, key="fit-optimize"):
            logger.info("User proceeding to optimization: score=%s, button=%s", score, button_text)
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    render_shell_end()


def render_mode_screen() -> None:
    """Execution mode selection screen (redesigned - API is default)."""
    render_shell_start()
    render_screen_intro(
        "mode",
        "Step 3 of 5",
        "Choose your path to optimization.",
        "Both paths use the same powerful prompt and validation flow. Pick the one that fits your workflow.",
    )

    selected_profile_items = _get_selected_profile_items()
    if st.session_state.get("use_career_profile") and selected_profile_items:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Career Profile Guidance</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-section-title">{len(selected_profile_items)} saved profile items will guide this run.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="apple-section-copy">The prompt will prioritize these items as relevance evidence while still keeping all output anchored to the uploaded resume text.</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                build_inline_chip_row([item.title or item.item_type.title() for item in selected_profile_items[:4]]),
                unsafe_allow_html=True,
            )

    # API Mode - Primary (Recommended)
    with st.container(border=True):
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div class="apple-kicker">RECOMMENDED</div>
            </div>
            <div class="apple-choice-title">Let the app run it (Automatic)</div>
            <div class="apple-section-copy">We'll handle the optimization end-to-end. Provide your API key, and we'll generate, run, validate, and have you ready to download in 30 seconds with no copy-paste.</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Use API Mode →", use_container_width=True, key="mode-api"):
            logger.info("User selected API mode")
            st.session_state.execution_mode = "api"
            st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
            st.session_state.api_prompt_customized = False
            st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
            st.session_state.screen = "api"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; color: #999; font-size: 12px;'>OR</div>", unsafe_allow_html=True)
    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    # Manual Mode - Secondary
    with st.container(border=True):
        st.markdown(
            """
            <div class="apple-kicker">Manual Control</div>
            <div class="apple-choice-title">I want to manage the optimization</div>
            <div class="apple-section-copy">Copy the prompt, paste it into ChatGPT/Claude/Gemini/your choice, get the result, and bring it back. Great if you want to compare outputs or use free tools.</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Use Manual Mode →", use_container_width=True, key="mode-manual"):
            logger.info("User selected manual mode")
            st.session_state.execution_mode = "manual"
            st.session_state.generated_prompt = _build_optimizer_prompt_from_state()
            st.session_state.api_prompt_customized = False
            st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
            st.session_state.screen = "manual"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)

    back_col = st.columns([1])[0]
    with back_col:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="mode-back"):
            st.session_state.screen = "fit_report"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def handle_validated_payload(payload: dict) -> None:
    """Store validation state and move to review."""
    baseline_report = st.session_state.baseline_fit_report or _evaluate_current_resume_fit(force=True)
    optimized_resume_text = _build_optimized_resume_text(payload)
    replacements = collect_replacements(payload)
    logger.info(
        "Optimization started: replacements=%s, resume=%s",
        len(replacements),
        st.session_state.resume_name or "unknown",
    )
    st.session_state.optimized_fit_report = evaluate_resume_fit(
        optimized_resume_text,
        st.session_state.job_description or "",
        selected_profile_items=_get_selected_profile_items(),
    )
    st.session_state.baseline_fit_report = baseline_report
    st.session_state.validated_payload = payload
    st.session_state.validation_summary = build_validation_summary(payload)
    st.session_state.review_details = analyze_payload(payload)
    st.session_state.output_docx_bytes = None
    st.session_state.output_filename = None
    st.session_state.show_review_changes = False
    st.session_state.optimization_change_examples = build_change_examples(
        st.session_state.review_details.get("results", []),
        limit=3,
    )
    st.session_state.optimization_metrics_summary = build_optimization_metrics_summary(
        baseline_report,
        st.session_state.optimized_fit_report or {},
    )

    # Calculate match scores and save optimization result for history
    match_score_before = int(baseline_report.get("overall_score", 0))
    match_score_after = int((st.session_state.optimized_fit_report or {}).get("overall_score", 0))

    # Generate improvements summary
    improvements = generate_improvements_summary(
        optimized_replacements=payload.get("replacements", []) if isinstance(payload, dict) else [],
        jd_text=st.session_state.job_description or "",
        max_improvements=5,
        min_impact="high"
    )

    # Save to optimization history database
    try:
        save_optimization_result(
            user_id="local-user",
            company_name=st.session_state.get("current_application_company", "").strip() or "Untitled Company",
            job_title=st.session_state.get("current_target_role", "").strip() or "Untitled Role",
            job_description=st.session_state.job_description or "",
            match_before=match_score_before,
            match_after=match_score_after,
            improvements=improvements,
            resume_used_id="",
        )
    except Exception as e:
        logger.warning("Failed to save optimization result: %s", str(e))

    logger.info(
        "Optimization completed: replacements=%s, before_fit=%s, after_fit=%s",
        len(replacements),
        match_score_before,
        match_score_after,
    )
    st.session_state.screen = "review"



def render_manual_screen() -> None:
    """Manual BYOM screen."""
    render_screen_intro(
        "manual",
        "Step 4 of 5",
        "Manual Optimization",
        "Copy the prompt into your AI tool, then paste the structured result back here.",
    )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Step 1</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Copy the generated prompt.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Manual copy-paste works best on desktop. Ask your AI tool to return only the structured JSON result.</div>',
            unsafe_allow_html=True,
        )
        render_prompt_block("Generated Prompt", st.session_state.generated_prompt or "", 320, "manual")
        st.markdown('<div class="apple-kicker">Step 2</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Follow the handoff steps.</div>', unsafe_allow_html=True)
        render_instruction_panel(
            "What To Do Next",
            [
                "Copy the prompt above and paste it into ChatGPT, Claude, or Gemini. Include the same resume you uploaded in the box.",
                "Ask the AI to return only the structured JSON output with no extra explanation.",
                "Paste the AI result into the box below, then click Validate Output.",
            ],
        )

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Step 3</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Paste the AI response.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">Bring back the full structured output exactly as your AI tool returned it.</div>',
            unsafe_allow_html=True,
        )
        pasted_output = st.text_area(
            "Paste Structured AI Output",
            height=260,
            placeholder="Paste the AI response here.",
        )

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Validate Output", use_container_width=True):
            try:
                payload = parse_replacement_payload(pasted_output)
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)


def render_api_screen() -> None:
    """Multi-provider API mode screen."""
    render_screen_intro(
        "api",
        "Step 4 of 5",
        "Run via API",
        "Use your own hosted or local model. The app validates the output before export.",
    )

    if not st.session_state.api_prompt_override and st.session_state.generated_prompt:
        st.session_state.api_prompt_override = st.session_state.generated_prompt

    api_key = ""
    base_url = ""
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Setup</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Choose your provider.</div>', unsafe_allow_html=True)

        provider = st.selectbox(
            "Provider",
            list(PROVIDER_CONFIG.keys()),
            index=list(PROVIDER_CONFIG.keys()).index(st.session_state.selected_provider),
        )
        st.session_state.selected_provider = provider
        provider_config = PROVIDER_CONFIG[provider]
        st.markdown(
            f'<div class="apple-section-copy">{provider_config.get("description", "")}</div>',
            unsafe_allow_html=True,
        )

        if provider == "Local Model / Custom Endpoint":
            st.markdown(
                '<div class="apple-section-copy">Works with Ollama and other OpenAI-compatible local endpoints.</div>',
                unsafe_allow_html=True,
            )
            base_url = st.text_input(
                "Base URL",
                value=st.session_state.custom_api_base_url,
                placeholder="http://localhost:11434/v1",
                help="For Ollama, use http://localhost:11434/v1",
            )
            model = st.text_input(
                "Model name",
                value=st.session_state.custom_api_model,
                placeholder="mistral",
                help="Use the exact local model tag available on your machine.",
            )
            api_key = st.text_input(
                provider_config["key_label"],
                type="password",
                value=st.session_state.custom_api_key,
                placeholder=provider_config["placeholder"],
                help="Most local endpoints do not require a key. Leave blank if not needed.",
            )
            st.session_state.custom_api_base_url = base_url
            st.session_state.custom_api_model = model
            st.session_state.custom_api_key = api_key
            st.markdown(
                '<div class="apple-section-copy">Local models can return malformed JSON. If that happens, retry or switch to Manual Mode.</div>',
                unsafe_allow_html=True,
            )
        else:
            api_key = st.text_input(
                provider_config["key_label"],
                type="password",
                placeholder=provider_config["placeholder"],
            )
            model = st.selectbox("Model", provider_config["models"], index=0)
            st.markdown(
                '<div class="apple-section-copy">Your key is used only for this session and is not stored.</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="apple-section-copy">After the provider responds, the same JSON validator and exact-match review still run before export.</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Prompt Preview", expanded=False):
            customize_prompt = st.checkbox(
                "Customize prompt before sending",
                value=st.session_state.api_prompt_customized,
                help="Advanced option. Editing the prompt may reduce JSON reliability.",
            )
            st.session_state.api_prompt_customized = customize_prompt
            if customize_prompt:
                edited_prompt = st.text_area(
                    "Editable Prompt",
                    value=st.session_state.api_prompt_override or st.session_state.generated_prompt or "",
                    height=260,
                    key="api-prompt-editor",
                    help="Advanced option. Keep the JSON instructions intact for best results.",
                )
                st.session_state.api_prompt_override = edited_prompt
                if st.button("Reset to Recommended Prompt", key="reset-api-prompt"):
                    st.session_state.api_prompt_override = st.session_state.generated_prompt or ""
                    st.session_state.api_prompt_customized = False
                    st.rerun()
                st.markdown(
                    '<div class="apple-section-copy">Changing the prompt may reduce JSON reliability. Use this only if you know what you want to adjust.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.text_area(
                    "Prompt Preview",
                    value=st.session_state.generated_prompt or "",
                    height=220,
                    disabled=True,
                )

    prompt_to_send = (
        st.session_state.api_prompt_override.strip()
        if st.session_state.api_prompt_customized and st.session_state.api_prompt_override.strip()
        else st.session_state.generated_prompt
    )

    checklist = [
        ("Resume", "Loaded" if st.session_state.resume_name else "Missing"),
        ("Job description", "Loaded" if st.session_state.job_description.strip() else "Missing"),
        ("Provider", provider),
        ("Model", model if model else "Missing"),
        ("Prompt mode", "Customized" if st.session_state.api_prompt_customized else "Recommended"),
    ]
    if provider == "Local Model / Custom Endpoint":
        checklist.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
    else:
        checklist.append(("API key", "Provided" if api_key.strip() else "Missing"))
    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
        st.markdown(build_readiness_rows(checklist), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Run Optimization", use_container_width=True):
            try:
                with st.spinner(f"Sending prompt to {provider}..."):
                    payload = optimize_with_provider(
                        provider=provider,
                        api_key=api_key,
                        prompt=prompt_to_send,
                        model=model,
                        base_url=base_url,
                    )
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Switch to Manual Mode", use_container_width=True):
            st.session_state.execution_mode = "manual"
            st.session_state.screen = "manual"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_review_screen() -> None:
    """Validation and export screen."""
    summary = st.session_state.validation_summary or {}
    stats = summary.get("stats", {})
    review_details = st.session_state.review_details or {}
    review_stats = review_details.get("stats", {})
    review_results = review_details.get("results", [])
    review_warnings = review_details.get("warnings", [])
    ready_for_export = review_stats.get("ready_for_export", False)
    manual_review_count = review_stats.get("unmatched_replacements", 0) + review_stats.get("duplicate_replacements", 0)
    grouped_results = _group_review_results(review_results)
    baseline_report = st.session_state.baseline_fit_report or {}
    optimized_report = st.session_state.optimized_fit_report or {}
    change_examples = st.session_state.get("optimization_change_examples", [])
    metrics_summary = st.session_state.get("optimization_metrics_summary", [])
    target_job_title = get_effective_target_role(st.session_state.job_description) or "your target role"
    target_company = st.session_state.get("current_application_company", "").strip()

    if ready_for_export and not st.session_state.output_docx_bytes:
        try:
            ensure_export_file_ready()
        except Exception as error:
            st.error(str(error))
            ready_for_export = False

    render_screen_intro(
        "review",
        "Step 4 of 5",
        "Validation and Export",
        "Review the optimized result, confirm the changes, and download when everything looks right.",
    )
    if not st.session_state.show_review_changes:
        if ready_for_export:
            st.success("Optimization complete. Your resume is validated and ready to download.")
        else:
            st.warning("This result needs review before export.")
            st.markdown("We validated the structured output, but some replacements still need attention before download.")

        with st.container(border=True):
            st.markdown('<div class="apple-summary-label">Success Snapshot</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="apple-summary-title">Optimized for {target_job_title}{f" at {target_company}" if target_company else ""}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="apple-section-copy">Review the most important changes first, then decide whether to inspect every edit or download right away.</div>',
                unsafe_allow_html=True,
            )

            summary_col1, summary_col2, summary_col3 = st.columns(3, gap="large")
            with summary_col1:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Summary Section</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("summary_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("summary_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)
            with summary_col2:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Bullet Points</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("bullet_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("bullet_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)
            with summary_col3:
                st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
                st.markdown('<div class="apple-kicker">Skills Section</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="apple-stat-value">{stats.get("skills_replacements", 0)}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(_section_label(stats.get("skills_replacements", 0), "change", "changes"))
                st.markdown("</div>", unsafe_allow_html=True)

            readiness_rows = [
                ("Exact matches", str(review_stats.get("matched_replacements", 0))),
                ("Issues found", "0" if ready_for_export else str(manual_review_count)),
                ("Export status", "Safe to export" if ready_for_export else "Needs review"),
            ]
            st.markdown(build_readiness_rows(readiness_rows), unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">What Changed</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Three concrete examples from the optimized draft.</div>', unsafe_allow_html=True)
            if change_examples:
                for example in change_examples:
                    st.markdown(f"**{example['label']}**")
                    st.markdown(f"- Before: {example['before']}")
                    st.markdown(f"- After: {example['after']}")
            else:
                st.markdown("Specific before/after previews are not available for this run, but the validated replacement counts above are still accurate.")

        if metrics_summary:
            metric_cols = st.columns(min(4, len(metrics_summary)), gap="large")
            for column, metric in zip(metric_cols, metrics_summary[:4]):
                delta = int(metric["delta"])
                delta_text = f"{delta:+d} {metric['suffix']}"
                with column:
                    st.metric(
                        str(metric["label"]),
                        f"{metric['after']}",
                        delta_text,
                    )

        if baseline_report and optimized_report:
            _render_fit_delta_card(baseline_report, optimized_report)

        if review_warnings:
            for warning in review_warnings:
                st.caption(warning)

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                st.download_button(
                    "Download Optimized Resume (.docx)",
                    data=io.BytesIO(st.session_state.output_docx_bytes),
                    file_name=st.session_state.output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    on_click=lambda: logger.info(
                        "Optimized resume downloaded: filename=%s",
                        st.session_state.output_filename,
                    ),
                )
            else:
                st.button("Download Optimized Resume (.docx)", use_container_width=True, disabled=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with action_col2:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Review Changes", use_container_width=True):
                logger.info("User opened detailed change review")
                st.session_state.show_review_changes = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with action_col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Start Over", use_container_width=True):
                logger.info("User started a new optimization from success state")
                reset_flow()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.is_first_optimization:
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown('<div class="apple-kicker">Level Up Your Results</div>', unsafe_allow_html=True)
                st.markdown('<div class="apple-section-title">Build your Career Profile</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="apple-section-copy">Save your experiences, education, and skills once. Then let the app personalize future optimizations with your full background.</div>',
                    unsafe_allow_html=True,
                )
                profile_col1, profile_col2 = st.columns(2)
                with profile_col1:
                    st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
                    if st.button("Build Profile", use_container_width=True, key="success-build-profile"):
                        st.session_state.is_first_optimization = False
                        st.session_state.screen = "profile_welcome"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with profile_col2:
                    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
                    if st.button("Skip for now", use_container_width=True, key="success-skip-profile"):
                        st.session_state.is_first_optimization = False
                        logger.info("User declined profile building prompt on first optimization")
                    st.markdown("</div>", unsafe_allow_html=True)

        previous_screen = "manual" if st.session_state.execution_mode == "manual" else "api"
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True):
            st.session_state.screen = previous_screen
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if st.button("Back", key="review-back-button"):
        logger.info("User returned from detailed review to success snapshot")
        st.session_state.show_review_changes = False
        st.rerun()

    st.subheader("Optimization Summary")
    st.caption("Review only the sections you care about. Everything is collapsed by default.")

    render_review_section("Summary Section", grouped_results.get("Summary", []), expanded=manual_review_count > 0)
    render_review_section("Bullet Points", grouped_results.get("Bullet", []), expanded=False)
    render_review_section("Skills Section", grouped_results.get("Skills", []), expanded=False)

    if manual_review_count and st.session_state.resume_paragraphs:
        with st.expander("Need help finding the exact resume text?", expanded=False):
            st.caption("If the AI used the wrong wording, use the exact text below from your resume.")
            for index, paragraph in enumerate(st.session_state.resume_paragraphs, start=1):
                st.text_area(
                    f"Resume text {index}",
                    value=paragraph,
                    height=90,
                    disabled=True,
                    key=f"resume-helper-{index}",
                )

    bottom_col1, bottom_col2, bottom_col3 = st.columns(3)
    with bottom_col1:
        if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
            st.download_button(
                "Download Optimized Resume",
                data=io.BytesIO(st.session_state.output_docx_bytes),
                file_name=st.session_state.output_filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                on_click=lambda: logger.info(
                    "Optimized resume downloaded from detail view: filename=%s",
                    st.session_state.output_filename,
                ),
            )
        else:
            st.button("Download Optimized Resume", use_container_width=True, disabled=True)
    with bottom_col2:
        if st.button("Back", use_container_width=True, key="review-back-bottom"):
            st.session_state.show_review_changes = False
            st.rerun()
    with bottom_col3:
        if st.button("Start Over", use_container_width=True, key="review-start-over"):
            reset_flow()
            st.rerun()


def main() -> None:
    """Run the Streamlit app."""
    logger.info("Streamlit app started")
    st.set_page_config(page_title="Resume Optimizer", page_icon="📄", layout="wide")
    init_profile_db()
    init_session_state()
    handle_step_navigation_request()
    apply_apple_theme()

    with st.sidebar:
        st.markdown("### Resume Optimizer")
        st.caption("A calmer way to tailor resumes with AI-guided review before export.")
        render_chip_row(["Apple-inspired redesign", "Prototype build"])
        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)
        st.write("Use the guided flow to upload, target, run, review, and download with confidence.")
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Start Over", use_container_width=True, key="sidebar-start-over"):
            reset_flow()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Application Workspace", use_container_width=True, key="sidebar-application-workspace"):
            st.session_state.screen = "application_workspace"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("📊 Your Optimizations", use_container_width=True, key="sidebar-optimization-history"):
            st.session_state.screen = "optimization_history"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Career Profile", use_container_width=True, key="sidebar-profile"):
            st.session_state.screen = "profile_welcome"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    screen = st.session_state.screen
    if screen == "landing":
        render_landing()
    elif screen == "profile_welcome":
        render_profile_welcome_screen()
    elif screen == "profile_import":
        render_profile_import_screen()
    elif screen == "profile_review":
        render_profile_review_screen()
    elif screen == "profile_dashboard":
        render_profile_dashboard_screen()
    elif screen == "application_match":
        render_application_match_screen()
    elif screen == "application_workspace":
        render_application_workspace_screen()
    elif screen == "optimization_history":
        render_optimization_history_screen()
    elif screen == "input":
        render_input_screen()
    elif screen == "fit_report":
        render_fit_report_screen()
    elif screen == "builder_input":
        render_builder_input_screen()
    elif screen == "builder_stub":
        render_builder_stub_screen()
    elif screen == "builder_review":
        render_builder_review_screen()
    elif screen == "mode":
        render_mode_screen()
    elif screen == "manual":
        render_manual_screen()
    elif screen == "api":
        render_api_screen()
    elif screen == "review":
        render_review_screen()


if __name__ == "__main__":
    main()
