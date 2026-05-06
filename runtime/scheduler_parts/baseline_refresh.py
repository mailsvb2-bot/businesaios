from __future__ import annotations

from runtime.scheduler_helpers import log, log_exception_throttled


def refresh_baseline_metrics(*, rollout, event_store, start_ms: int, now_ms: int) -> None:
    try:
        active_id = str(rollout.state().active_policy_id)
        base_events = event_store.load(start_ms, now_ms)
        from ml.metrics import compute_online_metrics

        base_online = compute_online_metrics(base_events, policy_id=active_id)
        prev = rollout.baseline_metrics()
        rollout.set_baseline_metrics(
            {
                **prev,
                "online_mean_reward": float(base_online.mean_reward),
                "online_mean_ltv": float(base_online.mean_ltv),
                "online_n": float(base_online.n),
            }
        )
    except Exception as exc:
        log_exception_throttled(log, "runtime_scheduler_baseline_metrics_refresh_failed", exc)
