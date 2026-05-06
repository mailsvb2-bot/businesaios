from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MessagingPolicyObservabilityBootFlags:
    navigation: bool = True
    snapshot: bool = True
    traces: bool = True
    dashboard: bool = True
    alerts: bool = True
    alert_subscriptions: bool = True
    messaging_preferences: bool = True


@dataclass(frozen=True)
class BootResultItem:
    key: str
    enabled: bool
    booted: bool


@dataclass(frozen=True)
class MessagingPolicyObservabilityBootResult:
    items: tuple[BootResultItem, ...]

    @property
    def booted_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.items if item.booted)


@dataclass(frozen=True)
class ObservabilityBootArgs:
    app: Any
    project_root: Path
    settings_gateway: Any
    messaging_policy_event_store: Any
    messaging_policy_read_service: Any


def run_boot_item(*, key: str, enabled: bool, fn: Callable[[], None]) -> BootResultItem:
    if not bool(enabled):
        return BootResultItem(key=str(key), enabled=False, booted=False)
    fn()
    return BootResultItem(key=str(key), enabled=True, booted=True)


def execute_observability_boot_plan(
    *,
    args: ObservabilityBootArgs,
    flags: MessagingPolicyObservabilityBootFlags | None,
    boot_navigation: Callable[..., None],
    boot_snapshot: Callable[..., None],
    boot_traces: Callable[..., None],
    boot_dashboard: Callable[..., None],
    boot_alerts: Callable[..., None],
    boot_alert_subscriptions: Callable[..., None],
    boot_messaging_preferences: Callable[..., None],
) -> MessagingPolicyObservabilityBootResult:
    f = flags or MessagingPolicyObservabilityBootFlags()
    items = []
    items.append(run_boot_item(key='navigation', enabled=f.navigation, fn=lambda: boot_navigation(app=args.app)))
    items.append(run_boot_item(key='snapshot', enabled=f.snapshot and args.messaging_policy_read_service is not None, fn=lambda: boot_snapshot(app=args.app, read_service=args.messaging_policy_read_service)))
    items.append(run_boot_item(key='traces', enabled=f.traces and args.messaging_policy_event_store is not None, fn=lambda: boot_traces(app=args.app, event_store=args.messaging_policy_event_store)))
    items.append(run_boot_item(key='dashboard', enabled=f.dashboard and args.messaging_policy_event_store is not None, fn=lambda: boot_dashboard(app=args.app, event_store=args.messaging_policy_event_store)))
    items.append(run_boot_item(key='alerts', enabled=f.alerts and args.messaging_policy_event_store is not None, fn=lambda: boot_alerts(app=args.app, event_store=args.messaging_policy_event_store)))
    items.append(run_boot_item(key='alert_subscriptions', enabled=f.alert_subscriptions and args.settings_gateway is not None, fn=lambda: boot_alert_subscriptions(app=args.app, project_root=args.project_root, settings_gateway=args.settings_gateway)))
    items.append(run_boot_item(key='messaging_preferences', enabled=f.messaging_preferences and args.settings_gateway is not None, fn=lambda: boot_messaging_preferences(app=args.app, project_root=args.project_root, settings_gateway=args.settings_gateway)))
    return MessagingPolicyObservabilityBootResult(items=tuple(items))


__all__ = [
    "MessagingPolicyObservabilityBootFlags",
    "BootResultItem",
    "MessagingPolicyObservabilityBootResult",
    "ObservabilityBootArgs",
    "run_boot_item",
    "execute_observability_boot_plan",
]
