from __future__ import annotations

"""Canonical event types used across products.

Keep stable. Additive-only.
"""

LLM_REQUESTED = "llm_requested"
LLM_COMPLETED = "llm_completed"
LLM_FAILED = "llm_failed"
LLM_CACHE_HIT = "llm_cache_hit"

# LLM operational signals (best-effort; additive-only)
LLM_SKIPPED = "llm_skipped"  # budgets / limiter / dedupe
LLM_BUDGET_BLOCKED = "llm_budget_blocked"
LLM_CIRCUIT_OPEN = "llm_circuit_open"
LLM_ALERT = "llm_alert"  # spikes/timeouts/cost

OFFER_SHOWN = "offer_shown"
OFFER_CLICKED = "offer_clicked"
PAYWALL_OPENED = "paywall_opened"
PURCHASE_ATTEMPT = "purchase_attempt"
PURCHASE_SUCCESS = "purchase_success"
PURCHASE_FAILED = "purchase_failed"
