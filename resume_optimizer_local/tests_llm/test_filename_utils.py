from filename_utils import build_resume_download_filename


def test_build_resume_download_filename_uses_requested_pattern():
    assert (
        build_resume_download_filename("Simum Tasnim", "Supply Chain Network Planning Manager")
        == "Simum Tasnim_Resume_Supply Chain Network Planning Manager.docx"
    )


def test_build_resume_download_filename_removes_unsafe_characters():
    assert (
        build_resume_download_filename("Jane / Doe", "Operations: Planning * Lead")
        == "Jane Doe_Resume_Operations Planning Lead.docx"
    )


def test_build_resume_download_filename_uses_clear_fallbacks():
    assert build_resume_download_filename("", "") == "Candidate_Resume_Target Role.docx"
