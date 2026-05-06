from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

CANON_RUNTIME_INTERNAL_ECONOMIC_EXECUTION_CONTRACT = True


@dataclass(frozen=True, slots=True)
class SealedEconomicExecutionContract:
    execution_kind: str
    status: str
    blockers: tuple[str, ...]
    lifecycle_stages: tuple[str, ...]
    idempotency_key: str
    transport_owner: str
    dispatch_owner: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "execution_kind": self.execution_kind,
            "status": self.status,
            "blockers": self.blockers,
            "lifecycle_stages": self.lifecycle_stages,
            "idempotency_key": self.idempotency_key,
            "transport_owner": self.transport_owner,
            "dispatch_owner": self.dispatch_owner,
            "payload": dict(self.payload),
        }

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)


def _dedupe(items: list[str]) -> tuple[str, ...]:
    out=[]
    for item in items:
        s=str(item).strip()
        if s and s not in out:
            out.append(s)
    return tuple(out)


def build_click_provider_dispatch_execution_contract(provider_dispatch: Mapping[str, Any] | None) -> SealedEconomicExecutionContract:
    payload = dict(provider_dispatch or {})
    inner = dict(payload.get("provider_dispatch") or {})
    blockers = list(payload.get('blockers') or ())
    stages = list(payload.get('lifecycle_stages') or ())
    invoice_id = str(payload.get('invoice_id') or inner.get('invoice_id') or '').strip()
    provider_name = str(payload.get('provider_name') or inner.get('provider_name') or '').strip()
    dispatch_owner = 'runtime._internal.effect_router'
    transport_owner = str(inner.get('transport_owner') or 'runtime._internal.http_transport')
    status='blocked'
    contract_payload={}
    if inner and invoice_id and provider_name:
        status='ready'
        stages.append('sealed_click_execution_contract_materialized')
        contract_payload = {
            'invoice_id': invoice_id,
            'provider_name': provider_name,
            'settled_amount_minor': int(payload.get('settled_amount_minor') or inner.get('settled_amount_minor') or 0),
            'operation': str(inner.get('operation') or 'collect'),
            'external_reference': str(inner.get('external_reference') or ''),
        }
    else:
        blockers.append('sealed_click_execution_contract_not_ready')
        stages.append('sealed_click_execution_contract_blocked')
    idem = str(inner.get('idempotency_key') or f'click-sealed-exec:{invoice_id or "unknown"}')
    return SealedEconomicExecutionContract(
        execution_kind='click_billing_provider_dispatch',
        status=status,
        blockers=_dedupe(blockers),
        lifecycle_stages=_dedupe(stages),
        idempotency_key=idem,
        transport_owner=transport_owner,
        dispatch_owner=dispatch_owner,
        payload=contract_payload,
    )


def build_spend_runtime_execution_contract(runtime_request: Mapping[str, Any] | None) -> SealedEconomicExecutionContract:
    payload = dict(runtime_request or {})
    inner = dict(payload.get('runtime_request') or {})
    blockers = list(payload.get('blockers') or ())
    stages = list(payload.get('lifecycle_stages') or ())
    batch_id = str(payload.get('batch_id') or inner.get('batch_id') or '').strip()
    dispatch_owner = 'runtime._internal.effect_router'
    transport_owner = str(inner.get('transport_owner') or 'runtime._internal.http_transport')
    status='blocked'
    contract_payload={}
    if inner and batch_id:
        status='ready'
        stages.append('sealed_spend_execution_contract_materialized')
        contract_payload = {
            'batch_id': batch_id,
            'amount_minor': int(payload.get('amount_minor') or inner.get('amount_minor') or 0),
            'currency': str(payload.get('currency') or inner.get('currency') or 'USD'),
            'manifest_hash': str(inner.get('manifest_hash') or ''),
            'source_channel': str(inner.get('source_channel') or ''),
            'source_kind': str(inner.get('source_kind') or ''),
        }
    else:
        blockers.append('sealed_spend_execution_contract_not_ready')
        stages.append('sealed_spend_execution_contract_blocked')
    idem = str(inner.get('idempotency_key') or f'spend-sealed-exec:{batch_id or "unknown"}')
    return SealedEconomicExecutionContract(
        execution_kind='spend_external_runtime_request',
        status=status,
        blockers=_dedupe(blockers),
        lifecycle_stages=_dedupe(stages),
        idempotency_key=idem,
        transport_owner=transport_owner,
        dispatch_owner=dispatch_owner,
        payload=contract_payload,
    )
