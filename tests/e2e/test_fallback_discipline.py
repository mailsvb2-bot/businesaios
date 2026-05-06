from __future__ import annotations

import pytest

from runtime.audit_log import RuntimeAuditLog
from runtime.integration.fallback_policy import STRICT_FALLBACK_POLICY
from runtime.integration.missing_input_error import MissingIntegrationInputError
from runtime.integration.world_state_integration_service import WorldStateIntegrationService
from runtime.runtime_observability import RuntimeObservability


def test_strict_fallback_policy_rejects_missing_inputs() -> None:
    service = WorldStateIntegrationService(
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    with pytest.raises(MissingIntegrationInputError):
        service.build_packet(generated_at_ms=1, fallback_policy=STRICT_FALLBACK_POLICY)
