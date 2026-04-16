from pathlib import Path

from llm_core.retrieval import store
from llm_core.schemas import EvidenceChunk


def test_persistent_store_round_trip(tmp_path, monkeypatch):
    fake_store_path = tmp_path / "llm_retrieval_store.json"
    monkeypatch.setattr(store, "STORE_PATH", fake_store_path)

    chunk = EvidenceChunk(
        chunk_id="resume:1:resume:0",
        source_type="resume",
        source_id="1",
        section="resume",
        text="Led analytics reporting across operations.",
    )
    store.put_chunks("resume_chunks", [chunk])

    assert fake_store_path.exists()
    loaded = store.get_chunks("resume_chunks")
    assert len(loaded) == 1
    assert loaded[0].text == "Led analytics reporting across operations."


def test_persistent_store_upserts_by_chunk_id(tmp_path, monkeypatch):
    fake_store_path = tmp_path / "llm_retrieval_store.json"
    monkeypatch.setattr(store, "STORE_PATH", fake_store_path)

    original = EvidenceChunk(
        chunk_id="resume:1:resume:0",
        source_type="resume",
        source_id="1",
        section="resume",
        text="Original text",
    )
    updated = EvidenceChunk(
        chunk_id="resume:1:resume:0",
        source_type="resume",
        source_id="1",
        section="resume",
        text="Updated text",
    )
    store.put_chunks("resume_chunks", [original])
    store.put_chunks("resume_chunks", [updated])

    loaded = store.get_chunks("resume_chunks")
    assert len(loaded) == 1
    assert loaded[0].text == "Updated text"


def test_clear_store_removes_index(tmp_path, monkeypatch):
    fake_store_path = tmp_path / "llm_retrieval_store.json"
    monkeypatch.setattr(store, "STORE_PATH", fake_store_path)

    chunk = EvidenceChunk(
        chunk_id="job:1:job_description:0",
        source_type="job",
        source_id="1",
        section="job_description",
        text="SQL and dashboard reporting responsibilities",
    )
    store.put_chunks("job_briefs", [chunk])
    assert store.get_chunks("job_briefs")

    store.clear_store("job_briefs")
    assert store.get_chunks("job_briefs") == []
