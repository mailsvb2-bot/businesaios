from __future__ import annotations

from dataclasses import dataclass

import execution.action_catalog as _action_catalog
from contracts.action_impact_contract import ActionCategory
from core.safety.operational.action_spec import ActionCostPolicy, ActionOperationalSpec

CANON_OPERATIONAL_ACTION_REGISTRY = True


@dataclass(frozen=True)
class OperationalActionRegistry:
    specs: dict[str, ActionOperationalSpec]

    def get(self, action_name: str) -> ActionOperationalSpec | None:
        return self.specs.get(str(action_name))

    def require(self, action_name: str) -> ActionOperationalSpec:
        spec = self.get(action_name)
        if spec is None:
            raise KeyError(f"unknown action spec: {action_name}")
        return spec


def _category_for_action_class(action_class: str) -> ActionCategory:
    normalized = str(action_class or '').strip()
    mapping = {
        'read_only': ActionCategory.SAFE_READ,
        'internal_execution': ActionCategory.INTERNAL_WRITE,
        'seo_publish': ActionCategory.PUBLICATION,
        'profile_publish': ActionCategory.PUBLICATION,
        'platform_listing_write': ActionCategory.PUBLICATION,
        'communications_write': ActionCategory.OUTBOUND,
        'budget_change': ActionCategory.BUDGET_CHANGE,
        'ads_write': ActionCategory.EXECUTION,
        'marketplace_routing': ActionCategory.EXECUTION,
    }
    return mapping.get(normalized, ActionCategory.UNKNOWN)


def _override_for_action(action_name: str) -> dict[str, object]:
    normalized = str(action_name or '').strip()
    overrides: dict[str, dict[str, object]] = {
        'create_listing': {'is_publication': True, 'publication_count': 1},
        'update_listing': {'is_publication': True, 'publication_count': 1},
        'optimize_listing_rank': {'is_publication': True, 'publication_count': 1},
        'publish_business_profile': {'is_publication': True, 'publication_count': 1, 'is_strategic': True},
        'create_landing_page': {'is_publication': True, 'publication_count': 1},
        'publish_article': {'is_publication': True, 'publication_count': 1},
        'publish_service_page': {'is_publication': True, 'publication_count': 1},
        'update_landing_page': {'is_publication': True, 'publication_count': 1},
        'refresh_keyword_cluster': {'is_publication': True, 'publication_count': 1},
        'reply_to_inquiry': {'is_outbound': True, 'outbound_count': 1, 'payload_outbound_count_key': 'recipient_count'},
        'request_review': {'is_outbound': True, 'outbound_count': 1, 'payload_outbound_count_key': 'recipient_count'},
        'send_email': {
            'is_outbound': True,
            'outbound_count': 1,
            'payload_outbound_count_key': 'recipient_count',
            'cost_policy': ActionCostPolicy(model='fixed_per_unit', payload_unit_count_key='recipient_count', unit_cost_minor=5),
        },
        'send_message@v1': {'is_outbound': True, 'outbound_count': 1, 'payload_outbound_count_key': 'recipient_count'},
        'update_budget': {
            'is_strategic': True,
            'cost_policy': ActionCostPolicy(model='payload_budget', payload_budget_key='budget_minor'),
        },
        'change_offer@v1': {'is_strategic': True, 'requires_human_approval': True},
        'change_pricing@v1': {'is_strategic': True, 'requires_human_approval': True},
        'rollback_action': {'is_rollback_event': True, 'rollback_event_count': 1},
        'rollback_campaign@v1': {'is_rollback_event': True, 'rollback_event_count': 1},
    }
    return dict(overrides.get(normalized, {}))


def _spec_from_action_catalog(action_name: str) -> ActionOperationalSpec:
    source = _action_catalog.get_action_spec(action_name)
    base = {
        'action_name': str(source.action_type),
        'category': _category_for_action_class(source.action_class),
        'requires_human_approval': bool(source.approval_required),
        'cost_policy': ActionCostPolicy(),
        'dimensions': {'action_class': str(source.action_class)},
    }
    base.update(_override_for_action(str(source.action_type)))
    spec = ActionOperationalSpec(**base)
    spec.validate()
    return spec


# Explicit descriptors for user-initiated Telegram actions. Each one only reads
# or writes the requesting user's own state (or replies to them), so no human
# approval is needed. Money, pricing, access, plan and LLM-cost actions are
# deliberately absent and stay fail-closed (approval required).
TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS: dict[str, ActionCategory] = {
    'admin_user_card@v1': ActionCategory.SAFE_READ,
    'growth_strategy_backlog@v1': ActionCategory.SAFE_READ,
    'answer_callback@v1': ActionCategory.OUTBOUND,
    'privacy_export@v1': ActionCategory.OUTBOUND,
    'business_ops_summary@v1': ActionCategory.OUTBOUND,
    'privacy_delete@v1': ActionCategory.OUTBOUND,
    'offer_ladder@v1': ActionCategory.OUTBOUND,
    'partners@v1': ActionCategory.OUTBOUND,
    'bookings@v1': ActionCategory.OUTBOUND,
    'bot_provisioning@v1': ActionCategory.OUTBOUND,
    'business_admin@v1': ActionCategory.OUTBOUND,
    'log_mood@v1': ActionCategory.INTERNAL_WRITE,
    'set_user_setting@v1': ActionCategory.INTERNAL_WRITE,
    'track_event@v1': ActionCategory.INTERNAL_WRITE,
    'emit_event@v1': ActionCategory.INTERNAL_WRITE,
    'poll_telegram_updates@v1': ActionCategory.INTERNAL_WRITE,
    'select_tariff@v1': ActionCategory.INTERNAL_WRITE,
    'request_pricing_change@v1': ActionCategory.INTERNAL_WRITE,
    'suggest_offer_patch@v1': ActionCategory.INTERNAL_WRITE,
    'growth_strategy_accept@v1': ActionCategory.INTERNAL_WRITE,
    'growth_strategy_reject@v1': ActionCategory.INTERNAL_WRITE,
    'profit_sprint_onboarding_start@v1': ActionCategory.INTERNAL_WRITE,
    'profit_sprint_onboarding_text@v1': ActionCategory.INTERNAL_WRITE,
    'profit_sprint_onboarding_lead_source@v1': ActionCategory.INTERNAL_WRITE,
}


# A reply to the user's own inbound update is bounded by inbound traffic, not by
# tenant autonomy, so it must not consume the tenant's autonomous action budget.
USER_REPLY_INTERACTION = 'user_reply'


def build_default_operational_action_registry() -> OperationalActionRegistry:
    specs = {name: _spec_from_action_catalog(name) for name in _action_catalog.known_action_types()}
    # Explicit non-runtime helper entries still allowed when consumed outside the decision loop.
    specs['read_metrics@v1'] = ActionOperationalSpec(
        action_name='read_metrics@v1',
        category=ActionCategory.SAFE_READ,
    )
    for name, category in TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS.items():
        specs[name] = ActionOperationalSpec(
            action_name=name,
            category=category,
            is_outbound=category is ActionCategory.OUTBOUND,
            outbound_count=1 if category is ActionCategory.OUTBOUND else 0,
            dimensions={'interaction': USER_REPLY_INTERACTION},
        )
    specs['publish_listing@v1'] = ActionOperationalSpec(
        action_name='publish_listing@v1',
        category=ActionCategory.PUBLICATION,
        is_publication=True,
        publication_count=1,
        payload_publication_count_key='publication_count',
        cost_policy=ActionCostPolicy(model='fixed', fixed_cost_minor=0),
    )
    specs['publish_landing_page@v1'] = ActionOperationalSpec(
        action_name='publish_landing_page@v1',
        category=ActionCategory.PUBLICATION,
        is_publication=True,
        publication_count=1,
        payload_publication_count_key='publication_count',
    )
    specs['send_email_outreach@v1'] = ActionOperationalSpec(
        action_name='send_email_outreach@v1',
        category=ActionCategory.OUTBOUND,
        is_outbound=True,
        outbound_count=1,
        payload_outbound_count_key='recipient_count',
        cost_policy=ActionCostPolicy(model='fixed_per_unit', payload_unit_count_key='recipient_count', unit_cost_minor=5),
    )
    specs['send_dm_outreach@v1'] = ActionOperationalSpec(
        action_name='send_dm_outreach@v1',
        category=ActionCategory.OUTBOUND,
        is_outbound=True,
        outbound_count=1,
        payload_outbound_count_key='recipient_count',
    )
    specs['set_campaign_budget@v1'] = ActionOperationalSpec(
        action_name='set_campaign_budget@v1',
        category=ActionCategory.BUDGET_CHANGE,
        is_strategic=True,
        requires_human_approval=True,
        cost_policy=ActionCostPolicy(model='payload_budget', payload_budget_key='budget_minor'),
    )
    specs['execute_paid_acquisition@v1'] = ActionOperationalSpec(
        action_name='execute_paid_acquisition@v1',
        category=ActionCategory.EXECUTION,
        cost_policy=ActionCostPolicy(model='payload_budget', payload_budget_key='budget_minor'),
    )
    specs['change_pricing@v1'] = ActionOperationalSpec(
        action_name='change_pricing@v1',
        category=ActionCategory.STRATEGIC_CHANGE,
        is_strategic=True,
        requires_human_approval=True,
        dimensions={'action_class': 'strategic_change'},
    )
    specs['change_offer@v1'] = ActionOperationalSpec(
        action_name='change_offer@v1',
        category=ActionCategory.STRATEGIC_CHANGE,
        is_strategic=True,
        requires_human_approval=True,
        dimensions={'action_class': 'strategic_change'},
    )
    return OperationalActionRegistry(specs=specs)


__all__ = [
    'OperationalActionRegistry',
    'TELEGRAM_INTERACTIVE_ACTION_DESCRIPTORS',
    'build_default_operational_action_registry',
]
