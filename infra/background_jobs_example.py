from __future__ import annotations

from infra.background_job_models import BackgroundJobSpec
from infra.background_jobs import BackgroundJobs


def register_example_jobs(background_jobs: BackgroundJobs) -> None:
    background_jobs.register(
        BackgroundJobSpec(name="runtime_boot_fingerprint_snapshot"),
        lambda: None,
    )
