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
        # ── Supply chain / logistics ──────────────────────────────────────────
        {
            "keywords": (
                "route optimization", "routing", "network design",
                "transportation modeling", "flow-path", "mode selection",
                "last mile", "freight network",
            ),
            "priority": "Route optimization & transportation network design",
        },
        {
            "keywords": (
                "supplier", "vendor", "negotiation", "contract",
                "procurement", "sourcing", "rfp", "rfq", "spend management",
            ),
            "priority": "Supplier management, sourcing & contract negotiation",
        },
        {
            "keywords": (
                "inventory", "warehouse", "fulfillment", "distribution",
                "carrier", "3pl", "demand planning", "s&op",
            ),
            "priority": "Inventory management, warehouse operations & distribution",
        },
        # ── Software / technology ─────────────────────────────────────────────
        {
            "keywords": (
                "software development", "engineering", "backend", "frontend",
                "full stack", "api", "microservices", "system design",
                "architecture", "ci/cd", "devops", "infrastructure",
            ),
            "priority": "Software design, system architecture & engineering best practices",
        },
        {
            "keywords": (
                "python", "java", "javascript", "typescript", "golang", "rust",
                "react", "node", "sql", "nosql", "kubernetes", "docker",
                "aws", "gcp", "azure", "cloud",
            ),
            "priority": "Technical stack depth and breadth across required languages & platforms",
        },
        {
            "keywords": (
                "machine learning", "deep learning", "nlp",
                "model training", "model deployment", "data science",
                "feature engineering", "a/b testing", "ml pipeline",
                "llm", "neural network",
            ),
            "priority": "Machine learning, AI/ML model development & data-driven experimentation",
        },
        # ── Product management ────────────────────────────────────────────────
        {
            "keywords": (
                "product strategy", "roadmap", "customer insight",
                "prioritization", "product vision", "go-to-market",
                "product-market fit", "user research", "product lifecycle",
            ),
            "priority": "Product strategy, roadmap prioritization & go-to-market execution",
        },
        {
            "keywords": (
                "user stories", "sprint", "agile", "scrum", "backlog",
                "product requirements", "prd", "acceptance criteria", "release",
            ),
            "priority": "Agile product development, backlog management & release planning",
        },
        # ── Finance / accounting ──────────────────────────────────────────────
        {
            "keywords": (
                "financial modeling", "fp&a", "variance analysis",
                "financial reporting", "p&l", "balance sheet", "cash flow",
                "valuation", "dcf", "investment analysis",
            ),
            "priority": "Financial modeling, reporting & investment/valuation analysis",
        },
        {
            "keywords": (
                "audit", "compliance", "sox", "internal controls", "gaap",
                "ifrs", "tax", "accounting", "reconciliation", "general ledger",
            ),
            "priority": "Audit, compliance, internal controls & accounting accuracy",
        },
        {
            "keywords": (
                "budget", "forecast", "cost reduction", "cost-reduction",
                "savings", "efficiency", "capex", "opex", "spend",
            ),
            "priority": "Budgeting, cost management & financial efficiency",
        },
        # ── Marketing / growth ────────────────────────────────────────────────
        {
            "keywords": (
                "brand", "brand strategy", "brand identity", "brand equity",
                "positioning", "messaging", "creative direction",
            ),
            "priority": "Brand strategy, positioning & messaging",
        },
        {
            "keywords": (
                "growth marketing", "user acquisition", "customer acquisition",
                "conversion rate", "funnel", "cac", "ltv", "churn",
                "performance marketing", "paid media", "seo", "sem", "ppc",
                "email marketing", "drip campaign",
            ),
            "priority": "Growth marketing, customer acquisition & retention metrics",
        },
        {
            "keywords": (
                "content marketing", "copywriting", "editorial", "social media",
                "influencer marketing", "brand community", "content campaign",
                "content engagement", "content strategy",
            ),
            "priority": "Content strategy, campaign execution & audience engagement",
        },
        # ── Healthcare / clinical ─────────────────────────────────────────────
        {
            "keywords": (
                "patient", "clinical", "care", "ehr", "emr", "hipaa",
                "outcomes", "treatment", "diagnosis", "clinical trial",
            ),
            "priority": "Clinical care quality, patient outcomes & healthcare compliance (HIPAA)",
        },
        {
            "keywords": (
                "healthcare operations", "revenue cycle", "billing",
                "coding", "prior authorization", "insurance", "payer",
            ),
            "priority": "Healthcare operations, revenue cycle & payer management",
        },
        # ── HR / people ───────────────────────────────────────────────────────
        {
            "keywords": (
                "talent acquisition", "recruiting", "recruiter",
                "employer brand", "candidate experience", "headcount",
                "open requisitions", "interview process",
            ),
            "priority": "Talent acquisition, recruiting strategy & onboarding excellence",
        },
        {
            "keywords": (
                "performance management", "employee engagement", "hrbp",
                "learning and development", "l&d", "succession planning",
                "organizational development", "workforce planning",
            ),
            "priority": "Performance management, employee development & organizational effectiveness",
        },
        {
            "keywords": (
                "compensation", "benefits", "total rewards", "equity",
                "payroll", "hris", "workday", "people analytics",
            ),
            "priority": "Compensation, benefits design & HR systems (HRIS)",
        },
        # ── Consulting / strategy ─────────────────────────────────────────────
        {
            "keywords": (
                "consulting", "client engagement", "advisory", "engagements",
                "client management", "deliverables", "workstream", "deck",
            ),
            "priority": "Client engagement, structured problem-solving & deliverable quality",
        },
        {
            "keywords": (
                "due diligence", "m&a", "transaction", "integration",
                "carve-out", "deal", "private equity", "portfolio",
            ),
            "priority": "M&A due diligence, integration planning & transaction support",
        },
        # ── Analytics / data (cross-domain) ──────────────────────────────────
        {
            "keywords": (
                "analytics", "dashboard", "dashboards", "kpi",
                "reporting", "metrics", "data-driven", "data analysis",
                "bi", "tableau", "power bi", "looker", "sql",
            ),
            "priority": "Data analysis, KPI reporting & business intelligence",
        },
        # ── Leadership / general management ───────────────────────────────────
        {
            "keywords": (
                "cross-functional", "cross functional", "stakeholder",
                "executive", "leadership", "manage teams", "director",
                "vp", "general manager",
            ),
            "priority": "Cross-functional leadership, stakeholder management & executive presence",
        },
        {
            "keywords": (
                "strategy", "strategic", "planning", "vision",
                "roadmap", "initiative", "transformation", "change management",
            ),
            "priority": "Strategic planning, transformation initiatives & organizational change",
        },
        {
            "keywords": (
                "process", "improvement", "lean", "six sigma", "kaizen",
                "standardization", "documentation", "workflow", "efficiency",
            ),
            "priority": "Process improvement, standardization & operational excellence",
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
    profile_context: str = "",
    missing_keywords: list[str] | None = None,
    missing_skills: list[str] | None = None,
) -> str:
    """Generate the manual/API prompt for the optimizer flow."""
    normalized_role = normalize_role_title(target_role) or "the target role"
    industry_text = target_industry if target_industry else "the target industry"
    prioritization_block = _build_prioritization_block(normalized_role, industry_text, job_description)

    # Profile context — placed early so the LLM has full candidate context before rules
    profile_context_block = ""
    if profile_context.strip():
        profile_context_block = f"""
CANDIDATE PROFILE EVIDENCE
Use this saved career-profile evidence as a relevance guide when deciding what to emphasize. Treat it as authoritative for the candidate's current education status, career stage, and target direction when it conflicts with stale wording in the uploaded resume. For work achievements, only surface this evidence when it is already supported by the uploaded resume text. Do not introduce employers, roles, dates, metrics, or skills that cannot be directly anchored back to the resume.

{profile_context}
"""

    # Missing keywords block — shows the LLM exactly where the gap is
    gap_block = ""
    _missing_kw = [k for k in (missing_keywords or []) if k]
    _missing_sk = [s for s in (missing_skills or []) if s]
    if _missing_kw or _missing_sk:
        gap_lines = []
        if _missing_kw:
            gap_lines.append(
                "Keywords present in the job description but NOT yet in the resume "
                f"(incorporate naturally where the candidate's background supports it):\n"
                + ", ".join(_missing_kw[:18])
            )
        if _missing_sk:
            gap_lines.append(
                "Skills/tools listed in the job description that are missing from the resume "
                f"(add only if they are genuinely supported by the candidate's experience):\n"
                + ", ".join(_missing_sk[:12])
            )
        gap_block = "\nGAP ANALYSIS — MISSING JD SIGNALS\n" + "\n\n".join(gap_lines) + "\n"

    return f"""ROLE
Act as an expert recruiter, resume strategist, and professional editor specializing in {industry_text}.

PERSONA CONTEXT
The candidate is at the {career_stage} stage and is targeting a {normalized_role} role.
{profile_context_block}
OBJECTIVE
Optimize the uploaded resume for the target role using only information that is clearly supported by the resume text. Your primary goals in order of priority:
1. Close keyword and skill gaps identified in the Gap Analysis section below.
2. Improve ATS alignment by using the exact terminology from the job description wherever possible.
3. Strengthen bullet clarity with action verbs and quantified impact.
4. Improve the professional summary to directly address the role.

CRITICAL CONSTRAINT: Every change must increase or maintain keyword alignment with the job description. If a change removes industry terminology that appears in the job description, reject that change.
{gap_block}
PRIORITIZATION
Emphasize these areas in every rewrite (ordered by importance for this role):
{prioritization_block}

RULES
1. Do not invent employers, job titles, dates, certifications, scope, or metrics.
2. Rewrite only what is already supported by the resume and job description.
3. Preserve the intent of the original experience while making it more targeted.
4. Keep all keywords and terminology that already appear in BOTH the resume and the JD.
5. Only remove a word or phrase if the replacement is MORE specific or equally specific for the role.
6. Use exact paragraph text from the resume as each match_anchor.
7. Return only valid JSON. No markdown fences. No explanation before or after the JSON.
8. Every match_anchor must exactly match one full paragraph from the resume text below.
9. If no changes are needed for a section, omit it. Return {{}} only if no changes are needed at all.
10. If you are not fully confident that a section's anchor can be copied EXACTLY, omit that section instead of guessing.
11. Do not describe the candidate as a student, current degree candidate, or "Class of ..." unless the current resume or profile evidence clearly says the degree is still in progress.
12. If profile evidence says a degree is completed, use completed language such as "MBA graduate" or "MBA" instead of "MBA candidate."

ANCHOR MATCHING IS CRITICAL
- Export will fail if a single match_anchor differs from the resume by even one character.
- Copy each match_anchor directly from RESUME TEXT. Do not normalize spacing, punctuation, symbols, capitalization, or abbreviations.
- Do not shorten, paraphrase, merge, split, or clean an anchor.
- Do not create a "better" anchor. Use only the original resume paragraph exactly as written.
- If a paragraph contains unusual punctuation, spacing, slashes, pipes, colons, or inconsistent formatting, preserve it exactly.

SECTION-SAFETY RULES
- summary_replacement is optional and high-risk. Include it only if you can copy the current summary paragraph EXACTLY from the resume.
- If the summary is spread across multiple lines or is ambiguous, omit summary_replacement.
- Do not convert a skills paragraph into a summary paragraph or a summary paragraph into a skills paragraph.
- Keep each replacement aligned to the same section type it came from: summary stays summary, bullet stays bullet, skills stays skills.
- It is better to return fewer replacements than to return a single unsafe anchor.

BULLET-WRITING REQUIREMENTS
Each rewritten bullet must:
- Start with a strong action verb (Led, Built, Negotiated, Implemented, Delivered, Designed, etc.)
- Quantify impact when any number, metric, or scope is present in the original
- Stay concise: 1–2 lines maximum
- Prioritize outcome and business impact over task description
- Weave in missing JD keywords where the underlying experience genuinely supports it
- Preserve company-specific facts, "first", proprietary names, and earned achievements

SKILLS SECTION GUIDANCE
- Lead with skills from the job description that are already supported by the resume
- Incorporate missing JD tools/platforms only if the candidate's background can honestly support them
- Use specific names (e.g. "Looker Studio", "SAP S/4HANA") over generic terms
- Group related skills logically; order groups by relevance to {normalized_role}
- Do not add skills that have no grounding in the resume text

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
- All top-level keys are optional. Include only sections that genuinely need updating.
- Each replacement object must contain both match_anchor and replacement_text.
- Do not include comments, analysis, or extra keys.
- Before finalizing the JSON, double-check that every match_anchor appears verbatim inside RESUME TEXT exactly once.

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
