from __future__ import annotations

from execution.action_contracts import ActionSpec
import re

from execution.market_intelligence_action_specs import build_market_intelligence_action_specs
from execution.revenue_os_action_specs import build_revenue_os_action_specs

CANON_ACTION_CATALOG = True




def normalize_action_type(action_type: str) -> str:
    token = str(action_type or '').strip()
    if not token:
        return ''
    lowered = token.lower()
    if lowered.startswith('action_'):
        lowered = lowered[len('action_'):]
    lowered = re.sub(r'([_@])v\d+$', '', lowered)
    return lowered


_ACTION_SPECS: dict[str, ActionSpec] = {
    'execute_plan': ActionSpec(
        action_type='ACTION_EXECUTE_PLAN_V1',
        action_class='internal_execution',
        routable=False,
        executable=False,
        prod_ready=True,
        notes=(
            'plan token is consumed by the autonomy loop',
            'must never be treated as a direct external effector action',
        ),
    ),
    'archive_underperforming_ads': ActionSpec(
        action_type='archive_underperforming_ads',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('google ads contour is the primary ads effector path', 'production connector path is not proven prod-ready'),
    ),
    'create_experiment': ActionSpec(
        action_type='create_experiment',
        action_class='internal_execution',
        externally_verified=False,
        reversible=True,
        prod_ready=True,
        notes=('internal runner exists', 'verification is internal, not external'),
    ),
    'create_landing_page': ActionSpec(
        action_type='create_landing_page',
        action_class='seo_publish',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('seo runner path exists', 'website connector layer is not proven prod-ready'),
    ),
    'deploy_policy': ActionSpec(
        action_type='deploy_policy@v1',
        action_class='internal_execution',
        approval_required=True,
        bounded_by_blast_radius=True,
        prod_ready=True,
        notes=('self-driving deploy path exists', 'must remain under governance approval and runtime safety controls'),
    ),
    'create_listing': ActionSpec(
        action_type='create_listing',
        action_class='platform_listing_write',
        externally_verified=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('listing publication path exists', 'public surface should stay human-reviewed until prod hardening'),
    ),
    'launch_campaign': ActionSpec(
        action_type='launch_campaign',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('ads runner path exists', 'production connector path is not proven prod-ready'),
    ),
    'match_client_to_business': ActionSpec(
        action_type='match_client_to_business',
        action_class='marketplace_routing',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('marketplace routing path exists', 'connector layer is not proven prod-ready'),
    ),
    'notify_owner': ActionSpec(
        action_type='notify_owner',
        action_class='internal_execution',
        prod_ready=True,
        notes=('internal owner-notify runner exists',),
    ),
    'optimize_listing_rank': ActionSpec(
        action_type='optimize_listing_rank',
        action_class='platform_listing_write',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('platform runner path exists', 'publication surfaces remain non-prod-ready'),
    ),
    'pause_campaign': ActionSpec(
        action_type='pause_campaign',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('ads runner path exists', 'production connector path is not proven prod-ready'),
    ),
    'publish_article': ActionSpec(
        action_type='publish_article',
        action_class='seo_publish',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('seo runner path exists', 'website connector layer is not proven prod-ready'),
    ),
    'publish_business_profile': ActionSpec(
        action_type='publish_business_profile',
        action_class='profile_publish',
        externally_verified=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('public business profile publication exists', 'treat as externally visible strategic write'),
    ),
    'publish_service_page': ActionSpec(
        action_type='publish_service_page',
        action_class='seo_publish',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('seo runner path exists', 'website connector layer is not proven prod-ready'),
    ),
    'refresh_keyword_cluster': ActionSpec(
        action_type='refresh_keyword_cluster',
        action_class='seo_publish',
        bounded_by_blast_radius=True,
        notes=('seo runner path exists', 'verification is analytical rather than external'),
    ),
    'reply_to_inquiry': ActionSpec(
        action_type='reply_to_inquiry',
        action_class='communications_write',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('communications runner path exists', 'verification is heuristic rather than hard connector verify'),
    ),
    'request_review': ActionSpec(
        action_type='request_review',
        action_class='communications_write',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('communications runner path exists', 'verification is heuristic rather than hard connector verify'),
    ),
    'resume_campaign': ActionSpec(
        action_type='resume_campaign',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('ads runner path exists', 'production connector path is not proven prod-ready'),
    ),
    'rollback_action': ActionSpec(
        action_type='rollback_action',
        action_class='internal_execution',
        idempotent=True,
        reversible=True,
        prod_ready=True,
        notes=('internal rollback runner exists',),
    ),
    'rollback_policy': ActionSpec(
        action_type='rollback_policy@v1',
        action_class='internal_execution',
        approval_required=True,
        bounded_by_blast_radius=True,
        reversible=True,
        prod_ready=True,
        notes=('self-driving rollback path exists', 'must remain under governance approval and runtime safety controls'),
    ),
    'route_lead': ActionSpec(
        action_type='route_lead',
        action_class='marketplace_routing',
        externally_verified=False,
        approval_required=True,
        bounded_by_blast_radius=True,
        prod_ready=False,
        notes=('routing request assembly exists', 'no external routing connector+verify path is wired yet'),
    ),
    'send_message': ActionSpec(
        action_type='send_message@v1',
        action_class='communications_write',
        externally_verified=True,
        idempotent=True,
        bounded_by_blast_radius=True,
        prod_ready=False,
        notes=('runtime messaging action exists', 'communications connector verification path is available but not production-hardened'),
    ),
    'send_email': ActionSpec(
        action_type='send_email',
        action_class='communications_write',
        externally_verified=True,
        idempotent=True,
        bounded_by_blast_radius=True,
        prod_ready=False,
        notes=('email communications connector path exists', 'verification path is available but not production-hardened'),
    ),
    'update_audience': ActionSpec(
        action_type='update_audience',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('ads runner path exists', 'production connector path is not proven prod-ready'),
    ),
    'update_budget': ActionSpec(
        action_type='update_budget',
        action_class='budget_change',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('google ads contour is the primary budget-change effector path', 'production connector path is not proven prod-ready'),
    ),
    'update_creative': ActionSpec(
        action_type='update_creative',
        action_class='ads_write',
        externally_verified=True,
        reversible=True,
        approval_required=True,
        bounded_by_blast_radius=True,
        notes=('ads runner path exists', 'production connector path is not proven prod-ready'),
    ),
    'update_landing_page': ActionSpec(
        action_type='update_landing_page',
        action_class='seo_publish',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('seo runner path exists', 'website connector layer is not proven prod-ready'),
    ),
    'update_listing': ActionSpec(
        action_type='update_listing',
        action_class='platform_listing_write',
        externally_verified=True,
        bounded_by_blast_radius=True,
        notes=('platform runner path exists', 'publication surfaces remain non-prod-ready'),
    ),
}

_ACTION_SPECS.update(build_market_intelligence_action_specs())
_ACTION_SPECS.update(build_revenue_os_action_specs())


_UNKNOWN_SPEC = ActionSpec(
    action_type='unknown_action',
    action_class='unknown',
    decisionable=False,
    routable=False,
    executable=False,
    externally_verified=False,
    approval_required=True,
    bounded_by_blast_radius=True,
    prod_ready=False,
    notes=('unknown action type is not operationally trusted',),
)


_READ_ONLY_PREFIXES = ('read', 'fetch', 'list', 'get_')
_INTERNAL_PREFIXES = ('execute_plan', 'run_plan', 'execute_workflow', 'dispatch_runtime')


def classify_action_type(action_type: str) -> str:
    normalized = normalize_action_type(action_type)
    if normalized in _ACTION_SPECS:
        return _ACTION_SPECS[normalized].action_class
    if not normalized:
        return 'unknown'
    if normalized.startswith(_READ_ONLY_PREFIXES):
        return 'read_only'
    if normalized.startswith(_INTERNAL_PREFIXES):
        return 'internal_execution'
    return 'unknown'


def get_action_spec(action_type: str) -> ActionSpec:
    normalized = normalize_action_type(action_type)
    explicit = _ACTION_SPECS.get(normalized)
    if explicit is not None:
        return explicit
    action_class = classify_action_type(normalized)
    if action_class == 'read_only':
        return ActionSpec(
            action_type=str(action_type or '').strip(),
            action_class='read_only',
            externally_verified=False,
            idempotent=True,
            reversible=True,
            prod_ready=True,
            notes=('read-only actions are safe by default',),
        )
    if action_class == 'internal_execution':
        return ActionSpec(
            action_type=str(action_type or '').strip(),
            action_class='internal_execution',
            routable=False,
            executable=False,
            prod_ready=True,
            notes=('decision token only', 'not a direct external action runner'),
        )
    return ActionSpec(
            action_type=str(action_type or '').strip() or _UNKNOWN_SPEC.action_type,
            action_class='unknown',
            decisionable=False,
            routable=False,
            executable=False,
            externally_verified=False,
            idempotent=False,
            reversible=False,
            approval_required=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=_UNKNOWN_SPEC.notes,
        )


def known_action_types() -> tuple[str, ...]:
    return tuple(spec.action_type for spec in _ACTION_SPECS.values())


__all__ = [
    'CANON_ACTION_CATALOG',
    'ActionSpec',
    'classify_action_type',
    'get_action_spec',
    'known_action_types',
    'normalize_action_type',
]
