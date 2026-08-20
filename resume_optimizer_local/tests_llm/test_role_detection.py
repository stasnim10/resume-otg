from streamlit_app import detect_role_title
from filename_utils import build_resume_download_filename


def test_detect_role_title_from_hiring_heading():
    job_description = """🚨 We’re Hiring: Amazon Brand Manager

Do you know Amazon inside and out — and know how to turn that knowledge into real growth for brands?

Velocity Sellers is looking for an Amazon Brand Manager to join our growing team.
This isn't a traditional account manager role.
"""

    detected_role = detect_role_title(job_description)

    assert detected_role == "Amazon Brand Manager"
    assert (
        build_resume_download_filename("Simum Tasnim", detected_role)
        == "Simum Tasnim_Resume_Amazon Brand Manager.docx"
    )


def test_detect_role_title_consumes_full_an_article():
    job_description = "Acme is looking for an Operations Manager to join our team."

    assert detect_role_title(job_description) == "Operations Manager"
