from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from runtime._internal.http_transport import form_urlencode as encode_oauth_form, sync_post_json, sync_request
from runtime.observability.error_handling import swallow
from runtime.platform.config.env_flags import env_str


def _raise_for_transport_failure(*, provider: str, url: str, response) -> None:
    status = int(getattr(response, 'status', 0) or 0)
    if 200 <= status < 300:
        return
    raise RuntimeError(f"llm_transport_failed provider={provider} status={status} url={url}")
def _headers_for(*, provider: str, api_key: str, extra_headers: dict[str, Any] | None = None) -> dict[str, str]:
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
def llm_post_json(*, provider: str, url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
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
def llm_generate_openai_compat(*, base_url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="openai_compat",
        url=base + "/responses",
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
def llm_generate_anthropic(*, base_url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="anthropic",
        url=base + "/v1/messages",
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )
_GIGACHAT_TOKENS: dict[str, tuple[str, float]] = {}

def _gigachat_access_token(api_key: str, timeout_s: int) -> str:
    key = str(api_key or "").strip()
    token, expires_at = _GIGACHAT_TOKENS.get(key, ("", 0.0))
    if token and expires_at - 60 > time.time():
        return token
    url = env_str("GIGACHAT_AUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth").strip()
    if url != "https://ngw.devices.sberbank.ru:9443/api/v2/oauth":
        raise RuntimeError("gigachat_oauth_endpoint_untrusted")
    resp = sync_request(
        method="POST", url=url, timeout_s=float(timeout_s or 20),
        body=encode_oauth_form({"scope": env_str("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip()}),
        headers={"Authorization": f"Basic {key}", "RqUID": str(uuid4()),
                 "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    _raise_for_transport_failure(provider="gigachat_oauth", url=url, response=resp)
    data = resp.json if isinstance(resp.json, dict) else {}
    token = str(data.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("gigachat_oauth_missing_token")
    _GIGACHAT_TOKENS[key] = (token, float(data.get("expires_at") or 0) / 1000.0 or time.time() + 1500)
    return token

def llm_generate_gigachat(*, base_url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
    base = str(base_url or "").strip().rstrip("/")
    return llm_post_json(
        provider="gigachat",
        url=base if base.endswith("/chat/completions") else base + "/chat/completions",
        api_key=_gigachat_access_token(api_key, timeout_s),
        payload=payload,
        timeout_s=timeout_s,
    )
def llm_generate_yandexgpt(*, base_url: str, api_key: str, payload: dict[str, Any], timeout_s: int = 20) -> dict[str, Any]:
    return llm_post_json(
        provider="yandexgpt",
        url=str(base_url or "").strip(),
        api_key=api_key,
        payload=payload,
        timeout_s=timeout_s,
    )


YANDEX_ART_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
YANDEX_OPERATION_URL = "https://operation.api.cloud.yandex.net/operations/"


def yandex_art_generate(
    *, api_key: str, folder_id: str, prompt: str, negative: str = "", seed: int = 0,
    width_ratio: int = 1, height_ratio: int = 1, timeout_s: int = 20, max_wait_s: float = 90.0,
    poll_s: float = 3.0, sleep=time.sleep,
) -> bytes:
    """YandexART async image generation on fixed sovereign Yandex hosts; returns image bytes."""
    import base64
    import re as _re

    key, folder = str(api_key or "").strip(), str(folder_id or "").strip()
    if not key:
        raise RuntimeError("LLM_API_KEY_MISSING")
    if not _re.fullmatch(r"[a-z0-9]{8,64}", folder):
        raise RuntimeError("yandex_art_folder_id_invalid")
    messages = [{"text": str(prompt)[:500], "weight": 1}]
    if negative:
        messages.append({"text": str(negative)[:500], "weight": -1})
    body = {
        "modelUri": f"art://{folder}/yandex-art/latest",
        "messages": messages,
        "generationOptions": {"seed": int(seed), "aspectRatio": {"widthRatio": int(width_ratio), "heightRatio": int(height_ratio)}},
    }
    headers = _headers_for(provider="yandexgpt", api_key=key)
    resp = sync_post_json(url=YANDEX_ART_URL, headers=headers, data=body, timeout_s=int(timeout_s or 20))
    _raise_for_transport_failure(provider="yandex_art", url=YANDEX_ART_URL, response=resp)
    op_id = str(resp.json.get("id") or "") if isinstance(resp.json, dict) else ""
    if not _re.fullmatch(r"[A-Za-z0-9_-]{4,128}", op_id):
        raise RuntimeError("yandex_art_operation_missing")
    waited = 0.0
    while True:
        r = sync_request(method="GET", url=YANDEX_OPERATION_URL + op_id, headers=headers, timeout_s=float(timeout_s or 20))
        _raise_for_transport_failure(provider="yandex_art", url=YANDEX_OPERATION_URL, response=r)
        data = r.json if isinstance(r.json, dict) else {}
        if data.get("error"):
            raise RuntimeError("yandex_art_failed")
        if data.get("done"):
            image = str((data.get("response") or {}).get("image") or "")
            if not image:
                raise RuntimeError("yandex_art_empty_image")
            return base64.b64decode(image)
        if waited >= max_wait_s:
            raise RuntimeError("yandex_art_timeout")
        sleep(poll_s)
        waited += poll_s
