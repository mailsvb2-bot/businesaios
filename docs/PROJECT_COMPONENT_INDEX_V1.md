# PROJECT_COMPONENT_INDEX_V1

Компактный индекс модулей проекта для ревью и онбординга: модуль → роль → ключевые зависимости.

---

## Boot

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `boot/app_boot.py` | Точка входа приложения, валидация контрактов | `boot/wiring`, `runtime` |
| `boot/startup_pipeline.py` | Конвейер запуска, порядок инициализации | `boot/factories`, `boot/registrations` |
| `boot/runtime_orchestrator.py` | Оркестрация сборки runtime‑сервисов | `boot/wiring`, `runtime` |
| `boot/wiring/*` | Загрузка манифеста, валидация, резолвинг зависимостей | `release/manifest.json` |
| `boot/factories/*` | Фабрики decision_core, governance, executor | `core`, `runtime` |
| `boot/registrations/*` | Регистрация сервисов в runtime registry | `runtime/registry` |
| `boot/telegram_boot.py` | Поднятие Telegram‑раннера | `interfaces/telegram` |
| `boot/http_boot.py` | Поднятие HTTP/API | `interfaces/api` |

---

## Runtime

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `runtime/application/*` | Приложение: диспетчер действий, порты, результат | `runtime/executor`, `core` |
| `runtime/registry.py` | Реестр сервисов, типизированный доступ | `runtime/manifest_entry`, `runtime/lifecycle` |
| `runtime/executor.py` | Выполнение эффектов через порты | `runtime/ports/effects*`, `runtime/handlers` |
| `runtime/boot/*` | Сборка runtime (finance, governance, product, world_model и др.) | `core`, `infra` |
| `runtime/execution/*` | Точки входа executor, recovery | `runtime/executor` |
| `runtime/handlers/*` | Обработчики: pricing, governance, ads_apply, reward и др. | `core/behavior`, `runtime/ports` |
| `runtime/_internal/effects_*` | Эффекты: offer patch, telegram actions, admin_state | `interfaces/ads`, `interfaces/telegram` |
| `runtime/ports/effects*.py` | Интерфейсы эффектов (admin, revenue, comms) | `runtime/executor` |
| `runtime/messaging/*` | Роутинг, доставка, каналы | `interfaces/messaging_runtime` |
| `runtime/finance/*` | Финансовая оркестрация, job catalog | `core/finance` |
| `runtime/scheduler*.py` | Планировщик, пороги | `infra/background_jobs` |
| `runtime/guard.py`, `guard_protocols.py` | Протоколы охраны и мутаций | `core/behavior/guards` |
| `runtime/audit*.py` | Аудит, записи | `infra/audit_log_service` |

---

## Core — Behavior Engine

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `core/behavior/contracts/*` | Контракты снимков, поведенческих состояний | — |
| `core/behavior/math/*` | Математика Dirac‑домена, агрегация, фазы | — |
| `core/behavior/operators/*` | Операторы, применение, отказы | `operator_catalogs`, `operator_policy_catalogs` |
| `core/behavior/operator_catalogs/*` | Каталог операторов, загрузка, парсер | — |
| `core/behavior/operator_policy_catalogs/*` | Каталог политик операторов | `operator_catalogs` |
| `core/behavior/builders/*` | Сборка spinor‑состояний | `math`, `observables` |
| `core/behavior/observables/*` | Наблюдаемые (market, segment, org, person) | `contracts` |
| `core/behavior/constraints/*` | Ограничения: safety, contact, offer, price | `operators` |
| `core/behavior/guards/*` | Охраны: no_hidden_selection, decision_rights | `constraints` |
| `core/behavior/integration/*` | Мосты: pricing, retention, runtime, telemetry | `core/behavior/runtime`, `runtime` |
| `core/behavior/runtime/*` | Retry, backpressure, world_state merger | `runtime` |
| `core/behavior/persistence/*` | Репозитории снимков (market, segment, org, person) | `contracts` |
| `core/behavior/read_models/*` | Read‑модели поведенческих снимков | `contracts` |
| `core/behavior/simulation/*` | What‑if сценарии | `builders`, `math` |
| `core/behavior/adapters/*` | Адаптеры: pricing, offer, decisioncore, simulation | `runtime` |

---

## Core — Other Domains

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `core/economics/*` | Экономика, capital engine | `core/finance` |
| `core/finance/*` | Финансовые контракты, feature registry | `runtime/finance` |
| `core/offers/*` | Офферы, каталоги, ценовые зоны | `core/behavior` |
| `core/product/*` | Продуктовые контракты | `runtime` |
| `core/knowledge/*` | Контракты знаний | — |
| `core/ads/*` | Контракты ADS, apply engine | `interfaces/ads` |

---

## Interfaces

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `interfaces/api/*` | HTTP API, FastAPI, route handlers, health | `runtime/application` |
| `interfaces/telegram/*` | Telegram runner, handler, presenter, pipeline | `runtime/application`, `interfaces/telegram/outbound` |
| `interfaces/telegram/outbound/*` | Очередь исходящих, worker, alerter, self-heal | `interfaces/messaging_runtime` |
| `interfaces/ads/*` | Google Ads, TikTok Ads connectors (canonical) | `runtime` |
| `interfaces/ads/*_legacy.py` | Тонкие alias‑шиммы | `interfaces/ads/*.py` (canonical) |
| `interfaces/behavior/*` | Адаптеры behavior ↔ runtime/telemetry | `core/behavior` |
| `interfaces/messaging/*` | WhatsApp, SMS, Email, Messenger и др. | `messaging_runtime` |
| `interfaces/messaging_runtime/*` | Раннер, роутинг, views, state | `runtime/messaging` |
| `interfaces/web/*` | API gateway, chat widget, settings | `interfaces/api` |
| `interfaces/regional/*` | LINE, WeChat, Viber, KakaoTalk | `messaging_runtime` |

---

## Infra

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `infra/approval_*.py` | Одобрения, хранилище, evidence | `infra/governance_*` |
| `infra/control_plane_*.py` | Control plane bootstrap | `infra/rollout_*`, `infra/feature_flags` |
| `infra/rollout_*.py` | Rollout policy, модели, promotion | `infra/release_fingerprint` |
| `infra/governance_*` | Конституционное управление, evidence, автономия | `runtime` |
| `infra/compliance_*.py` | Compliance bootstrap | `infra` |
| `infra/audit_*.py` | Аудит, sink, события | `runtime/audit` |
| `infra/idempotency*.py` | Идемпотентность | — |
| `infra/retry_*.py` | Политика повторов | — |
| `infra/readiness_gates.py` | Проверки готовности | `infra/dependency_health` |
| `infra/lifecycle*.py` | Состояние жизненного цикла | `infra/process_manager`, `infra/graceful_shutdown` |
| `infra/background_jobs*.py` | Фоновая работа | `runtime/jobs` |
| `infra/kill_switches.py` | Аварийные выключатели | `runtime` |

---

## Observability

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `observability/*` | Метрики, трейсы, события | `runtime`, `core/behavior/observability` |
| `core/behavior/observability/*` | Логгер, structured events, metric names | `core/behavior` |

---

## Scripts (ключевые)

| Модуль | Роль | Зависимости |
|--------|------|-------------|
| `scripts/gen_release_manifest.py` | Генерация `release/manifest.json` | `core/security/release_manifest` |
| `scripts/import_*_bundle.py` | Импорт кода из внешних .txt | — |
| `scripts/apply_cicd/*` | CI/CD pipeline | `ci` |

---

## Соглашения

- **Owner**: модуль владеет логикой в своей зоне ответственности.
- **Legacy**: `*_legacy.py` — только тонкий re‑export из canonical, без новой логики.
- **Canonical**: основная реализация; legacy — alias для обратной совместимости.

См. также:
- `docs/PROJECT_FUNCTIONAL_MAP_V1.md` — карта слоёв и инвариантов
- `docs/PROJECT_FLOW_V1.md` — диаграмма потока
- `docs/LEGACY_ENTITY_AUDIT_V1.md` — аудит legacy‑модулей
