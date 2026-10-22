"""October 22 sovereign LLM, creative scene and release ingress regressions."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.llm.contracts import LLMMessage, LLMRequest
from runtime._internal import llm_transport
from runtime.llm import build_runtime_llm_client


def test_cloud_chat_completions_payload_and_tenant_redaction(monkeypatch):
    observed = []
    monkeypatch.setattr(llm_transport, "sync_post_json", lambda **kw: observed.append(kw) or SimpleNamespace(
        status=200, json={"choices": [{"message": {"content": "ок"}, "finish_reason": "stop"}]}, text=""))
    client = build_runtime_llm_client(
        provider="openai_compat", base_url="https://foundation-models.api.cloud.ru/v1",
        api_key="key", model="model",
        openai_transport=lambda base, key, body, timeout: llm_transport.llm_generate_openai_compat(
            base_url=base, api_key=key, payload=body, timeout_s=timeout))
    request = LLMRequest(messages=[LLMMessage(role="user", content="привет")],
                         model="model", metadata={"tenant_id": "secret"})
    assert client.generate_sync(request).content == "ок"
    assert observed[0]["url"] == "https://foundation-models.api.cloud.ru/v1/chat/completions"
    sent = observed[0]["data"]
    assert sent["messages"] == [{"role": "user", "content": "привет"}]
    assert "metadata" not in sent and "input" not in sent and "max_output_tokens" not in sent


def test_chat_completion_suffix_is_not_duplicated(monkeypatch):
    urls = []
    monkeypatch.setattr(llm_transport, "sync_post_json", lambda **kw: urls.append(kw["url"]) or SimpleNamespace(status=200, json={}, text=""))
    llm_transport.llm_generate_openai_compat(base_url="https://h.cloud.ru/v1/chat/completions/",
                                              api_key="key", payload={})
    assert urls == ["https://h.cloud.ru/v1/chat/completions"]


class _Agent:
    def __init__(self):
        self.calls = 0

    def run_task(self, task, ctx):
        self.calls += 1
        return SimpleNamespace(json={"subject": "диван", "action": "мастер чистит диван"}, text="")


def test_creative_scene_memoized_per_agent_tenant_and_request():
    from core.growth.ads.creative.pipeline import visual_scene_breakdown
    from core.llm.agent import LLMTaskContext
    agent, another = _Agent(), _Agent()
    ctx = LLMTaskContext(tenant_id="first", offer={"request": "сцена"})
    original = visual_scene_breakdown(agent, ctx, "сцена")
    assert visual_scene_breakdown(agent, ctx, "сцена") == original
    assert agent.calls == 1
    visual_scene_breakdown(agent, LLMTaskContext(tenant_id="second", offer={}), "сцена")
    visual_scene_breakdown(another, ctx, "сцена")
    assert (agent.calls, another.calls) == (2, 1)
    assert visual_scene_breakdown(None, ctx, "сцена").get("action") != "мастер чистит диван"


def test_invalid_brief_rejected_before_llm(monkeypatch):
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient
    from adapters.api.fastapi import business_workspace_commercial_routes as mod
    monkeypatch.setattr(mod, "business_owner_scope", lambda **kwargs: ("owner", "tenant", "business"))
    agent = _Agent()
    router = APIRouter()
    mod.register_business_workspace_commercial_routes(router=router, auth_bundle=None, purchases=None, scene_agent=agent)
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post("/business-workspace/commercial/advertising/creatives/prepare",
        json={"campaign_id": "c", "headline": 7, "description": "valid", "brand_context": "x",
              "campaign_goal": "x", "kind": "image", "formats": ["square"]})
    assert response.status_code == 422 and agent.calls == 0


def test_loopback_api_host_by_default(monkeypatch):
    from scripts.server import run_profile
    import bootstrap.system_boot_surface as boot
    for env in ("API_HOST", "HEALTH_HOST"):
        monkeypatch.delenv(env, raising=False)
    observed = {}
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(
        run=lambda app, host, port: observed.update(host=host, port=port)))
    monkeypatch.setattr(boot, "build_system_boot_surface", lambda: SimpleNamespace(http_app=object()))
    assert run_profile._run_api() == 0
    assert observed["host"] == "127.0.0.1" and os.environ["HEALTH_HOST"] == "127.0.0.1"


def test_pytest_data_dir_is_outside_checkout():
    checkout = Path(__file__).resolve().parents[3]
    data = Path(os.environ["DATA_DIR"]).resolve()
    assert data != checkout and checkout not in data.parents


@pytest.mark.parametrize("base,allowed", [
    ("https://llm.api.cloud.yandex.net/foundationModels/v1/completion", True),
    ("https://gigachat.devices.sberbank.ru/api/v1", True),
    ("https://foundation-models.api.cloud.ru/v1", True),
    ("https://api.openai.com/v1", False),
    ("https://yandex.net.evil.example/v1", False),
    ("https://evilcloud.ru/v1", False),
    ("http://foundation-models.api.cloud.ru/v1", False),
])
def test_sovereign_host_allowlist(monkeypatch, base, allowed):
    monkeypatch.delenv("LLM_ALLOW_FOREIGN_PROVIDERS", raising=False)
    monkeypatch.delenv("LLM_SOVEREIGN_HOSTS", raising=False)
    def build():
        return build_runtime_llm_client(provider="openai_compat", base_url=base,
                                        api_key="key", model="model", openai_transport=lambda *_: {})
    if allowed:
        build()
    else:
        with pytest.raises(RuntimeError):
            build()


def test_anthropic_always_forbidden(monkeypatch):
    monkeypatch.setenv("LLM_SOVEREIGN_HOSTS", "anthropic.com")
    with pytest.raises(RuntimeError, match="anthropic"):
        build_runtime_llm_client(provider="anthropic", base_url="https://api.anthropic.com",
                                 api_key="key", model="model", anthropic_transport=lambda *_: {})
