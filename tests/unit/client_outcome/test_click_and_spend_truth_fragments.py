from __future__ import annotations

from click_economics.public_api import build_click_billable_fact_contract_from_client_outcome, build_click_billing_collection_preview_from_client_outcome, build_click_billing_execution_record_from_client_outcome, build_click_billing_handoff_payload_from_client_outcome, build_click_billing_invoice_preview_from_client_outcome, build_click_billing_provider_dispatch_from_client_outcome, build_click_billing_settlement_record_from_client_outcome, build_click_commercial_fact_from_client_outcome
from runtime.economic_core.click_economics_bridge import (
    build_click_economics_truth_fragment,
    build_click_economics_truth_snapshot_from_client_outcome,
)
from runtime.economic_core.spend_bridge import (
    build_spend_truth_fragment,
    build_spend_truth_snapshot_from_client_outcome,
)
from spend.public_api import build_spend_external_ingress_batch_from_client_outcome, build_spend_external_ingress_runtime_request_from_client_outcome, build_spend_fact_from_client_outcome, build_spend_ingress_envelope_from_client_outcome, build_spend_ingress_manifest_from_client_outcome, build_spend_manifest_from_client_outcome, build_spend_source_ingress_record_from_client_outcome
from runtime.executor import build_click_provider_dispatch_execution_contract, build_spend_runtime_execution_contract


def test_click_economics_owner_fact_and_fragment_project_existing_click_provenance_without_new_revenue_truth() -> None:
    fact = build_click_commercial_fact_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-click',
            'business_id': 'biz-click',
            'order_id': 'order-click',
            'source_channel': 'ads',
            'tracking_token': 'trk-click',
            'reconciliation_consistent': True,
        },
        lifecycle={
            'lead': {'click_id': 'clk-1', 'session_id': 'sess-1', 'source_channel': 'ads', 'tracking_token': 'trk-click'},
            'stages': {'lead_captured': {'payload': {'click_id': 'clk-1'}}},
        },
    )
    assert fact.billable_candidate is True
    snapshot = build_click_economics_truth_snapshot_from_client_outcome(
        truth_snapshot={
            'tenant_id': fact.tenant_id,
            'business_id': fact.business_id,
            'order_id': fact.entity_id,
            'source_channel': fact.source_channel,
            'tracking_token': fact.tracking_token,
            'reconciliation_consistent': True,
        },
        lifecycle={
            'lead': {'click_id': fact.click_id, 'session_id': fact.session_id, 'source_channel': fact.source_channel, 'tracking_token': fact.tracking_token},
            'stages': {'lead_captured': {'payload': {'click_id': fact.click_id}}},
        },
    )
    fragment = build_click_economics_truth_fragment(click_snapshot=snapshot)
    assert fragment.domain == 'click_economics'
    assert fragment.aggregation_mode == 'consistency_only'
    assert 'click_candidate_identified' in fragment.lifecycle_stages
    assert 'clk-1' in fragment.evidence_refs
    assert fragment.booked_amount_minor is None


def test_spend_owner_fact_and_fragment_become_the_single_cost_primary_surface() -> None:
    fact = build_spend_fact_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-spend',
            'business_id': 'biz-spend',
            'order_id': 'order-spend',
            'source_channel': 'ads',
            'tracking_token': 'trk-spend',
            'acquisition_cost': 20.0,
            'cac': 20.0,
            'reconciliation_consistent': True,
        }
    )
    assert fact.amount_minor == 2000
    snapshot = build_spend_truth_snapshot_from_client_outcome(
        truth_snapshot={
            'tenant_id': fact.tenant_id,
            'business_id': fact.business_id,
            'order_id': fact.entity_id,
            'source_channel': fact.source_channel,
            'tracking_token': 'trk-spend',
            'acquisition_cost': 20.0,
            'cac': 20.0,
            'reconciliation_consistent': True,
        }
    )
    fragment = build_spend_truth_fragment(spend_snapshot=snapshot)
    assert fragment.domain == 'spend'
    assert fragment.aggregation_mode == 'cost_primary'
    assert 'spend_fact_attached' in fragment.lifecycle_stages
    assert fragment.cost_total_minor == 2000
    assert fragment.corrected_amount_minor is None



def test_click_billable_fact_contract_requires_explicit_price_and_becomes_ready_when_present() -> None:
    empty = build_click_billable_fact_contract_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-click-bill',
            'business_id': 'biz-click-bill',
            'order_id': 'order-click-bill',
            'source_channel': 'ads',
            'tracking_token': 'trk-click-bill',
            'currency': 'USD',
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-bill', 'session_id': 'sess-bill', 'source_channel': 'ads', 'tracking_token': 'trk-click-bill'}},
    )
    assert empty is None
    ready = build_click_billable_fact_contract_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-click-bill',
            'business_id': 'biz-click-bill',
            'order_id': 'order-click-bill',
            'source_channel': 'ads',
            'tracking_token': 'trk-click-bill',
            'currency': 'USD',
            'click_price_minor': 450,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-bill', 'session_id': 'sess-bill', 'source_channel': 'ads', 'tracking_token': 'trk-click-bill'}},
    )
    assert ready is not None
    assert ready.amount_minor == 450
    assert ready.currency == 'USD'
    assert ready.domain == 'click_economics'



def test_click_handoff_payload_and_spend_manifest_use_existing_owner_truth_only() -> None:
    handoff = build_click_billing_handoff_payload_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-handoff',
            'business_id': 'biz-handoff',
            'order_id': 'order-handoff',
            'source_channel': 'ads',
            'tracking_token': 'trk-handoff',
            'currency': 'USD',
            'click_price_minor': 375,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-handoff', 'session_id': 'sess-handoff', 'source_channel': 'ads', 'tracking_token': 'trk-handoff'}},
    )
    assert handoff['handoff_ready'] is True
    assert handoff['handoff_contract']['amount_minor'] == 375
    manifest = build_spend_manifest_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-handoff',
            'business_id': 'biz-handoff',
            'order_id': 'order-handoff',
            'source_channel': 'ads',
            'tracking_token': 'trk-handoff',
            'acquisition_cost': 12.5,
            'cac': 12.5,
            'reconciliation_consistent': True,
        }
    )
    assert manifest['verified'] is True
    assert manifest['payload']['amount_minor'] == 1250


def test_click_billing_invoice_preview_and_spend_source_ingress_stay_owner_safe() -> None:
    preview = build_click_billing_invoice_preview_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-invoice',
            'business_id': 'biz-invoice',
            'order_id': 'order-invoice',
            'source_channel': 'ads',
            'tracking_token': 'trk-invoice',
            'currency': 'USD',
            'click_price_minor': 515,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-invoice', 'session_id': 'sess-invoice', 'source_channel': 'ads', 'tracking_token': 'trk-invoice'}},
    )
    assert preview.status == 'ready'
    assert preview.invoice_preview is not None
    assert preview.invoice_preview['total_minor'] == 515
    ingress = build_spend_source_ingress_record_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-ingress',
            'business_id': 'biz-ingress',
            'order_id': 'order-ingress',
            'source_channel': 'ads',
            'tracking_token': 'trk-ingress',
            'click_id': 'clk-ingress',
            'session_id': 'sess-ingress',
            'reconciliation_consistent': True,
        }
    )
    assert ingress.status == 'ready'
    assert 'traffic_linkage_bound' in ingress.lifecycle_stages


def test_click_billing_collection_preview_and_cross_domain_inputs_stay_owner_safe() -> None:
    preview = build_click_billing_collection_preview_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-collect',
            'business_id': 'biz-collect',
            'order_id': 'order-collect',
            'source_channel': 'ads',
            'tracking_token': 'trk-collect',
            'currency': 'USD',
            'click_price_minor': 640,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-collect', 'session_id': 'sess-collect', 'source_channel': 'ads', 'tracking_token': 'trk-collect'}},
    )
    assert preview.status == 'ready'
    assert preview.collection_preview is not None
    assert preview.collection_preview['collected_amount_minor'] == 640
    assert 'billing_collection_preview_built' in preview.lifecycle_stages



def test_click_billing_execution_and_spend_ingress_envelope_stay_owner_safe() -> None:
    execution = build_click_billing_execution_record_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-exec',
            'business_id': 'biz-exec',
            'order_id': 'order-exec',
            'source_channel': 'ads',
            'tracking_token': 'trk-exec',
            'currency': 'USD',
            'click_price_minor': 710,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-exec', 'session_id': 'sess-exec', 'source_channel': 'ads', 'tracking_token': 'trk-exec'}},
    )
    assert execution.status == 'executed'
    assert execution.execution_result is not None
    assert execution.collected_amount_minor == 710
    envelope = build_spend_ingress_envelope_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-exec',
            'business_id': 'biz-exec',
            'order_id': 'order-exec',
            'source_channel': 'ads',
            'tracking_token': 'trk-exec',
            'click_id': 'clk-exec',
            'session_id': 'sess-exec',
            'acquisition_cost': 17.5,
            'reconciliation_consistent': True,
        }
    )
    assert envelope.status == 'ready'
    assert envelope.amount_minor == 1750
    manifest = build_spend_ingress_manifest_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-exec',
            'business_id': 'biz-exec',
            'order_id': 'order-exec',
            'source_channel': 'ads',
            'tracking_token': 'trk-exec',
            'click_id': 'clk-exec',
            'session_id': 'sess-exec',
            'acquisition_cost': 17.5,
            'reconciliation_consistent': True,
        }
    )
    assert manifest['verified'] is True
    assert manifest['payload']['status'] == 'ready'



def test_click_billing_settlement_and_spend_external_ingress_stay_owner_safe() -> None:
    settlement = build_click_billing_settlement_record_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-settle', 'business_id': 'biz-settle', 'order_id': 'order-settle',
            'source_channel': 'ads', 'tracking_token': 'trk-settle', 'currency': 'USD', 'click_price_minor': 910, 'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-settle', 'session_id': 'sess-settle', 'source_channel': 'ads', 'tracking_token': 'trk-settle'}},
    )
    assert settlement.status == 'settled'
    assert settlement.settlement_result is not None
    assert settlement.settled_amount_minor == 910
    batch = build_spend_external_ingress_batch_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-settle', 'business_id': 'biz-settle', 'order_id': 'order-settle',
            'source_channel': 'ads', 'tracking_token': 'trk-settle', 'click_id': 'clk-settle', 'session_id': 'sess-settle',
            'acquisition_cost': 19.0, 'cac': 19.0, 'currency': 'USD', 'reconciliation_consistent': True,
        }
    )
    assert batch.status == 'ready'
    assert batch.batch_payload is not None
    assert batch.batch_payload['manifest_hash']



def test_click_provider_dispatch_and_spend_runtime_request_stay_owner_safe() -> None:
    dispatch = build_click_billing_provider_dispatch_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-dispatch', 'business_id': 'biz-dispatch', 'order_id': 'order-dispatch',
            'source_channel': 'ads', 'tracking_token': 'trk-dispatch', 'currency': 'USD', 'click_price_minor': 880,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-dispatch', 'session_id': 'sess-dispatch', 'source_channel': 'ads', 'tracking_token': 'trk-dispatch'}},
    )
    assert dispatch.status == 'ready'
    assert dispatch.provider_dispatch is not None
    assert dispatch.provider_dispatch['transport_owner'] == 'runtime._internal.http_transport'

    runtime_request = build_spend_external_ingress_runtime_request_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-runtime', 'business_id': 'biz-runtime', 'order_id': 'order-runtime',
            'source_channel': 'ads', 'tracking_token': 'trk-runtime', 'click_id': 'clk-runtime', 'session_id': 'sess-runtime',
            'acquisition_cost': 19.0, 'cac': 19.0, 'reconciliation_consistent': True,
        }
    )
    assert runtime_request.status == 'ready'
    assert runtime_request.runtime_request is not None
    assert runtime_request.runtime_request['transport_owner'] == 'runtime._internal.http_transport'


def test_sealed_execution_contracts_materialize_only_from_owner_safe_ready_payloads() -> None:
    dispatch = build_click_billing_provider_dispatch_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-sealed',
            'business_id': 'biz-sealed',
            'order_id': 'order-sealed',
            'source_channel': 'ads',
            'tracking_token': 'trk-sealed',
            'currency': 'USD',
            'click_price_minor': 700,
            'reconciliation_consistent': True,
        },
        lifecycle={'lead': {'click_id': 'clk-sealed', 'session_id': 'sess-sealed', 'source_channel': 'ads', 'tracking_token': 'trk-sealed'}},
    )
    click_contract = build_click_provider_dispatch_execution_contract({
        'invoice_id': dispatch.invoice_id,
        'provider_name': dispatch.provider_name,
        'settled_amount_minor': dispatch.settled_amount_minor,
        'blockers': dispatch.blockers,
        'lifecycle_stages': dispatch.lifecycle_stages,
        'provider_dispatch': dispatch.provider_dispatch,
    })
    assert click_contract['status'] == 'ready'
    assert click_contract['transport_owner'] == 'runtime._internal.http_transport'
    assert click_contract['dispatch_owner'] == 'runtime._internal.effect_router'

    runtime_request = build_spend_external_ingress_runtime_request_from_client_outcome(
        truth_snapshot={
            'tenant_id': 'tenant-sealed',
            'business_id': 'biz-sealed',
            'order_id': 'order-sealed',
            'source_channel': 'ads',
            'tracking_token': 'trk-sealed',
            'click_id': 'clk-sealed',
            'session_id': 'sess-sealed',
            'acquisition_cost': 20.0,
            'cac': 20.0,
            'reconciliation_consistent': True,
        }
    )
    spend_contract = build_spend_runtime_execution_contract({
        'batch_id': runtime_request.batch_id,
        'amount_minor': runtime_request.amount_minor,
        'currency': runtime_request.currency,
        'blockers': runtime_request.blockers,
        'lifecycle_stages': runtime_request.lifecycle_stages,
        'runtime_request': runtime_request.runtime_request,
    })
    assert spend_contract['status'] == 'ready'
    assert spend_contract['transport_owner'] == 'runtime._internal.http_transport'
    assert spend_contract['dispatch_owner'] == 'runtime._internal.effect_router'
