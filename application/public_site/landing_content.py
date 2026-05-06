from __future__ import annotations

from typing import Any, Iterable

from application.business_autonomy.integration_capability_catalog import (
    CapabilitySurface,
    list_integration_capability_payloads,
    summarize_integration_capabilities,
)

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
    'CANON_PUBLIC_SITE_CONTENT',
    'PUBLIC_SITE_SECTION_ORDER',
    'build_landing_payload',
    'build_public_capabilities_payload',
]
