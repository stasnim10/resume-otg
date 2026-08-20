from supabase_profile_store import (
    _dedupe_legacy_optimization_rows,
    _optimization_history_item,
)


def _run(run_id: str, run_at: str, mode: str, *, score_after: int = 80) -> dict:
    return {
        "id": run_id,
        "job_id": "job-1",
        "match_before": 60,
        "match_after": score_after,
        "improvements": [{"type": "keyword_addition"}],
        "cover_letter_storage_path": f"meta://execution-mode/{mode}" if mode else "",
        "run_at": run_at,
        "tracked_jobs": {"job_title": "Operations Manager", "company": "Acme"},
    }


def test_dedupes_legacy_hosted_pair_and_preserves_recorded_mode():
    tracker_copy = _run("duplicate", "2026-08-20T10:00:05+00:00", "")
    original = _run("original", "2026-08-20T10:00:00+00:00", "api")

    rows = _dedupe_legacy_optimization_rows([tracker_copy, original])

    assert len(rows) == 1
    assert rows[0]["id"] == "original"


def test_keeps_legitimate_repeat_runs():
    first = _run("first", "2026-08-20T10:00:00+00:00", "api")
    repeat = _run("repeat", "2026-08-20T10:01:00+00:00", "api")

    assert len(_dedupe_legacy_optimization_rows([repeat, first])) == 2


def test_history_mapping_exposes_dashboard_timestamp_and_counts():
    item = _optimization_history_item(
        _run("run-1", "2026-08-20T10:00:00+00:00", "manual")
    )

    assert item["created_at"] == "2026-08-20T10:00:00+00:00"
    assert item["execution_mode"] == "manual"
    assert item["company"] == "Acme"
    assert item["improvements_count"] == 1
