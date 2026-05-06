from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from security.payload_redaction import PayloadRedactor


CANON_AUDIT_REDACTION_POLICY = True


@dataclass(frozen=True)
class AuditRedactionPolicy:
    allowed_top_level_fields: tuple[str, ...] = (
        'audit_id', 'tenant_id', 'event_type', 'category', 'severity', 'emitted_at',
        'actor_id', 'source_component', 'source_namespace', 'trace_id', 'run_id',
        'decision_id', 'action_id', 'correlation_id', 'subject_type', 'subject_id',
        'tags', 'payload', 'metadata',
    )
    allowed_header_fields: tuple[str, ...] = ('x-request-id', 'x-correlation-id', 'traceparent')
    drop_unknown_fields: bool = True
    payload_redactor: PayloadRedactor = field(default_factory=PayloadRedactor)

    def redact_event_dict(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        if self.drop_unknown_fields:
            allowed = set(self.allowed_top_level_fields)
            data = {key: value for key, value in data.items() if key in allowed}
        for field_name in ('payload', 'metadata'):
            if field_name in data:
                data[field_name] = self.payload_redactor.redact(data.get(field_name))
        return data

    def redact_headers(self, headers: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = {str(key).lower(): value for key, value in dict(headers or {}).items()}
        if self.drop_unknown_fields:
            normalized = {key: value for key, value in normalized.items() if key in set(self.allowed_header_fields)}
        redacted = self.payload_redactor.redact(normalized)
        return redacted if isinstance(redacted, dict) else {'payload': redacted}


__all__ = [
    'AuditRedactionPolicy',
    'CANON_AUDIT_REDACTION_POLICY',
]
