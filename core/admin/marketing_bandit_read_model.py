"""Marketing uplift (bandit) read-model.

READ-ONLY, event-sourced:
- no writes
- no network
- deterministic given the event log

We compute Beta(alpha,beta) priors per step_key and variant (a/b):

Exposure:
  step event (default: 'tariffs_viewed') with payload {'marketing_variant': 'a'|'b'}
  Exposure increments beta (adds a failure prior).

Outcomes (attributed to latest exposure for that user within attribution_window_ms):

  Success signals (alpha += weight):
    - payment/capture success: policy-configured alpha
    - access granted: policy-configured alpha
    - tariff selected: policy-configured alpha
    - audio progress above threshold: policy-configured alpha

  Negative signals add policy-configured beta:
    - close_tariffs / back / menu_main

Behavioral uplift (multipliers on success weight):
  - fast follow-up window: policy-configured multiplier
  - hesitation window: policy-configured multiplier
  - fast purchase window: policy-configured multiplier
  - medium purchase window: policy-configured multiplier

Output:
  {step_key: {'a': {'alpha': .., 'beta': ..}, 'b': {...}}}
"""

from __future__ import annotations

from typing import Any
from config.marketing_bandit_policy import DEFAULT_MARKETING_BANDIT_POLICY, MarketingBanditPolicy
from core.admin.marketing_bandit_read_model_support import resolve_window_bounds
from core.read_model.cache import global_cache, watermark_for

def marketing_bandit_stats(
    event_store: Any,
    *,
    tenant_id: str = "default",
    step_key: str = "tariffs_viewed",
    window_days: int = DEFAULT_MARKETING_BANDIT_POLICY.default_window_days,
    attribution_window_ms: int = DEFAULT_MARKETING_BANDIT_POLICY.default_attribution_window_ms,
    now_ms: int | None = None,
    policy: MarketingBanditPolicy = DEFAULT_MARKETING_BANDIT_POLICY,
) -> dict[str, dict[str, dict[str, float]]]:
    # Invalidate on relevant event types (best-effort).
    wm = watermark_for(
        event_store,
        user_id=None,
        event_types=(str(step_key), *policy.relevant_event_types),
    )

    def _compute() -> dict[str, dict[str, dict[str, float]]]:
        start_ms, resolved_now_ms = resolve_window_bounds(now_ms=now_ms, window_days=window_days)

        out: dict[str, dict[str, dict[str, float]]] = {str(step_key): policy.variant_priors}

        if event_store is None or not hasattr(event_store, "iter_events"):
            return out

        # user_id -> {'ts': int, 'variant': 'a'|'b'}
        last_exposure: dict[str, dict[str, object]] = {}
        # user_id -> first exposure ts (for time-to-purchase)
        first_exposure_ts: dict[str, int] = {}
        # user_id -> last processed ts (for reaction/hesitation heuristics)
        last_event_ts: dict[str, int] = {}

        try:
            for ev in event_store.iter_events(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=resolved_now_ms):
                if not isinstance(ev, dict):
                    continue
                et = str(ev.get("event_type") or ev.get("type") or "")
                uid = str(ev.get("user_id") or "")
                ts = int(ev.get("timestamp_ms") or 0)
                payload = ev.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {}

                # Exposure
                if et == str(step_key):
                    v = str(payload.get("marketing_variant") or "").strip().lower()
                    if v not in set(policy.variants):
                        continue
                    out[str(step_key)][v]["beta"] += policy.exposure_prior_beta
                    last_exposure[uid] = {"ts": ts, "variant": v}
                    if uid and uid not in first_exposure_ts:
                        first_exposure_ts[uid] = int(ts)
                    last_event_ts[uid] = int(ts)
                    continue

                # Outcomes (success + negatives), attributed to latest exposure.
                if et not in set(policy.outcome_events):
                    continue

                lx = last_exposure.get(uid)
                if not lx:
                    continue

                dt = ts - int(lx.get("ts") or 0)
                if dt < 0 or dt > int(attribution_window_ms):
                    continue

                v = str(lx.get("variant") or "")
                if v not in set(policy.variants):
                    continue

                # Negative signals.
                if et in set(policy.negative_events):
                    out[str(step_key)][v]["beta"] += policy.negative_signal_beta
                    last_event_ts[uid] = int(ts)
                    continue

                # Success weights.
                weight = policy.exposure_prior_beta
                if et in {"payment_succeeded", "payment_captured"}:
                    weight = policy.payment_success_alpha
                elif et == "access_granted":
                    weight = policy.access_granted_alpha
                elif et == "tariff_selected":
                    weight = policy.tariff_selected_alpha
                elif et == "audio_progress":
                    try:
                        percent = float(payload.get("percent", float(0)))
                    except Exception:
                        percent = float(0)
                    if percent < policy.audio_progress_threshold:
                        last_event_ts[uid] = int(ts)
                        continue
                    weight = policy.audio_progress_alpha

                # Behavioral uplift multipliers (best-effort, deterministic).
                prev_ts = last_event_ts.get(uid)
                if prev_ts is not None:
                    delta = int(ts) - int(prev_ts)
                    if delta >= 0 and delta < policy.fast_followup_window_ms:
                        weight *= policy.fast_followup_multiplier
                    elif delta > policy.hesitation_window_ms:
                        weight *= policy.hesitation_multiplier

                if et in {"payment_succeeded", "payment_captured"}:
                    fe = first_exposure_ts.get(uid)
                    if fe is not None:
                        ttp = int(ts) - int(fe)
                        if ttp >= 0 and ttp < policy.fast_purchase_window_ms:
                            weight *= policy.fast_purchase_multiplier
                        elif ttp < policy.medium_purchase_window_ms:
                            weight *= policy.medium_purchase_multiplier

                out[str(step_key)][v]["alpha"] += float(weight)
                last_event_ts[uid] = int(ts)

        except Exception:
            return out

        return out

    return global_cache().get(
        key=("marketing_bandit_stats", str(step_key), int(window_days), int(attribution_window_ms), int(now_ms) if now_ms is not None else None),
        compute=_compute,
        watermark_ms=int(wm),
    )
