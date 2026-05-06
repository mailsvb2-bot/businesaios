from observability.action_audit_log import ActionAuditLog


def test_action_audit_log_records_inference_selection_and_verification():
    log = ActionAuditLog()
    log.record_inference_selection(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        capacity_tier='local_gpu',
        estimated_cost_usd=0.25,
    )
    log.record_inference_verification(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        accepted=True,
        verification_reason='accepted',
    )
    records = log.list_by_tenant(tenant_id='tenant-a')
    assert len(records) == 2
    assert records[0]['payload']['stage'] == 'inference.verification'
    assert records[1]['payload']['stage'] == 'inference.capacity_selection'
