from __future__ import annotations

import time


def test_evolution_worker_processes_outbox(tmp_path, monkeypatch):
    """Integration: enqueue job -> worker.tick_once -> job done.

    Guards against regressions where deploy starts but the worker does nothing.
    """
    outbox_path = tmp_path / "evolution.db"
    monkeypatch.setenv("EVOLUTION_DB_PATH", str(outbox_path))
    monkeypatch.setenv("EVOLUTION_ENABLED", "1")
    monkeypatch.setenv("EVOLUTION_BATCH_SIZE", "10")
    monkeypatch.setenv("EVOLUTION_POLL_INTERVAL_SEC", "1")

    from core.evolution.outbox import EvolutionOutbox
    from runtime.evolution.worker import EvolutionWorker

    outbox = EvolutionOutbox.from_env()

    job_id = outbox.enqueue(job_kind="health_tick", payload={"ts": int(time.time())})
    assert job_id

    worker = EvolutionWorker(outbox=outbox, poll_interval_sec=1, batch_size=10, max_runtime_sec=5)
    n = worker.tick_once()
    assert n >= 1

    assert outbox.count_pending() == 0
    assert outbox.get_status(job_id) == "done"
