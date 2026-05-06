from __future__ import annotations

from typing import Protocol, runtime_checkable

from demand_os.demand_os_health import DemandOsHealth
from runtime.service_names import RuntimeServiceName


@runtime_checkable
class DemandDecisionIssuerPort(Protocol):
    def issue(self, *args, **kwargs): ...


REQUIRED_COMPONENTS = (
    'demand_capture_service',
    'client_intent_builder',
    'business_live_state_builder',
    'business_directory',
    'match_engine',
    'demand_router',
    RuntimeServiceName.DECISION_CORE,
    'lead_delivery_dispatcher',
)

_METHOD_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    'demand_capture_service': ('capture',),
    'client_intent_builder': ('build',),
    'business_live_state_builder': ('build',),
    'business_directory': ('list_profiles',),
    'match_engine': ('build_bundle',),
    'demand_router': ('prepare',),
    'lead_delivery_dispatcher': ('dispatch',),
}
_DECISION_CORE_METHOD_ALTERNATIVES: tuple[str, ...] = ('issue', 'decide')


def _has_any_callable(component: object, methods: tuple[str, ...]) -> bool:
    return any(callable(getattr(component, method, None)) for method in methods)


def evaluate_readiness(components: dict[str, object]) -> DemandOsHealth:
    missing = [name for name in REQUIRED_COMPONENTS if components.get(name) is None]
    if missing:
        return DemandOsHealth(False, f"missing components: {', '.join(missing)}", tuple(missing))

    broken: list[str] = []
    for name, methods in _METHOD_REQUIREMENTS.items():
        component = components.get(name)
        for method in methods:
            if not callable(getattr(component, method, None)):
                broken.append(f'{name}.{method}')

    decision_core = components.get(RuntimeServiceName.DECISION_CORE)
    if decision_core is None:
        broken.append(f'{RuntimeServiceName.DECISION_CORE}.issue|decide')
    elif not _has_any_callable(decision_core, _DECISION_CORE_METHOD_ALTERNATIVES):
        broken.append(f'{RuntimeServiceName.DECISION_CORE}.issue|decide')

    if broken:
        return DemandOsHealth(False, f"broken components: {', '.join(broken)}", tuple(broken))
    return DemandOsHealth(True, 'ready', REQUIRED_COMPONENTS)
