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


def build_builder_prompt(
    full_name: str,
    contact_info: str,
    education: str,
    experience_dump: str,
    activities: str,
    skills: str,
    job_description: str,
    career_stage: str,
    target_role: str,
) -> str:
    """Generate a future-facing prompt for the first-resume builder stub."""
    jd_block = job_description if job_description.strip() else "No specific job description was provided."

    return f"""ROLE
Act as an empathetic university career advisor and resume writer.

PERSONA CONTEXT
The candidate is at the {career_stage} stage and is targeting a {target_role} role.

OBJECTIVE
Turn the candidate's plain-English background into a clean first professional resume. Use only the information provided below. Do not invent achievements, certifications, dates, or tools.

INSTRUCTIONS
1. Translate casual experience into professional, truthful bullet points.
2. Highlight transferable skills, leadership, teamwork, and reliability when relevant.
3. Keep the tone appropriate for a first or early-career resume.
4. If a job description is provided, align the language carefully without fabricating experience.
5. Return only valid JSON.

OUTPUT JSON SCHEMA
{{
  "basics": {{
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "555-555-5555",
    "location": "New York, NY",
    "linkedin": "linkedin.com/in/janedoe"
  }},
  "summary": "1 short professional summary paragraph",
  "education": [
    {{
      "school": "University Name",
      "degree": "B.S. in Something",
      "graduation_date": "May 2027",
      "details": [
        "Relevant Coursework: ...",
        "GPA: 3.8/4.0"
      ]
    }}
  ],
  "experience": [
    {{
      "title": "Barista",
      "organization": "Coffee Shop",
      "location": "Boston, MA",
      "dates": "Jun 2024 - Aug 2024",
      "bullets": [
        "Professional bullet 1",
        "Professional bullet 2"
      ]
    }}
  ],
  "projects": [
    {{
      "name": "Project Name",
      "details": [
        "Project bullet 1",
        "Project bullet 2"
      ]
    }}
  ],
  "skills": [
    "Excel",
    "SQL",
    "Customer Service"
  ]
}}

CANDIDATE NAME
{full_name}

CONTACT INFO
{contact_info}

EDUCATION
{education}

EXPERIENCE BRAIN DUMP
{experience_dump}

ACTIVITIES / LEADERSHIP / PROJECTS
{activities}

SKILLS
{skills}

JOB DESCRIPTION
{jd_block}
"""
