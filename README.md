# BusinesAIOS

## Canonical specification (single source of truth)
**The only source of truth for architecture, invariants, and implementation rules is:**

- `docs/SYSTEM_TZ_CANONICAL.md`

All other documents in `docs/` are **non-normative** (appendices, notes, historical drafts)
unless explicitly referenced as normative *inside* `SYSTEM_TZ_CANONICAL.md`.

### What to do if documents disagree
If any file contradicts `docs/SYSTEM_TZ_CANONICAL.md`, treat it as **non-canonical** and update it
to match the canonical spec (or delete it if obsolete).

# BusinesAIOS — DecisionCore Ring (Compiled)

BusinesAIOS is a **Behavioral Operating System** for autonomous management of microbusinesses
(Ring + DecisionCore = Business Autopilot).

This repository is positioned and deployed as **BusinesAIOS**: a product-agnostic platform prepared for many connected organizations.

This repository is a compiled, single-system build that follows:
- **DECISIONCORE RING SPEC** (Decision Sovereignty, 8 mandatory blocks)
- The project's **Unified Super-TZ** (see `docs/SYSTEM_TZ_CANONICAL.md`).

## Run (dev)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Reproducible install (CI): pip freeze > requirements.lock.txt && pip install -r requirements.lock.txt

# Default behavior:
# - if TELEGRAM_BOT_TOKEN is set -> starts Telegram Long Polling
# - else -> runs local demo mode
python main.py
```

### Run in Telegram mode (Long Polling)

1) Create `.env` (or set environment variables in your shell):

```bash
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
RUN_MODE=telegram
```

2) Start the bot:

```bash
python main.py
```

Important:
- You must open the bot chat in Telegram and press **Start** at least once.
- If you see `Bad Request: chat not found`, it means you are trying to send to a chat_id that never started the bot.

### Run in demo mode (pure local)

```bash
RUN_MODE=demo
python main.py
```

## Run tests

```bash
pytest -q
```

## Architecture

- `core/ai/` — DecisionCore Ring (PolicySelector, DecisionCore, hashes/signature, snapshots, schema registry)
- `runtime/` — Guard + Executor + Handlers (the only place for side-effects)
- `runtime/platform/ledger/` — execute-once ledger (SQLite dev, Postgres prod)
- `runtime/platform/event_store/` — proof event store (memory/sqlite/postgres)
- `core/reward/` and `core/learning/` — reward + learning scaffolding to close the self-driving loop

**Hard rule:** no side-effects outside `runtime/executor.py`.

Where to put new code: domain/decisions → `core/`; execution/effects → `runtime/`; persistence → `platform_layer/`; adapters → `interfaces/`. See `docs/SYSTEM_TZ_CANONICAL.md`.


## Canonical specification

Единственный источник архитектурной истины:

`docs/SYSTEM_TZ_CANONICAL.md`


See also: `docs/ARCHITECTURE_CANON_V20.md` for the single-brain, single-executor canon.

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
