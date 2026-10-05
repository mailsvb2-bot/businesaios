from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from contracts.landing_page import EventLandingContent, EventLandingFaq, EventLandingTheme


@dataclass(frozen=True, slots=True)
class EventLandingFacts:
    title: str
    description: str = ""
    timezone_name: str = "UTC"
    starts_at: tuple[datetime, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessLandingFacts:
    business_name: str = ""
    activity_description: str = ""
    confirmed_audiences: tuple[str, ...] = ()


def _sentences(value: object, *, maximum: int = 4) -> tuple[str, ...]:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ()
    parts = [p.strip(" •-—") for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip(" •-—")]
    return tuple((parts or [text])[:maximum])


def _schedule(facts: EventLandingFacts) -> tuple[str, ...]:
    if not facts.starts_at:
        return ()
    zone = ZoneInfo(facts.timezone_name)
    total = len(facts.starts_at)
    return tuple(
        (f"День {index}: " if total > 1 else "") + starts_at.astimezone(zone).strftime("%d.%m.%Y · %H:%M")
        for index, starts_at in enumerate(facts.starts_at, start=1)
    )


def build_event_landing_template(
    *,
    event: EventLandingFacts,
    business: BusinessLandingFacts = BusinessLandingFacts(),
) -> EventLandingContent:
    title = " ".join(event.title.split()).strip()
    if not title:
        raise ValueError("event title must not be empty")
    schedule = _schedule(event)
    description = " ".join(event.description.split()).strip()
    description_points = _sentences(description)
    audience = business.confirmed_audiences or (f"Тем, кому актуальна тема «{title}».",)
    outcomes = description_points or (f"Разобраться в теме «{title}» на онлайн-встрече.",)
    speaker = ". ".join(part for part in (business.business_name.strip(), business.activity_description.strip()) if part)
    when = schedule[0] if schedule else "Дата и время будут указаны организатором"
    return EventLandingContent(
        eyebrow=f"Онлайн-мероприятие · {when}",
        hero_title=title,
        hero_subtitle=description or when,
        audience_title="Для кого эта встреча",
        audience_points=tuple(audience[:6]),
        outcomes_title="Что будет полезного",
        outcome_points=tuple(outcomes[:6]),
        agenda_title="Расписание",
        agenda_points=tuple(schedule[:6]) or (when,),
        speaker_title="Организатор",
        speaker_text=speaker,
        faq_title="Частые вопросы",
        faq=(
            EventLandingFaq(question="Как зарегистрироваться?", answer="Заполните регистрационную форму мероприятия."),
            EventLandingFaq(question="Где будет ссылка на эфир?", answer="Используйте актуальную страницу участника или инструкции организатора."),
        ),
        cta_title="Зарегистрироваться",
        cta_text="Оставьте данные в канонической форме регистрации мероприятия.",
        theme=EventLandingTheme.CALM,
    )


def minimize_event_landing_ai_context(
    *,
    event: EventLandingFacts,
    business: BusinessLandingFacts,
    safe_template: EventLandingContent,
) -> dict[str, object]:
    return {
        "event": {
            "title": event.title,
            "description": event.description,
            "timezone_name": event.timezone_name,
            "schedule": list(_schedule(event)),
        },
        "business": {
            "name": business.business_name,
            "activity_description": business.activity_description,
            "confirmed_audiences": list(business.confirmed_audiences),
        },
        "current_safe_template": safe_template.to_payload(),
    }


__all__ = [
    "BusinessLandingFacts",
    "EventLandingFacts",
    "build_event_landing_template",
    "minimize_event_landing_ai_context",
]
