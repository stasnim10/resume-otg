"""
Prompt generation for the Streamlit prototype.
"""
from __future__ import annotations

import re


def normalize_role_title(extracted_title: str) -> str:
    """Strip company, location, and LinkedIn-style framing from a role title."""
    title = " ".join(extracted_title.split()).strip()
    if not title:
        return ""

    title = re.sub(r"^.*?\bhiring\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+in\s+[^,]+,\s*[A-Z]{2}.*$", "", title)
    title = re.sub(r"\s+-\s+remote$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+\|\s+linkedin.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+at\s+[A-Z][A-Za-z0-9&' .,-]*$", "", title)
    title = re.sub(r"\s{2,}", " ", title).strip(" -|,")
    return title


def _extract_role_specific_priorities(job_description: str, target_role: str, target_industry: str) -> list[str]:
    """Return up to five priorities tailored to the JD and normalized role."""
    jd_lower = job_description.lower()
    role_lower = target_role.lower()
    industry_lower = target_industry.lower()

    mappings = [
        {
            "keywords": (
                "route optimization",
                "routing",
                "network design",
                "transportation modeling",
                "flow-path",
                "mode selection",
            ),
            "priority": "Route optimization & network design",
        },
        {
            "keywords": (
                "analytics",
                "dashboard",
                "dashboards",
                "kpi",
                "reporting",
                "metrics",
                "data-driven",
                "forecasting",
            ),
            "priority": "Advanced analytics, dashboards & performance reporting",
        },
        {
            "keywords": (
                "cost",
                "savings",
                "budget",
                "efficiency",
                "reduce",
                "freight",
                "$100mm",
                "cost-reduction",
            ),
            "priority": "Cost reduction, budget management & operational efficiency",
        },
        {
            "keywords": (
                "supplier",
                "vendor",
                "negotiation",
                "contract",
                "procurement",
                "sourcing",
            ),
            "priority": "Supplier management, sourcing & contract negotiation",
        },
        {
            "keywords": (
                "cross-functional",
                "collaboration",
                "stakeholder",
                "distribution",
                "inventory",
                "finance",
                "carrier",
                "operations",
            ),
            "priority": "Cross-functional collaboration & stakeholder management",
        },
        {
            "keywords": (
                "strategy",
                "strategic",
                "planning",
                "execution",
                "initiative",
                "initiatives",
            ),
            "priority": "Strategic planning, project execution & operational leadership",
        },
        {
            "keywords": (
                "process",
                "improvement",
                "standardized",
                "standardizing",
                "documentation",
                "procedures",
                "workflow",
            ),
            "priority": "Process improvement, standardization & workflow design",
        },
        {
            "keywords": (
                "product strategy",
                "roadmap",
                "customer insight",
                "experimentation",
                "prioritization",
            ),
            "priority": "Product strategy, customer insight & roadmap prioritization",
        },
    ]

    priorities: list[str] = []
    seen: set[str] = set()
    for mapping in mappings:
        if any(keyword in jd_lower or keyword in role_lower or keyword in industry_lower for keyword in mapping["keywords"]):
            if mapping["priority"] not in seen:
                priorities.append(mapping["priority"])
                seen.add(mapping["priority"])

    fallback_priorities = [
        "Core responsibilities and skill keywords from the target role",
        "Quantified business impact, metrics, and measurable outcomes",
        "Cross-functional leadership, collaboration, and ownership",
        "Systems thinking, process improvement, and execution discipline",
        "Strategic relevance to the target role and industry",
    ]
    for fallback in fallback_priorities:
        if len(priorities) >= 5:
            break
        if fallback not in seen:
            priorities.append(fallback)
            seen.add(fallback)

    return priorities[:5]


def _build_prioritization_block(target_role: str, target_industry: str, job_description: str) -> str:
    """Return a deterministic prioritization block for the optimizer prompt."""
    priorities = _extract_role_specific_priorities(job_description, target_role, target_industry)
    return "\n".join(f"{index}. {priority}" for index, priority in enumerate(priorities, start=1))


def build_optimizer_prompt(
    resume_text: str,
    job_description: str,
    career_stage: str,
    target_role: str,
    target_industry: str,
) -> str:
    """Generate the manual/API prompt for the optimizer flow."""
    normalized_role = normalize_role_title(target_role) or "the target role"
    industry_text = target_industry if target_industry else "the target industry"
    prioritization_block = _build_prioritization_block(normalized_role, industry_text, job_description)

    return f"""ROLE
Act as an expert recruiter, resume strategist, and professional editor focused on {industry_text}.

PERSONA CONTEXT
The candidate is at the {career_stage} stage and is targeting a {normalized_role} role.

OBJECTIVE
Optimize the uploaded resume for the target role using only information that is clearly supported by the resume. Improve relevance, clarity, and ATS alignment while preserving honesty.

PRIORITIZATION
Focus your optimization on these areas (in order of importance):
{prioritization_block}

When rewriting, emphasize accomplishments and experience that directly align with these five areas.

RULES
1. Do not invent employers, job titles, dates, certifications, scope, or metrics.
2. Rewrite only what is already supported by the resume and job description.
3. Preserve the intent of the original experience while making it more targeted.
4. Use exact paragraph text from the resume as each match_anchor.
5. Return only valid JSON. No markdown fences. No explanation before or after the JSON.
6. Every match_anchor must exactly match one full paragraph from the resume text below.
7. If no changes are needed for a section, omit it from the output. Return {{}} if no changes are needed at all.

BULLET-WRITING REQUIREMENTS
Each bullet point in replacements should:
- Start with a strong action verb (Led, Managed, Developed, Coordinated, Negotiated, Established, Implemented, etc.)
- Include a quantifiable result or impact when present in the original (metrics, percentages, cost savings, efficiency gains)
- Remain concise (1-2 lines maximum)
- Focus on outcome and impact, not just activities
- Align with the prioritization areas above

SKILLS SECTION GUIDANCE
For skills replacements:
- Prioritize technical and operational skills from the job description
- Include analytical tools and platforms mentioned in the JD when they are already supported by the resume
- Remain truthful to resume experience and do not add unsupported skills
- Order skills by relevance to the {normalized_role} role
- Group related skills together when it improves readability

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
