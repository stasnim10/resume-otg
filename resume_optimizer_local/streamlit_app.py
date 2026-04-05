"""
Streamlit prototype for the Resume Optimizer MVP.
"""
from __future__ import annotations

import io
import json
import re
import tempfile
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
    parse_builder_payload,
    parse_replacement_payload,
)
from prompt_engine import build_builder_prompt, build_optimizer_prompt
from review_engine import analyze_payload_against_document


CAREER_STAGES = [
    "Student",
    "Early Career",
    "Mid-Level",
    "Manager",
    "Executive",
    "Career Pivot",
]

INDUSTRIES = [
    "",
    "Technology",
    "Consulting",
    "Finance",
    "Supply Chain / Operations",
    "Healthcare",
    "Marketing",
    "General Business",
]

ROLE_KEYWORDS = [
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
    "Product Manager",
    "Program Manager",
]


def format_preview_text(text: str, max_len: int = 260) -> str:
    """Trim long paragraph previews so comparison cards stay readable."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len].rstrip()}..."


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


def render_replacement_preview(item: dict, index: int, key_prefix: str, show_status: bool = True) -> None:
    """Render a cleaner before/after preview for one replacement."""
    status = item["status"]
    if show_status:
        if status == "matched":
            st.markdown("**✏️ AI-updated**")
        elif status == "duplicate":
            st.markdown("**⚠️ Needs manual review: multiple paragraphs matched**")
        else:
            st.markdown("**⚠️ Needs manual review: no exact anchor was found**")

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown("**Current Resume Text**")
        st.text_area(
            f"Current Resume Text {index}",
            value=item["match_anchor"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-anchor-{index}",
        )
        st.caption(format_preview_text(item["match_anchor"]))
    with right_col:
        st.markdown("**Proposed Replacement**")
        st.text_area(
            f"Proposed Replacement {index}",
            value=item["replacement_text"],
            height=130,
            disabled=True,
            key=f"{key_prefix}-replacement-{index}",
        )
        st.caption(format_preview_text(item["replacement_text"]))

    if item["suggestions"]:
        suggestion_lines = [
            f"{suggestion['score']}: {format_preview_text(suggestion['text'], 180)}"
            for suggestion in item["suggestions"]
        ]
        st.caption("Closest resume paragraphs:")
        st.code("\n\n".join(suggestion_lines), language="text")


def _section_label(count: int, singular: str, plural: str) -> str:
    """Return a compact count label."""
    return f"{count} {singular if count == 1 else plural}"


def _group_review_results(review_results: list[dict]) -> dict[str, list[dict]]:
    """Group review items into user-facing sections."""
    grouped = {"Summary": [], "Bullet": [], "Skills": []}
    for item in review_results:
        grouped.setdefault(item.get("section", "Other"), []).append(item)
    return grouped


def render_review_section(title: str, items: list[dict], expanded: bool = False) -> None:
    """Render one grouped review section with progressive disclosure."""
    count_label = _section_label(len(items), "change", "changes")
    section_slug = title.lower().replace(" ", "-")
    with st.expander(f"{title} · {count_label}", expanded=expanded):
        if not items:
            st.caption("No changes in this section.")
            return

        if title != "Bullet Points" and len(items) == 1:
            render_replacement_preview(items[0], 1, f"{section_slug}-1", show_status=True)
            return

        for index, item in enumerate(items, start=1):
            status = item["status"]
            if status == "matched":
                status_label = "✏️ AI-updated"
            elif status == "duplicate":
                status_label = "⚠️ Needs manual review"
            else:
                status_label = "⚠️ Needs manual review"

            nested_title = f"{index}. {status_label}"
            if title == "Bullet Points":
                nested_title = f"{index}. {status_label} · {format_preview_text(item['replacement_text'], 72)}"

            with st.expander(nested_title, expanded=(len(items) == 1 and expanded)):
                render_replacement_preview(item, index, f"{section_slug}-{index}", show_status=False)


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
        "builder_payload": None,
        "builder_validation_summary": None,
        "builder_output_docx_bytes": None,
        "builder_output_filename": None,
        "jd_source_url": "",
        "jd_cleaning_result": None,
        "show_review_changes": False,
        "pending_job_description_input": None,
        "jd_role_hint": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_flow() -> None:
    """Reset the prototype flow to the landing page."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()


def save_uploaded_resume(uploaded_file) -> None:
    """Store uploaded resume data and extracted plain text in session state."""
    resume_bytes = uploaded_file.getvalue()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
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
    st.title("Resume Optimizer")
    st.caption("Tailor your resume for a job in minutes, not hours.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Optimize Existing Resume")
        st.write("Upload a `.docx`, target a specific role, and export an optimized `.docx`.")
        if st.button("Start Optimizing", use_container_width=True):
            st.session_state.screen = "input"
            st.rerun()

    with col2:
        st.subheader("Build First Resume")
        st.write("Start from a plain-English brain dump and shape the content for a first professional resume.")
        if st.button("Start Building", use_container_width=True):
            st.session_state.career_stage = "Student"
            st.session_state.screen = "builder_input"
            st.rerun()


def render_input_screen() -> None:
    """Resume and job input screen."""
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

    st.title("Optimizer Input")
    st.write("Upload your draft resume and describe the role you want to target.")

    uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"])
    if uploaded_file is not None:
        save_uploaded_resume(uploaded_file)
        st.success(f"Loaded `{uploaded_file.name}`")

    if st.session_state.pending_job_description_input is not None:
        st.session_state.job_description_input = st.session_state.pending_job_description_input
        st.session_state.pending_job_description_input = None

    if "job_description_input" not in st.session_state:
        st.session_state.job_description_input = st.session_state.job_description

    job_description = st.text_area(
        "Job Description",
        height=220,
        placeholder="Paste the full job description here, or paste a job-post URL.",
        key="job_description_input",
    )
    job_description = st.session_state.get("job_description_input", job_description)
    st.caption("Click below to process a pasted job link or clean pasted job description text.")
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

    if st.session_state.jd_source_url and not looks_like_url(st.session_state.job_description):
        st.caption(f"Loaded from URL: {st.session_state.jd_source_url}")
    if st.session_state.jd_cleaning_result:
        cleaning_result = st.session_state.jd_cleaning_result
        st.success(str(cleaning_result["confidence_message"]))

    detected_role = (
        st.session_state.jd_role_hint if st.session_state.jd_source_url else detect_role_title(job_description)
    )
    detected_industry = detect_industry(job_description) if job_description.strip() else ""

    career_stage = st.selectbox(
        "Career Stage",
        CAREER_STAGES,
        index=CAREER_STAGES.index(st.session_state.career_stage),
    )
    if job_description.strip():
        detected_lines = [
            f"Detected role: {detected_role or 'Could not confidently detect'}",
            f"Detected industry: {detected_industry or 'Could not confidently detect'}",
        ]
        st.caption("Auto-detected from the job description")
        st.info("\n".join(detected_lines))

    with st.expander("Advanced options", expanded=False):
        target_role = st.text_input(
            "Target Role Title Override",
            value=st.session_state.target_role,
            placeholder=detected_role or "Example: Product Manager Intern",
            help="Leave blank to use the detected role title from the JD.",
        )
        industry_options = INDUSTRIES if st.session_state.target_industry in INDUSTRIES else [""] + INDUSTRIES[1:]
        target_industry = st.selectbox(
            "Industry Override",
            industry_options,
            index=industry_options.index(st.session_state.target_industry),
            help="Leave blank to use the detected industry from the JD.",
        )

    st.session_state.job_description = job_description
    st.session_state.career_stage = career_stage
    st.session_state.target_role = target_role
    st.session_state.target_industry = target_industry

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
    with col2:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
        )
        if st.button("Continue", use_container_width=True, disabled=not can_continue):
            if looks_like_url(job_description):
                if fetch_and_store_job_description(job_description):
                    st.rerun()
            else:
                st.session_state.jd_cleaning_result = None
                st.session_state.screen = "mode"
                st.rerun()


def render_builder_input_screen() -> None:
    """Student-friendly first-resume intake stub."""
    st.title("Build First Resume")
    st.write("Tell us about yourself in plain English. This stub generates a builder prompt, but full resume generation is the next phase.")

    full_name = st.text_input(
        "Full Name",
        value=st.session_state.builder_full_name,
        placeholder="Example: Jane Doe",
    )
    contact_info = st.text_area(
        "Contact Info",
        value=st.session_state.builder_contact_info,
        height=100,
        placeholder="Email, phone, location, LinkedIn, portfolio, or anything else you want on the resume.",
    )
    education = st.text_area(
        "Education",
        value=st.session_state.builder_education,
        height=120,
        placeholder="School, major, graduation date, GPA, coursework, honors, certifications.",
    )
    experience_dump = st.text_area(
        "Experience Brain Dump",
        value=st.session_state.builder_experience_dump,
        height=160,
        placeholder="Part-time jobs, internships, volunteer work, responsibilities, wins, numbers, anything you remember.",
    )
    activities = st.text_area(
        "Activities / Leadership / Projects",
        value=st.session_state.builder_activities,
        height=140,
        placeholder="Clubs, leadership roles, case competitions, capstone projects, side projects, community work.",
    )
    skills = st.text_area(
        "Skills",
        value=st.session_state.builder_skills,
        height=100,
        placeholder="Tools, languages, technical skills, certifications, strengths.",
    )
    builder_job_description = st.text_area(
        "Optional Job Description",
        value=st.session_state.builder_job_description,
        height=160,
        placeholder="Paste a target internship or job description if you have one.",
    )
    career_stage = st.selectbox(
        "Career Stage",
        CAREER_STAGES,
        index=CAREER_STAGES.index(st.session_state.career_stage) if st.session_state.career_stage in CAREER_STAGES else 0,
    )
    target_role = st.text_input(
        "Target Role Title",
        value=st.session_state.target_role,
        placeholder="Example: Business Analyst Intern",
    )

    st.session_state.builder_full_name = full_name
    st.session_state.builder_contact_info = contact_info
    st.session_state.builder_education = education
    st.session_state.builder_experience_dump = experience_dump
    st.session_state.builder_activities = activities
    st.session_state.builder_skills = skills
    st.session_state.builder_job_description = builder_job_description
    st.session_state.career_stage = career_stage
    st.session_state.target_role = target_role

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True, key="builder-back"):
            st.session_state.screen = "landing"
            st.rerun()
    with col2:
        can_continue = bool(full_name.strip() and education.strip() and experience_dump.strip() and target_role.strip())
        if st.button("Generate Builder Prompt", use_container_width=True, disabled=not can_continue):
            st.session_state.builder_prompt = build_builder_prompt(
                full_name=full_name,
                contact_info=contact_info,
                education=education,
                experience_dump=experience_dump,
                activities=activities,
                skills=skills,
                job_description=builder_job_description,
                career_stage=career_stage,
                target_role=target_role,
            )
            st.session_state.screen = "builder_stub"
            st.rerun()


def render_builder_stub_screen() -> None:
    """Future-facing builder manual BYOM screen."""
    st.title("First Resume Builder")
    st.warning("This builder path validates structured output, but full `.docx` resume generation is still the next phase.")

    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Career Stage", st.session_state.career_stage or "Student")
    summary_col2.metric("Target Role", st.session_state.target_role or "Not set")
    summary_col3.metric("Has JD", "Yes" if st.session_state.builder_job_description.strip() else "No")

    render_prompt_block("Generated Builder Prompt", st.session_state.builder_prompt, 360, "builder")

    render_instruction_panel(
        "What To Do Next",
        [
            "Copy the builder prompt above and paste it into ChatGPT, Claude, or Gemini.",
            "Ask the AI to return only the structured JSON output for the first resume.",
            "Paste the AI result below, then click Validate Builder Output.",
        ],
    )

    pasted_output = st.text_area(
        "Paste Builder Output",
        height=280,
        placeholder="Paste the AI response here.",
    )

    with st.expander("Builder Intake Snapshot", expanded=False):
        st.text_area("Full Name", value=st.session_state.builder_full_name, height=68, disabled=True)
        st.text_area("Contact Info", value=st.session_state.builder_contact_info, height=100, disabled=True)
        st.text_area("Education", value=st.session_state.builder_education, height=120, disabled=True)
        st.text_area("Experience Brain Dump", value=st.session_state.builder_experience_dump, height=160, disabled=True)
        st.text_area("Activities / Leadership / Projects", value=st.session_state.builder_activities, height=140, disabled=True)
        st.text_area("Skills", value=st.session_state.builder_skills, height=100, disabled=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Edit Builder Inputs", use_container_width=True):
            st.session_state.screen = "builder_input"
            st.rerun()
    with col2:
        if st.button("Validate Builder Output", use_container_width=True):
            try:
                payload = parse_builder_payload(pasted_output)
                st.session_state.builder_payload = payload
                st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                st.session_state.builder_output_docx_bytes = None
                st.session_state.builder_output_filename = None
                st.session_state.screen = "builder_review"
                st.rerun()
            except Exception as error:
                st.error(str(error))

    if st.button("Back to Landing", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()


def render_builder_review_screen() -> None:
    """Review validated builder output before full document generation exists."""
    payload = st.session_state.builder_payload or {}
    summary = st.session_state.builder_validation_summary or {}
    stats = summary.get("stats", {})

    st.title("Builder Review")
    st.success("Builder output validated successfully.")
    st.info("This builder output is structurally valid and can now be turned into a first-draft `.docx` resume.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Education", stats.get("education_items", 0))
    col2.metric("Experience", stats.get("experience_items", 0))
    col3.metric("Projects", stats.get("project_items", 0))
    col4.metric("Skills", stats.get("skills_items", 0))

    basics = payload.get("basics", {})
    st.markdown("**Basics**")
    st.info(
        f"{basics.get('full_name', '')}\n\n"
        f"Email: {basics.get('email', '')}\n\n"
        f"Phone: {basics.get('phone', '')}\n\n"
        f"Location: {basics.get('location', '')}\n\n"
        f"LinkedIn: {basics.get('linkedin', '')}"
    )

    st.markdown("**Summary**")
    st.text_area("Professional Summary", value=payload.get("summary", ""), height=120, disabled=True)

    with st.expander("Education Preview", expanded=True):
        for index, item in enumerate(payload.get("education", []), start=1):
            st.markdown(f"**Education {index}**")
            st.write(f"{item.get('school', '')} | {item.get('degree', '')} | {item.get('graduation_date', '')}")
            if item.get("details"):
                st.code("\n".join(item["details"]), language="text")

    with st.expander("Experience Preview", expanded=True):
        for index, item in enumerate(payload.get("experience", []), start=1):
            st.markdown(f"**Experience {index}**")
            st.write(
                f"{item.get('title', '')} | {item.get('organization', '')} | "
                f"{item.get('location', '')} | {item.get('dates', '')}"
            )
            if item.get("bullets"):
                st.code("\n".join(item["bullets"]), language="text")

    with st.expander("Projects Preview", expanded=False):
        for index, item in enumerate(payload.get("projects", []), start=1):
            st.markdown(f"**Project {index}: {item.get('name', '')}**")
            if item.get("details"):
                st.code("\n".join(item["details"]), language="text")

    with st.expander("Skills Preview", expanded=False):
        st.code("\n".join(payload.get("skills", [])), language="text")

    with st.expander("Validated Builder Payload", expanded=False):
        st.json(payload)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Builder Prompt", use_container_width=True):
            st.session_state.screen = "builder_stub"
            st.rerun()
    with col2:
        if st.button("Generate Resume .docx", use_container_width=True):
            try:
                st.session_state.builder_output_docx_bytes = build_resume_from_scratch(payload)
                safe_name = (basics.get("full_name", "First_Resume").strip() or "First_Resume").replace(" ", "_")
                st.session_state.builder_output_filename = f"{safe_name}_Resume.docx"
                st.success("First resume document generated successfully.")
            except Exception as error:
                st.error(str(error))

    if st.session_state.builder_output_docx_bytes and st.session_state.builder_output_filename:
        st.markdown("**Builder Export Ready**")
        st.download_button(
            "Download First Resume (.docx)",
            data=io.BytesIO(st.session_state.builder_output_docx_bytes),
            file_name=st.session_state.builder_output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    if st.button("Back to Landing", use_container_width=True, key="builder-review-landing"):
            st.session_state.screen = "landing"
            st.rerun()


def render_mode_screen() -> None:
    """Execution mode selection screen."""
    st.title("Choose Execution Mode")
    st.write("Use a manual low-cost flow or run the same prompt directly with your own OpenAI key.")

    manual_col, api_col = st.columns(2)
    with manual_col:
        st.subheader("Use ChatGPT / Claude / Gemini Manually")
        st.write("Lowest cost, a little more copy-paste.")
        if st.button("Use Manual Mode", use_container_width=True):
            st.session_state.execution_mode = "manual"
            st.session_state.generated_prompt = build_optimizer_prompt(
                st.session_state.resume_text,
                st.session_state.job_description,
                st.session_state.career_stage,
                get_effective_target_role(st.session_state.job_description),
                get_effective_industry(st.session_state.job_description),
            )
            st.session_state.screen = "manual"
            st.rerun()

    with api_col:
        st.subheader("Use My API Key")
        st.write("Faster, requires your own key.")
        if st.button("Use API Mode", use_container_width=True):
            st.session_state.execution_mode = "api"
            st.session_state.generated_prompt = build_optimizer_prompt(
                st.session_state.resume_text,
                st.session_state.job_description,
                st.session_state.career_stage,
                get_effective_target_role(st.session_state.job_description),
                get_effective_industry(st.session_state.job_description),
            )
            st.session_state.screen = "api"
            st.rerun()

    if st.button("Back to Input"):
        st.session_state.screen = "input"
        st.rerun()


def handle_validated_payload(payload: dict) -> None:
    """Store validation state and move to review."""
    st.session_state.validated_payload = payload
    st.session_state.validation_summary = build_validation_summary(payload)
    st.session_state.review_details = analyze_payload(payload)
    st.session_state.output_docx_bytes = None
    st.session_state.output_filename = None
    st.session_state.show_review_changes = False
    st.session_state.screen = "review"


def render_copy_prompt_button(prompt: str, key: str) -> None:
    """Render a one-click clipboard copy button with feedback."""
    prompt_json = json.dumps(prompt)
    button_id = f"copy-btn-{key}"
    feedback_id = f"copy-feedback-{key}"
    components.html(
        f"""
        <div style="display:flex;flex-direction:column;align-items:flex-end;margin:0.1rem 0 0.45rem 0;">
          <button
            id="{button_id}"
            type="button"
            style="background:#2563eb;color:white;border:none;padding:0.55rem 0.9rem;border-radius:0.55rem;cursor:pointer;font-weight:700;font-size:0.92rem;"
          >
            📋 Copy Prompt
          </button>
          <span id="{feedback_id}" style="min-height:1.15rem;margin-top:0.35rem;font-size:0.88rem;font-weight:700;color:#15803d;"></span>
        </div>
        <script>
          const button = document.getElementById("{button_id}");
          const feedback = document.getElementById("{feedback_id}");
          const promptText = {prompt_json};
          button.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(promptText);
              feedback.textContent = "✓ Copied!";
              feedback.style.color = "#15803d";
              setTimeout(() => {{
                feedback.textContent = "";
              }}, 2000);
            }} catch (err) {{
              feedback.textContent = "Failed to copy. Try Cmd+C instead.";
              feedback.style.color = "#b45309";
              setTimeout(() => {{
                feedback.textContent = "";
              }}, 2000);
            }}
          }});
        </script>
        """,
        height=74,
    )


def render_prompt_block(label: str, prompt: str, height: int, copy_key: str) -> None:
    """Render the prompt with a heading and right-aligned copy button."""
    st.markdown(f"**{label}**")
    render_copy_prompt_button(prompt, copy_key)
    st.text_area(
        label,
        value=prompt,
        height=height,
        key=f"{copy_key}-prompt-display",
        label_visibility="collapsed",
        help="Select the prompt text manually if the browser blocks clipboard access.",
    )


def render_instruction_panel(title: str, steps: list[str]) -> None:
    """Render a prominent instruction block."""
    step_html = "".join(
        [
            f"""
            <div style="display:flex;gap:0.75rem;align-items:flex-start;margin-bottom:0.8rem;">
              <div style="background:#0f766e;color:white;min-width:1.9rem;height:1.9rem;border-radius:999px;display:flex;align-items:center;justify-content:center;font-weight:700;">
                {index}
              </div>
              <div style="color:#e5e7eb;line-height:1.45;">{step}</div>
            </div>
            """
            for index, step in enumerate(steps, start=1)
        ]
    )
    components.html(
        f"""
        <div style="margin: 0.8rem 0 1rem 0; padding: 1rem 1rem 0.4rem 1rem; border: 1px solid #1f2937; border-radius: 0.85rem; background: linear-gradient(180deg, rgba(15,118,110,0.18), rgba(17,24,39,0.92));">
          <div style="color:white;font-weight:700;font-size:1rem;margin-bottom:0.9rem;">{title}</div>
          {step_html}
        </div>
        """,
        height=max(170, 88 + (len(steps) * 58)),
    )


def render_manual_screen() -> None:
    """Manual BYOM screen."""
    st.title("Manual Optimization")
    st.info("Copy the prompt into your AI tool, then paste the structured result back here.")
    st.warning("Manual copy-paste works best on desktop. Large JSON payloads can be frustrating on mobile.")

    render_prompt_block("Generated Prompt", st.session_state.generated_prompt or "", 320, "manual")
    render_instruction_panel(
        "What To Do Next",
        [
            "Copy the prompt above and paste it into ChatGPT, Claude, or Gemini.",
            "Ask the AI to return only the structured JSON output with no extra explanation.",
            "Paste the AI result into the box below, then click Validate Output.",
        ],
    )

    pasted_output = st.text_area(
        "Paste Structured AI Output",
        height=260,
        placeholder="Paste the AI response here.",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
    with col2:
        if st.button("Validate Output", use_container_width=True):
            try:
                payload = parse_replacement_payload(pasted_output)
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))


def render_api_screen() -> None:
    """Multi-provider API mode screen."""
    st.title("API Mode")
    st.caption("The app uses the same prompt and validation flow, but runs it for the user.")

    provider = st.selectbox(
        "Provider",
        list(PROVIDER_CONFIG.keys()),
        index=list(PROVIDER_CONFIG.keys()).index(st.session_state.selected_provider),
    )
    st.session_state.selected_provider = provider
    provider_config = PROVIDER_CONFIG[provider]
    api_key = st.text_input(
        provider_config["key_label"],
        type="password",
        placeholder=provider_config["placeholder"],
    )
    model = st.selectbox("Model", provider_config["models"], index=0)
    st.info("After the provider responds, the same JSON validator and exact-match review still run before export.")

    st.text_area(
        "Prompt Preview",
        value=st.session_state.generated_prompt or "",
        height=220,
        disabled=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "mode"
            st.rerun()
    with col2:
        if st.button("Run Optimization", use_container_width=True):
            try:
                with st.spinner(f"Sending prompt to {provider}..."):
                    payload = optimize_with_provider(
                        provider=provider,
                        api_key=api_key,
                        prompt=st.session_state.generated_prompt,
                        model=model,
                    )
                handle_validated_payload(payload)
                st.rerun()
            except Exception as error:
                st.error(str(error))


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

    if ready_for_export and not st.session_state.output_docx_bytes:
        try:
            ensure_export_file_ready()
        except Exception as error:
            st.error(str(error))
            ready_for_export = False

    st.title("Validation and Export")
    if not st.session_state.show_review_changes:
        if ready_for_export:
            st.success("All replacements validated successfully.")
            st.markdown(
                "\n".join(
                    [
                        "Your resume has been optimized and is ready to download.",
                        f"- {review_stats.get('matched_replacements', 0)} replacements matched exactly",
                        "- 0 issues found",
                        "- Safe to export",
                    ]
                )
            )
        else:
            st.warning("This result needs review before export.")
            issue_count = manual_review_count
            st.markdown(
                "\n".join(
                    [
                        "We validated the structured output, but some replacements still need attention before download.",
                        f"- {review_stats.get('matched_replacements', 0)} replacements matched exactly",
                        f"- {issue_count} issue(s) need review",
                        "- Export stays disabled until every anchor matches safely",
                    ]
                )
            )

        summary_col1, summary_col2, summary_col3 = st.columns(3)
        summary_col1.metric("Summary Section", _section_label(stats.get("summary_replacements", 0), "change", "changes"))
        summary_col2.metric("Bullet Points", _section_label(stats.get("bullet_replacements", 0), "change", "changes"))
        summary_col3.metric("Skills Section", _section_label(stats.get("skills_replacements", 0), "change", "changes"))

        if review_warnings:
            for warning in review_warnings:
                st.caption(warning)

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if ready_for_export and st.session_state.output_docx_bytes and st.session_state.output_filename:
                st.download_button(
                    "Download Optimized Resume (.docx)",
                    data=io.BytesIO(st.session_state.output_docx_bytes),
                    file_name=st.session_state.output_filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            else:
                st.button("Download Optimized Resume (.docx)", use_container_width=True, disabled=True)
        with action_col2:
            if st.button("Review Changes", use_container_width=True):
                st.session_state.show_review_changes = True
                st.rerun()
        with action_col3:
            if st.button("Start Over", use_container_width=True):
                reset_flow()
                st.rerun()

        previous_screen = "manual" if st.session_state.execution_mode == "manual" else "api"
        if st.button("Back", use_container_width=True):
            st.session_state.screen = previous_screen
            st.rerun()
        return

    if st.button("Back", key="review-back-button"):
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
    st.set_page_config(page_title="Resume Optimizer", page_icon="📄", layout="wide")
    init_session_state()

    with st.sidebar:
        st.header("Prototype")
        st.write("Locked MVP: optimize an existing `.docx` resume with manual BYOM or OpenAI API mode.")
        if st.button("Start Over", use_container_width=True):
            reset_flow()
            st.rerun()

    screen = st.session_state.screen
    if screen == "landing":
        render_landing()
    elif screen == "input":
        render_input_screen()
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
