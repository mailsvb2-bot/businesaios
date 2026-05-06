from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_truth import connector_truth_payload


def test_connector_truth_payload_marks_stub_and_observability() -> None:
    payload = connector_truth_payload(
        connector_name='X',
        configured=False,
        capabilities=ConnectorCapabilities(),
        operation='read',
        dry_run=False,
        idempotency_key='abc',
        payload={'correlation_id': 'cid-1'},
    )
    assert payload['truth_layer']['stub'] is True
    assert payload['observability']['trace_id'] == 'cid-1'
    assert payload['idempotency_key'] == 'abc'
