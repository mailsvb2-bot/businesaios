from __future__ import annotations

from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup_persistent.settings_key_builder import build_settings_key
from runtime.messaging_policy_alert_dedup_persistent.value_builder import build_dedup_value
from runtime.messaging_policy_alert_dedup_persistent.value_parser import parse_dedup_value
from runtime.tenancy import normalize_tenant_id


class PersistentAlertNotificationDedupStore:
    def __init__(self, *, settings_gateway, tenant_id: str):
        self._settings_gateway = settings_gateway
        self._tenant_id = normalize_tenant_id(tenant_id, fallback="unknown_tenant")

    def get(self, *, dedup_key: str) -> AlertNotificationDedupRecord | None:
        value = self._settings_gateway.get_value(
            tenant_id=self._tenant_id,
            key=build_settings_key(dedup_key=str(dedup_key)),
        )
        return parse_dedup_value(dedup_key=str(dedup_key), value=value)

    def put(self, record: AlertNotificationDedupRecord) -> None:
        self._settings_gateway.set_value(
            tenant_id=self._tenant_id,
            key=build_settings_key(dedup_key=str(record.dedup_key)),
            value=build_dedup_value(sent_at_epoch_s=int(record.sent_at_epoch_s)),
        )
