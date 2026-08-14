from __future__ import annotations

from collections.abc import Mapping, Sequence

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.state.crm_state_snapshot import CrmStateSnapshot

_COUNT_KEYS = (
    'pipeline_count',
    'contact_count',
    'deal_count',
    'open_deals',
    'won_deals_last_30d',
    'lost_deals_last_30d',
    'stalled_deals',
)


def _optional_count(snapshot: Mapping[str, object], key: str) -> tuple[int, bool]:
    raw = snapshot.get(key)
    if raw is None:
        return 0, False
    if isinstance(raw, bool):
        raise ValueError(f'CRM snapshot metric {key} must be a non-negative integer')
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f'CRM snapshot metric {key} must be a non-negative integer'
        ) from exc
    if value < 0:
        raise ValueError(f'CRM snapshot metric {key} must be a non-negative integer')
    return value, True


def _source_available(snapshot: Mapping[str, object]) -> bool:
    raw = snapshot.get('snapshot_available', True)
    if not isinstance(raw, bool):
        raise ValueError('CRM snapshot_available must be boolean')
    return raw


def _recent_activity(snapshot: Mapping[str, object]) -> tuple[object, ...]:
    raw = snapshot.get('recent_activity', ())
    if raw is None:
        return ()
    if isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
        return tuple(raw)
    raise ValueError('CRM recent_activity must be a sequence')


class CrmStateFeed:
    def fetch(self, connector: CrmConnector, connection: CrmConnectionRef) -> CrmStateSnapshot:
        raw_snapshot = connector.build_snapshot(connection)
        if not isinstance(raw_snapshot, Mapping):
            raise ValueError('CRM connector snapshot must be a mapping')

        snapshot = dict(raw_snapshot)
        source_available = _source_available(snapshot)
        values: dict[str, int] = {}
        metric_availability: dict[str, bool] = {}
        for key in _COUNT_KEYS:
            value, present = _optional_count(snapshot, key)
            values[key] = value if source_available else 0
            metric_availability[key] = bool(source_available and present)

        missing_metrics = tuple(
            key for key in _COUNT_KEYS if not metric_availability[key]
        )
        reason_raw = snapshot.get('reason')
        reason = str(reason_raw).strip() if reason_raw is not None else ''

        return CrmStateSnapshot(
            tenant_id=connection.tenant_id,
            business_id=connection.business_id,
            provider_key=connection.provider_key,
            open_deals=values['open_deals'],
            won_deals_last_30d=values['won_deals_last_30d'],
            lost_deals_last_30d=values['lost_deals_last_30d'],
            stalled_deals=values['stalled_deals'],
            metadata={
                'pipeline_count': values['pipeline_count'],
                'contact_count': values['contact_count'],
                'deal_count': values['deal_count'],
                'recent_activity': _recent_activity(snapshot),
                'snapshot_available': source_available,
                'snapshot_complete': source_available and not missing_metrics,
                'snapshot_reason': reason or None,
                'metric_availability': metric_availability,
                'missing_metrics': missing_metrics,
            },
        )
