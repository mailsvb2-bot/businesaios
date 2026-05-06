from observability.inference_acceleration_log import InferenceAccelerationLog


def test_inference_acceleration_log_records_events():
    log = InferenceAccelerationLog()

    log.record(
        tenant_id='tenant-a',
        provider_name='local_gpu_provider',
        tier='local_gpu',
        execution_mode='accelerated',
        transport_kind='pci_local',
        batch_items=4,
        expected_transfer_overhead_ms=2,
    )

    event = log.list_events()[0]
    assert event.provider_name == 'local_gpu_provider'
    assert event.transport_kind == 'pci_local'
    assert event.batch_items == 4
