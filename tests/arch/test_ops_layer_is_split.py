from pathlib import Path


def test_ops_layer_is_split() -> None:
    for rel in (
        "infra/lifecycle.py",
        "infra/lifecycle_state.py",
        "infra/graceful_shutdown.py",
        "infra/shutdown_hooks.py",
        "infra/background_jobs.py",
        "infra/background_job_models.py",
        "infra/secret_provider.py",
        "infra/ops_boot.py",
        "infra/ops_boot_result.py",
        "infra/signal_handlers.py",
    ):
        assert Path(rel).exists(), rel
