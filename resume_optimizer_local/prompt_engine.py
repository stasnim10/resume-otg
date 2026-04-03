"""
Prompt generation for the Streamlit prototype.
"""


def build_optimizer_prompt(
    resume_text: str,
    job_description: str,
    career_stage: str,
    target_role: str,
    target_industry: str,
) -> str:
    """Generate the manual/API prompt for the optimizer flow."""
    industry_text = target_industry if target_industry else "the target industry"

    return f"""ROLE
Act as an expert recruiter, resume strategist, and professional editor focused on {industry_text}.

PERSONA CONTEXT
The candidate is at the {career_stage} stage and is targeting a {target_role} role.

OBJECTIVE
Optimize the uploaded resume for the target role using only information that is clearly supported by the resume. Improve relevance, clarity, and ATS alignment while preserving honesty.

RULES
1. Do not invent employers, job titles, dates, certifications, scope, or metrics.
2. Rewrite only what is already supported by the resume and job description.
3. Preserve the intent of the original experience while making it more targeted.
4. Use exact paragraph text from the resume as each match_anchor.
5. Return only valid JSON. No markdown fences. No explanation before or after the JSON.
6. Every match_anchor must exactly match one full paragraph from the resume text below.

OUTPUT JSON SCHEMA
{{
  "summary_replacement": {{
    "match_anchor": "Full exact summary paragraph from the resume",
    "replacement_text": "New full summary paragraph"
  }},
  "bullet_replacements": [
    {{
      "match_anchor": "Full exact bullet paragraph from the resume",
      "replacement_text": "New bullet paragraph"
    }}
  ],
  "skills_replacements": [
    {{
      "match_anchor": "Full exact skills paragraph from the resume",
      "replacement_text": "New skills paragraph"
    }}
  ]
}}

TOP-LEVEL RULES
- All top-level keys are optional.
- Include only sections that truly need updating.
- Each replacement object must contain both match_anchor and replacement_text.
- Do not include comments, analysis, or any extra keys.

RESUME TEXT
{resume_text}

JOB DESCRIPTION
{job_description}
"""
