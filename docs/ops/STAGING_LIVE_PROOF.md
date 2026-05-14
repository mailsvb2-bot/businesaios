# BusinessAIOS Staging/Live Proof

Generated: 2026-05-14T21:28:45Z  
Branch: canon-p0-architecture-boundary-pack  
Commit: 3b9044a

## Scope

This document records the current externally reachable staging/live proof for BusinessAIOS.

The system is still classified as:

- alpha/staging
- read-only/advisory pilot
- not fully production-ready

This proof does not claim full commercial production readiness. It confirms that the current server boot, API readiness, nginx routing, Postgres-backed storage readiness, and canonical CI gate are healthy at the time of verification.

## Server Identity

Server path:

```
/opt/businesaios
```

API service:

```
businesaios-api.service
```

Expected service entrypoint:

```
/opt/businesaios/.venv/bin/python -m entrypoints.api.run_http
```

## Runtime Environment Contract

Required runtime environment:

```
APP_ENV=prod
RUN_MODE=api
METRO_DB_ENGINE=postgres
POSTGRES_DSN=present
PRODUCTION_STRICT_MODE=1
RELEASE_ATTEST=1
ADMIN_USER_IDS=768478185,8335001156
MODEL_REGISTRY_BACKEND=sqlite
```

Notes:

- POSTGRES_DSN must be present but must not be written into documentation or logs in clear text.
- MODEL_REGISTRY_BACKEND=sqlite is intentional for model artifact registry and is separate from durable runtime Postgres storage.
- Governance requires at least two admins in production strict mode.

## External Surfaces

Public landing site:

```
https://businessaios.ru
```

API readiness endpoint:

```
https://api.businessaios.ru/readyz
```

Important: `/readyz` supports GET. A HEAD request may return `405 Method Not Allowed`; this is not a readiness failure.

## Verified Readiness Conditions

The following conditions were verified on the server:

- systemd service active/running
- API readiness returns HTTP 200 with GET
- readiness status is `ready`
- health overall status is `pass`
- runtime orchestrator is present
- missing runtime services list is empty
- missing runtime components list is empty
- nginx config test passes
- active nginx site is a symlink from sites-enabled to sites-available
- no active backup nginx configs remain in sites-enabled
- full CI gate passes
- release manifest verifies
- generated audit/proof artifacts are moved outside the git repo after checks

## Canonical Commands Used

Service identity:

```bash
systemctl show businesaios-api.service \
  -p ActiveState \
  -p SubState \
  -p MainPID \
  -p ActiveEnterTimestamp \
  --no-pager
```

API readiness:

```bash
curl -fsS https://api.businessaios.ru/readyz | python -m json.tool
```

Nginx verification:

```bash
nginx -t
find /etc/nginx/sites-enabled -maxdepth 1 \( -type f -o -type l \) -ls | sort
```

Storage readiness:

```bash
set -a
. /opt/businesaios/.env
set +a

python - <<'PY'
from runtime.wiring import resolve_storage_config, describe_storage_readiness, storage_live_smoke_status

storage = resolve_storage_config()
print("storage_backend=", storage.backend)
print("storage_env=", storage.env)
print("postgres_dsn_configured=", bool(storage.postgres_dsn))
print("readiness=", describe_storage_readiness(storage))
print("live_smoke=", storage_live_smoke_status(base_dir="/opt/businesaios/data/runtime", storage=storage))
PY
```

Full gate:

```bash
env -u APP_ENV -u ENV -u PRODUCTION_STRICT_MODE -u RELEASE_ATTEST -u ADMIN_USER_IDS \
  APP_ENV=ci ENV=ci RUN_MODE=test TENANT_ID=ci-test-tenant BUSINESAIOS_SAFETY_PERSISTENT=0 \
  python -m scripts.ci.cli --gate full
```

Manifest verification:

```bash
python - <<'PY'
from pathlib import Path
from runtime.security import verify_manifest

root = Path.cwd()
verify_manifest(root_dir=root, manifest_path=root / "release" / "manifest.json")
print("RELEASE_MANIFEST_OK")
PY
```

## Current Closure Status

### P0 closed

- Server boot proof
- API external readiness proof
- nginx active topology proof
- Postgres storage readiness proof
- full CI gate proof
- release manifest verification
- repo clean proof

### P1 remaining

- Long-running soak test
- explicit production/release GitHub workflow proof
- deeper executor negative-mass split
- repo-wide sealed effects / raw side-effect scanner hardening
- admin/control-plane visibility expansion for every newly added capability

## Honest Status

BusinessAIOS is currently stronger than a raw alpha and has a confirmed staging/live API readiness proof.

It should still be described as:

```
staging-live / alpha pilot / read-only advisory
```

It should not yet be described as:

```
fully production-ready commercial autonomous operating system
```
