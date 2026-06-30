from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeWebRoutedServices:
    messaging_preferences_bundle: Any = None
    alert_subscriptions_bundle: Any = None
    messaging_policy_snapshot_bundle: Any = None
    messaging_policy_trace_search_bundle: Any = None
    messaging_policy_dashboard_bundle: Any = None
    messaging_policy_alerts_bundle: Any = None
    messaging_policy_observability_nav_bundle: Any = None
    messaging_policy_trace_search_service: Any = None
    messaging_policy_dashboard_service: Any = None
    messaging_policy_alert_service: Any = None
    messaging_policy_alert_subscription_service: Any = None
    messaging_policy_alert_notifier_stack: Any = None
