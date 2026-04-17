"""
Regression tests for profile_store — focused on data-integrity edge cases.
These tests use a real SQLite database in a tmp_path so they exercise the
actual SQL logic rather than a mock.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path) -> Path:
    """Return a path to a fresh database pre-initialised with the applications schema."""
    db_path = tmp_path / "test_profile.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            company         TEXT NOT NULL DEFAULT '',
            job_title       TEXT NOT NULL DEFAULT '',
            job_description TEXT NOT NULL DEFAULT '',
            match_before    INTEGER DEFAULT 0,
            match_after     INTEGER DEFAULT 0,
            improvements    TEXT DEFAULT '[]',
            resume_used_id  TEXT DEFAULT '',
            created_at      TEXT,
            updated_at      TEXT,
            optimized_at    TEXT,
            status          TEXT DEFAULT 'completed',
            -- extra columns used by job-tracker layer
            location        TEXT DEFAULT '',
            job_url         TEXT DEFAULT '',
            applied_date    TEXT DEFAULT '',
            next_action     TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    conn.close()
    return db_path


def _save(db_path, *, application_id=None, company="Acme", job_title="Engineer",
          match_before=40, match_after=75):
    """Call save_optimization_result against the given test DB."""
    import profile_store

    # Redirect the module's connection factory to our test DB.
    original_get_connection = profile_store.get_connection

    class _Conn:
        def __init__(self):
            self._conn = sqlite3.connect(str(db_path))
            self._conn.row_factory = sqlite3.Row

        def __enter__(self):
            return self._conn

        def __exit__(self, *_):
            self._conn.commit()
            self._conn.close()

    profile_store.get_connection = _Conn

    try:
        return profile_store.save_optimization_result(
            user_id="local-user",
            company_name=company,
            job_title=job_title,
            job_description="Some JD text",
            match_before=match_before,
            match_after=match_after,
            improvements=[],
            resume_used_id="",
            application_id=application_id,
        )
    finally:
        profile_store.get_connection = original_get_connection


def _rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM applications").fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_save_without_application_id_inserts_new_row(tmp_path):
    """Baseline: no application_id always produces a new row."""
    db = _make_db(tmp_path)
    returned_id = _save(db)
    rows = _rows(db)
    assert len(rows) == 1
    assert rows[0]["id"] == returned_id
    assert rows[0]["job_title"] == "Engineer"


def test_save_with_valid_application_id_updates_existing_row(tmp_path):
    """When application_id matches an existing row, it is updated in place."""
    db = _make_db(tmp_path)
    first_id = _save(db, company="Acme", match_before=30, match_after=55)

    updated_id = _save(db, application_id=first_id, company="Updated Corp",
                       match_before=30, match_after=80)

    rows = _rows(db)
    assert len(rows) == 1, "Must not create a second row"
    assert updated_id == first_id
    assert rows[0]["company"] == "Updated Corp"
    assert rows[0]["match_after"] == 80


def test_save_with_stale_application_id_falls_back_to_insert(tmp_path):
    """
    Regression: if application_id does not exist in the DB (deleted or
    wrong session), the UPDATE matches zero rows.  The function must fall
    back to an INSERT and return the new row's id — not silently return the
    stale id while creating no record.
    """
    db = _make_db(tmp_path)
    stale_id = 9999  # no row with this id exists

    returned_id = _save(db, application_id=stale_id, company="New Corp",
                        match_before=50, match_after=70)

    rows = _rows(db)
    assert len(rows) == 1, "Fallback INSERT must create exactly one row"
    assert returned_id != stale_id, "Must not return the non-existent stale id"
    assert rows[0]["id"] == returned_id
    assert rows[0]["company"] == "New Corp"
    assert rows[0]["match_after"] == 70


def test_save_with_wrong_user_id_also_falls_back_to_insert(tmp_path):
    """
    The UPDATE clause includes AND user_id = ?, so a row belonging to a
    different user also produces zero rowcount and should fall back to INSERT.
    """
    db = _make_db(tmp_path)
    first_id = _save(db, company="Owner Corp")

    # Patch to save as a different user pointing at the first row.
    import profile_store

    original_get_connection = profile_store.get_connection

    class _Conn:
        def __init__(self):
            self._conn = sqlite3.connect(str(db))
            self._conn.row_factory = sqlite3.Row

        def __enter__(self):
            return self._conn

        def __exit__(self, *_):
            self._conn.commit()
            self._conn.close()

    profile_store.get_connection = _Conn

    try:
        intruder_id = profile_store.save_optimization_result(
            user_id="attacker-user",
            company_name="Intruder Corp",
            job_title="Hacker",
            job_description="...",
            match_before=0,
            match_after=99,
            improvements=[],
            resume_used_id="",
            application_id=first_id,
        )
    finally:
        profile_store.get_connection = original_get_connection

    rows = _rows(db)
    assert len(rows) == 2, "Attacker's save must not overwrite owner's row"
    owner_row = next(r for r in rows if r["user_id"] == "local-user")
    assert owner_row["company"] == "Owner Corp", "Owner row must be unchanged"
    intruder_row = next(r for r in rows if r["user_id"] == "attacker-user")
    assert intruder_row["id"] == intruder_id
