from __future__ import annotations

import asyncio

from core.ai.world_state import WorldStateV1
from core.ai_ceo.intent import build_intent, build_intent_from_session_args
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.planner import build_ceo_plan
from core.ai_ceo.safety import AutonomyPolicyV1
from core.llm import build_yandexgpt_client
from core.llm.contracts import LLMMessage, LLMRequest
from interfaces.ads.google_ads_connector import GoogleAdsConfig, GoogleAdsConnector
from interfaces.ads.oauth_helper import OAuthAppConfig


class _Tokens:
    async def put(self, **kwargs):
        return None

    async def get(self, **kwargs):
        return {"access_token": "tok"}


class _Vault:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_secret(self, *args):
        if len(args) == 2:
            tenant_id, key = str(args[0]), str(args[1])
        else:
            tenant_id, key = "", str(args[0])
        self.calls.append((tenant_id, key))
        if key.endswith("CLIENT_ID") or key.endswith("client_id"):
            return "cid"
        if key.endswith("CLIENT_SECRET") or key.endswith("client_secret"):
            return "secret"
        return None


class _Http:
    async def post(self, *args, **kwargs):
        return {"access_token": "tok", "customer_id": "acc1"}


class _TransportRecorder:
    def __init__(self) -> None:
        self.called = False

    def __call__(self, base_url: str, api_key: str, payload: dict, timeout_s: int) -> dict:
        self.called = True
        return {
            "result": {
                "alternatives": [{"message": {"text": "ok"}}],
                "usage": {"inputTextTokens": 1, "completionTokens": 1, "totalTokens": 2},
            }
        }


def test_ai_ceo_intent_builder_normalizes_objective_and_horizon() -> None:
    intent = build_intent(objective="roi", horizon="30d", risk_level="medium")
    assert intent.kind == "steady_roi"
    assert intent.horizon_days == 30
    assert intent.risk_level == "medium"


def test_ai_ceo_state_intent_parser_uses_objective_from_session() -> None:
    intent = build_intent_from_session_args(args="21 high", objective="risk")
    assert intent.kind == "reduce_risk"
    assert intent.horizon_days == 21
    assert intent.risk_level == "high"


def test_ai_ceo_planner_keeps_single_policy_and_rank_path() -> None:
    state = WorldStateV1(
        schema_version=1,
        tenant_id="t1",
        user_id="u1",
        session={"args": "14 low", "objective": "growth"},
        user={"user_id": "u1"},
        product={},
        economy={},
        timestamp_ms=0,
        meta={},
    )
    plan = build_ceo_plan(state=state, snapshot=GrowthSnapshotV1(), autonomy=AutonomyPolicyV1())
    assert plan.intent.kind == "increase_profit"
    assert plan.steps


def test_google_ads_connector_does_not_depend_on_hidden_mutable_tenant_state() -> None:
    vault = _Vault()
    connector = GoogleAdsConnector(http=_Http(), tokens=_Tokens(), vault=vault, cfg=GoogleAdsConfig(oauth=OAuthAppConfig(client_id="", client_secret="", authorize_url="", token_url="", scopes="")))
    out = asyncio.run(connector.connect(tenant_id="tenant-42", redirect_uri="https://example.test/cb"))
    assert out.url
    assert any(call[0] == "tenant-42" for call in vault.calls)


def test_yandex_async_generation_uses_async_surface() -> None:
    transport = _TransportRecorder()
    client = build_yandexgpt_client(transport=transport, base_url="https://llm.test", api_key="k", default_model="yandexgpt-lite")

    async def _run() -> str:
        resp = await client.generate(LLMRequest(model="yandexgpt-lite", messages=[LLMMessage(role="user", content="hi")], timeout_s=1.0))
        return resp.content

    assert asyncio.run(_run()) == "ok"
    assert transport.called is True
