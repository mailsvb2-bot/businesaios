from pathlib import Path

from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.guards import BusinessBlastRadiusGuard, BusinessBudgetGuard
from application.business_autonomy.non_ai_onboarding_mode import NonAiOperatingMode
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.operator_admin_plane import UnifiedOperatorAdminPlane
from application.business_autonomy.service import BusinessAutonomyService

TARGET_FILES = (
    'application/business_autonomy/service.py',
    'application/business_autonomy/registry.py',
    'application/business_autonomy/guards.py',
    'application/business_autonomy/onboarding_contract.py',
    'application/business_autonomy/non_ai_onboarding_mode.py',
    'application/business_autonomy/channel_backed_adapter.py',
    'application/business_autonomy/channel_adapter_registry.py',
)


def test_business_autonomy_surfaces_have_no_placeholder_passes() -> None:
    for rel in TARGET_FILES:
        text = Path(rel).read_text(encoding='utf-8')
        assert '\n    pass\n' not in text
        assert text.strip() != 'pass'


def test_business_autonomy_service_onboards_via_channel_registry() -> None:
    service = BusinessAutonomyService(
        channel_registry=TypedChannelAdapterRegistry(
            [ChannelBackedBusinessAdapter(adapter_name='telegram.default', channel_kind='telegram')]
        ),
        blast_radius_guard=BusinessBlastRadiusGuard(max_parallel_actions=1),
        budget_guard=BusinessBudgetGuard(max_budget_minor=0),
    )
    request = BusinessOnboardingRequest(
        business_id='biz-1',
        tenant_id='tenant-1',
        channel_kind='telegram',
        integration_mode='non_ai',
        metadata={'non_ai_mode': 'channel_driven', 'requested_budget_minor': 0, 'parallel_actions': 1},
        requested_capabilities=('messaging',),
    )

    result = service.onboard(request)

    assert result.business_id == 'biz-1'
    assert result.adapter_name == 'telegram.default'
    assert result.operating_mode == NonAiOperatingMode.CHANNEL_DRIVEN.value
    assert result.guard_decisions['blast_radius']['allowed'] is True
    assert service.registered_adapter('biz-1').adapter_name == 'telegram.default'
    assert service.registered_capabilities('biz-1').capabilities


def test_operator_admin_plane_without_read_model_is_honest() -> None:
    view = UnifiedOperatorAdminPlane().get_fleet_view()
    assert view.fleet_cards[0].value == '0'
    assert view.export_surface['status'] == 'not_configured'
    assert view.business_class_rows == ()
