# Telegram interface (long polling)

This interface is deliberately minimal and respects Decision Sovereignty:
- Decisions are produced only by `DecisionCore.decide(WorldState)`
- All side-effects (network I/O) are executed only by `RuntimeExecutor` via sealed effects implementation

## Setup

1) Copy env template:

```bash
cp interfaces/telegram/.env.example .env
```

2) Fill values in `.env` and export them to your environment.

## Run

```bash
RUN_MODE=telegram python main.py
```

## Notes

- Polling is **transport only** (Long Polling `getUpdates`) and does NOT go through DecisionCore.
- Each update is converted into `WorldState` and passed to `DecisionCore.decide(WorldState)`.
- Payment reconciliation is also executed as an action (`reconcile_payments@v1`) on a timer.
- Access is granted only via `grant_access@v1` (DecisionCore -> envelope -> executor).
