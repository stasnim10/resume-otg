"""
Builder screens: first-resume intake, prompt handoff, and draft review.
"""
from __future__ import annotations

import streamlit as st

from ai_gateway import PROVIDER_CONFIG, optimize_with_provider
from docx_handler import build_resume_from_scratch
from json_parser import (
    build_builder_validation_summary,
    parse_builder_payload,
)
from prompt_engine import build_builder_prompt
from screens.ui_helpers import (
    CAREER_STAGES,
    build_inline_chip_row,
    render_chip_row,
    render_copy_prompt_button,
    render_instruction_panel,
    render_prompt_block,
    render_screen_intro,
    render_shell_end,
    render_shell_start,
)


def render_builder_input_screen() -> None:
    """Student-friendly first-resume intake flow."""
    render_shell_start()
    render_screen_intro(
        "builder_input",
        "Step 2 of 5",
        "Build your first resume.",
        "Tell us about yourself in plain English. We'll shape it into a professional draft.",
    )

    basics_col, extras_col = st.columns(2, gap="large")
    with basics_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">The Basics</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Start with the story you already have.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Add the essentials first: who you are, where you studied, and the experience you want the draft to reflect.</div>',
                unsafe_allow_html=True,
            )
            full_name = st.text_input(
                "Full Name",
                value=st.session_state.builder_full_name,
                placeholder="Example: Jane Doe",
            )
            contact_info = st.text_area(
                "Contact Info",
                value=st.session_state.builder_contact_info,
                height=110,
                placeholder="Email, phone, location, LinkedIn, portfolio, or anything else you want on the resume.",
            )
            education = st.text_area(
                "Education",
                value=st.session_state.builder_education,
                height=140,
                placeholder="School, major, graduation date, GPA, coursework, honors, certifications.",
            )
            experience_dump = st.text_area(
                "Experience Brain Dump",
                value=st.session_state.builder_experience_dump,
                height=200,
                placeholder="Part-time jobs, internships, volunteer work, responsibilities, wins, numbers, anything you remember.",
            )

    with extras_col:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Extras & Target</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Add anything that sharpens the draft.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">This is where you give the builder more context about your activities, skills, target role, and any job you want to aim for.</div>',
                unsafe_allow_html=True,
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
                height=110,
                placeholder="Tools, languages, technical skills, certifications, strengths.",
            )
            builder_job_description = st.text_area(
                "Optional Job Description",
                value=st.session_state.builder_job_description,
                height=170,
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

    col1, col2 = st.columns([0.8, 1.2], gap="large")
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back", use_container_width=True, key="builder-back"):
            st.session_state.screen = "landing"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        can_continue = bool(full_name.strip() and education.strip() and experience_dump.strip() and target_role.strip())
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
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
            st.session_state.builder_execution_mode = None
            st.session_state.screen = "builder_stub"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_stub_screen() -> None:
    """Builder prompt handoff screen."""
    render_shell_start()
    render_screen_intro(
        "builder_stub",
        "Step 3 of 5",
        "Generate your draft.",
        "Choose how you want to generate the first draft, then move on to review.",
    )

    builder_rows = [
        ("Career stage", st.session_state.career_stage or "Student"),
        ("Target role", st.session_state.target_role or "Not set"),
        ("Has job description", "Yes" if st.session_state.builder_job_description.strip() else "No"),
    ]

    mode_col1, mode_col2 = st.columns(2, gap="large")
    with mode_col1:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Manual</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Copy the prompt and use your favorite AI.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Best if you want to compare outputs, stay in control, or use ChatGPT, Claude, or Gemini directly.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Use Manual Mode", use_container_width=True, key="builder-use-manual"):
                st.session_state.builder_execution_mode = "manual"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    with mode_col2:
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">API</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-choice-title">Let the app generate the draft for you.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-choice-copy">Use your own provider key or local endpoint and move straight from prompt to structured draft review.</div>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Use API Mode", use_container_width=True, key="builder-use-api"):
                st.session_state.builder_execution_mode = "api"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    builder_mode = st.session_state.get("builder_execution_mode")

    with st.container(border=True):
        st.markdown('<div class="apple-kicker">Builder Context</div>', unsafe_allow_html=True)
        st.markdown('<div class="apple-section-title">Your draft setup is ready.</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="apple-section-copy">This is the information the builder will use, regardless of whether you run it manually or through API mode.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(build_readiness_rows(builder_rows), unsafe_allow_html=True)

    if builder_mode == "manual":
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Manual Drafting</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Copy the builder prompt.</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="apple-section-copy">Paste this into your AI tool, ask for only the structured JSON output, then bring the result back below.</div>',
                unsafe_allow_html=True,
            )
            render_prompt_block("Generated Builder Prompt", st.session_state.builder_prompt, 360, "builder")

        render_instruction_panel(
            "What To Do Next",
            [
                "Copy the builder prompt above and paste it into ChatGPT, Claude, or Gemini.",
                "Ask the AI to return only the structured JSON output for the first resume.",
                "Paste the AI result below, then click Validate Builder Output.",
            ],
        )

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Builder Output</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Paste the AI response.</div>', unsafe_allow_html=True)
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

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-manual"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Validate Builder Output", use_container_width=True, key="builder-validate-output-manual"):
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
            st.markdown("</div>", unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-manual"):
                st.session_state.screen = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    elif builder_mode == "api":
        if st.session_state.selected_provider not in PROVIDER_CONFIG:
            st.session_state.selected_provider = "OpenAI"

        api_key = ""
        base_url = ""
        with st.container(border=True):
            st.markdown('<div class="apple-kicker">API Setup</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Choose your provider.</div>', unsafe_allow_html=True)

            provider = st.selectbox(
                "Provider",
                list(PROVIDER_CONFIG.keys()),
                index=list(PROVIDER_CONFIG.keys()).index(st.session_state.selected_provider),
                key="builder-provider",
            )
            st.session_state.selected_provider = provider
            provider_config = PROVIDER_CONFIG[provider]
            st.markdown(
                f'<div class="apple-section-copy">{provider_config.get("description", "")}</div>',
                unsafe_allow_html=True,
            )

            if provider == "Local Model / Custom Endpoint":
                base_url = st.text_input(
                    "Base URL",
                    value=st.session_state.custom_api_base_url,
                    placeholder="http://localhost:11434/v1",
                    help="For Ollama, use http://localhost:11434/v1",
                    key="builder-base-url",
                )
                model = st.text_input(
                    "Model name",
                    value=st.session_state.custom_api_model,
                    placeholder="mistral",
                    help="Use the exact local model tag available on your machine.",
                    key="builder-model-local",
                )
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    value=st.session_state.custom_api_key,
                    placeholder=provider_config["placeholder"],
                    help="Most local endpoints do not require a key. Leave blank if not needed.",
                    key="builder-api-key-local",
                )
                st.session_state.custom_api_base_url = base_url
                st.session_state.custom_api_model = model
                st.session_state.custom_api_key = api_key
            else:
                api_key = st.text_input(
                    provider_config["key_label"],
                    type="password",
                    placeholder=provider_config["placeholder"],
                    key="builder-api-key",
                )
                model = st.selectbox("Model", provider_config["models"], index=0, key="builder-model")
                st.markdown(
                    '<div class="apple-section-copy">Your key is used only for this session and is not stored.</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("Prompt Preview", expanded=False):
                st.text_area(
                    "Builder Prompt Preview",
                    value=st.session_state.builder_prompt,
                    height=240,
                    disabled=True,
                    key="builder-prompt-preview-api",
                )

        api_rows = builder_rows + [
            ("Provider", provider),
            ("Model", model if model else "Missing"),
        ]
        if provider == "Local Model / Custom Endpoint":
            api_rows.append(("Base URL", "Ready" if base_url.strip() else "Missing"))
        else:
            api_rows.append(("API key", "Provided" if api_key.strip() else "Missing"))

        with st.container(border=True):
            st.markdown('<div class="apple-kicker">Ready Check</div>', unsafe_allow_html=True)
            st.markdown('<div class="apple-section-title">Everything you need is in place.</div>', unsafe_allow_html=True)
            st.markdown(build_readiness_rows(api_rows), unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-api"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
            if st.button("Run Builder via API", use_container_width=True, key="builder-run-api"):
                try:
                    with st.spinner(f"Sending prompt to {provider}..."):
                        payload = optimize_with_provider(
                            provider=provider,
                            api_key=api_key,
                            prompt=st.session_state.builder_prompt,
                            model=model,
                            base_url=base_url,
                        )
                    st.session_state.builder_payload = payload
                    st.session_state.builder_validation_summary = build_builder_validation_summary(payload)
                    st.session_state.builder_output_docx_bytes = None
                    st.session_state.builder_output_filename = None
                    st.session_state.screen = "builder_review"
                    st.rerun()
                except Exception as error:
                    st.error(str(error))
            st.markdown("</div>", unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-api"):
                st.session_state.screen = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="apple-minor-copy" style="margin-top:0.35rem;">Choose a run mode above to continue.</div>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Edit Builder Inputs", use_container_width=True, key="builder-edit-inputs-preselect"):
                st.session_state.screen = "builder_input"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
            if st.button("Back to Landing", use_container_width=True, key="builder-back-landing-preselect"):
                st.session_state.screen = "landing"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


def render_builder_review_screen() -> None:
    """Review validated builder output before full document generation exists."""
    payload = st.session_state.builder_payload or {}
    summary = st.session_state.builder_validation_summary or {}
    stats = summary.get("stats", {})
    basics = payload.get("basics", {})

    render_shell_start()
    render_screen_intro(
        "builder_review",
        "Step 4 of 5",
        "Review your foundation.",
        "Your draft is structurally valid and ready to be converted into a .docx file.",
    )

    st.markdown('<div class="apple-summary-grid">', unsafe_allow_html=True)
    st.markdown('<div class="apple-summary-label">Builder Summary</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-summary-title">A quick view of the content blocks that are ready for your first draft.</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4, gap="large")
    with col1:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Education</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("education_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Education items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Experience</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("experience_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Experience items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Projects</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("project_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Project items")
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="apple-stat-card">', unsafe_allow_html=True)
        st.markdown('<div class="apple-kicker">Skills</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="apple-stat-value">{stats.get("skills_items", 0)}</div>', unsafe_allow_html=True)
        st.caption("Skill groups")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.markdown('<div class="apple-kicker">Resume Content Snapshot</div>', unsafe_allow_html=True)
    st.markdown('<div class="apple-section-title">Review the structure before you create the .docx file.</div>', unsafe_allow_html=True)
    st.markdown(
        build_readiness_rows(
            [
                ("Full name", basics.get("full_name", "") or "Missing"),
                ("Email", basics.get("email", "") or "Missing"),
                ("Phone", basics.get("phone", "") or "Missing"),
                ("Location", basics.get("location", "") or "Missing"),
                ("LinkedIn", basics.get("linkedin", "") or "Missing"),
            ]
        ),
        unsafe_allow_html=True,
    )

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
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
        if st.button("Back to Builder Prompt", use_container_width=True):
            st.session_state.screen = "builder_stub"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        if st.button("Generate Resume .docx", use_container_width=True):
            try:
                st.session_state.builder_output_docx_bytes = build_resume_from_scratch(payload)
                safe_name = (basics.get("full_name", "First_Resume").strip() or "First_Resume").replace(" ", "_")
                st.session_state.builder_output_filename = f"{safe_name}_Resume.docx"
                st.success("First resume document generated successfully.")
            except Exception as error:
                st.error(str(error))
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.builder_output_docx_bytes and st.session_state.builder_output_filename:
        st.markdown('<div class="apple-primary">', unsafe_allow_html=True)
        st.download_button(
            "Download First Resume (.docx)",
            data=io.BytesIO(st.session_state.builder_output_docx_bytes),
            file_name=st.session_state.builder_output_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="apple-secondary">', unsafe_allow_html=True)
    if st.button("Back to Landing", use_container_width=True, key="builder-review-landing"):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    render_shell_end()


