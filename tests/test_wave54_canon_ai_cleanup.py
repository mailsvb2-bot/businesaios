from __future__ import annotations

from bootstrap.world_snapshot_input_adapter import build_world_snapshot_input
from core.ai.world_state import WorldStateV1
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.service import build_minimal_plan_steps
from core.growth.ads.creative.pipeline import generate_candidates
from core.llm import LLMRequest, LLMResponse, OpenAICompatClient, OpenAICompatConfig
from core.traffic.creative_generator import LLMCreativeGenerator


class _CreativeGateway:
    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content='{"headline":"Заголовок","primary_text":"Текст","cta":"Написать","interests":["healthcare"]}',
            raw={"provider": "test"},
        )

    async def generate(self, req: LLMRequest) -> LLMResponse:
        return self.generate_sync(req)


def test_llm_creative_generator_prefers_sync_gateway_without_asyncio_run() -> None:
    gen = LLMCreativeGenerator(llm=_CreativeGateway())
    creative = gen.build(what="стоматология", offer_title="Осмотр")
    assert creative.headline == "Заголовок"
    assert creative.primary_text == "Текст"


def test_creative_pipeline_marks_non_templated_responses_as_llm_even_without_raw_mode() -> None:
    out = generate_candidates(
        offer_arm="offer_a",
        business_type="Стоматология",
        offer_title="Осмотр",
        offer_details="Без боли",
        llm=_CreativeGateway(),
        n=1,
    )
    assert out[0].meta["gen"] == "llm"


def test_openai_compat_preserves_raw_payload_for_single_response_shape() -> None:
    client = OpenAICompatClient(
        OpenAICompatConfig(
            base_url="https://example.test/v1",
            api_key="secret",
            transport=lambda *args: {"output_text": "hi", "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
        )
    )
    resp = client.generate_sync(LLMRequest(messages=[], model="m"))
    assert resp.raw and resp.raw.get("output_text") == "hi"
    assert resp.text == "hi"


def test_ai_ceo_service_uses_canonical_step_shape_with_track_payload() -> None:
    steps = build_minimal_plan_steps(
        tenant_id="tenant-a",
        user_id="u1",
        snapshot=GrowthSnapshotV1(),
        intent=None,  # type: ignore[arg-type]
    )
    assert steps[0].payload["locale"] == "ru"
    assert steps[0].payload["channel"] == "telegram"
    assert steps[0].payload["track_payload"]["tenant_id"] == "tenant-a"
    assert steps[2].payload["track_payload"]["mode"] == "dry_run"


def test_world_snapshot_input_rewrites_placeholder_ids_to_unknowns() -> None:
    built = build_world_snapshot_input(payload={"tenant_id": "default", "business_id": "legacy"}, now_ms=1)
    assert built.tenant_id == "unknown_tenant"
    assert built.business_id == "unknown_business"
