"""
Streamlit prototype for the Resume Optimizer MVP.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ai_gateway import PROVIDER_CONFIG, optimize_with_provider
from docx_handler import apply_replacements, build_resume_from_scratch, extract_text
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


def format_preview_text(text: str, max_len: int = 260) -> str:
    """Trim long paragraph previews so comparison cards stay readable."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[:max_len].rstrip()}..."


def render_status_card(review_stats: dict, stats: dict) -> None:
    """Render the high-level validation summary."""
    lines = [
        "- Resume loaded",
        "- Job description loaded",
        "- Structured output valid",
        f"- Requested replacements: {stats.get('requested_replacements', 0)}",
        f"- Exact matches: {review_stats.get('matched_replacements', 0)}",
        f"- Needs manual review: {review_stats.get('unmatched_replacements', 0) + review_stats.get('duplicate_replacements', 0)}",
    ]
    st.markdown("**Validation Summary**")
    st.info("\n".join(lines))


def render_replacement_preview(item: dict, index: int) -> None:
    """Render a cleaner before/after preview for one replacement."""
    status = item["status"]
    if status == "matched":
        st.success(f"{index}. {item['section']} updated automatically")
    elif status == "duplicate":
        st.error(f"{index}. {item['section']} needs manual review because multiple paragraphs matched")
    else:
        st.error(f"{index}. {item['section']} needs manual review because no exact anchor was found")

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown("**Current Resume Text**")
        st.text_area(
            f"Current Resume Text {index}",
            value=item["match_anchor"],
            height=130,
            disabled=True,
            key=f"review-anchor-{index}",
        )
        st.caption(format_preview_text(item["match_anchor"]))
    with right_col:
        st.markdown("**Proposed Replacement**")
        st.text_area(
            f"Proposed Replacement {index}",
            value=item["replacement_text"],
            height=130,
            disabled=True,
            key=f"review-replacement-{index}",
        )
        st.caption(format_preview_text(item["replacement_text"]))

    if item["suggestions"]:
        suggestion_lines = [
            f"{suggestion['score']}: {format_preview_text(suggestion['text'], 180)}"
            for suggestion in item["suggestions"]
        ]
        st.caption("Closest resume paragraphs:")
        st.code("\n\n".join(suggestion_lines), language="text")


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
        "cover_letter_later": False,
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
    st.title("Optimizer Input")
    st.write("Upload your draft resume and describe the role you want to target.")

    uploaded_file = st.file_uploader("Upload Resume (.docx)", type=["docx"])
    if uploaded_file is not None:
        save_uploaded_resume(uploaded_file)
        st.success(f"Loaded `{uploaded_file.name}`")

    job_description = st.text_area(
        "Job Description",
        value=st.session_state.job_description,
        height=220,
        placeholder="Paste the full job description here.",
    )
    career_stage = st.selectbox(
        "Career Stage",
        CAREER_STAGES,
        index=CAREER_STAGES.index(st.session_state.career_stage),
    )
    target_role = st.text_input(
        "Target Role Title",
        value=st.session_state.target_role,
        placeholder="Example: Product Manager Intern",
    )
    target_industry = st.selectbox(
        "Industry (Optional)",
        INDUSTRIES,
        index=INDUSTRIES.index(st.session_state.target_industry),
    )
    cover_letter_later = st.checkbox(
        "Generate cover letter later",
        value=st.session_state.cover_letter_later,
    )

    st.session_state.job_description = job_description
    st.session_state.career_stage = career_stage
    st.session_state.target_role = target_role
    st.session_state.target_industry = target_industry
    st.session_state.cover_letter_later = cover_letter_later

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
    with col2:
        can_continue = bool(
            st.session_state.resume_text
            and job_description.strip()
            and target_role.strip()
        )
        if st.button("Continue", use_container_width=True, disabled=not can_continue):
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

    st.text_area(
        "Generated Builder Prompt",
        value=st.session_state.builder_prompt,
        height=360,
        disabled=True,
    )
    render_copy_prompt_button(st.session_state.builder_prompt)

    st.code(
        "1. Paste the prompt into ChatGPT, Claude, or Gemini\n2. Ask it to return only the structured output\n3. Paste the result below and validate it",
        language="text",
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
                st.session_state.target_role,
                st.session_state.target_industry,
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
                st.session_state.target_role,
                st.session_state.target_industry,
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
    st.session_state.screen = "review"


def render_copy_prompt_button(prompt: str) -> None:
    """Render a lightweight copy-to-clipboard button."""
    escaped_prompt = (
        prompt.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    components.html(
        f"""
        <div style="margin: 0.5rem 0 1rem 0;">
          <button
            onclick="navigator.clipboard.writeText(`{escaped_prompt}`); this.innerText='Prompt Copied';"
            style="background:#0f766e;color:white;border:none;padding:0.6rem 1rem;border-radius:0.5rem;cursor:pointer;font-weight:600;"
          >
            Copy Prompt
          </button>
        </div>
        """,
        height=55,
    )


def render_manual_screen() -> None:
    """Manual BYOM screen."""
    st.title("Manual Optimization")
    st.info("Copy the prompt into your AI tool, then paste the structured result back here.")
    st.warning("Manual copy-paste works best on desktop. Large JSON payloads can be frustrating on mobile.")

    if st.session_state.resume_paragraphs:
        with st.expander("Resume Paragraph Helper", expanded=False):
            st.caption("Use the full exact paragraph text below as each match_anchor.")
            for index, paragraph in enumerate(st.session_state.resume_paragraphs, start=1):
                st.text_area(
                    f"Paragraph {index}",
                    value=paragraph,
                    height=90,
                    disabled=True,
                    key=f"resume-paragraph-{index}",
                )

    st.text_area(
        "Generated Prompt",
        value=st.session_state.generated_prompt or "",
        height=320,
        disabled=True,
    )
    render_copy_prompt_button(st.session_state.generated_prompt or "")
    st.code(
        "1. Paste the prompt into ChatGPT, Claude, or Gemini\n2. Ask it to return only the structured output\n3. Paste the result below and validate it",
        language="text",
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

    st.title("Validation and Export")
    st.success("Structured output validated successfully.")

    render_status_card(review_stats, stats)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Requested", stats.get("requested_replacements", 0))
    metric_col2.metric("Exact Matches", review_stats.get("matched_replacements", 0))
    metric_col3.metric("Unmatched", review_stats.get("unmatched_replacements", 0))
    metric_col4.metric("Duplicates", review_stats.get("duplicate_replacements", 0))

    detail_col1, detail_col2, detail_col3 = st.columns(3)
    detail_col1.metric("Summary Edits", stats.get("summary_replacements", 0))
    detail_col2.metric("Bullet Edits", stats.get("bullet_replacements", 0))
    detail_col3.metric("Skills Edits", stats.get("skills_replacements", 0))

    if review_warnings:
        for warning in review_warnings:
            st.warning(warning)
    elif ready_for_export:
        st.info("All requested replacements matched exactly. This payload is ready for export.")

    preview_col1, preview_col2 = st.columns(2)
    preview_col1.metric("Updated Automatically", review_stats.get("matched_replacements", 0))
    preview_col2.metric("Needs Manual Review", manual_review_count)

    with st.expander("Replacement Preview", expanded=True):
        for index, item in enumerate(review_results, start=1):
            render_replacement_preview(item, index)
            if index != len(review_results):
                st.divider()

    with st.expander("Validated Payload", expanded=True):
        st.json(st.session_state.validated_payload)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back", use_container_width=True):
            previous_screen = "manual" if st.session_state.execution_mode == "manual" else "api"
            st.session_state.screen = previous_screen
            st.rerun()
    with col2:
        if st.button("Generate Optimized .docx", use_container_width=True, disabled=not ready_for_export):
            try:
                with st.spinner("Applying exact paragraph replacements..."):
                    output_bytes, _message = build_output_docx(st.session_state.validated_payload)
                original_name = Path(st.session_state.resume_name)
                st.session_state.output_docx_bytes = output_bytes
                st.session_state.output_filename = f"{original_name.stem}_Optimized{original_name.suffix}"
                st.success("Optimized resume generated successfully.")
            except Exception as error:
                st.error(str(error))

    if not ready_for_export:
        st.info("Export is disabled until every replacement has exactly one matching paragraph in the uploaded resume.")

    if st.session_state.output_docx_bytes and st.session_state.output_filename:
        st.markdown("**Export Ready**")
        st.success(
            f"Your optimized file is ready. {review_stats.get('matched_replacements', 0)} replacement(s) were prepared for export."
        )
        st.download_button(
            "Download Optimized Resume (.docx)",
            data=io.BytesIO(st.session_state.output_docx_bytes),
            file_name=st.session_state.output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

        action_col1, action_col2 = st.columns(2)
        with action_col1:
            st.button("Generate Cover Letter", use_container_width=True, disabled=True)
        with action_col2:
            st.button("Compare with Original", use_container_width=True, disabled=True)

        with st.expander("Original Resume Snapshot", expanded=False):
            for index, paragraph in enumerate(st.session_state.resume_paragraphs, start=1):
                st.text_area(
                    f"Original Paragraph {index}",
                    value=paragraph,
                    height=80,
                    disabled=True,
                    key=f"original-paragraph-{index}",
                )

        if st.button("Optimize Another Role", use_container_width=True):
            reset_flow()
            st.session_state.screen = "input"
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
