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

## Preconditions

The target release must already be checked out at `/opt/businesaios`, its canonical virtualenv must exist, and `/etc/businesaios/api.env` must contain the production pepper, PostgreSQL settings, and explicit persistent API-key/tenant-registry paths. The selected tenant must already exist and be active; this lifecycle deliberately does **not** create a tenant as a side effect of credential issuance.

`EXPECTED_SHA` must be the exact 40-character SHA selected from trusted release evidence (normally the intended GitHub `main` commit) **before** the production host is changed. Do not derive `EXPECTED_SHA` from the current production checkout and do not persist it in `api.env`; otherwise a stale or unintended checkout could validate itself.

## Canonical command

After the canonical deployment has placed the intended release at `/opt/businesaios`, run exactly one host lifecycle with the externally selected release SHA:

```bash
sudo env \
  EXPECTED_SHA="<exact-40-character-github-main-sha>" \
  SMOKE_TENANT_ID="<existing-active-production-tenant>" \
  bash /opt/businesaios/scripts/server/bootstrap_and_verify_production.sh
```

Before running it, the operator must verify that `<exact-40-character-github-main-sha>` is the release SHA approved for deployment. The lifecycle itself will independently compare that value with `/opt/businesaios` `HEAD` before mutating the credential.

Do not generate a control-plane token manually, write an unhashed token into the application key store, use `default-business`, derive `EXPECTED_SHA` from the production host being verified, or invoke a separate ad-hoc smoke verifier.

## What the lifecycle proves

`bootstrap_and_verify_production.sh` first refuses to mutate credentials unless the deployed SHA exactly equals the externally supplied `EXPECTED_SHA`. It then calls `bootstrap_production_control_plane.py`, which validates the active tenant and persistent stores, issues an OWNER service credential through the application API-key store, proves the plaintext is absent from that store, and atomically writes the new credential plus `SMOKE_TENANT_ID` into `/etc/businesaios/api.env`.

The API service is restarted so the in-process authentication store sees the newly issued record. The existing canonical `verify_runtime_host_contract.sh` then remains the sole post-deploy verifier and executes the SHA-bound chain:

`health -> readiness -> runtime -> PostgreSQL -> authenticated synthetic action -> action audit -> exact SHA verdict`

A PASS verdict is written only by that verifier under `PRODUCTION_VERDICT_DIR`; its filename and payload are bound to `EXPECTED_SHA`.

## Failure behavior

Bootstrap failures before the environment replacement leave the previous plaintext environment unchanged and revoke the newly issued candidate key. Unknown, suspended or disabled tenants fail before credential issuance. Missing pepper, memory-backed security/tenant stores, relative production store paths, duplicate environment assignments, a symlinked environment file, or an unsafe default tenant all fail closed.

If service restart or post-deploy verification fails after a successful bootstrap, treat production verification as failed and investigate the emitted SHA-bound verdict. Do not manufacture a replacement token outside the canonical lifecycle.