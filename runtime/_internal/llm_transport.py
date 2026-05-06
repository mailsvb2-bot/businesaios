from __future__ import annotations
from typing import Any, Dict
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_str
from runtime._internal.http_transport import sync_post_json

def _raise_for_transport_failure(*, provider: str, url: str, response) -> None:
    status = int(getattr(response, 'status', 0) or 0)
    if 200 <= status < 300:
        return
    raise RuntimeError(f"llm_transport_failed provider={provider} status={status} url={url}")
def _headers_for(*, provider: str, api_key: str, extra_headers: Dict[str, Any] | None = None) -> Dict[str, str]:
    key = str(api_key or "").strip()
    provider_name = str(provider or "openai_compat").strip().lower()
    if provider_name == "anthropic":
        headers = {
            "x-api-key": key,
            "anthropic-version": env_str("ANTHROPIC_VERSION", "2023-06-01").strip() or "2023-06-01",
            "Content-Type": "application/json",
            "User-Agent": "businesaios/llm-anthropic",
        }
    elif provider_name == "yandexgpt":
        headers = {
            "Authorization": f"Api-Key {key}",
            "Content-Type": "application/json",
            "User-Agent": "businesaios/llm-yandexgpt",
        }
    else:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": f"businesaios/llm-{provider_name}",
        }
        if provider_name == "openai_compat":
            org = env_str("OPENAI_ORGANIZATION", "").strip()
            if org:
                headers["OpenAI-Organization"] = org
            project = env_str("OPENAI_PROJECT", "").strip()
            if project:
                headers["OpenAI-Project"] = project
    for hk, hv in (extra_headers or {}).items():
        if hv is None:
            continue
        headers[str(hk)] = str(hv)
    try:
        from runtime.observability.tracing import get_correlation_key
        ck = str(get_correlation_key() or "").strip()
        if ck:
            headers["X-Correlation-Key"] = ck
    except Exception:
        swallow(__name__, 'runtime/_internal/llm_transport.py')
    return headers
def llm_post_json(*, provider: str, url: str, api_key: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    target = str(url or "").strip()
    if not target:
        raise RuntimeError("LLM_BASE_URL_MISSING")
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("LLM_API_KEY_MISSING")
    body = dict(payload if isinstance(payload, dict) else {})
    extra_headers = body.pop("_headers", None)
    resp = sync_post_json(
        url=target,
        headers=_headers_for(provider=provider, api_key=key, extra_headers=(extra_headers if isinstance(extra_headers, dict) else None)),
        data=body,
        timeout_s=int(timeout_s or 20),
    )
    _raise_for_transport_failure(provider=str(provider or ''), url=target, response=resp)
    if isinstance(resp.json, dict) and resp.json:
        return dict(resp.json)
    return {"output_text": str(resp.text or ""), "status": int(resp.status or 0)}
def llm_generate_openai_compat(*, base_url: str, api_key: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="openai_compat",
        url=base + "/responses",
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
def llm_generate_anthropic(*, base_url: str, api_key: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="anthropic",
        url=base + "/v1/messages",
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
def llm_generate_gigachat(*, base_url: str, api_key: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="gigachat",
        url=base + "/chat/completions",
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
def llm_generate_yandexgpt(*, base_url: str, api_key: str, payload: Dict[str, Any], timeout_s: int = 20) -> Dict[str, Any]:
    return llm_post_json(
        provider="yandexgpt",
        url=str(base_url or "").strip(),
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
