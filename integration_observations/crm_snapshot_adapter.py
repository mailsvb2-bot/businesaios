from __future__ import annotations

from collections.abc import Mapping as MappingABC
from datetime import UTC, datetime

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from integration_observations.contracts import ProviderObservationEnvelope

_BLOCKED_SECRET_KEYS = frozenset({
    'secretref', 'accesstoken', 'refreshtoken', 'authorization',
    'authorizationcode', 'clientsecret', 'apikey', 'password',
    'bearertoken', 'privatekey', 'sessiontoken', 'token',
    'xapikey', 'proxyauthorization', 'secret', 'secretkey',
    'webhooksecret', 'signingsecret', 'credential', 'credentials',
})


def _normalized_secret_key(key: object) -> str:
    return ''.join(ch for ch in str(key).casefold() if ch.isalnum())


class CrmSnapshotObservationAdapter:
    """Turns connector state into facts; never into recommendations/actions."""

    def from_connector(self, *, connector: CrmConnector, connection: CrmConnectionRef) -> ProviderObservationEnvelope:
        snapshot = dict(connector.build_snapshot(connection))
        return ProviderObservationEnvelope(
            tenant_id=connection.tenant_id,
            business_id=connection.business_id,
            provider_key=connection.provider_key,
            observation_type='crm.snapshot',
            observed_at=datetime.now(UTC),
            payload=self._sanitize(snapshot),
            metadata={'connection_id': connection.connection_id},
        )

    @classmethod
    def _sanitize_value(cls, value: object) -> object:
        if isinstance(value, MappingABC):
            return {
                str(key): cls._sanitize_value(nested)
                for key, nested in value.items()
                if _normalized_secret_key(key) not in _BLOCKED_SECRET_KEYS
            }
        if isinstance(value, list):
            return [cls._sanitize_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._sanitize_value(item) for item in value)
        if isinstance(value, set | frozenset):
            sanitized_items = [cls._sanitize_value(item) for item in value]
            return tuple(sorted(sanitized_items, key=repr))
        return value

    @classmethod
    def _sanitize(cls, payload: MappingABC[str, object]) -> dict[str, object]:
        sanitized = cls._sanitize_value(payload)
        if not isinstance(sanitized, dict):
            raise TypeError("sanitized CRM snapshot must remain a mapping")
        return sanitized
