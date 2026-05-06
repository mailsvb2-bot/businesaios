from __future__ import annotations

from dataclasses import dataclass

from contracts.action_impact_contract import ActionCategory
from core.safety.operational.action_spec import ActionCostPolicy, ActionOperationalSpec
import execution.action_catalog as _action_catalog


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


def build_default_operational_action_registry() -> OperationalActionRegistry:
    specs = {name: _spec_from_action_catalog(name) for name in _action_catalog.known_action_types()}
    # Explicit non-runtime helper entries still allowed when consumed outside the decision loop.
    specs['read_metrics@v1'] = ActionOperationalSpec(
        action_name='read_metrics@v1',
        category=ActionCategory.SAFE_READ,
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
    'build_default_operational_action_registry',
]
