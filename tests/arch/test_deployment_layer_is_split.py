from pathlib import Path


def test_deployment_layer_is_split() -> None:
    for rel in (
        "infra/process_manager.py",
        "infra/process_spec.py",
        "infra/readiness_gates.py",
        "infra/dependency_health.py",
        "infra/retry_policy.py",
        "infra/retry_models.py",
        "infra/idempotency.py",
        "infra/idempotency_store.py",
        "infra/deployment_boot.py",
        "infra/deployment_boot_result.py",
        "observability/metrics_exporter.py",
        "observability/trace_exporter.py",
    ):
        assert Path(rel).exists(), rel
