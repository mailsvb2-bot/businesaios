from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True)
class LandingPage:
    page_id: str = ''
    url: str = ''
    intent: str = ''


class EventLandingTheme(StrEnum):
    CALM = "calm"
    BOLD = "bold"
    MINIMAL = "minimal"


def _text(value: object, *, field: str, maximum: int, required: bool = False) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    if required and not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters")
    return normalized


def _items(value: object, *, field: str, limit: int = 6) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        source = [value]
    elif isinstance(value, (list, tuple)):
        source = list(value)
    else:
        raise ValueError(f"{field} must be a list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for raw in source:
        item = _text(raw, field=field, maximum=280)
        if not item:
            continue
        marker = item.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
        if len(result) > limit:
            raise ValueError(f"{field} must contain at most {limit} items")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class EventLandingFaq:
    question: str
    answer: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "question", _text(self.question, field="faq question", maximum=220, required=True))
        object.__setattr__(self, "answer", _text(self.answer, field="faq answer", maximum=700, required=True))

    def to_payload(self) -> dict[str, str]:
        return {"question": self.question, "answer": self.answer}

    @classmethod
    def from_payload(cls, payload: object) -> "EventLandingFaq":
        if not isinstance(payload, dict) or set(payload) != {"question", "answer"}:
            raise ValueError("event landing faq item must contain only question and answer")
        return cls(question=str(payload["question"]), answer=str(payload["answer"]))


@dataclass(frozen=True, slots=True)
class EventLandingContent:
    eyebrow: str
    hero_title: str
    hero_subtitle: str
    audience_title: str
    audience_points: tuple[str, ...]
    outcomes_title: str
    outcome_points: tuple[str, ...]
    agenda_title: str
    agenda_points: tuple[str, ...]
    speaker_title: str
    speaker_text: str
    faq_title: str
    faq: tuple[EventLandingFaq, ...]
    cta_title: str
    cta_text: str
    theme: EventLandingTheme = EventLandingTheme.CALM

    def __post_init__(self) -> None:
        object.__setattr__(self, "eyebrow", _text(self.eyebrow, field="eyebrow", maximum=120))
        object.__setattr__(self, "hero_title", _text(self.hero_title, field="hero title", maximum=180, required=True))
        object.__setattr__(self, "hero_subtitle", _text(self.hero_subtitle, field="hero subtitle", maximum=800))
        object.__setattr__(self, "audience_title", _text(self.audience_title, field="audience title", maximum=120, required=True))
        object.__setattr__(self, "audience_points", _items(self.audience_points, field="audience points"))
        object.__setattr__(self, "outcomes_title", _text(self.outcomes_title, field="outcomes title", maximum=120, required=True))
        object.__setattr__(self, "outcome_points", _items(self.outcome_points, field="outcome points"))
        object.__setattr__(self, "agenda_title", _text(self.agenda_title, field="agenda title", maximum=120, required=True))
        object.__setattr__(self, "agenda_points", _items(self.agenda_points, field="agenda points"))
        object.__setattr__(self, "speaker_title", _text(self.speaker_title, field="speaker title", maximum=120, required=True))
        object.__setattr__(self, "speaker_text", _text(self.speaker_text, field="speaker text", maximum=1200))
        object.__setattr__(self, "faq_title", _text(self.faq_title, field="faq title", maximum=120, required=True))
        faq = tuple(item if isinstance(item, EventLandingFaq) else EventLandingFaq.from_payload(item) for item in self.faq)
        if len(faq) > 6:
            raise ValueError("event landing faq must contain at most 6 items")
        object.__setattr__(self, "faq", faq)
        object.__setattr__(self, "cta_title", _text(self.cta_title, field="cta title", maximum=180, required=True))
        object.__setattr__(self, "cta_text", _text(self.cta_text, field="cta text", maximum=600))
        object.__setattr__(self, "theme", self.theme if isinstance(self.theme, EventLandingTheme) else EventLandingTheme(str(self.theme)))

    def to_payload(self) -> dict[str, Any]:
        return {
            "eyebrow": self.eyebrow,
            "hero_title": self.hero_title,
            "hero_subtitle": self.hero_subtitle,
            "audience_title": self.audience_title,
            "audience_points": list(self.audience_points),
            "outcomes_title": self.outcomes_title,
            "outcome_points": list(self.outcome_points),
            "agenda_title": self.agenda_title,
            "agenda_points": list(self.agenda_points),
            "speaker_title": self.speaker_title,
            "speaker_text": self.speaker_text,
            "faq_title": self.faq_title,
            "faq": [item.to_payload() for item in self.faq],
            "cta_title": self.cta_title,
            "cta_text": self.cta_text,
            "theme": self.theme.value,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "EventLandingContent":
        if not isinstance(payload, dict):
            raise ValueError("event landing content must be an object")
        expected = set(cls.__dataclass_fields__)
        unknown = set(payload) - expected
        if unknown:
            raise ValueError("event landing content has unsupported fields")
        missing = (expected - {"theme"}) - set(payload)
        if missing:
            raise ValueError("event landing content is missing required fields")
        return cls(
            eyebrow=payload["eyebrow"],
            hero_title=payload["hero_title"],
            hero_subtitle=payload["hero_subtitle"],
            audience_title=payload["audience_title"],
            audience_points=payload["audience_points"],
            outcomes_title=payload["outcomes_title"],
            outcome_points=payload["outcome_points"],
            agenda_title=payload["agenda_title"],
            agenda_points=payload["agenda_points"],
            speaker_title=payload["speaker_title"],
            speaker_text=payload["speaker_text"],
            faq_title=payload["faq_title"],
            faq=tuple(EventLandingFaq.from_payload(item) for item in payload["faq"]),
            cta_title=payload["cta_title"],
            cta_text=payload["cta_text"],
            theme=payload.get("theme", EventLandingTheme.CALM.value),
        )
