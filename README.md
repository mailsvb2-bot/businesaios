# BusinesAIOS

BusinesAIOS is a **Behavioral Operating System** for autonomous management of microbusinesses (DecisionCore Ring + business autopilot).

It is a product-agnostic platform for many connected organizations and supports **pluggable communication providers**. Telegram is one optional connector; it is not the platform runtime and is not the architectural center of the product.

## Canonical specification

The canonical architecture is defined by:

- `docs/SYSTEM_TZ_CANONICAL.md`
- `docs/SYSTEM_TZ_MULTICHANNEL_PLATFORM.md` — normative multichannel addendum that removes channel-specific ambiguity from runtime and deployment rules

When historical documentation conflicts with this canonical set, update or delete the historical wording.

## Multichannel provider layer

The existing provider and connector framework already supplies:

- provider catalog and per-business onboarding;
- connector capability, maturity and registry contracts;
- scoped secrets, rotation and compromise handling;
- webhook routing, signature/replay protection and inbound processing;
- queue execution, retries, pagination and live-sync planning;
- health probes, incidents, observability, circuit breakers and failover;
- normalized messaging capability bindings.

The provider catalog currently models Telegram, WhatsApp, email, SMS and web-chat communication channels. Transport maturity is provider-specific: catalog/binding support does not by itself claim that every provider has complete live-network execution.

## Production runtime model

The mandatory platform processes are:

```text
businesaios-api.service
businesaios-worker.service
```

- **API Runtime** accepts web/API traffic, provider webhooks and control-plane operations.
- **Worker Runtime** executes channel-agnostic queues, autonomous cycles and outbound provider work.

A provider gets its own service only when its transport requires a dedicated polling or streaming process. The current optional example is:

```text
businesaios-connector-telegram.service
```

Install the core runtime:

```bash
sudo APP_DIR=/opt/businesaios deploy/systemd/install.sh
```

Enable the optional Telegram long-polling connector only for deployments that actually use it:

```bash
sudo ENABLE_TELEGRAM_CONNECTOR=1 APP_DIR=/opt/businesaios deploy/systemd/install.sh
```

Webhook-based providers remain attached to the API/provider-webhook runtime and do not require a fake always-on service per messenger.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

API profile:

```bash
APP_PROFILE=api python -m scripts.server.run_profile
```

Worker profile:

```bash
APP_PROFILE=worker python -m scripts.server.run_profile
```

Optional Telegram polling connector:

```bash
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
APP_PROFILE=telegram python -m scripts.server.run_profile
```

Local demo entrypoint remains available:

```bash
RUN_MODE=demo python main.py
```

## Tests

The required repository proof is the canonical gate:

```bash
python -m scripts.ci.cli --gate full
```

The complete pytest tree can also be run directly:

```bash
pytest -q
```

The complete tree runs without a hidden debt registry, wildcard exclusions, skip lists or an xfail baseline. Any failing test is release-blocking until its underlying defect is fixed. Every required release workflow must pass on the exact pull-request head SHA before merge; results from an earlier commit are not transferable.

## Architecture

- `core/ai/` — DecisionCore Ring, signatures, snapshots and schema registry
- `runtime/` — Guard + Executor + handlers; the only place for side effects
- `connectors/platform/` — channel-agnostic connector contracts, registry, resilience and observability
- `application/business_autonomy/` — provider catalog, onboarding and administration
- `runtime/business_autonomy/` — provider webhooks, queues, probes, sync and vendor transports
- `runtime/platform/ledger/` — execute-once ledger (SQLite dev, PostgreSQL prod)
- `runtime/platform/event_store/` — proof event store
- `core/reward/` and `core/learning/` — reward and learning loop

**Hard rule:** no side effects outside `runtime/executor.py` and the canonical internal effects boundary.

Domain decisions belong in `core/`; execution/effects in `runtime/`; persistence in `platform_layer/`; external adapters in `interfaces/` and `connectors/`.

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:START -->
Super Canon addendum

The repository now treats world-model integrity as a constitutional rule.

See:

- `docs/SYSTEM_TZ_CANONICAL.md`
- `docs/ARCHITECTURE_CANON_V20.md`

The canonical decision-world-model path is:

`WorldModelStore → build_default_world_model() → CanonicalDecisionWorldModel → DecisionCore → RuntimeExecutor`

Any alternative world-model wiring path is non-canonical.
<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:END -->
