from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from application.business_autonomy.integration_capability_catalog import (
    CAPABILITY_SCHEMA_VERSION,
    CapabilitySurface,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)
from contracts.landing_page import EventLandingContent, EventLandingFaq, EventLandingTheme

CANON_PUBLIC_SITE_CONTENT = True
PUBLIC_SITE_SECTION_ORDER = (
    'hero',
    'use_cases',
    'products',
    'capabilities',
    'canon_flow',
    'roadmap',
    'cta',
)

def _status_label(status: str) -> str:
    labels = {
        'production_ready': 'Готово',
        'implemented': 'Реализовано',
        'partial': 'Частично',
        'contract_only': 'Контракт',
        'not_implemented': 'Не реализовано',
        'not_found': 'Не найдено',
    }
    return labels.get(status, status)

def build_public_capabilities_payload(*, include_roadmap: bool = True) -> dict[str, Any]:
    capabilities = list_integration_capability_payloads(include_roadmap=include_roadmap)
    return {
        'source_of_truth': 'application.business_autonomy.integration_capability_catalog',
        'capabilities_schema_version': CAPABILITY_SCHEMA_VERSION,
        'include_roadmap': bool(include_roadmap),
        'summary': summarize_integration_capabilities(),
        'surfaces': {
            surface.value: list_integration_capability_payloads(surface=surface, include_roadmap=include_roadmap)
            for surface in CapabilitySurface
        },
        'capabilities': capabilities,
        'policy': {
            'roadmap_only_must_not_be_connectable': True,
            'public_site_must_not_hardcode_fake_channels': True,
            'budgeted_channels_require_spend_guard': True,
            'client_messaging_requires_consent': True,
            'write_actions_require_guarded_execution': True,
        },
    }

def _capability_cards(capabilities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in capabilities:
        cards.append(
            {
                'id': item['id'],
                'title': item['title'],
                'surface': item['surface'],
                'group': item['group'],
                'status': item['status'],
                'status_label': _status_label(item['status']),
                'connectable': bool(item['connectable']),
                'roadmap_only': bool(item['roadmap_only']),
                'owner_text': item['owner_text'],
                'next_required_step': item['next_required_step'],
                'risk_level': item['risk_level'],
                'requires_budget_guard': item['requires_budget_guard'],
                'requires_consent': item['requires_consent'],
                'requires_credentials': item['requires_credentials'],
                'requires_admin_surface': item['requires_admin_surface'],
                'evidence': item['evidence'],
            }
        )
    return cards

def build_landing_payload(*, include_roadmap: bool = True) -> dict[str, Any]:
    capability_payload = build_public_capabilities_payload(include_roadmap=include_roadmap)
    capability_cards = _capability_cards(capability_payload['capabilities'])
    return {
        'version': 'public_site.v1',
        'source_of_truth': 'application.public_site.landing_content',
        'sections_order': list(PUBLIC_SITE_SECTION_ORDER),
        'sections': {
            'hero': {
                'eyebrow': 'Business AI OS',
                'title': 'BusinesAIOS управляет продажами, рисками и повторными деньгами микробизнеса.',
                'subtitle': (
                    'Клиент приходит из канала, система собирает факты, DecisionCore выбирает безопасное действие, '
                    'а владелец подтверждает рискованные решения.'
                ),
                'canonical_flow': 'world_state → DecisionCore → guard → execution → verification → evidence',
            },
            'use_cases': [
                {'title': 'Автопилот продаж', 'text': 'Система связывает канал, оффер, оплату, риск и следующий шаг.'},
                {'title': 'Контроль владельца', 'text': 'Деньги, скидки, доступы и репутационные риски не выполняются вслепую.'},
                {'title': 'Единая воронка', 'text': 'Лиды, дозревание, потери, реактивация и повторные продажи собираются в один контур.'},
                {'title': 'Честные подключения', 'text': 'Каждый канал имеет статус готовности из backend capability catalog.'},
            ],
            'products': [
                {'name': 'Метротерапия', 'text': 'Заявки, оплаты, доступы, возвраты слетевших и контроль спорных действий.'},
                {'name': 'Школа гипноза', 'text': 'Офферы, дозревание, скидочные решения и реактивация старых лидов.'},
                {'name': 'Маркетплейс', 'text': 'Подбор специалистов, доверие, рейтинги и остановка рискованных действий.'},
            ],
            'capabilities': {
                'summary': capability_payload['summary'],
                'cards': capability_cards,
                'policy': capability_payload['policy'],
            },
            'canon_flow': [
                {'step': '01', 'title': 'World State', 'text': 'Система собирает факты.'},
                {'step': '02', 'title': 'DecisionCore', 'text': 'Единый центр выбирает действие.'},
                {'step': '03', 'title': 'Guard', 'text': 'Бюджеты, скидки, доступы и риски проходят проверки.'},
                {'step': '04', 'title': 'Execution', 'text': 'Действие выполняется через канонический исполнитель.'},
                {'step': '05', 'title': 'Evidence', 'text': 'Результат фиксируется в проверяемой истории.'},
            ],
            'roadmap': [
                {'title': 'Доказать живой e2e', 'text': 'Клиент → канал → DecisionCore → действие → проверка → evidence.'},
                {'title': 'Закрыть registry conflict', 'text': 'Telegram runtime/provider/registry должны говорить одно и то же.'},
                {'title': 'Довести Email и CRM', 'text': 'Это самые полезные контуры для дожима и реактивации.'},
                {'title': 'Рекламу держать read-only', 'text': 'Write-доступ только после spend guard, verification и rollback.'},
            ],
            'cta': {
                'title': 'Начать с одного доказанного живого контура.',
                'text': 'Не подключать всё подряд: сначала входящий клиент, решение, действие, проверка и evidence.',
            },
        },
        'capabilities': capability_payload,
    }

__all__ = [
    'CANON_PUBLIC_SITE_CONTENT', 'PUBLIC_SITE_SECTION_ORDER', 'build_landing_payload', 'build_public_capabilities_payload',
    'BusinessLandingFacts', 'EventLandingFacts', 'build_event_landing_template', 'minimize_event_landing_ai_context',
    'CANON_EVENT_LANDING_LIFECYCLE', 'EventLandingPublicationStatus', 'EventLandingState', 'new_event_landing_state',
]

@dataclass(frozen=True, slots=True)
class EventLandingFacts:
    title: str; description: str = ""; timezone_name: str = "UTC"; starts_at: tuple[datetime, ...] = ()

@dataclass(frozen=True, slots=True)
class BusinessLandingFacts:
    business_name: str = ""; activity_description: str = ""; confirmed_audiences: tuple[str, ...] = ()

def _sentences(value: object, *, maximum: int = 4) -> tuple[str, ...]:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ()
    parts = [p.strip(" •-—") for p in re.split(r"(?<=[.!?])\\s+|\\n+", text) if p.strip(" •-—")]
    return tuple((parts or [text])[:maximum])

def _schedule(facts: EventLandingFacts) -> tuple[str, ...]:
    if not facts.starts_at:
        return ()
    zone, total = ZoneInfo(facts.timezone_name), len(facts.starts_at)
    return tuple((f"День {i}: " if total > 1 else "") + dt.astimezone(zone).strftime("%d.%m.%Y · %H:%M")
                 for i, dt in enumerate(facts.starts_at, 1))

def build_event_landing_template(*, event: EventLandingFacts, business: BusinessLandingFacts = BusinessLandingFacts()) -> EventLandingContent:
    title = " ".join(event.title.split()).strip()
    if not title:
        raise ValueError("event title must not be empty")
    schedule, description = _schedule(event), " ".join(event.description.split()).strip()
    points = _sentences(description)
    audience = business.confirmed_audiences or (f"Тем, кому актуальна тема «{title}».",)
    outcomes = points or (f"Разобраться в теме «{title}» на онлайн-встрече.",)
    speaker = ". ".join(x for x in (business.business_name.strip(), business.activity_description.strip()) if x)
    when = schedule[0] if schedule else "Дата и время будут указаны организатором"
    return EventLandingContent(
        eyebrow=f"Онлайн-мероприятие · {when}", hero_title=title, hero_subtitle=description or when,
        audience_title="Для кого эта встреча", audience_points=tuple(audience[:6]),
        outcomes_title="Что будет полезного", outcome_points=tuple(outcomes[:6]),
        agenda_title="Расписание", agenda_points=tuple(schedule[:6]) or (when,),
        speaker_title="Организатор", speaker_text=speaker, faq_title="Частые вопросы",
        faq=(EventLandingFaq(question="Как зарегистрироваться?", answer="Заполните регистрационную форму мероприятия."),
             EventLandingFaq(question="Где будет ссылка на эфир?", answer="Используйте актуальную страницу участника или инструкции организатора.")),
        cta_title="Зарегистрироваться", cta_text="Оставьте данные в канонической форме регистрации мероприятия.",
        theme=EventLandingTheme.CALM,
    )

def minimize_event_landing_ai_context(*, event: EventLandingFacts, business: BusinessLandingFacts, safe_template: EventLandingContent) -> dict[str, object]:
    return {
        "event": {"title": event.title, "description": event.description, "timezone_name": event.timezone_name,
                  "schedule": list(_schedule(event))},
        "business": {"name": business.business_name, "activity_description": business.activity_description,
                     "confirmed_audiences": list(business.confirmed_audiences)},
        "current_safe_template": safe_template.to_payload(),
    }

CANON_EVENT_LANDING_LIFECYCLE = True

class EventLandingPublicationStatus(StrEnum):
    DRAFT, PUBLISHED = "draft", "published"

@dataclass(frozen=True, slots=True)
class EventLandingState:
    event_id: str; draft: EventLandingContent; draft_source: str
    revision: int = 1; status: EventLandingPublicationStatus = EventLandingPublicationStatus.DRAFT
    published_revision: int | None = None; published: EventLandingContent | None = None

    def __post_init__(self) -> None:
        event_id, source, revision = str(self.event_id or "").strip(), str(self.draft_source or "").strip(), int(self.revision)
        if not event_id or len(event_id) > 200: raise ValueError("event_id must be 1..200 characters")
        if source not in {"template", "manual", "ai"}: raise ValueError("draft_source must be template, manual or ai")
        if revision < 1: raise ValueError("revision must be >= 1")
        object.__setattr__(self, "event_id", event_id); object.__setattr__(self, "draft_source", source); object.__setattr__(self, "revision", revision)
        status = EventLandingPublicationStatus(self.status); object.__setattr__(self, "status", status)
        if self.published_revision is not None:
            published_revision = int(self.published_revision)
            if not 1 <= published_revision <= revision: raise ValueError("published_revision must be within the revision history")
            object.__setattr__(self, "published_revision", published_revision)
        if (self.published_revision is None) != (self.published is None): raise ValueError("published content and published_revision must exist together")
        if status is EventLandingPublicationStatus.PUBLISHED and self.published is None: raise ValueError("published status requires a published snapshot")

    @property
    def is_published(self) -> bool: return self.status is EventLandingPublicationStatus.PUBLISHED

    @property
    def has_unpublished_changes(self) -> bool: return self.published_revision is not None and self.published_revision != self.revision

    def preview(self) -> EventLandingContent: return self.draft

    def _checked(self, expected_revision: int) -> None:
        if isinstance(expected_revision, bool) or int(expected_revision) != self.revision: raise RuntimeError("event_landing_revision_conflict")

    def save_draft(self, *, content: EventLandingContent, source: str, expected_revision: int) -> "EventLandingState":
        self._checked(expected_revision)
        return replace(self, draft=content, draft_source=source, revision=self.revision + 1)

    def publish(self, *, expected_revision: int) -> "EventLandingState":
        self._checked(expected_revision)
        return replace(self, status=EventLandingPublicationStatus.PUBLISHED,
                       published_revision=self.revision, published=self.draft)

    def unpublish(self, *, expected_revision: int) -> "EventLandingState":
        self._checked(expected_revision)
        return replace(self, status=EventLandingPublicationStatus.DRAFT, published_revision=None, published=None)

    def public_content(self) -> EventLandingContent | None: return self.published if self.is_published else None

def new_event_landing_state(*, event_id: str, content: EventLandingContent, source: str = "template") -> EventLandingState:
    return EventLandingState(event_id=event_id, draft=content, draft_source=source)


# --- public event landing HTML (port of donor event_public_surface) ---
SECURITY_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                                "base-uri 'none'; frame-ancestors 'none'"),
}
_CHECK = "<label><input style='width:auto' type=checkbox"


def _marketing_block(advertiser_label: object | None) -> str:
    """Optional, channel-scoped commercial consent (text/hash from business_flows.event_consent)."""
    if not advertiser_label:
        return ""
    from html import escape

    from application.business_flows.event_consent import consent_text, text_sha256
    channels = (("email", "E-mail", " checked"), ("telegram", "Telegram", ""), ("vk", "ВКонтакте", ""), ("max", "MAX", ""))
    return ("<fieldset><legend>Полезные материалы и предложения (необязательно)</legend>"
            f"<input type=hidden name=marketing_consent_hash value='{escape(text_sha256(advertiser_label), quote=True)}'>"
            f"{_CHECK} name=marketing_consent value=yes> {escape(consent_text(advertiser_label))}</label>"
            "<p>Выберите каналы. E-mail подтверждается этой формой. Для Telegram, ВКонтакте и MAX после регистрации "
            "появится одноразовая кнопка: коммерческие сообщения в мессенджере включатся только после подтверждения "
            "владения аккаунтом.</p>"
            + " ".join(f"{_CHECK} name=marketing_channel value={v}{c}> {t}</label>" for v, t, c in channels)
            + "</fieldset>")


def _registration_form(slug: str, *, source: object, campaign_ref: object, advertiser_label: object | None,
                       enabled: bool = True) -> str:
    from html import escape
    from urllib.parse import quote

    if not enabled:
        return ("<section id=registration class='landing-registration'><fieldset disabled>"
                "<legend>Регистрация на мероприятие</legend><label>Имя</label><input value='Предпросмотр'>"
                "<label>E-mail</label><input value='preview@example.test'><label>Телефон (необязательно)</label><input>"
                f"{_CHECK} checked> Согласие на обработку данных</label></fieldset>"
                "<button type=button disabled>Зарегистрироваться</button>"
                "<p><small>В предпросмотре форма отключена и ничего не отправляет.</small></p></section>")
    action = escape(f"/e/{quote(slug, safe='')}/register", quote=True)
    return ("<section id=registration class='landing-registration'>"
            f"<form method=post action='{action}'><fieldset><legend>Регистрация на мероприятие</legend>"
            "<label>Имя</label><input name=name maxlength=120 required autocomplete=name>"
            "<label>E-mail</label><input name=email maxlength=320 type=email required autocomplete=email>"
            "<label>Телефон (необязательно)</label><input name=phone maxlength=40 autocomplete=tel>"
            "<div class=hp aria-hidden=true><input name=company tabindex=-1 autocomplete=off></div>"
            f"{_CHECK} name=consent value=yes required> Согласен на обработку данных для регистрации и получения "
            "организационных сообщений об этом мероприятии.</label></fieldset>"
            f"<input type=hidden name=source value='{escape(str(source or '').strip()[:160], quote=True)}'>"
            f"<input type=hidden name=campaign_ref value='{escape(str(campaign_ref or '').strip()[:240], quote=True)}'>"
            + _marketing_block(advertiser_label)
            + "<button type=submit>Зарегистрироваться</button></form></section>")


def _points(title: str, values: tuple[str, ...], *, css_class: str) -> str:
    from html import escape

    if not values:
        return ""
    items = "".join(f"<li>{escape(v)}</li>" for v in values)
    return (f"<section class='landing-section {escape(css_class, quote=True)}'>"
            f"<h2>{escape(title)}</h2><ul class=landing-points>{items}</ul></section>")


def _sales_landing(start_label: str, landing: EventLandingContent, form: str) -> str:
    from html import escape

    faq = ("<section class='landing-section landing-faq'>" f"<h2>{escape(landing.faq_title)}</h2>"
           + "".join(f"<details><summary>{escape(i.question)}</summary><p>{escape(i.answer)}</p></details>" for i in landing.faq)
           + "</section>") if landing.faq else ""
    speaker = ("<section class='landing-section landing-speaker'>"
               f"<h2>{escape(landing.speaker_title)}</h2><p>{escape(landing.speaker_text)}</p></section>"
               ) if landing.speaker_text else ""
    return (f"<div class='landing landing--{escape(landing.theme.value, quote=True)}'><section class=landing-hero>"
            + (f"<p class=landing-eyebrow>{escape(landing.eyebrow)}</p>" if landing.eyebrow else "")
            + f"<h1>{escape(landing.hero_title)}</h1>"
            + (f"<p class=landing-lead>{escape(landing.hero_subtitle)}</p>" if landing.hero_subtitle else "")
            + f"<p class=landing-date><b>{escape(start_label)}</b></p>"
            "<a class=landing-cta href='#registration'>Зарегистрироваться</a></section>"
            + _points(landing.audience_title, landing.audience_points, css_class="landing-audience")
            + _points(landing.outcomes_title, landing.outcome_points, css_class="landing-outcomes")
            + _points(landing.agenda_title, landing.agenda_points, css_class="landing-agenda")
            + speaker + faq
            + "<section class='landing-section landing-final-cta'>" f"<h2>{escape(landing.cta_title)}</h2>"
            + (f"<p>{escape(landing.cta_text)}</p>" if landing.cta_text else "") + "</section>" + form + "</div>")


def render_event_landing_body(*, slug: str, title: str, start_label: str, description: str = "",
                              source: object = "", campaign_ref: object = "", advertiser_label: object | None = None,
                              landing: EventLandingContent | None = None, registration_enabled: bool = True) -> str:
    """Escaped landing HTML; ``public_events.PubEvent.local_start_label()`` gives ``start_label``."""
    from html import escape

    form = _registration_form(slug, source=source, campaign_ref=campaign_ref, advertiser_label=advertiser_label,
                              enabled=registration_enabled)
    if landing is not None:
        return _sales_landing(start_label, landing, form)
    return f"<h1>{escape(title)}</h1><p>{escape(description)}</p><p><b>{escape(start_label)}</b></p>" + form
