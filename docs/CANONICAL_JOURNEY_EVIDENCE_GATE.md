# Canonical Journey Evidence Gate

This is a **read-only verification layer** over existing canonical BusinessAIOS owners. It does **not** create a second DecisionCore, outcome ledger, diagnostic owner or runtime execution path.

## What runs

The GitHub Actions workflow `.github/workflows/canonical-journey-evidence.yml` runs six existing integration/critical suites against the exact pull-request source SHA:

- Verified messaging ingress → canonical CRM lead, duplicate prevention and tenant isolation.
- Merchant settlement → invoice and verified access/reversal contracts.
- Stars and RUB provider separation, payment replay/restart behavior.
- Runtime executor recovery after crash windows.
- Capability health feedback into runtime decisions.
- World-model self-check integrity.

The gate evaluates actual JUnit testcases rather than treating a command's zero exit alone as evidence. Every named suite must contain at least one successful, non-skipped test; any errors, failures, skips or missing reports produce FAIL. It writes `artifacts/ci/journey-evidence/{junit.xml,verdict.json}` and uploads them even on failures.

## Evidence levels

The verdict is explicitly tagged `controlled_integration` and always sets `claims_production_ready=false`; passing never proves:
- Real Telegram/VK/MAX delivery to an external recipient.
- Real merchant settlement, bank confirmation, or live chargeback.
- An end customer's received service or business outcome in production.
- A million tenants, any specified RPS, or end-to-end latency SLO.

Those claims require separate, approved staging/live synthetic probes with dedicated test identities, no customer exposure, authoritative provider receipts, isolated payments, data minimization and outcome verification. Existing `scripts/server/production_synthetic_evidence.sh` checks production-host contracts and also explicitly does not certify the whole business journey.

## Existing diagnostics reused, not replaced

- `bootstrap/world_model_self_check.py` — canonical world-model integrity.
- `boot/self_check.py`, `runtime/boot/self_check.py` — boot wiring and DecisionCore contract.
- `application/capability/capability_diagnostics.py` — read-only capability verdict signals.
- `core/observability/perf_watchdog.py` — rolling latency budget and SLA events.
- `runtime/boot/storage_self_check.py` — production PostgreSQL requirement.
- Provider health/replay/queue and canonical recovery components remain under their existing owners.

This workflow aggregates test evidence only. It performs no repairs, external actions, or new business decisions.

## Remaining closure

1. After PR #504, add Telegram callback ingress → canonical DecisionCore → actual executor send outcome → next-turn observation coverage to this matrix.
2. Add live provider acknowledgement tests and a safe, tenant-isolated production synthetic scenario.
3. Prove a real onboarding → lead → service/order → verified settlement → outcome → subsequent decision journey.
4. Benchmark concurrency, p95/p99 end-to-end latency, queue lag, retries and cross-tenant isolation on a dedicated staging fleet.
5. Set `canonical-journey-evidence` as a required status check **only after the workflow passes on the exact integration head**.

The workflow is an additional gate, not a substitute for `full`, `release`, browser E2E or trusted production certification.

## Entry-point matrix extension

The CI integration evidence now also runs existing tests for VK/MAX messaging parity, WhatsApp signed webhook contracts, Slack and Discord inbound normalization, LINE/Viber transport foundation, SMS transport truth, Meta messenger outbound contracts, canonical multichannel registry/routing, CRM webhook ingestion, website/public site and headless acquisition/decision paths. These are **not all the same evidence level**: platform contracts and mocked inbound tests do not imply live-network readiness. All mapped suites must pass and report at least one real JUnit testcase.

This is intentionally a growing **cross-channel evidence matrix**, not yet exhaustive evidence of every externally reachable entry point. Full coverage additionally requires machine-generated route/connector inventory with drift detection, each provider's live readiness proof, and outcome attribution through DecisionCore/RuntimeExecutor. Avoid inferring production acceptance from generic route or provider contracts.
