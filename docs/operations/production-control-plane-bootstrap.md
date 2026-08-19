# Production control-plane credential lifecycle

This runbook defines the single canonical host lifecycle for the production control-plane credential, tenant runtime ownership, pricing-version binding, service restart/readiness, release-declared systemd profiles, and the existing post-deploy synthetic verdict.

## Security and ownership contract

- `SMOKE_TENANT_ID` must name an existing **active** record in the canonical persistent tenant registry.
- The same tenant must already have a persistent `TenantPolicyBundle`. Production runtime is a consumer of tenant registry/policy state and must never auto-create either surface during process startup.
- Historical tenant records or policy bundles that still live under `/opt/businesaios/data/tenancy` may be migrated only by the explicit one-time `scripts.server.migrate_legacy_tenancy_state` operator action. That migration is merge-only: canonical runtime records win for tenant IDs they already own, only missing tenant IDs are imported, and the preserved legacy files are never deleted or rewritten.
- Tenancy migration writes must run as the canonical runtime owner (`businesaios`), never as root. Atomic replacement creates a new inode as the calling user; the migration refuses a write when the process does not own the runtime tenancy directory and forces written surfaces to mode `0640`.
- Credential issuance uses `entrypoints.api.api_key_policy.PersistentApiKeyStore`; no second hashing or credential implementation is allowed.
- The application store persists `key_id`, the pepper-derived secret hash, tenant binding, roles/scopes and lifecycle metadata. It must never persist the plaintext credential.
- `API_CONTROL_PLANE_API_KEY_PEPPER` remains application-side secret material in the production environment.
- The only persistent plaintext copy of the issued credential is `CONTROL_PLANE_API_KEY` in `/etc/businesaios/api.env`.
- `PRICING_VERSION` is an explicit operator-approved business/governance version. It is supplied to the canonical host lifecycle and atomically bound into the same `/etc/businesaios/api.env`; strict production does not accept `PRICING_VERSION_OVERRIDE_PATH` as a fallback authority.
- The pricing fingerprint is mutable runtime evidence and must live under `/var/lib/businesaios/runtime`, normally `/var/lib/businesaios/runtime/governance/pricing_fingerprint.json`.
- Lifecycle-owned immutable runtime bindings are not a second operator configuration source. Missing or blank legacy-host values are overlaid in memory during preflight and atomically bound into the same environment cutover as the credential, smoke tenant and pricing version. A conflicting non-empty host value fails closed.
- The environment file is replaced atomically, preserves its owner/group and is forced to mode `0600`.
- The bootstrap never prints the credential. It reports only non-secret identifiers and the approved pricing version.
- A second bootstrap invocation rotates only a previous credential carrying this lifecycle's canonical metadata; unrelated credentials are not revoked.
- Privileged synthetic control-plane traffic must traverse the canonical public HTTPS ingress. Loopback HTTP remains valid only for local health/readiness probes.
- The API may trust `X-Forwarded-*` only from the local nginx peer: `BUSINESAIOS_TRUST_PROXY_HEADERS=true` with `BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128`.
- The systemd worker health surface is internal-only: `HEALTH_HOST=127.0.0.1`, `WORKER_HEALTH_PORT=8087`, `EVOLUTION_HEALTH_PORT=8087`, `EVOLUTION_ENABLED=1`. Port `8087` must never be intentionally exposed on `0.0.0.0` in canonical production.
- If the canonical Telegram polling connector is already enabled, it participates in the same environment cutover and readiness deadline; the lifecycle clears an old `start-limit-hit`, restarts it, and requires its loopback `/readyz` health surface to answer successfully.
- Optional systemd drop-ins are permitted only when the exact same path basename is declared under `deploy/systemd/dropins/<service>.d/` in the deployed release and the installed bytes match that exact SHA. Unknown or modified drop-ins fail closed. The Amsterdam Telegram egress profile is `deploy/systemd/dropins/businesaios-connector-telegram.service.d/20-amsterdam-egress.conf` and preserves the `wg-quick@wg-baios.service` dependency.
- Production verification must source credentials, tenant ID, PostgreSQL DSN and runtime bindings from `/etc/businesaios/api.env`; ambient shell values are not an accepted fallback after bootstrap.

## Preconditions

The target release must already be checked out at `/opt/businesaios`, its canonical virtualenv must exist, and `/etc/businesaios/api.env` must contain the production pepper, PostgreSQL settings, explicit persistent API-key path, canonical worker/TLS bindings, and any other secrets required by the release. The following lifecycle-owned immutable bindings are canonical:

```text
PRODUCTION_STRICT_MODE=1
DATA_DIR=/var/lib/businesaios/runtime
PRICING_FINGERPRINT_PATH=/var/lib/businesaios/runtime/governance/pricing_fingerprint.json
BUSINESAIOS_TENANT_REGISTRY_BACKEND=file
BUSINESAIOS_TENANT_REGISTRY_PATH=/var/lib/businesaios/runtime/tenancy/tenant_registry.json
BUSINESAIOS_TENANT_POLICY_STORE_BACKEND=file
BUSINESAIOS_TENANT_POLICY_STORE_PATH=/var/lib/businesaios/runtime/tenancy/tenant_policies.json
```

On a current host these values should already be present. On a historical host they may be missing or blank; the canonical lifecycle overlays only these exact values for preflight and writes them atomically during the credential/pricing cutover. Do **not** hand-edit them merely to make a release pass. Any non-empty value that disagrees with the canonical value is configuration drift and the lifecycle refuses the cutover.

The existing host must also satisfy:

```text
HEALTH_HOST=127.0.0.1
WORKER_HEALTH_PORT=8087
EVOLUTION_HEALTH_PORT=8087
EVOLUTION_ENABLED=1
PUBLIC_BASE_URL=https://api.businessaios.ru
BUSINESAIOS_TRUST_PROXY_HEADERS=true
BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128
```

`PRICING_VERSION` may be blank in the template or hold the previously approved value in the live environment. The next approved value is supplied explicitly to the lifecycle command below; the bootstrap replaces it atomically together with the credential, smoke tenant and immutable runtime bindings. Do not hand-edit it during a release and do not use an override file to bypass the production gate.

The selected tenant must already exist, be active, and have its persistent policy bundle in `/var/lib/businesaios/runtime/tenancy`. If an older deployment still has required business state only in `/opt/businesaios/data/tenancy`, inspect the migration first:

```bash
sudo runuser -u businesaios -- \
  /opt/businesaios/.venv/bin/python -m scripts.server.migrate_legacy_tenancy_state --check
```

The write form must run only in the coordinated deployment window when participating services are not concurrently mutating tenant state, and it must run as the runtime owner rather than root:

```bash
sudo runuser -u businesaios -- \
  /opt/businesaios/.venv/bin/python -m scripts.server.migrate_legacy_tenancy_state
```

The write command is intentionally idempotent for records that have already crossed the historical boundary and never overwrites a runtime-owned tenant ID. It is a deployment migration, not a runtime bootstrap convenience. The migration validates both registry and policy plans before the first write, refuses a process that does not own the runtime tenancy directory, and forces changed JSON files to mode `0640`.

The systemd units installed on the host must be byte-identical to the corresponding files in `deploy/systemd/` from the exact deployed SHA. The systemd manager must already have reloaded those files (`NeedDaemonReload=no`). Any active drop-in must likewise be declared in `deploy/systemd/dropins/<service>.d/` and be byte-identical to the deployed release. The lifecycle deliberately refuses environment mutation when installed units/drop-ins lag the release or include host-only overrides.

Nginx must terminate TLS for `PUBLIC_BASE_URL` and forward the original scheme to the local API. The verifier rejects a non-HTTPS public origin, rejects any trusted-proxy network wider than loopback, and rejects a worker health binding wider than loopback.

`EXPECTED_SHA` must be the exact 40-character SHA selected from trusted release evidence (normally the intended GitHub `main` commit) **before** the production host is changed. Do not derive `EXPECTED_SHA` from the current production checkout and do not persist it in `api.env`; otherwise a stale or unintended checkout could validate itself.

`PRICING_VERSION` must be the exact business/governance pricing version approved for this production cutover. It is intentionally independent from `EXPECTED_SHA`: deriving a pricing version automatically from a code SHA would hide the required explicit business decision when pricing-relevant configuration changes.

## Canonical command

After the canonical deployment has placed the intended release at `/opt/businesaios`, migrated any required historical tenancy state and installed the release's systemd units/profiles, run exactly one host lifecycle with the externally selected release SHA, existing production tenant, and approved pricing version:

```bash
sudo env \
  EXPECTED_SHA="<exact-40-character-github-main-sha>" \
  SMOKE_TENANT_ID="<existing-active-production-tenant>" \
  PRICING_VERSION="<approved-production-pricing-version>" \
  bash /opt/businesaios/scripts/server/bootstrap_and_verify_production.sh
```

Before running it, the operator must verify both trusted inputs: `<exact-40-character-github-main-sha>` is the release approved for deployment and `<approved-production-pricing-version>` is the pricing version approved for the effective pricing configuration. The lifecycle independently compares `EXPECTED_SHA` with `/opt/businesaios` `HEAD` before mutating the environment.

Do not generate a control-plane token manually, write an unhashed token into the application key store, use `default-business`, derive `EXPECTED_SHA` from the production host being verified, derive `PRICING_VERSION` from the deployed SHA, use `PRICING_VERSION_OVERRIDE_PATH` as a production fallback, let runtime auto-create a production tenant/policy, replace runtime-owned tenant state from a legacy checkout, run the tenancy write migration as root, inject an ad-hoc `SMOKE_BASE_URL`, widen trusted proxy networks, widen the worker health bind, add host-only systemd drop-ins, or invoke a separate smoke verifier.

## What the lifecycle proves

`bootstrap_and_verify_production.sh` first refuses mutation unless the deployed SHA exactly equals the externally supplied `EXPECTED_SHA`. Before credential/environment mutation it overlays only lifecycle-owned immutable bindings, rejects conflicts, validates the canonical HTTPS boundary, PostgreSQL presence, loopback-only worker bindings, canonical pricing-fingerprint location, and persistent tenant-registry/policy surfaces. It proves the selected tenant is active and already has a policy bundle. It also verifies that the effective installed systemd configuration for core services and any enabled canonical Telegram connector is exact release state: no stale daemon state, byte-identical unit fragments, and only byte-identical release-declared drop-ins.

It then calls `bootstrap_production_control_plane.py`, which validates the active tenant and persistent credential/tenant stores, validates the explicit pricing version with the same pricing-governance contract used by runtime, issues an OWNER service credential through the application API-key store, proves the plaintext is absent from that store, and atomically writes the new credential, `SMOKE_TENANT_ID`, approved `PRICING_VERSION`, and lifecycle-owned immutable runtime bindings into `/etc/businesaios/api.env`.

The API and worker services are restarted together so both processes execute the deployed release and read the newly bound environment. If the canonical Telegram polling connector is enabled, an old systemd failure counter is cleared and that connector is restarted in the same cutover. The lifecycle then waits, fail-closed and under one 60-second wall-clock deadline, until API `/health` + `/readyz`, worker `/health` + `/ready`, and enabled Telegram `/readyz` all answer successfully; `systemd` reporting a process merely `active` is not sufficient.

The existing canonical `verify_runtime_host_contract.sh` remains the sole post-deploy verifier. Local core health/readiness/runtime checks stay on loopback HTTP, while the privileged authenticated synthetic action and audit flow is forced through `PUBLIC_BASE_URL` over HTTPS. The verifier executes the SHA-bound chain:

`health -> readiness -> runtime -> PostgreSQL -> authenticated synthetic action over HTTPS -> action audit -> exact SHA verdict`

A PASS verdict is written only by that verifier under `PRODUCTION_VERDICT_DIR`; its filename and payload are bound to `EXPECTED_SHA`.

## Failure behavior

Failures before the environment replacement leave the previous plaintext environment unchanged. A candidate API key issued during an unsuccessful atomic cutover is revoked. Unknown, suspended or disabled tenants, missing tenant policies, missing pepper, memory-backed security/tenant stores, invalid or conflicting immutable runtime bindings, relative production store paths, invalid/placeholder pricing versions, a pricing fingerprint outside the canonical runtime StateDirectory, duplicate environment assignments, a symlinked environment file, an unsafe default tenant, a non-HTTPS `PUBLIC_BASE_URL`, disabled proxy trust, trusted proxy networks wider than loopback, worker health bindings wider than loopback, missing PostgreSQL configuration, stale systemd daemon state, undeclared or modified systemd drop-ins, or installed participating units that do not match the deployed SHA all fail closed.

If API, worker, or an enabled Telegram connector does not become genuinely healthy and ready after the coordinated restart, or if post-deploy verification fails after a successful bootstrap, treat production verification as failed and investigate the emitted SHA-bound verdict. Do not manufacture a replacement token or pricing override outside the canonical lifecycle and do not bypass `encryption_required` with direct privileged loopback HTTP.
