# Production control-plane credential lifecycle

This runbook defines the single canonical lifecycle for the production control-plane credential used by the post-deploy synthetic verdict.

## Security contract

- `SMOKE_TENANT_ID` must name an existing **active** record in the canonical persistent tenant registry.
- Credential issuance uses `entrypoints.api.api_key_policy.PersistentApiKeyStore`; no second hashing or credential implementation is allowed.
- The application store persists `key_id`, the pepper-derived secret hash, tenant binding, roles/scopes and lifecycle metadata. It must never persist the plaintext credential.
- `API_CONTROL_PLANE_API_KEY_PEPPER` remains application-side secret material in the production environment.
- The only persistent plaintext copy of the issued credential is `CONTROL_PLANE_API_KEY` in `/etc/businesaios/api.env`.
- The environment file is replaced atomically, preserves its owner/group and is forced to mode `0600`.
- The bootstrap never prints the credential. It reports only tenant ID and key ID.
- A second bootstrap invocation rotates only a previous credential carrying this lifecycle's canonical metadata; unrelated credentials are not revoked.
- Privileged synthetic control-plane traffic must traverse the canonical public HTTPS ingress. Loopback HTTP remains valid only for local health/readiness probes.
- The API may trust `X-Forwarded-*` only from the local nginx peer: `BUSINESAIOS_TRUST_PROXY_HEADERS=true` with `BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128`.
- The systemd worker health surface is internal-only: `HEALTH_HOST=127.0.0.1`, `WORKER_HEALTH_PORT=8087`, `EVOLUTION_HEALTH_PORT=8087`, `EVOLUTION_ENABLED=1`. Port `8087` must never be intentionally exposed on `0.0.0.0` in canonical production.
- Production verification must source credentials, tenant ID, PostgreSQL DSN and runtime bindings from `/etc/businesaios/api.env`; ambient shell values are not an accepted fallback.

## Preconditions

The target release must already be checked out at `/opt/businesaios`, its canonical virtualenv must exist, and `/etc/businesaios/api.env` must contain the production pepper, PostgreSQL settings, explicit persistent API-key/tenant-registry paths, canonical worker bindings, and the canonical TLS boundary:

```text
HEALTH_HOST=127.0.0.1
WORKER_HEALTH_PORT=8087
EVOLUTION_HEALTH_PORT=8087
EVOLUTION_ENABLED=1
PUBLIC_BASE_URL=https://api.businessaios.ru
BUSINESAIOS_TRUST_PROXY_HEADERS=true
BUSINESAIOS_TRUSTED_PROXY_IPS=127.0.0.1/32,::1/128
```

The systemd units installed on the host must be byte-identical to `deploy/systemd/businesaios-api.service` and `deploy/systemd/businesaios-worker.service` from the exact deployed SHA. The systemd manager must already have reloaded those files (`NeedDaemonReload=no`) and neither core service may have a drop-in override. The canonical deployment path is `deploy/systemd/install.sh`; the credential lifecycle deliberately refuses to mutate a credential when the installed unit files lag the deployed release or effective systemd configuration differs from it.

The selected tenant must already exist and be active; this lifecycle deliberately does **not** create a tenant as a side effect of credential issuance. Nginx must terminate TLS for `PUBLIC_BASE_URL` and forward the original scheme to the local API. The verifier rejects a non-HTTPS public origin, rejects any trusted-proxy network wider than loopback, and rejects a worker health binding wider than loopback.

`EXPECTED_SHA` must be the exact 40-character SHA selected from trusted release evidence (normally the intended GitHub `main` commit) **before** the production host is changed. Do not derive `EXPECTED_SHA` from the current production checkout and do not persist it in `api.env`; otherwise a stale or unintended checkout could validate itself.

## Canonical command

After the canonical deployment has placed the intended release at `/opt/businesaios` and installed the release's systemd units, run exactly one host lifecycle with the externally selected release SHA:

```bash
sudo env \
  EXPECTED_SHA="<exact-40-character-github-main-sha>" \
  SMOKE_TENANT_ID="<existing-active-production-tenant>" \
  bash /opt/businesaios/scripts/server/bootstrap_and_verify_production.sh
```

Before running it, the operator must verify that `<exact-40-character-github-main-sha>` is the release SHA approved for deployment. The lifecycle itself will independently compare that value with `/opt/businesaios` `HEAD` before mutating the credential.

Do not generate a control-plane token manually, write an unhashed token into the application key store, use `default-business`, derive `EXPECTED_SHA` from the production host being verified, inject an ad-hoc `SMOKE_BASE_URL`, widen trusted proxy networks, widen the worker health bind, add production-only systemd drop-ins, or invoke a separate smoke verifier.

## What the lifecycle proves

`bootstrap_and_verify_production.sh` first refuses to mutate credentials unless the deployed SHA exactly equals the externally supplied `EXPECTED_SHA`. Before credential mutation it also validates the production environment's canonical HTTPS boundary, PostgreSQL presence and loopback-only worker bindings, and verifies that the effective installed API/worker systemd configuration is the exact deployed configuration: no stale daemon state, no drop-ins, and byte-identical unit fragments from the deployed SHA.

It then calls `bootstrap_production_control_plane.py`, which validates the active tenant and persistent stores, issues an OWNER service credential through the application API-key store, proves the plaintext is absent from that store, and atomically writes the new credential plus `SMOKE_TENANT_ID` into `/etc/businesaios/api.env`.

The API and worker services are restarted together so both processes execute the deployed release and the API authentication store sees the newly issued record. The lifecycle then waits, fail-closed and under one 60-second wall-clock deadline, until API `/health` + `/readyz` and worker `/health` + `/ready` all answer successfully; `systemd` reporting either service merely `active` is not sufficient.

The existing canonical `verify_runtime_host_contract.sh` remains the sole post-deploy verifier. Local core health/readiness/runtime checks stay on loopback HTTP, while the privileged authenticated synthetic action and audit flow is forced through `PUBLIC_BASE_URL` over HTTPS. The verifier executes the SHA-bound chain:

`health -> readiness -> runtime -> PostgreSQL -> authenticated synthetic action over HTTPS -> action audit -> exact SHA verdict`

A PASS verdict is written only by that verifier under `PRODUCTION_VERDICT_DIR`; its filename and payload are bound to `EXPECTED_SHA`.

## Failure behavior

Bootstrap failures before the environment replacement leave the previous plaintext environment unchanged and revoke the newly issued candidate key. Unknown, suspended or disabled tenants fail before credential issuance. Missing pepper, memory-backed security/tenant stores, relative production store paths, duplicate environment assignments, a symlinked environment file, an unsafe default tenant, a non-HTTPS `PUBLIC_BASE_URL`, disabled proxy trust, trusted proxy networks wider than loopback, worker health bindings wider than loopback, missing PostgreSQL configuration, stale systemd daemon state, systemd drop-ins, or installed systemd units that do not match the deployed SHA all fail closed.

If either API or worker does not become genuinely healthy and ready after the coordinated restart, or if post-deploy verification fails after a successful bootstrap, treat production verification as failed and investigate the emitted SHA-bound verdict. Do not manufacture a replacement token outside the canonical lifecycle and do not bypass `encryption_required` with direct privileged loopback HTTP.
