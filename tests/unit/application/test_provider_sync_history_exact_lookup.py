from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore  # noqa: I001
from runtime.business_autonomy.provider_sync_history import FileProviderSyncHistoryStore, InMemoryProviderSyncHistoryStore, ProviderSyncHistory


def _row(job_id: str, stamp: str) -> dict[str, object]:
    return {"tenant_id": "tenant-a", "business_id": "business-a", "provider_key": "email_connector", "queue_job_id": job_id, "recorded_at_utc": stamp, "status": "live_executed", "accepted": True}


def test_exact_queue_job_lookup_is_not_limited_by_recent_history() -> None:
    history = ProviderSyncHistory(InMemoryProviderSyncHistoryStore())
    history.append(_row("target-job", "0000"))
    for index in range(150):
        history.append(_row(f"newer-{index}", f"{index + 1:04d}"))
    assert all(row["queue_job_id"] != "target-job" for row in history.list_for_provider(tenant_id="tenant-a", business_id="business-a", provider_key="email_connector", limit=50))
    found = history.find_for_queue_jobs(tenant_id="tenant-a", business_id="business-a", provider_key="email_connector", queue_job_ids=("target-job",))["target-job"]
    assert found["queue_job_id"] == "target-job"


def test_file_history_exact_lookup_scans_canonical_collection(tmp_path) -> None:
    history = ProviderSyncHistory(FileProviderSyncHistoryStore(FileDistributedDocumentStore(tmp_path)))
    history.append(_row("target-job", "0000"))
    for index in range(120):
        history.append(_row(f"newer-{index}", f"{index + 1:04d}"))
    found = history.find_for_queue_jobs(tenant_id="tenant-a", business_id="business-a", provider_key="email_connector", queue_job_ids=("target-job",))["target-job"]
    assert found["queue_job_id"] == "target-job"
    assert history.find_for_queue_jobs(tenant_id="tenant-a", business_id="other-business", provider_key="email_connector", queue_job_ids=("target-job",)) == {}

def test_file_batch_lookup_reads_collection_once_and_keeps_latest(tmp_path, monkeypatch) -> None:
    documents = FileDistributedDocumentStore(tmp_path)
    history = ProviderSyncHistory(FileProviderSyncHistoryStore(documents))
    history.append({**_row("target-a", "0000"), "updated_at_utc": "0000", "marker": "old"})
    history.append({**_row("target-a", "9999"), "updated_at_utc": "9999", "marker": "latest"})
    for index in range(80):
        history.append(_row(f"noise-{index}", f"{index + 1:04d}"))
    original = documents._read_collection
    calls = 0
    def counted(collection: str):
        nonlocal calls
        calls += 1
        return original(collection)
    monkeypatch.setattr(documents, "_read_collection", counted)
    found = history.find_for_queue_jobs(tenant_id="tenant-a", business_id="business-a", provider_key="email_connector", queue_job_ids=("target-a", "noise-79"))
    assert calls == 1
    assert found["target-a"]["marker"] == "latest"
    assert found["noise-79"]["queue_job_id"] == "noise-79"

def test_file_history_scopes_before_limit_so_cross_tenant_noise_cannot_hide_recent_rows(tmp_path, monkeypatch) -> None:
    documents = FileDistributedDocumentStore(tmp_path)
    history = ProviderSyncHistory(FileProviderSyncHistoryStore(documents))
    history.append({**_row("target-old", "2026-09-29T10:00:00+00:00"), "marker": "old"})
    history.append({**_row("target-new", "2026-09-29T12:00:00+00:00"), "marker": "new"})
    for index in range(80):
        history.append({
            "tenant_id": "tenant-noise",
            "business_id": "business-noise",
            "provider_key": "email_connector",
            "queue_job_id": f"noise-{index}",
            "recorded_at_utc": f"2026-09-29T13:{index % 60:02d}:00+00:00",
            "updated_at_utc": f"2026-09-29T14:{index % 60:02d}:00+00:00",
            "status": "live_executed",
            "accepted": True,
        })
    original = documents._read_collection
    calls = 0
    def counted(collection: str):
        nonlocal calls
        calls += 1
        return original(collection)
    monkeypatch.setattr(documents, "_read_collection", counted)

    rows = history.list_for_provider(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="email_connector",
        limit=2,
    )

    assert calls == 1
    assert [row["queue_job_id"] for row in rows] == ["target-new", "target-old"]
    assert all(row["tenant_id"] == "tenant-a" for row in rows)

