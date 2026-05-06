from __future__ import annotations


class CrmAuditRedactionPolicy:
    def redact(self, payload: dict[str, object]) -> dict[str, object]:
        redacted = dict(payload)
        for key in ('access_token', 'refresh_token', 'authorization_code'):
            if key in redacted:
                redacted[key] = '***REDACTED***'
        return redacted
