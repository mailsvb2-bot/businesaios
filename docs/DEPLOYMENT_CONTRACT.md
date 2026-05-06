# Deployment Contract (Canonical) — BusinesAIOS

This document is the single source of truth for how BusinesAIOS is deployed.
Anything in deploy/ and infrastructure/ MUST comply with this contract.

## 1) Canonical Identity

**Product name:** BusinesAIOS
**Canonical app_id:** `businesaios`

Hard rule: deployment artifacts must not use legacy single-product identifiers and tenant-specific names in service names, directories, container names, k8s resource names, etc.

## 2) Processes / Run Modes

BusinesAIOS runs in **2-process mode** (two independent processes using the same codebase):

1) **Telegram Runtime**
   - `RUN_MODE=telegram`
   - Purpose: serve Telegram UI / bot interactions, command processing.

2) **Evolution Worker**
   - `RUN_MODE=evolution`
   - Purpose: background ticks / policy execution / orchestration loops.
   - Exposes health endpoint.

Both processes are stateless aside from the shared data volume (see §4).

## 3) Network Contract

### 3.1 Health

Evolution Worker MUST expose:

- `GET /healthz` on port `EVOLUTION_HEALTH_PORT` (default `8087`)

### 3.2 Public exposure

By default, only the health endpoint is exposed. Telegram Runtime typically does not need inbound ports.

## 4) Storage Contract

### 4.1 Data directory

The runtime data directory is:

- `/app/runtime/entrypoints/data` (inside container)

### 4.2 Volume

Docker compose MUST mount a named volume:

- `businesaios_data:/app/runtime/entrypoints/data`

Kubernetes SHOULD mount a persistent volume to the same path.

## 5) Environment Contract

### 5.1 Required variables (minimum)

- `ENV` (e.g. `prod`, `stage`, `dev`)
- `LOG_LEVEL` (e.g. `INFO`)
- `RUN_MODE` (`telegram` or `evolution`)

### 5.2 Evolution Worker variables

- `EVOLUTION_POLL_INTERVAL_SEC` (default `2`)
- `EVOLUTION_BATCH_SIZE` (default `10`)
- `EVOLUTION_HEALTH_PORT` (default `8087`)

### 5.3 Telegram variables

Telegram runtime requires its own credentials (token/keys) depending on adapter choice.
The `.env.example` MUST list placeholders for those secrets (but never real values).

## 6) Security / Hardening Contract (baseline)

Deployments SHOULD enforce:
- least privilege execution (non-root where feasible)
- no hostNetwork/hostPID/hostIPC on k8s
- `automountServiceAccountToken: false` unless explicitly required
- runtime sandboxing (e.g. `gvisor`) where available

## 7) Deployment Targets

This repo provides:
- Docker Compose: `deploy/docker-compose.yml`
- systemd units: `deploy/systemd/*.service` + `deploy/systemd/install.sh`
- Windows Task Scheduler: `deploy/windows/install_tasks.cmd`
- Kubernetes manifests: `infrastructure/k8s/*.yaml`

All targets MUST comply with this contract.

## 8) Drift Prevention

CI MUST fail if:
- legacy identifiers appear in deploy/infrastructure docs or manifests
- compose services/volumes drift from canonical names
- systemd install script uses legacy app paths
- this file is missing or modified to remove contract anchors


See also: `docs/ARCHITECTURE_CANON_V20.md` for the single-brain, single-executor canon.
