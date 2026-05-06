from __future__ import annotations


def normalize_env(env: str | None) -> str:
    raw = str(env or "").strip().lower()
    if not raw:
        return "prod"
    return "prod" if raw == "production" else raw
