BusinesAIOS (Behavioral Operating System) — канон

Эта кодовая база — **BusinesAIOS**, операционная система автономного управления микробизнесами.
Продукты и организации подключаются как конфиги/домены и не являются “ядром”.

Все реальные интеграции только через runtime/_internal/_effects_impl.py

Core:
DECISIONCORE RING SPEC
Норматив архитектуры автономной AI-системы
1. БАЗОВЫЙ ЗАКОН СИСТЕМЫ
1.1 Decision Sovereignty

В системе существует ровно один источник решений:

DecisionCore.decide(WorldState) → DecisionEnvelope


Любое необратимое действие (side-effect):

платёж

отправка сообщения

выдача доступа

изменение тарифа

изменение оффера

запуск маркетингового действия

запись в внешнюю систему

разрешено только при наличии валидного DecisionEnvelope, прошедшего:

RuntimeGuard.verify

DecisionLedger.execute_once

RuntimeExecutor.execute

Нарушение этого правила считается:

ARCHITECTURAL FAILURE: DECISION BYPASS


и делает систему не-AI по определению.

2. СОСТАВ DECISIONCORE RING

DecisionCore определяется как замкнутый контур из 8 обязательных блоков.

Удаление любого блока размыкает закон.

БЛОК 1 — Policy Selector
Назначение

Выбор политики, которая будет принимать решение.

Контракт
select(WorldState) → PolicyRef

Инварианты

Selector не принимает бизнес-решения.

Детерминированность при фиксированном входе.

Разрешены только:

rollout

A/B

safe-mode fallback

guardrails выбора

Запрещено

вычислять action

изменять payload

выполнять side-effects

БЛОК 2 — DecisionCore.decide()
Назначение

Единственная точка выпуска решения.

Контракт
decide(WorldState) → DecisionEnvelope

Обязательные шаги

PolicySelector.select

Policy.decide → PolicyOutput(action, payload)

Построение канонического Decision

Расчёт:

payload_hash

state_hash / snapshot_id

Подпись → DecisionEnvelope

Инварианты

DecisionCore никогда не выполняет side-effects.

Decision создаётся только здесь.

БЛОК 3 — Signature & Hashes
Назначение

Криптографическая доказуемость решения.

Подписываемые поля

Обязательный минимум:

decision_id

issued_at_ms

policy_id (+ version)

action

payload_hash

state_hash / snapshot_id

kid

Инварианты

Канонизация payload и state строго единая.

Проверка подписи — constant-time.

Подпись неотделима от решения.

БЛОК 4 — State Hash / Snapshot
Назначение

Связь решения с состоянием мира.

Требования

WorldState обязан быть:

версионирован (schema_version)

валидируем

канонизируем

детерминирован при сериализации

Допустимые реализации

Минимум:

state_hash = sha256(canonical_state)


Эталон:

snapshot_id = SnapshotStore.put(state)


Snapshot ID включается в подпись.

БЛОК 5 — Decision Ledger (execute-once)
Назначение

Гарантия однократного исполнения решения.

Контракт
try_mark_executed(envelope) → bool

Инварианты

decision_id = PRIMARY KEY

Только атомарный INSERT.

Любая схема exists → insert запрещена.

Хранимые поля

Минимум:

decision_id

executed_at_ms

policy_id

action

payload_hash

signature

state_hash / snapshot_id

Прод-требование

PostgreSQL или эквивалент.

SQLite допустим только dev.

БЛОК 6 — Runtime Guard
Назначение

Исполняемый закон перед side-effects.

Контракт
verify(envelope) → OK | Exception
execute_once(envelope) → OK | Exception

Обязательные проверки

kid существует и не отозван

payload_hash совпадает

подпись валидна

schema/action валидны

execute-once через ledger

TTL / safe-mode (опционально)

Guard — единственный gate перед эффектами.

БЛОК 7 — Runtime Executor
Назначение

Единственный путь выполнения side-effects.

Контракт
execute(DecisionEnvelope) → ExecutionResult

Обязательная последовательность
guard.execute_once →
schema.validate →
handlers.dispatch →
effects →
event: decision_executed

Инварианты

Executor не принимает решений.

Любые внешние действия возможны только здесь.

БЛОК 8 — Schema Registry
Назначение

Запрет скрытых решений в payload.

Инварианты

Unknown action запрещён.

Payload:

required keys обязательны

optional разрешены

extra keys запрещены

типы валидируются

Версионирование схем обязательно.

Registry должен быть инъецируемым, не глобальным singleton.

3. КАНОНИЧЕСКАЯ ЦЕПОЧКА ИСПОЛНЕНИЯ
Внутри мозга
WorldState
 → PolicySelector
 → Policy.decide
 → DecisionCore
 → DecisionEnvelope

Внутри runtime
DecisionEnvelope
 → RuntimeExecutor
 → RuntimeGuard
 → DecisionLedger
 → SchemaRegistry
 → ActionHandlers
 → EffectsPort
 → External systems

4. АРХИТЕКТУРНЫЕ ЗАПРЕТЫ

Строго запрещено:

side-effects вне RuntimeExecutor

решения вне DecisionCore

второй decide()

бизнес-логика в runtime

unknown actions

обход ledger

исполнение без подписи

Любое нарушение = ARCHITECTURAL FAILURE.

5. ОБЯЗАТЕЛЬНЫЕ СОБЫТИЯ ДОКАЗУЕМОСТИ

Система обязана фиксировать:

decision_issued

decision_executed

reward_observed

payment_captured (с decision_id)

Без этого self-driving loop считается отсутствующим.

6. ОБЯЗАТЕЛЬНЫЕ SECURITY-ТЕСТЫ

Минимальный набор:

Подмена payload → FAIL

Подмена signature → FAIL

Unknown kid → FAIL

Unknown action → FAIL

Duplicate execution → FAIL

TTL expiry → FAIL

Replay после revoke ключа → FAIL

Если любой тест проходит неправильно →
Decision Sovereignty нарушен.

7. КРИТЕРИЙ “НАСТОЯЩЕЙ AI-СИСТЕМЫ”

Система считается автономной AI-экономикой только если:

DecisionCore Ring полностью замкнут

bypass архитектурно невозможен

события доказуемости полные

self-driving loop воспроизводим offline

Иначе это:

NON-AI AUTOMATION SYSTEM



ПОДКЛЮЧЁННЫЕ ОРГАНИЗАЦИИ
ЕДИНАЯ СИСТЕМНАЯ КОНСТИТУЦИЯ И PRODUCTION-СПЕЦИФИКАЦИЯ
ОКОНЧАТЕЛЬНАЯ РЕДАКЦИЯ (БЕЗ ДВУСМЫСЛЕННОСТИ)
0. НАЗНАЧЕНИЕ ДОКУМЕНТА

Документ определяет:

полную архитектуру системы

правила разработки

правила принятия решений

правила роста и обучения

правила удаления кода

правила релизов

границы ответственности модулей

Главная цель:

гарантировать единственную возможную реализацию системы.

Если 10 инженеров реализуют систему строго по этому документу —
они получат одинаковый продукт.

Любое расхождение считается:

АРХИТЕКТУРНОЙ ОШИБКОЙ УРОВНЯ СИСТЕМЫ

1. СУЩНОСТЬ СИСТЕМЫ

Подключённая организация — это:

автономная мультиплатформенная AI-управляемая экономическая SaaS-система, которая:

изменяет состояние пользователя

принимает продуктовые и финансовые решения

обучается на поведении и деньгах

управляет маркетингом, ценами и контентом

функционирует без постоянного ручного управления

2. ЗАКОН ЕДИНОГО МОЗГА (DECISION SOVEREIGNTY)
2.1 Единственный центр решений

В системе существует только:

DecisionCore.decide(WorldState) → Decision


Все, что влияет на:

деньги

цены

UX

контент

маркетинг

сценарии

удержание

продуктовые переходы

обязано исходить только из DecisionCore.

2.2 Полный запрет альтернатив

В production запрещено:

параллельные decision-engine

локальные вычисления цены

выбор оффера в handlers/services

ML-решения вне learning-контура

скрытая бизнес-логика в UI

Нарушение:

ARCHITECTURAL FAILURE: DECISION BYPASS

2.3 Runtime-гарантия единственности

Обязательно:

один экземпляр DecisionCore на процесс

детекция повторной инициализации

аварийное завершение при нарушении

лог ARCH_VIOLATION

переход в SAFE-MODE

3. КАНОНИЧЕСКИЙ SELF-DRIVING ЦИКЛ

Система обязана иметь замкнутый экономический контур:

Policy
→ Decision
→ Action
→ Поведение пользователя
→ Reward
→ Обучение
→ Деплой policy
→ Следующее решение


Если цикл разорван:

SYSTEM STATE = НЕ-AI СИСТЕМА

4. ГЛОБАЛЬНАЯ АРХИТЕКТУРА

Строго четыре слоя:

1. Interface Layer
2. Runtime SaaS Layer
3. AI Economy Core
4. Self-Healing & Evolution


Кросс-логика слоёв запрещена.

5. INTERFACE LAYER

Поддержка:

Telegram

Web

Mobile

Email

Push

API

Интерфейсы:

не принимают решений

не содержат ML

не содержат бизнес-логики

Разрешено только:

принять событие → вызвать DecisionCore → исполнить Decision

6. RUNTIME SAAS LAYER

Обязан обеспечивать:

доставку сообщений

платежи

scheduler

БД

идемпотентность

outbox

FSM

восстановление после падений

логи

health-метрики

воспроизводимость релизов

Инвариант:

Runtime исполняет решения, но не создаёт их.

7. МОДЕЛЬ СОБЫТИЙ

Каждое событие строго содержит:

event_id
user_id
source
event_type
timestamp (UTC)
payload
decision_id
correlation_id


Отсутствие decision_id:

попытка восстановления

иначе статус UNATTRIBUTED

обучение не останавливается

8. AI ECONOMY CORE

Состав:

Decision Engine

Reward Engine

Learning System

Policy Registry

Marketing AI

Product AI

Evolution Guard

Constraint Engine

DecisionCore управляет:

ценами

контентом

сценариями

маркетингом

персонализацией

удержанием

экономикой продукта

9. ONLINE / OFFLINE ОБУЧЕНИЕ
Online

contextual bandits

быстрые обновления policy

safety-ограничения

Offline

регулярный retrain

валидация

guardrails

auto-deploy

auto-rollback

10. РЕАЛЬНЫЙ УРОВЕНЬ AI (КРИТЕРИЙ)

Наличие ML-модулей не означает AI-систему.

Обязательно:

замкнутый reward-loop

offline-оценка

guardrails

rollback

автоматическое продвижение policy

Иначе система считается:

AI-подобным R&D прототипом

11. КОНСОЛИДАЦИЯ АРХИТЕКТУРЫ

Обязательно единое:

DecisionCore

Pricing authority

Revenue attribution

Growth runtime

LTV источник истины

Любые альтернативы:

изолировать → пометить deprecated → удалить

12. ВОСПРОИЗВОДИМОСТЬ PRODUCTION

Обязательно:

полный requirements lock

фиксированные версии

bootstrap окружения

воспроизводимый CI билд

Иначе:

CRITICAL RELEASE BLOCKER

13. ХРАНЕНИЕ ДАННЫХ

Запрещено в репозитории:

SQLite runtime-БД

пользовательские данные

mutable-состояние

Хранилище обязано поддерживать:

конкуренцию

миграции

CI/CD

масштабирование

14. ОЧИСТКА КОДА

Удаляется код, который:

не участвует в runtime

дублирует логику

устарел

не используется ≥ N релизов

временный патч

Хранить такой код запрещено.

15. БЕЗОПАСНОЕ УДАЛЕНИЕ

Строгая процедура:

анализ зависимостей
→ изоляция
→ релиз-наблюдение
→ финальное удаление


Проверки:

компиляция

запуск

целостность decision-цикла

стабильность метрик

16. ЗАПРЕТ «КОДОВ БОГА»

Запрещено:

мультиответственные классы

смешение слоёв

БД + бизнес-логика + UX в одном файле

Каждый модуль:

одна ответственность
явный контракт
подключение только через DecisionCore

17. ДОБАВЛЕНИЕ НОВОГО ФУНКЦИОНАЛА

Строгий путь:

идея
→ контракт
→ доменный модуль
→ интеграция в DecisionCore
→ observability
→ контролируемый релиз


Прямое подключение к UI запрещено.

18. OBSERVABILITY

Обязательно доступны:

версия policy

очереди

ошибки

режим работы

training-отчёты

ключевые метрики

19. СТРУКТУРА PRODUCTION-РЕПО
repo/
  core/ai/
  runtime/
  interfaces/
  infrastructure/
  observability/
  migrations/
  tests/
  scripts/
  docs/


Принципы:

одна папка — одна ответственность

нет кросс-логики

только DecisionCore как центр

research изолирован

20. КРИТЕРИЙ ЗАВЕРШЁННОСТИ

Система завершена, если:

один DecisionCore

замкнутый self-driving loop

автономный рост метрик

воспроизводимый production

устойчивость к сбоям

21. ГЛАВНЫЙ ТЕСТ

Если отключить человека
и метрики продолжают расти:

АРХИТЕКТУРА КОРРЕКТНА

ФИНАЛ

Это окончательная инженерная конституция платформы BusinesAIOS.

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:START -->
## World Model Integrity & Single-Decision-Brain Contract

### Purpose

BusinesAIOS must preserve exactly one canonical decision brain.

All economics, pricing, LTV, world-model, causal, replay and explainability layers
may enrich, constrain, explain or audit `DecisionCore`, but must never become
a parallel decision issuer.

### Architectural prohibition

The following are forbidden:

- alternative world-model wiring paths into decision issuance
- direct boot/runtime injection of legacy `WorldModel(LTVModel())`
- multiple competing semantic truth sources for decision-time state
- hidden or parallel pricing/economics decision engines
- execution-time use of unpinned model semantics in strict mode

Any such pattern is a **second brain violation**.

### Canonical world-model wiring path

The only canonical path is:

```text
WorldModelStore
→ runtime.boot.world_model_builder.build_default_world_model()
→ CanonicalDecisionWorldModel
→ DecisionCore
→ decision_state_enrichment
→ RuntimeExecutor
```

No other path may provide decision-time world-model semantics.

### DecisionCore contract

DecisionCore is the only final issuance point of business decisions.

Allowed dependency:

`DecisionCore(world_model: DecisionWorldModelPort)`

Forbidden dependencies:

- `DecisionCore(world_model=WorldModel(LTVModel()))`
- `DecisionCore(world_model=<non-canonical direct model>)`

### Status of economics / pricing / world-model layers

These layers are allowed only as:

- feature layers
- constraint layers
- explainability layers
- audit / replay layers

They are forbidden from becoming autonomous decision issuers.

### Pinning and execution integrity

Every decision must carry pinned world-model metadata when available:

- `world_model`
- `world_model_kind`
- `pricing_world_model`
- `pricing_world_model_version`
- `pricing_world_model_hash`
- `pricing_world_state_hash`

Runtime execution must validate pinned metadata against current active model metadata.

If strict pinning is enabled, hash mismatch must reject execution.

### Replay and auditability

The system must support canonical replay of:

- world-model enrichment
- pricing/economics constraints
- causal guardrails
- pinned metadata comparison
- decision trace explanation

A decision that cannot be audited against its model context is not institutionally valid.

### Boot / CI enforcement

Boot must construct the decision world model only through the canonical builder
and verify integrity during startup.

Repository enforcement must include:

- forbidden-path scanner
- typing enforcement for DecisionWorldModelPort
- boot self-check
- tests for pinning, replay and migration
- CI failure on forbidden legacy wiring

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:END -->
