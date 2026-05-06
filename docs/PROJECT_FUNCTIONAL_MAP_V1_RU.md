# PROJECT_FUNCTIONAL_MAP_V1_RU

## 1) Миссия и границы

Миссия проекта:
- Обеспечивать единый канонический контур принятия и исполнения решений.
- Сохранять безопасность, наблюдаемость и воспроизводимость поведения в runtime.
- Исключать "второй мозг" (параллельные скрытые decision-пути).

Жёсткая граница:
- Решение/намерение формируется только в каноническом decision-контуре.
- Исполнение выполняется только через runtime/effects boundary.
- Интерфейсы (API/Telegram) остаются тонкими и не содержат бизнес-решений.

---

## 2) Карта слоёв (архитектурно-инженерная)

### A. Boot и Runtime

Основные модули:
- `boot/*`
- `runtime/*`

Задачи:
- Сборка runtime-реестра и обязательных сервисов.
- Проверка boot-контракта и порядка манифеста.
- Экспорт типизированных runtime-провайдеров.
- Контроль создания критичных классов через фабрики/токены.

Гарантии:
- Нет обходной сборки runtime вне boot.
- Единый словарь runtime service names и регистраций.

### B. Application и decision-surface

Основные модули:
- `runtime/application/*`
- канонические decision/policy поверхности в `core/*`

Задачи:
- Преобразование входных данных в структурированное decision-намерение.
- Чистый recommendation-этап без side effects.

Гарантии:
- Нет скрытого исполнения в decision-слое.
- Нет неявной реконструкции transport payload в recommendation-этапе.

### C. Effects и интеграции

Основные модули:
- `runtime/_internal/effects_*`
- `interfaces/ads/*`
- bridge-модули в `core/behavior/integration/*`

Задачи:
- Исполнение внешних действий через контролируемые эффекты/порты.
- Инкапсуляция провайдер-специфики в адаптерах/коннекторах.

Гарантии:
- Сетевые маркеры не выходят за пределы разрешённых зон.
- Нет скрытых side effects в неподходящих слоях.

### D. Интерфейсы

Основные модули:
- `interfaces/api/*`
- `interfaces/telegram/*`
- `interfaces/behavior/*`

Задачи:
- Приём запроса, маппинг в контракт, вызов application service, презентация ответа.
- Разделение channel concerns и decision concerns.

Гарантии:
- Интерфейсы не получают доступ к runtime internals в обход канона.
- Telegram-runner работает через application service контракт.

### E. Infra, Governance, Compliance

Основные модули:
- `infra/*`

Задачи:
- Lifecycle, readiness, retry/idempotency, process-control.
- Approvals, policy versioning, decision ledger, promotion/rollback.
- Control-plane и compliance/audit сервисы.

Гарантии:
- Infra boot-модули не строят runtime напрямую.
- Governance/evidence разделены на отдельные bounded-модули.

### F. Behavior Engine

Основные модули:
- `core/behavior/contracts/*`
- `core/behavior/math/*`
- `core/behavior/operators/*`
- `core/behavior/builders/*`
- `core/behavior/observables/*`
- `core/behavior/constraints/*`
- `core/behavior/read_models/*`
- `core/behavior/operator_catalogs/*`
- `core/behavior/operator_policy_catalogs/*`
- `core/behavior/guards/*`
- `core/behavior/runtime/*`
- `core/behavior/persistence/*`
- `core/behavior/integration/*`

Задачи:
- Сбор behavioral state из событий.
- Применение ограниченной операторной математики.
- Формирование неисполняемых ограничений/наблюдаемых метрик.
- Безопасный bridge к pricing/offer/retention/runtime.

Гарантии:
- Behavior payload остаётся неисполняемым.
- Скрытые ключи выбора и обходные decision-поля запрещены.
- Policy denials трассируются и наблюдаются.

### G. Observability

Основные модули:
- `observability/*`
- telemetry-слой в runtime/behavior bridges

Задачи:
- Метрики, трассировка, структурированные события.
- Операционная видимость decision/runtime/governance поведения.

---

## 3) Сквозной поток (end-to-end)

1. Вход в систему через API/Telegram интерфейс.
2. Интерфейс маппит запрос в application-контракт.
3. Boot-собранный application service направляет запрос в канонический decision-path.
4. Decision/recommendation этап формирует намерение без side effects.
5. Runtime исполняет эффекты через контролируемые порты/адаптеры.
6. Governance/control-plane может подтвердить, ограничить, эскалировать, откатить.
7. Audit и telemetry фиксируют трассу действий.
8. Интерфейс возвращает результат пользователю/оператору.

---

## 4) Полный пользовательский функционал

- Работа через API и Telegram как единые входы.
- Управляемое выполнение действий с safety-ограничениями.
- Governance-функции:
  - approvals,
  - policy versioning,
  - release promotion и rollback,
  - evidence/constitutional tracking.
- Повышенная надёжность в production:
  - retry, idempotency, readiness/lifecycle.
- Прозрачность для оператора:
  - audit trail,
  - decision/evidence packets,
  - observability сигналы.
- Behavior-интеллект:
  - расчёт поведенческих ограничений и observables,
  - интеграция в pricing/offer/retention без второго мозга.

---

## 5) Архитектурные инварианты

Проверяются lock-тестами (`tests/arch` и связанные строгие проверки):
- единый decision-center;
- запрет скрытой бизнес-логики в неразрешённых слоях;
- запрет несанкционированного доступа к runtime registry;
- запрет ручного создания критичных sealed runtime-классов;
- запрет сетевой активности вне разрешённых effects-периметров;
- Canon FS правила доменной структуры;
- release attestation через `release/manifest.json`.

Практический смысл:
- Новый модуль добавляется только в корректную роль слоя.
- Межслойные зависимости идут только по разрешённому направлению.
- Compat/legacy допускаются только как тонкие alias-shim без логики.

---

## 6) Политика совместимости и legacy

- Реализация живёт в canonical-модулях.
- Legacy-модули, если нужны, остаются только тонкими alias-шлюзами.
- Новые фичи не создают новые legacy/compat ветки.
- Удаление legacy — только после доказанного нулевого импорта и зелёного регресса.

---

## 7) Инженерные quality-gates

Обязательные:
- `pytest -q tests/arch`
- `pytest -q --maxfail=20`
- очистка артефактов (`__pycache__`, `.pyc`, tool caches)
- регенерация и верификация `release/manifest.json` при изменениях состава/содержимого релизных файлов

Рекомендуемые:
- целевые тест-паки по затронутому домену (behavior/infra/interfaces/ads и т.д.).

---

## 8) Безопасный вектор развития

- Углубление validation для behavior catalogs/policy catalogs.
- Расширение governance evidence и операторской аналитики.
- Поэтапное удаление legacy после подтверждённой канонизации.
- Дальнейшее утончение interface-слоёв без переноса туда decision-логики.

Неподвижный принцип:
- Нет второго decision-path, нет скрытого исполнения, нет нетрассируемых side effects.
