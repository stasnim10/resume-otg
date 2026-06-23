"""
Session state initialisation and reset.

Extracted from streamlit_app.py so that screen modules can reference the
default session keys without importing the full main module.
"""
from __future__ import annotations

import logging

import streamlit as st

from ollama_local_ai import DEFAULT_LOCAL_AI_MODEL, OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

CAREER_STAGES = [
    "Student",
    "Early Career",
    "Mid-Level",
    "Manager",
    "Executive",
    "Career Pivot",
]


def init_session_state() -> None:
    """Initialize expected session keys with safe defaults."""
    defaults = {
        "screen": "landing",
        "resume_name": None,
        "resume_bytes": None,
        "resume_text": None,
        "resume_paragraphs": [],
        "resume_source": "",
        "last_uploaded_resume_signature": "",
        "default_resume_last_saved": "",
        "job_description": "",
        "career_stage": CAREER_STAGES[0],
        "target_role": "",
        "target_industry": "",
        "execution_mode": None,
        "selected_provider": "OpenAI",
        "optimization_path": "fast_start",
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
        "onboarding_name": "",
        "onboarding_email": "",
        "onboarding_phone": "",
        "onboarding_location": "",
        "onboarding_linkedin": "",
        "onboarding_target_roles": "",
        "onboarding_target_industries": "",
        "onboarding_education": "",
        "onboarding_experience": "",
        "onboarding_projects": "",
        "onboarding_skills": "",
        "onboarding_summary": "",
        "onboarding_complete": False,
        "jd_source_url": "",
        "jd_cleaning_result": None,
        "show_review_changes": False,
        "pending_job_description_input": None,
        "jd_role_hint": "",
        "custom_api_base_url": "http://localhost:11434/v1",
        "custom_api_model": "mistral",
        "custom_api_key": "",
        "local_ai_base_url": OLLAMA_BASE_URL,
        "local_ai_model_name": DEFAULT_LOCAL_AI_MODEL,
        "local_ai_ready": False,
        "local_ai_setup_status": {},
        "local_ai_job_signals": {},
        "local_ai_profile_summary": "",
        "local_ai_profile_headline": "",
        "local_ai_last_job_meta": {},
        "local_ai_last_profile_meta": {},
        "local_ai_last_draft_meta": {},
        "local_ai_last_builder_meta": {},
        "local_ai_profile_error": "",
        "local_ai_draft_error": "",
        "local_ai_draft_running": False,
        "profile_import_notes": "",
        "profile_import_source_name": "",
        "profile_extracted_basics": {},
        "profile_extracted_items": [],
        "profile_last_source_id": None,
        "profile_last_source_raw_text": "",
        "profile_items_edit_history": [],
        "profile_items_edit_history_index": -1,
        "profile_edit_mode": False,
        "profile_edit_item_id": None,
        "profile_dashboard_section": "overview",
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
        "tracker_pending_save": None,
        "tracker_auto_saved_to": None,
        "active_tracker_job_id": None,
        "bulk_jobs": [],
        "bulk_execution_mode": None,
        "bulk_selected_provider": "OpenAI",
        "bulk_selected_model": "",
        "bulk_api_key": "",
        "bulk_custom_api_base_url": "http://localhost:11434/v1",
        "bulk_custom_api_model": "mistral",
        "bulk_custom_api_key": "",
        "bulk_last_run_summary": "",
        # Auth
        "_sb_access_token": "",
        "_sb_refresh_token": "",
        "auth_user_id": "",
        "auth_user_email": "",
        "is_authenticated": False,
        "hosted_web_mode": False,
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
