# Deployment Contract (Canonical) — BusinesAIOS

This document is the single source of truth for how BusinesAIOS is deployed.
Anything in `deploy/` and `infrastructure/` MUST comply with this contract.

## 1) Canonical identity

**Product name:** BusinesAIOS  
**Canonical app_id:** `businesaios`

Deployment artifacts must not make any messenger or tenant the platform identity.

## 2) Production process model

BusinesAIOS has two mandatory channel-agnostic core processes using the same codebase:

1. **API Runtime**
   - `APP_PROFILE=api`
   - serves HTTP/API traffic, control-plane operations and provider webhooks;
   - default port: `API_PORT=8000`.

2. **Background Worker**
   - `APP_PROFILE=worker`
   - executes queues, autonomous cycles and background provider work;
   - default health port: `WORKER_HEALTH_PORT=8087`.

Messaging transports are providers, not platform runtimes. A transport gets a dedicated process only when its protocol requires polling/streaming. The current optional example is:

3. **Telegram polling connector (optional)**
   - `APP_PROFILE=telegram`
   - enabled only for deployments that choose Telegram long polling.

`RUN_MODE=telegram/evolution` may still exist inside compatibility implementation modules, but it is not the deployment authority and MUST NOT replace the `APP_PROFILE` process contract above.

## 3) Network and health contract

### 3.1 API Runtime

The API Runtime MUST expose:

- `GET /health`
- `GET /readyz`

on `API_PORT` (default `8000`).

### 3.2 Worker Runtime

The worker health server exposes:

- `GET /health`
- `GET /ready`

on `WORKER_HEALTH_PORT` (default `8087`). `EVOLUTION_HEALTH_PORT` is an internal compatibility name only.

### 3.3 Optional connector

The Telegram polling connector may expose its own health endpoint on `TELEGRAM_HEALTH_PORT` (default `8088`). Webhook-based providers enter through the API/provider-webhook runtime and do not require a dedicated always-on service per messenger.

## 4) Storage contract

Production deployments use PostgreSQL for configured durable stores and a persistent runtime data root for file-backed runtime state/evidence.

- systemd canonical runtime root: `/var/lib/businesaios/runtime`
- Docker Compose canonical runtime root: `/app/runtime/data`
- `BAIOS_DATA_DIR` and `APP_RUNTIME_DATA_DIR` MUST point at the selected persistent runtime root.

Docker Compose MUST mount the named volume `businesaios_data` at its runtime root.

## 5) Environment contract

Minimum production configuration is based on `.env.example.prod` and includes:

- `APP_ENV=prod`
- `ENV=prod`
- `LOG_LEVEL`
- `STORAGE_BACKEND=postgres`
- `DATABASE_URL` / `POSTGRES_DSN`
- production secret/key backend configuration
- provider credentials only for providers that are actually enabled.

Process identity is set by the deployment target (`APP_PROFILE=api`, `worker`, or an optional connector profile), not by copying one global `APP_PROFILE` value to every process.

## 6) Linux systemd contract

Canonical production units are:

- `businesaios-api.service`
- `businesaios-worker.service`

Optional polling connector:

- `businesaios-connector-telegram.service`

`deploy/systemd/install.sh` installs/restarts the core units, optionally enables the Telegram connector, writes release state, and disables historical `businesaios-telegram.service` / `businesaios-evolution.service` names after successful installation.

## 7) Docker Compose contract

`deploy/docker-compose.yml` MUST mirror the same process ownership:

- `businesaios_api` → `APP_PROFILE=api`
- `businesaios_worker` → `APP_PROFILE=worker`
- optional `businesaios_connector_telegram` → `APP_PROFILE=telegram`

The compose file MUST execute `scripts.server.migrate_before_start` before starting a server profile and MUST use `scripts.server.run_profile` as the runtime entrypoint.

## 8) Security / hardening baseline

Deployments SHOULD enforce:

- least privilege execution;
- no hostNetwork/hostPID/hostIPC on Kubernetes;
- `automountServiceAccountToken: false` unless explicitly required;
- runtime sandboxing where available;
- secrets supplied by the deployment environment, never committed to the repository.

## 9) Deployment targets

This repository provides:

- Linux systemd: `deploy/systemd/*.service` + `deploy/systemd/install.sh` (canonical production server path);
- Docker Compose: `deploy/docker-compose.yml` (containerized parity/staging/production where Compose is the chosen operator);
- Kubernetes manifests under `infrastructure/k8s/`;
- Windows deployment helpers where explicitly supported.

Every maintained target MUST preserve the API + Worker core and optional-provider model.

## 10) Drift prevention

CI MUST fail if:

- core systemd units stop using `APP_PROFILE=api/worker`;
- Docker Compose reintroduces mandatory messenger-specific platform services or legacy evolution/telegram ownership;
- compose/systemd runtime entrypoints bypass `scripts.server.run_profile`;
- historical `businesaios-telegram.service` / `businesaios-evolution.service` become canonical again;
- this file loses the API + Worker + optional-provider ownership contract.

See also `docs/ARCHITECTURE_CANON_V20.md` for the single-brain, single-executor Canon.
