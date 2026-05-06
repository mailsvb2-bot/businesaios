# Secrets Never Cross The Decision Boundary

> NON-NORMATIVE DOCUMENT (Appendix).
> Canonical spec: docs/SYSTEM_TZ_CANONICAL.md


**Invariant (new system law):**

> SECRETS NEVER CROSS THE DECISION BOUNDARY

## Forbidden inside Decision Ring

The following layers must never have access to secrets:

- DecisionCore
- Policy
- ML
- WorldState
- Events
- Logs

Forbidden capabilities:

- SecretProvider implementations
- `.env` / environment secret access
- Vault clients
- tokens / API keys / private keys

## Allowed only in Secure Infra Layer

Secure Infra Layer may access secrets:

- SecretProvider implementation
- Payments clients
- External SDK clients

## Enforcement

1. **Release-blocking architectural test**
   - `tests/test_secret_isolation.py` blocks any `infra.secrets` usage in `core/`.

2. **Runtime secret guard**
   - `core/runtime/guards/secret_guard.py` prevents secret-like keys entering:
     - `DecisionCore.decide()` (via `validate_world_state`)
     - envelope creation params/world_state

3. **Log redaction helper**
   - `infrastructure/observability/redaction.py` provides `redact_dict()` for infra logging.
