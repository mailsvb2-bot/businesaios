from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


"""Canonical defaults for offline ML job wiring.

These defaults are intentionally stricter than the ad-hoc values that used to be
embedded directly in boot_ml_job.py.

Important:
- evaluation delay remains 0 by default because the current offline learning job
  performs candidate validation inside the same bounded job execution.
  Dataset separation and component separation are still enforced.
- rollout soak and promotion thresholds remain non-zero by default.
"""

DEFAULT_ML_MONITOR_WINDOW_MS = 60_000
DEFAULT_ML_ROLLBACK_DROP = 0.2
DEFAULT_ML_MIN_ONLINE_N = 20
DEFAULT_ML_MIN_SAMPLE_SIZE = 500
DEFAULT_ML_MIN_IMPROVEMENT = 0.03
DEFAULT_ML_SOAK_PERIOD_MS = 6 * 60 * 60 * 1000
DEFAULT_ML_MIN_EVAL_DELAY_MS = 0
