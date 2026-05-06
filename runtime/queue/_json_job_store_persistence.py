from __future__ import annotations

from pathlib import Path
import os

from governance.persistence_codec import atomic_write_json, from_dataclass, read_json_or_default, to_jsonable
from runtime.queue._inmemory_job_store_ops import ClaimTokenMap, DedupeMap, JobMap
from runtime.queue.job_contract import JobRecord


CANON_RUNTIME_QUEUE_JSON_JOB_STORE_PERSISTENCE = True


def runtime_queue_store_path() -> Path:
    explicit = os.getenv("BUSINESAIOS_JOB_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv("DATA_DIR", "data").strip() or "data"
    return Path(data_dir) / "runtime" / "job_store.json"


def load_json_job_store_state(path: str | Path) -> tuple[JobMap, DedupeMap, ClaimTokenMap]:
    store_path = Path(path)
    raw = read_json_or_default(store_path, default={"jobs": [], "claim_tokens": {}})
    items = raw.get("jobs", []) if isinstance(raw, dict) else []
    jobs: JobMap = {}
    by_dedupe: DedupeMap = {}
    for payload in items:
        job = from_dataclass(JobRecord, dict(payload))
        jobs[(job.tenant_id, job.job_id)] = job
        by_dedupe[(job.tenant_id, job.dedupe_key)] = job.job_id
    claim_tokens_raw = raw.get("claim_tokens", {}) if isinstance(raw, dict) else {}
    claim_tokens: ClaimTokenMap = {}
    for key, value in dict(claim_tokens_raw).items():
        tenant_id, _, job_id = str(key).partition(":")
        if tenant_id and job_id:
            claim_tokens[(tenant_id, job_id)] = int(value)
    return jobs, by_dedupe, claim_tokens


def flush_json_job_store_state(*, path: str | Path, jobs: JobMap, claim_tokens: ClaimTokenMap) -> None:
    atomic_write_json(
        Path(path),
        {
            "jobs": [to_jsonable(item) for item in jobs.values()],
            "claim_tokens": {f"{tenant}:{job_id}": token for (tenant, job_id), token in claim_tokens.items()},
        },
    )


__all__ = [
    "CANON_RUNTIME_QUEUE_JSON_JOB_STORE_PERSISTENCE",
    "flush_json_job_store_state",
    "load_json_job_store_state",
    "runtime_queue_store_path",
]
