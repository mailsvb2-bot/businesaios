# RL Ads Optimization (production-safe)

This patchset adds a **closed-loop** ads optimizer under `core/growth/ads/rl/`.

The design is intentionally conservative:
- **finite action space** (budget/bid/cpa + creative/audience/objective)
- **contextual bandit policy (UCB1)** as a safe stepping stone
- **append-only experience** in the canonical `event_store` (`ads_rl_*` events)
- **safety gates** (canary rollout, rollout guard, budget increase cap)
- **no background loops**: all updates are driven by explicit runtime actions

## Runtime actions

- `ads_rl_suggest@v1`
  Returns a suggestion + an `AdsPlan` (generic `update_campaign` command).
  Stores `ads_rl_suggested@v1` in event store.

- `ads_rl_train_tick@v1`
  Attaches reward to a window observation and stores `ads_rl_observed@v1`.

- (worker) `core.growth.ads.rl.observer.observe_tick_once`
  Polls `ads_metrics_imported` events and automatically calls `.observe(...)` for the latest suggestion per campaign.
  It persists a tenant-aware checkpoint as `ads_rl_observer_checkpoint@v1`.

- `ads_rl_report@v1`
  Quick stats view (recent reward mean + last steps).

All actions are registered in `runtime/boot/actions_registry.py` and wired in `runtime/boot/system_builder.py`.

## Enable

Set environment variable:

- `ADS_RL_ENABLED=1`

Without it, the actions return `ads_rl_service_missing` (service not wired).

## Event types

- `ads_rl_suggested@v1` (policy + action + state snapshot + metadata)
- `ads_rl_observed@v1` (reward attached)

Aux (worker only):
- `ads_rl_observer_checkpoint@v1` (tenant checkpoint for imported metrics scanning)

## Auto observe/tick

To make reward attachment automatic after metrics imports, run a small polling worker:

- Input: `ads_metrics_imported` events
- Output: `ads_rl_observed@v1` events

Implementation: `core/growth/ads/rl/observer.py`.

Important: the RL suggestion handler stores a **spec snapshot** into `ads_rl_suggested@v1.payload.meta.spec`.
If you bypass runtime handlers, make sure you store the spec snapshot too, otherwise the observer will skip.

These events are enough to later build a dataset snapshot for offline training if desired.

## Notes

This is intentionally not "full" deep RL.
For ads knobs, **bandits** + **safety gates** are usually the correct production default:
- stable
- interpretable
- easy to roll back
- compatible with off-policy evaluation

If you later want a true MDP RL agent (stateful, delayed reward), add it as a new policy implementation **without** changing the runtime surface.
