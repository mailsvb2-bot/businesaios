from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from collections.abc import Iterable, Mapping

from application.business_autonomy.provider_catalog import provider_map

CANON_INTEGRATION_CAPABILITY_CATALOG = True


class CapabilityStatus(str, Enum):
    PRODUCTION_READY = 'production_ready'
    IMPLEMENTED = 'implemented'
    PARTIAL = 'partial'
    CONTRACT_ONLY = 'contract_only'
    NOT_IMPLEMENTED = 'not_implemented'
    NOT_FOUND = 'not_found'


class CapabilitySurface(str, Enum):
    ACQUISITION = 'acquisition'
    INTERACTION = 'interaction'
    INFRASTRUCTURE = 'infrastructure'


_STATUS_RANK = {
    CapabilityStatus.PRODUCTION_READY: 5,
    CapabilityStatus.IMPLEMENTED: 4,
    CapabilityStatus.PARTIAL: 3,
    CapabilityStatus.CONTRACT_ONLY: 2,
    CapabilityStatus.NOT_IMPLEMENTED: 1,
    CapabilityStatus.NOT_FOUND: 0,
}


@dataclass(frozen=True)
class CapabilityEvidence:
    source: str
    claim: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        source = str(self.source or '').strip()
        claim = str(self.claim or '').strip()
        if not source:
            raise ValueError('capability evidence source is required')
        if not claim:
            raise ValueError('capability evidence claim is required')
        confidence = max(0.0, min(1.0, float(self.confidence)))
        object.__setattr__(self, 'source', source)
        object.__setattr__(self, 'claim', claim)
        object.__setattr__(self, 'confidence', confidence)

    def to_payload(self) -> dict[str, Any]:
        return {'source': self.source, 'claim': self.claim, 'confidence': self.confidence}


@dataclass(frozen=True)
class IntegrationCapability:
    capability_id: str
    title: str
    surface: CapabilitySurface
    group: str
    status: CapabilityStatus
    owner_text: str
    next_required_step: str
    provider_keys: tuple[str, ...] = ()
    registry_sources: tuple[str, ...] = ()
    read_supported: bool = False
    write_supported: bool = False
    verify_supported: bool = False
    production_ready: bool = False
    requires_owner_approval: bool = True
    requires_credentials: bool = False
    requires_webhook: bool = False
    requires_budget_guard: bool = False
    requires_consent: bool = False
    requires_admin_surface: bool = True
    risk_level: str = 'medium'
    evidence: tuple[CapabilityEvidence, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        capability_id = str(self.capability_id or '').strip()
        title = str(self.title or '').strip()
        if not capability_id:
            raise ValueError('capability_id is required')
        if not title:
            raise ValueError('capability title is required')
        provider_keys = tuple(str(item).strip() for item in self.provider_keys if str(item).strip())
        registry_sources = tuple(str(item).strip() for item in self.registry_sources if str(item).strip())
        status = CapabilityStatus(self.status)
        surface = CapabilitySurface(self.surface)
        production_ready = bool(self.production_ready or status is CapabilityStatus.PRODUCTION_READY)
        if production_ready and status not in (CapabilityStatus.PRODUCTION_READY, CapabilityStatus.IMPLEMENTED):
            raise ValueError(f'production_ready cannot be true for status={status.value}')
        object.__setattr__(self, 'capability_id', capability_id)
        object.__setattr__(self, 'title', title)
        object.__setattr__(self, 'provider_keys', provider_keys)
        object.__setattr__(self, 'registry_sources', registry_sources)
        object.__setattr__(self, 'status', status)
        object.__setattr__(self, 'surface', surface)
        object.__setattr__(self, 'production_ready', production_ready)
        object.__setattr__(self, 'metadata', dict(self.metadata or {}))

    @property
    def connectable(self) -> bool:
        return self.status in (
            CapabilityStatus.PRODUCTION_READY,
            CapabilityStatus.IMPLEMENTED,
            CapabilityStatus.PARTIAL,
        )

    @property
    def roadmap_only(self) -> bool:
        return not self.connectable

    def to_payload(self, *, active_provider_keys: Iterable[str] = ()) -> dict[str, Any]:
        active = {str(item).strip() for item in active_provider_keys if str(item).strip()}
        provider_rows = []
        providers = provider_map()
        for key in self.provider_keys:
            provider = providers.get(key)
            provider_rows.append(
                {
                    'provider_key': key,
                    'title': getattr(provider, 'title', key),
                    'connector_id': getattr(provider, 'connector_id', ''),
                    'channel_kind': getattr(provider, 'channel_kind', ''),
                    'connected': key in active,
                }
            )
        return {
            'id': self.capability_id,
            'title': self.title,
            'surface': self.surface.value,
            'group': self.group,
            'status': self.status.value,
            'connectable': self.connectable,
            'roadmap_only': self.roadmap_only,
            'owner_text': self.owner_text,
            'next_required_step': self.next_required_step,
            'read_supported': bool(self.read_supported),
            'write_supported': bool(self.write_supported),
            'verify_supported': bool(self.verify_supported),
            'production_ready': bool(self.production_ready),
            'requires_owner_approval': bool(self.requires_owner_approval),
            'requires_credentials': bool(self.requires_credentials),
            'requires_webhook': bool(self.requires_webhook),
            'requires_budget_guard': bool(self.requires_budget_guard),
            'requires_consent': bool(self.requires_consent),
            'requires_admin_surface': bool(self.requires_admin_surface),
            'risk_level': self.risk_level,
            'provider_keys': list(self.provider_keys),
            'providers': provider_rows,
            'registry_sources': list(self.registry_sources),
            'evidence': [item.to_payload() for item in self.evidence],
            'metadata': dict(self.metadata),
        }


def _e(source: str, claim: str, confidence: float = 1.0) -> CapabilityEvidence:
    return CapabilityEvidence(source=source, claim=claim, confidence=confidence)


CAPABILITIES: tuple[IntegrationCapability, ...] = (
    IntegrationCapability(
        capability_id='acquisition.website',
        title='Сайт / лендинг',
        surface=CapabilitySurface.ACQUISITION,
        group='Owned media',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('generic_website',),
        registry_sources=('application.business_autonomy.provider_catalog',),
        read_supported=True,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Есть provider для сайта и website surface, но нужен доказанный путь форма → лид → DecisionCore → действие → evidence.',
        next_required_step='Закрепить website lead schema, webhook verification, idempotency и evidence archive.',
        evidence=(_e('provider_catalog.generic_website', 'provider exists with website.site connector'),),
    ),
    IntegrationCapability(
        capability_id='acquisition.quiz_landing',
        title='Квиз-лендинги',
        surface=CapabilitySurface.ACQUISITION,
        group='Owned media',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='В коде не найден отдельный quiz lead connector; показывать как готовое подключение нельзя.',
        next_required_step='Добавить quiz lead contract, submit webhook, validation, dedupe и evidence.',
        evidence=(_e('code_audit', 'separate quiz landing connector was not found', 0.7),),
    ),
    IntegrationCapability(
        capability_id='acquisition.web_chat_widget',
        title='Чат-виджет',
        surface=CapabilitySurface.ACQUISITION,
        group='Owned media',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('generic_website',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Есть website/chatbot surface, но нужен полноценный channel adapter через единый Conversation Router.',
        next_required_step='Сделать webchat session, identity link, transcript evidence и каноничный inbound event.',
        evidence=(_e('website/chatbot surface', 'partial web chat surface exists', 0.75),),
    ),
    IntegrationCapability(
        capability_id='acquisition.google_ads',
        title='Google Ads',
        surface=CapabilitySurface.ACQUISITION,
        group='Paid ads',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('google_ads',),
        registry_sources=('application.business_autonomy.provider_catalog', 'connectors.platform.ads.registry'),
        read_supported=True,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_budget_guard=True,
        risk_level='high',
        owner_text='Provider есть; рекламный write-контур нельзя включать без spend guard, verification и rollback.',
        next_required_step='Оставить read-only до budget guard + campaign verification + human approval policy.',
        evidence=(
            _e('provider_catalog.google_ads', 'provider exists'),
            _e('ads registry audit', 'google ads is treated as not production-ready/read-oriented', 0.8),
        ),
    ),
    IntegrationCapability(
        capability_id='acquisition.meta_ads',
        title='Meta Ads',
        surface=CapabilitySurface.ACQUISITION,
        group='Paid ads',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('meta_ads',),
        registry_sources=('application.business_autonomy.provider_catalog', 'connectors.platform.ads.registry'),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_budget_guard=True,
        risk_level='high',
        owner_text='Provider заявлен, но рабочий ads adapter и e2e не доказаны.',
        next_required_step='Сделать auth, read metrics, campaign dry-run, spend guard и verification before write.',
        evidence=(_e('provider_catalog.meta_ads', 'provider exists'), _e('ads registry audit', 'implementation not proven', 0.8)),
    ),
    IntegrationCapability(
        capability_id='acquisition.tiktok_ads',
        title='TikTok Ads',
        surface=CapabilitySurface.ACQUISITION,
        group='Paid ads',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('tiktok_ads',),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_budget_guard=True,
        risk_level='high',
        owner_text='Provider заявлен, но реальный adapter/e2e не доказан.',
        next_required_step='Начать с read-only ingestion, затем spend guard и только потом write.',
        evidence=(_e('provider_catalog.tiktok_ads', 'provider exists'),),
    ),
    IntegrationCapability(
        capability_id='acquisition.telegram_ads',
        title='Telegram Ads',
        surface=CapabilitySurface.ACQUISITION,
        group='Paid ads',
        status=CapabilityStatus.NOT_IMPLEMENTED,
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_budget_guard=True,
        risk_level='high',
        owner_text='Telegram bot/runtime не равен Telegram Ads. Paid ads connector не доказан.',
        next_required_step='Развести telegram_bot messaging runtime и отдельный telegram_ads provider.',
        evidence=(_e('code_audit', 'telegram bot exists, telegram ads provider was not found', 0.85),),
    ),
    IntegrationCapability(
        capability_id='acquisition.seo_intelligence',
        title='SEO / search intelligence',
        surface=CapabilitySurface.ACQUISITION,
        group='Organic',
        status=CapabilityStatus.PARTIAL,
        read_supported=True,
        write_supported=False,
        verify_supported=False,
        risk_level='medium',
        owner_text='Market/search intelligence может помогать с аналитикой спроса, но это не полноценный acquisition connector.',
        next_required_step='Добавить real provider provenance, freshness, source evidence и lead attribution.',
        evidence=(_e('contracts/platforms/market_intelligence_provider_catalog.py', 'market intelligence catalog exists', 0.7),),
    ),
    IntegrationCapability(
        capability_id='acquisition.telegram_channel',
        title='Telegram-канал',
        surface=CapabilitySurface.ACQUISITION,
        group='Organic',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='Не найден отдельный acquisition connector для Telegram-канала; не путать с Telegram Bot.',
        next_required_step='Добавить post attribution, deeplink/UTM mapping и channel analytics ingestion.',
        evidence=(_e('code_audit', 'separate telegram channel acquisition connector was not found', 0.75),),
    ),
    IntegrationCapability(
        capability_id='acquisition.email_reactivation',
        title='Email-реактивация',
        surface=CapabilitySurface.ACQUISITION,
        group='Reactivation',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('email_connector',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='medium',
        owner_text='Email provider есть, но до production нужны consent, unsubscribe, bounce и delivery evidence.',
        next_required_step='Закрыть delivery receipts, bounce handling, unsubscribe policy и audit.',
        evidence=(_e('provider_catalog.email_connector', 'email provider exists with send_message operation'),),
    ),
    IntegrationCapability(
        capability_id='acquisition.sms_reactivation',
        title='SMS-реактивация',
        surface=CapabilitySurface.ACQUISITION,
        group='Reactivation',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('sms_connector',),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='high',
        owner_text='SMS provider заявлен, но рабочий коммуникационный contour/e2e не доказан.',
        next_required_step='Сделать SMS adapter, consent, delivery receipts и cost guard.',
        evidence=(_e('provider_catalog.sms_connector', 'sms provider exists'),),
    ),
    IntegrationCapability(
        capability_id='acquisition.whatsapp_reactivation',
        title='WhatsApp-реактивация',
        surface=CapabilitySurface.ACQUISITION,
        group='Reactivation',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('whatsapp_cloud',),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='high',
        owner_text='WhatsApp provider surface есть, но рабочий production contour не доказан.',
        next_required_step='Довести WhatsApp Cloud adapter, template approvals, consent и delivery evidence.',
        evidence=(_e('provider_catalog.whatsapp_cloud', 'whatsapp provider exists'),),
    ),
    IntegrationCapability(
        capability_id='acquisition.crm_reactivation',
        title='CRM-реактивация',
        surface=CapabilitySurface.ACQUISITION,
        group='Reactivation',
        status=CapabilityStatus.IMPLEMENTED,
        provider_keys=('hubspot',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='CRM-контуры выглядят одними из самых зрелых: HubSpot provider, CRM actions/webhooks/onboarding.',
        next_required_step='Доказать idempotent CRM event → DecisionCore → action → evidence.',
        evidence=(_e('provider_catalog.hubspot', 'hubspot provider exists'), _e('crm providers', 'crm contour exists', 0.8)),
    ),
    IntegrationCapability(
        capability_id='acquisition.referral_program',
        title='Referral program',
        surface=CapabilitySurface.ACQUISITION,
        group='Partnerships',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='Отдельный referral контур не найден; нельзя показывать как готовый канал.',
        next_required_step='Добавить referral attribution, reward policy, fraud guard и payout evidence.',
        evidence=(_e('code_audit', 'referral program implementation was not found', 0.7),),
    ),
    IntegrationCapability(
        capability_id='acquisition.commerce_marketplaces',
        title='Маркетплейсы / commerce',
        surface=CapabilitySurface.ACQUISITION,
        group='Commerce',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('shopify', 'woocommerce'),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Shopify/WooCommerce providers есть, но marketplace acquisition и commerce integration нужно разводить явно.',
        next_required_step='Разделить commerce catalog/order sync и marketplace lead acquisition capability.',
        evidence=(_e('provider_catalog.shopify', 'shopify provider exists'), _e('provider_catalog.woocommerce', 'woocommerce provider exists')),
    ),
    IntegrationCapability(
        capability_id='acquisition.inbound_api',
        title='Inbound API',
        surface=CapabilitySurface.ACQUISITION,
        group='API',
        status=CapabilityStatus.IMPLEMENTED,
        read_supported=True,
        write_supported=True,
        verify_supported=True,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='API/webhook surface есть и может быть честным каналом входящих событий при наличии auth/schema/idempotency.',
        next_required_step='Закрепить auth, schema validation, rate limit, idempotency и audit evidence.',
        evidence=(_e('app/web/pages/platform_control_center.py', 'control-plane webhook/API endpoints are surfaced', 0.8),),
    ),
    IntegrationCapability(
        capability_id='interaction.telegram',
        title='Telegram',
        surface=CapabilitySurface.INTERACTION,
        group='Messengers',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('telegram_bot',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Telegram bot/runtime контур есть, но его нужно сделать единой правдой для provider catalog, runtime и admin capability map.',
        next_required_step='Синхронизировать Telegram provider/runtime/admin registry и доказать webhook/polling e2e без второго transport brain.',
        evidence=(_e('provider_catalog.telegram_bot', 'telegram provider exists'), _e('boot/config telegram files', 'telegram runtime surfaces exist', 0.8)),
    ),
    IntegrationCapability(
        capability_id='interaction.whatsapp',
        title='WhatsApp',
        surface=CapabilitySurface.INTERACTION,
        group='Messengers',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('whatsapp_cloud',),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='high',
        owner_text='WhatsApp provider есть, но рабочий communication e2e не доказан.',
        next_required_step='Добавить WhatsApp Cloud adapter, template policy, consent и delivery receipts.',
        evidence=(_e('provider_catalog.whatsapp_cloud', 'whatsapp provider exists'),),
    ),
    IntegrationCapability(
        capability_id='interaction.instagram_direct',
        title='Instagram Direct',
        surface=CapabilitySurface.INTERACTION,
        group='Messengers',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='Отдельный Instagram Direct connector не найден в проверенных surfaces.',
        next_required_step='Добавить official API constraints, inbound/outbound adapter и Conversation Router binding.',
        evidence=(_e('code_audit', 'instagram direct connector was not found', 0.7),),
    ),
    IntegrationCapability(
        capability_id='interaction.facebook_messenger',
        title='Facebook Messenger',
        surface=CapabilitySurface.INTERACTION,
        group='Messengers',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='Отдельный Facebook Messenger connector не найден в проверенных surfaces.',
        next_required_step='Добавить Messenger adapter через canonical Conversation Router.',
        evidence=(_e('code_audit', 'facebook messenger connector was not found', 0.7),),
    ),
    IntegrationCapability(
        capability_id='interaction.email',
        title='Email',
        surface=CapabilitySurface.INTERACTION,
        group='Messaging',
        status=CapabilityStatus.IMPLEMENTED,
        provider_keys=('email_connector',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='medium',
        owner_text='Email provider есть и может быть рабочим каналом после production delivery/consent hardening.',
        next_required_step='Добавить unsubscribe, bounce handling, delivery receipts и audit.',
        evidence=(_e('provider_catalog.email_connector', 'email provider exists with send_message operation'),),
    ),
    IntegrationCapability(
        capability_id='interaction.sms',
        title='SMS',
        surface=CapabilitySurface.INTERACTION,
        group='Messaging',
        status=CapabilityStatus.CONTRACT_ONLY,
        provider_keys=('sms_connector',),
        read_supported=False,
        write_supported=False,
        verify_supported=False,
        requires_credentials=True,
        requires_consent=True,
        risk_level='high',
        owner_text='SMS provider есть, но communication runtime/e2e не доказан.',
        next_required_step='Добавить adapter, consent, delivery receipts и cost guard.',
        evidence=(_e('provider_catalog.sms_connector', 'sms provider exists'),),
    ),
    IntegrationCapability(
        capability_id='interaction.web_chat',
        title='Web chat',
        surface=CapabilitySurface.INTERACTION,
        group='Web',
        status=CapabilityStatus.PARTIAL,
        provider_keys=('generic_website',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Есть website/chatbot surface, но не доказан отдельный channel adapter.',
        next_required_step='Сделать webchat session, identity link, transcript evidence и Conversation Router binding.',
        evidence=(_e('website/chatbot surface', 'partial web chat surface exists', 0.75),),
    ),
    IntegrationCapability(
        capability_id='interaction.crm_events',
        title='CRM-события',
        surface=CapabilitySurface.INTERACTION,
        group='Business systems',
        status=CapabilityStatus.IMPLEMENTED,
        provider_keys=('hubspot',),
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='CRM events/actions/onboarding являются одним из самых полезных контуров взаимодействия с бизнес-системами.',
        next_required_step='Доказать canonical event → decision → action → evidence без параллельного решения.',
        evidence=(_e('provider_catalog.hubspot', 'hubspot provider exists'), _e('crm providers', 'crm contour exists', 0.8)),
    ),
    IntegrationCapability(
        capability_id='interaction.calendar',
        title='Календарь',
        surface=CapabilitySurface.INTERACTION,
        group='Business systems',
        status=CapabilityStatus.NOT_FOUND,
        owner_text='Отдельный calendar adapter не найден; нельзя обещать запись/переносы встреч.',
        next_required_step='Добавить calendar adapter, availability model, booking guard и evidence.',
        evidence=(_e('code_audit', 'calendar adapter was not found', 0.7),),
    ),
    IntegrationCapability(
        capability_id='interaction.payment_notifications',
        title='Платёжные уведомления',
        surface=CapabilitySurface.INTERACTION,
        group='Payments',
        status=CapabilityStatus.PARTIAL,
        read_supported=True,
        write_supported=True,
        verify_supported=False,
        requires_webhook=True,
        risk_level='high',
        owner_text='Платёжные события важны, но доступ/выдача продукта должны проходить через idempotency и evidence.',
        next_required_step='Доказать payment webhook → verification → access decision → evidence archive.',
        evidence=(_e('payment webhook contour', 'payment notification surface exists in project memory/code context', 0.65),),
    ),
    IntegrationCapability(
        capability_id='interaction.webhook_api',
        title='Webhook / API',
        surface=CapabilitySurface.INTERACTION,
        group='API',
        status=CapabilityStatus.IMPLEMENTED,
        read_supported=True,
        write_supported=True,
        verify_supported=True,
        requires_credentials=True,
        requires_webhook=True,
        risk_level='medium',
        owner_text='Control-plane/API webhook surface может быть честным интеграционным каналом.',
        next_required_step='Усилить auth, schema validation, rate limit, idempotency и audit.',
        evidence=(_e('app/web/pages/platform_control_center.py', 'control-plane API endpoints are surfaced', 0.8),),
    ),
)


def list_integration_capabilities(
    *,
    surface: CapabilitySurface | str | None = None,
    include_roadmap: bool = True,
) -> tuple[IntegrationCapability, ...]:
    selected = CAPABILITIES
    if surface is not None:
        wanted = CapabilitySurface(surface)
        selected = tuple(item for item in selected if item.surface is wanted)
    if not include_roadmap:
        selected = tuple(item for item in selected if item.connectable)
    return tuple(sorted(selected, key=lambda item: (item.surface.value, item.group, -_STATUS_RANK[item.status], item.title)))


def capability_map() -> dict[str, IntegrationCapability]:
    return {item.capability_id: item for item in CAPABILITIES}


def summarize_integration_capabilities(capabilities: Iterable[IntegrationCapability] | None = None) -> dict[str, Any]:
    rows = tuple(capabilities or CAPABILITIES)
    by_status = {status.value: 0 for status in CapabilityStatus}
    by_surface = {surface.value: 0 for surface in CapabilitySurface}
    for item in rows:
        by_status[item.status.value] += 1
        by_surface[item.surface.value] += 1
    return {
        'total': len(rows),
        'connectable': sum(1 for item in rows if item.connectable),
        'roadmap_only': sum(1 for item in rows if item.roadmap_only),
        'production_ready': by_status[CapabilityStatus.PRODUCTION_READY.value],
        'implemented': by_status[CapabilityStatus.IMPLEMENTED.value],
        'partial': by_status[CapabilityStatus.PARTIAL.value],
        'contract_only': by_status[CapabilityStatus.CONTRACT_ONLY.value],
        'not_implemented': by_status[CapabilityStatus.NOT_IMPLEMENTED.value],
        'not_found': by_status[CapabilityStatus.NOT_FOUND.value],
        'by_status': by_status,
        'by_surface': by_surface,
        'requires_budget_guard': sum(1 for item in rows if item.requires_budget_guard),
        'requires_consent': sum(1 for item in rows if item.requires_consent),
        'requires_credentials': sum(1 for item in rows if item.requires_credentials),
    }


def list_integration_capability_payloads(
    *,
    surface: CapabilitySurface | str | None = None,
    include_roadmap: bool = True,
    active_provider_keys: Iterable[str] = (),
) -> list[dict[str, Any]]:
    return [
        item.to_payload(active_provider_keys=active_provider_keys)
        for item in list_integration_capabilities(surface=surface, include_roadmap=include_roadmap)
    ]


__all__ = [
    'CANON_INTEGRATION_CAPABILITY_CATALOG',
    'CapabilityEvidence',
    'CapabilityStatus',
    'CapabilitySurface',
    'IntegrationCapability',
    'CAPABILITIES',
    'capability_map',
    'list_integration_capabilities',
    'list_integration_capability_payloads',
    'summarize_integration_capabilities',
]
