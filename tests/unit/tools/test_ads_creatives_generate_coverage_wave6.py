from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from tools import ads_creatives_generate as tool


@dataclass(frozen=True)
class FakeCreative:
    creative_id: str
    headline: str
    primary_text: str
    description: str
    cta: str


@dataclass(frozen=True)
class FakeSelection:
    selected: FakeCreative
    scores: dict[str, float]
    reason: str


def test_ads_creatives_generate_main_prints_selected_json(monkeypatch, capsys) -> None:
    created_llms: list[object] = []

    class FakeLLM:
        def __init__(self) -> None:
            created_llms.append(self)

    def fake_generate_candidates(**kwargs: object) -> list[FakeCreative]:
        assert kwargs["offer_arm"] == "trial"
        assert kwargs["business_type"] == "clinic"
        assert kwargs["offer_title"] == "Audit"
        assert kwargs["offer_details"] == "Details"
        assert kwargs["city"] == "Amsterdam"
        assert kwargs["n"] == 2
        assert isinstance(kwargs["llm"], FakeLLM)
        return [
            FakeCreative(
                creative_id="creative-1",
                headline="Headline",
                primary_text="Primary",
                description="Description",
                cta="Book",
            )
        ]

    def fake_select_creative(*, candidates: list[FakeCreative]) -> FakeSelection:
        assert len(candidates) == 1
        return FakeSelection(
            selected=candidates[0],
            scores={"creative-1": 0.9},
            reason="best",
        )

    monkeypatch.setattr(tool, "TemplatedLLM", FakeLLM)
    monkeypatch.setattr(tool, "generate_candidates", fake_generate_candidates)
    monkeypatch.setattr(tool, "select_creative", fake_select_creative)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ads_creatives_generate",
            "--offer-arm",
            "trial",
            "--business-type",
            "clinic",
            "--offer-title",
            "Audit",
            "--offer-details",
            "Details",
            "--city",
            "Amsterdam",
            "--n",
            "2",
        ],
    )

    assert tool.main() == 0
    assert len(created_llms) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "selected": {
            "creative_id": "creative-1",
            "headline": "Headline",
            "primary_text": "Primary",
            "description": "Description",
            "cta": "Book",
        },
        "scores": {"creative-1": 0.9},
        "reason": "best",
    }
