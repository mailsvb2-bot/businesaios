# runtime/guard

Role:
- validate execution envelopes and payloads
- enforce survival/idempotency/signature/action-contract laws
- fail closed before side-effects

Must NOT contain:
- action generation
- policy authorship
- direct business optimization logic
