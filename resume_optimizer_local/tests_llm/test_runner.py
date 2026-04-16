from llm_core.schemas import JobBrief


def test_job_brief_to_dict_round_trip():
    brief = JobBrief(
        normalized_role_title="Operations Analyst",
        seniority="Early Career",
        industry_hint="Supply Chain",
        responsibilities=["Build dashboards"],
        required_skills=["SQL"],
        domain_hints=["Logistics"],
        prioritization_signals=["Reporting"],
        summary="Helpful summary",
        source_evidence_refs=["job_description:current_job:job_description:0"],
    )
    payload = brief.to_dict()
    assert payload["normalized_role_title"] == "Operations Analyst"
    assert payload["required_skills"] == ["SQL"]
