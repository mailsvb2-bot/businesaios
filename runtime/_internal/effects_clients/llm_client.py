from __future__ import annotations

"""Sealed transport: LLM clients.

Currently supports OpenAI-compatible /responses endpoint.
Kept internal to runtime/_internal.
"""

from typing import Any, Dict

from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_str

from .http_client import http_json


def generate_openai_compat(*, base_url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
    """OpenAI-compatible LLM call executed in sealed effects."""
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("LLM_BASE_URL_MISSING")
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("LLM_API_KEY_MISSING")

    url = base + "/responses"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "businesaios/llm-openai-compat",
    }

    # Optional OpenAI headers (ignored by other providers)
    org = env_str("OPENAI_ORGANIZATION", "").strip()
    if org:
        headers["OpenAI-Organization"] = org
    project = env_str("OPENAI_PROJECT", "").strip()
    if project:
        headers["OpenAI-Project"] = project

    # Correlation key for cross-service tracing
    try:
        from runtime.observability.tracing import get_correlation_key

        ck = str(get_correlation_key() or "").strip()
        if ck:
            headers["X-Correlation-Key"] = ck
    except Exception:
        swallow(__name__, "llm_correlation")

    return http_json("POST", url, payload if isinstance(payload, dict) else {}, headers=headers, timeout_s=int(timeout_s or 20))
