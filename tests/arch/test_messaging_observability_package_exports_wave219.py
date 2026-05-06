from __future__ import annotations

import importlib

MODULE_EXPORT_EXPECTATIONS={
    'runtime.messaging_policy_alerts': {'MessagingPolicyAlertService'},
    'runtime.messaging_policy_alert_subscriptions': {'MessagingPolicyAlertSubscriptionService','SETTING_KEY'},
    'runtime.messaging_policy_alert_dedup_persistent': {'build_persistent_deduping_alert_notifier','build_persistent_alert_subscription_service'},
    'runtime.messaging_policy_readmodel': {'boot_messaging_policy_readmodel','read_messaging_policy_snapshot'},
    'interfaces.web.debug.messaging_policy_observability_nav': {'MessagingPolicyObservabilityNavRouteBundle'},
    'interfaces.web.debug.messaging_policy_snapshot': {'MessagingPolicySnapshotRouteBundle'},
}

def test_observability_packages_export_expected_surface():
    offenders=[]
    for mod_name, expected in MODULE_EXPORT_EXPECTATIONS.items():
        mod=importlib.import_module(mod_name)
        exported=set(getattr(mod,'__all__',()))
        missing=sorted(expected - exported)
        if missing:
            offenders.append(f'{mod_name}: missing {missing}')
    assert not offenders, offenders
