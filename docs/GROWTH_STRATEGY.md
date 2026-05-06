# AI Growth Strategy (BusinesAIOS)

Цель: стратегический слой роста поверх Ring (events) и Autopilot (execution),
без «второго мозга» и без god-modules.

## UX (Telegram)
Меню **AI Growth Strategy**:
- 🔁 Сгенерировать backlog гипотез
- 📋 Посмотреть backlog
- ✅ Принять / ❌ отклонить гипотезы

## Архитектура (маленькие примитивы)
- `core/growth/strategy/contracts.py` — контракты goal/signal/hypothesis/experiment
- `core/growth/strategy/signals.py` — read-only сбор сигналов из event_store
- `core/growth/strategy/llm_generator.py` — опциональная генерация через LLM (строгий JSON)
- `core/growth/strategy/scoring.py` — детерминированный скоринг (ICE-ish + risk penalty)
- `core/growth/strategy/backlog_store.py` — append-only события backlog + read-model
- `core/growth/strategy/service.py` — тонкий app-service (оркестрация)

## Ring events
- `growth_strategy_snapshot@v1`
- `growth_hypothesis_created@v1`
- `growth_hypothesis_scored@v1`
- `growth_hypothesis_state@v1` (accepted/rejected/archived)
- `growth_experiment_created@v1`

## Action registry
- `growth_strategy_generate@v1` (LLM, idempotent)
- `growth_strategy_backlog@v1` (read-only)
- `growth_strategy_accept@v1` / `growth_strategy_reject@v1` (idempotent)

## Следующие шаги
- кнопка “создать эксперимент” → `growth_experiment_created@v1`
- привязка accepted гипотез к Autopilot tasks (scheduler)
