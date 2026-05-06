from __future__ import annotations


def handle_evolution_job(job) -> None:
    """Pure evolution job dispatcher.

    Никаких side effects вне явных вызовов доменных функций.
    """

    kind = getattr(job, "job_kind", None)
    payload = getattr(job, "payload", None) or {}

    if kind == "health_tick":
        # Minimal no-op job used for integration tests / liveness.
        return

    if kind == "regenerate_marketing_copy":
        # NOTE: путь может отличаться в вашем проекте — тогда меняете ИМПОРТ тут.
        from core.marketing.evolution import regenerate_marketing_copy

        regenerate_marketing_copy(payload)
        return

    raise ValueError(f"Unknown evolution job kind: {kind}")
