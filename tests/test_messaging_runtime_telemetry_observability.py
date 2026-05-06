from interfaces.messaging_runtime.telemetry import RuntimeTelemetryFacade, InMemoryTelemetrySink, AuditTrailStore, RuntimeAnomalyHooks


def test_runtime_telemetry_records_timestamp_and_anomaly_snapshot() -> None:
    sink = InMemoryTelemetrySink()
    audit = AuditTrailStore()
    hooks = RuntimeAnomalyHooks()
    facade = RuntimeTelemetryFacade(sink=sink, audit_trail=audit, anomaly_hooks=hooks)

    facade.emit(
        event_name='delivery_transport_not_configured',
        correlation_id='c1',
        channel='sms',
        severity='error',
        component='dispatcher',
        payload={'status': 'transport_not_configured'},
    )

    snap = sink.snapshot()
    assert snap[0]['timestamp_ms'] > 0
    anomalies = hooks.snapshot()
    assert anomalies[0]['timestamp_ms'] > 0
    assert anomalies[0]['kind'] == 'runtime_error_event'
