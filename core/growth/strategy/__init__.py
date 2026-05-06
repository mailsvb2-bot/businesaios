from __future__ import annotations

"""AI Growth Strategy primitives.

Small, boring, explicit pieces:
- contracts for goals/signals/hypotheses/experiments
- deterministic scoring
- optional LLM-backed hypothesis generation (strict JSON)
- event_store backlog (append-only) + read helpers
"""
