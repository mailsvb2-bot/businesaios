from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from core.growth.ads.creative.models import CreativeCandidate, CreativeGuardrails
from core.growth.ads.creative.pipeline import (
    CreativePipeline,
    CreativePipelineConfig,
    _complete_creative_prompt,
    _extract_llm_text,
    _parse_labeled_line,
    _parse_llm_text,
    _response_generation_mode,
    _safe_fallback_candidate,
    _score_candidate,
    _stable_id,
    generate_candidates,
    select_creative,
)
from core.growth.ads.creative.prompting import CreativeBrief
from core.llm.agent import LLMTaskContext, TaskType


def _candidate(
    ident: str,
    *,
    headline: str = "Запись на встречу",
    primary: str = "Оставьте заявку на консультацию",
    description: str = "Без восклицаний",
) -> CreativeCandidate:
    return CreativeCandidate(
        creative_id=ident,
        offer_arm="arm",
        headline=headline,
        primary_text=primary,
        description=description,
    )


def test_stable_id_is_deterministic_and_input_sensitive() -> None:
    assert _stable_id("a", "b") == _stable_id("a", "b")
    assert _stable_id("a", "b") != _stable_id("a", "c")
    assert _stable_id("a", "b").startswith("cr_")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Headline: Value", ("headline", "Value")),
        ("- Primary — Value", ("primary", "Value")),
        ("* Description – Value", ("description", "Value")),
        ("1. CTA=book now", ("cta", "book now")),
        ("2) Headline - Numbered", ("headline", "Numbered")),
        ("Unknown: Value", None),
        ("Unlabeled line", None),
    ],
)
def test_parse_labeled_line_supports_common_provider_formats(
    line: str,
    expected: object,
) -> None:
    assert _parse_labeled_line(line) == expected


def test_parse_llm_text_uses_labeled_fields_and_normalizes_cta() -> None:
    parsed = _parse_llm_text(
        "\n".join(
            [
                "- Headline: Первая версия",
                "Primary — Текст для записи",
                "Description – Кратко",
                "CTA=book now",
            ]
        )
    )
    assert parsed == ("Первая версия", "Текст для записи", "Кратко", "Book Now")


def test_parse_llm_text_uses_only_unlabeled_lines_for_fallbacks_and_truncates() -> None:
    headline = "H" * 70
    primary_a = "P" * 120
    primary_b = "Q" * 120
    description = "D" * 100
    parsed = _parse_llm_text(
        "\n".join(
            [
                headline,
                primary_a,
                primary_b,
                description,
                "CTA: unsupported",
            ]
        )
    )
    assert parsed[0] == headline[:60]
    assert parsed[1] == f"{primary_a} {primary_b}"[:200]
    assert parsed[2] == description[:90]
    assert parsed[3] == "Learn More"


def test_parse_llm_text_handles_empty_and_single_unlabeled_line() -> None:
    assert _parse_llm_text("") == ("", "", "", "Learn More")
    assert _parse_llm_text("Only headline") == (
        "Only headline",
        "",
        "",
        "Learn More",
    )


def test_parse_llm_text_preserves_labeled_values_when_unlabeled_lines_exist() -> None:
    parsed = _parse_llm_text(
        "Headline: Labeled\nPrimary: Labeled primary\nDescription: Labeled desc\nextra"
    )
    assert parsed == ("Labeled", "Labeled primary", "Labeled desc", "Learn More")


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (SimpleNamespace(content=" content ", text="legacy"), " content "),
        (SimpleNamespace(content="   ", text="legacy"), "legacy"),
        (SimpleNamespace(content=None, text=""), ""),
        (SimpleNamespace(content=123, text=456), ""),
    ],
)
def test_extract_llm_text_uses_canonical_content_then_legacy_text(
    response: object,
    expected: str,
) -> None:
    assert _extract_llm_text(response) == expected


def test_response_generation_mode_honors_explicit_templated_marker() -> None:
    templated = SimpleNamespace(raw={"mode": " TEMPLATED "}, content="text")
    provider = SimpleNamespace(raw={"mode": "provider"}, content="text")
    empty = SimpleNamespace(raw=None, content="")
    assert _response_generation_mode(templated) == "templated"
    assert _response_generation_mode(provider) == "llm"
    assert _response_generation_mode(empty) == "templated"


def test_complete_creative_prompt_prefers_generate_sync_and_builds_canonical_request() -> None:
    captured: list[object] = []

    class Client:
        def generate_sync(self, req: object) -> object:
            captured.append(req)
            return "response"

        def complete(self, **kwargs: object) -> object:
            raise AssertionError(kwargs)

    result = _complete_creative_prompt(
        llm=Client(),
        brief=CreativeBrief("clinic", "offer", "details", "city"),
    )
    assert result == "response"
    req = captured[0]
    assert req.model == "ads-creative-fallback"
    assert req.temperature == 0.4
    assert req.max_tokens == 350
    assert req.metadata == {"surface": "ads_creative_generate"}
    assert [message.role for message in req.messages] == ["system", "user"]


def test_complete_creative_prompt_uses_legacy_complete_and_rejects_missing_surface() -> None:
    captured: list[dict[str, object]] = []

    class Legacy:
        def complete(self, **kwargs: object) -> str:
            captured.append(dict(kwargs))
            return "legacy"

    assert _complete_creative_prompt(
        llm=Legacy(),
        brief=CreativeBrief("b", "o", "d"),
    ) == "legacy"
    assert captured[0]["temperature"] == 0.4
    assert captured[0]["max_tokens"] == 350
    assert len(captured[0]["messages"]) == 2

    with pytest.raises(TypeError, match="creative_pipeline_requires"):
        _complete_creative_prompt(llm=object(), brief=CreativeBrief("b", "o", "d"))


def test_complete_creative_prompt_preserves_provider_failure() -> None:
    class Broken:
        def generate_sync(self, req: object) -> object:
            raise RuntimeError("provider-down")

    with pytest.raises(RuntimeError, match="provider-down"):
        _complete_creative_prompt(llm=Broken(), brief=CreativeBrief("b", "o", "d"))


def test_safe_fallback_preserves_safe_user_copy_and_replaces_unsafe_copy() -> None:
    guardrails = CreativeGuardrails()
    safe = _safe_fallback_candidate(
        offer_arm="arm",
        business_type="Клиника",
        offer_title="Специальная консультация",
        offer_details="Запишитесь на удобное время",
        guardrails=guardrails,
    )
    assert safe.headline == "Специальная консультация"
    assert safe.primary_text == "Запишитесь на удобное время"

    unsafe = _safe_fallback_candidate(
        offer_arm="arm",
        business_type="Клиника",
        offer_title="ЛУЧШИЙ В МИРЕ",
        offer_details="100% гарантия",
        guardrails=guardrails,
    )
    assert unsafe.headline == "Специальное предложение"
    assert unsafe.primary_text == (
        "Узнайте подробности и запишитесь на удобное время."
    )


def test_generate_candidates_returns_empty_for_nonpositive_count() -> None:
    assert generate_candidates(
        offer_arm="arm",
        business_type="b",
        offer_title="o",
        offer_details="d",
        n=0,
    ) == []
    assert generate_candidates(
        offer_arm="arm",
        business_type="b",
        offer_title="o",
        offer_details="d",
        n=-1,
    ) == []


def test_generate_candidates_accepts_safe_responses_filters_unsafe_and_tracks_modes() -> None:
    responses = iter(
        [
            SimpleNamespace(
                content=(
                    "Headline: Запись на встречу\n"
                    "Primary: Оставьте заявку\n"
                    "Description: Кратко\n"
                    "CTA: sign up"
                ),
                raw={"mode": "provider"},
            ),
            SimpleNamespace(
                content=(
                    "Headline: ВЫЛЕЧИМ ВСЕХ\n"
                    "Primary: Гарантированно вылечит\n"
                    "CTA: Book Now"
                ),
                raw={"mode": "templated"},
            ),
        ]
    )
    requests: list[object] = []

    class Client:
        def generate_sync(self, req: object) -> object:
            requests.append(req)
            return next(responses)

    result = generate_candidates(
        offer_arm="arm",
        business_type=" clinic ",
        offer_title=" offer ",
        offer_details=" details ",
        city=" city ",
        llm=Client(),
        n=2,
    )
    assert len(result) == 1
    assert result[0].cta == "Sign Up"
    assert result[0].meta == {"gen": "llm"}
    assert len(requests) == 2
    user_prompt = requests[0].messages[1].content
    assert "Business: clinic" in user_prompt
    assert "Offer: offer" in user_prompt
    assert "Details: details" in user_prompt
    assert "City: city" in user_prompt


def test_generate_candidates_whitespace_fallback_uses_business_and_safe_details() -> None:
    class EmptyClient:
        def generate_sync(self, req: object) -> object:
            return SimpleNamespace(content="", raw={"mode": "templated"})

    result = generate_candidates(
        offer_arm="arm",
        business_type="  Стоматология  ",
        offer_title="   ",
        offer_details="   ",
        city="  Москва ",
        llm=EmptyClient(),
        n=1,
    )
    assert len(result) == 1
    assert result[0].headline == "Стоматология"
    assert result[0].primary_text == (
        "Узнайте подробности и запишитесь на удобное время."
    )
    assert result[0].meta == {"gen": "fallback"}


def test_generate_candidates_default_templated_client_reaches_generic_fallback() -> None:
    result = generate_candidates(
        offer_arm="arm",
        business_type=" ",
        offer_title=" ",
        offer_details=" ",
        llm=None,
        n=1,
    )
    assert result[0].headline == "Специальное предложение"
    assert result[0].meta == {"gen": "fallback"}


def test_score_candidate_covers_all_heuristic_rules() -> None:
    strong = _candidate("strong")
    weak = _candidate(
        "weak",
        headline="short",
        primary="Нейтральный текст!",
        description="",
    )
    assert _score_candidate(strong) == pytest.approx(0.22)
    assert _score_candidate(weak, base=0.2) == pytest.approx(0.2)


def test_select_creative_requires_candidates_and_scores_valid_and_invalid() -> None:
    with pytest.raises(ValueError, match="creative_selection_requires_candidates"):
        select_creative(candidates=[])

    valid = _candidate("valid")
    invalid = _candidate("invalid", headline="ВЫЛЕЧИМ ВСЕХ")
    selection = select_creative(candidates=[invalid, valid])
    assert selection.selected is valid
    assert selection.scores["invalid"] == -1.0
    assert selection.scores["valid"] == pytest.approx(0.22)
    assert selection.guardrails_ok is True
    assert selection.reason == "heuristic_best"

    all_invalid = select_creative(candidates=[invalid])
    assert all_invalid.selected is invalid
    assert all_invalid.guardrails_ok is False


@dataclass
class _TaskResult:
    text: str
    json: dict[str, object]
    meta: dict[str, object]


def test_canonical_pipeline_facade_delegates_tasks_and_builds_ads_plan() -> None:
    calls: list[tuple[TaskType, object]] = []

    class Agent:
        def run_task(self, task: TaskType, ctx: object) -> _TaskResult:
            calls.append((task, ctx))
            if task is TaskType.ADS_PLAN_BUILD:
                return _TaskResult("plan", {"plan": ["step"]}, {"m": 3})
            return _TaskResult(task.value, {"k": task.value}, {"m": 1})

    built: list[tuple[str, dict[str, object]]] = []
    plan = object()

    class Ads:
        def build_plan(self, tenant_id: str, spec: dict[str, object]) -> object:
            built.append((tenant_id, spec))
            return plan

    ctx = LLMTaskContext(
        tenant_id="tenant",
        business={"name": "B"},
        audience={"segment": "A"},
        offer={"title": "O"},
    )
    pipeline = CreativePipeline(Agent(), Ads(), CreativePipelineConfig(max_variants=7))
    assert pipeline.generate_creatives(ctx) == {
        "text": "ads.creative.generate",
        "data": {"k": "ads.creative.generate"},
        "meta": {"m": 1},
    }
    assert pipeline.critique_creatives(ctx) == {
        "text": "ads.creative.critique",
        "data": {"k": "ads.creative.critique"},
        "meta": {"m": 1},
    }
    assert pipeline.build_ads_plan(ctx) is plan
    assert [task for task, _ in calls] == [
        TaskType.ADS_CREATIVE_GENERATE,
        TaskType.ADS_CREATIVE_CRITIQUE,
        TaskType.ADS_PLAN_BUILD,
    ]
    assert built == [
        (
            "tenant",
            {
                "plan": ["step"],
                "inputs": {
                    "business": {"name": "B"},
                    "audience": {"segment": "A"},
                    "offer": {"title": "O"},
                },
            },
        )
    ]
