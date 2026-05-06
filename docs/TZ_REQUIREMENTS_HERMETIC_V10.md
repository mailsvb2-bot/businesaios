# BusinesAIOS — уточнение требований ТЗ (V11 Hermetic)

> NON-NORMATIVE DOCUMENT (Appendix).
> Canonical spec: docs/SYSTEM_TZ_CANONICAL.md


Этот документ **не заменяет** «Единую системную конституцию». Он фиксирует
дополнительные **жёсткие, проверяемые инварианты**, которые были введены
в сборке **V11 Hermetic** и закреплены тестами.

## 1. Термины

**Production (prod)** — `ENV=prod` или `ENV=production`.

**Strict economic mode** — режим, в котором Economic Autonomy Layer
является **частью исполняемого закона** и способен блокировать исполнение.

## 2. Инвариант: единственный production entrypoint

### Требование

В корне репозитория разрешены **только** следующие Python-файлы:

- `main.py`
- `sitecustomize.py`
- `usercustomize.py`

Любой другой `*.py` в корне репозитория считается:

**ARCHITECTURAL FAILURE: MULTIPLE ENTRYPOINTS / BYPASS RISK**

### Проверка

Закреплено тестом:

- `tests/test_root_py_whitelist.py`

## 3. Инвариант: legacy entrypoints запрещены в production root

### Требование

Legacy/демо entrypoints (например `runtime_execution.py`, `policy_loop.py`,
`state_and_envelope.py`) **не должны** существовать в production-root.

Если такие файлы нужны для исследований, они допускаются только в:

- `experimental/legacy_runtime/`

### Проверка

Закреплено тестом:

- `tests/test_no_legacy_entrypoints.py`

## 4. Инвариант: production код не импортирует experimental/examples

### Требование

Ни один модуль из следующих областей production-кода:

- `core/`
- `runtime/`
- `platform_layer/` (или инфраструктурный слой)
- `services/`
- `ml/`
- `governance/`
- `formal/`
- `main.py`

не имеет права импортировать:

- `experimental.*`
- `examples.*`

Любой импорт в production-коде считается:

**ARCHITECTURAL FAILURE: RESEARCH IN PROD PATH**

### Проверка

Закреплено тестом:

- `tests/test_examples_not_imported.py`

## 5. Закон: prod ⇒ strict economic governance

### Требование

В production экономический контур обязан быть строгим:

- `is_strict_mode()` **должен возвращать `True`** при `ENV in {prod, production}`.
- В non-production strict включается только флагом `ECONOMIC_STRICT=1`.

### Следствия strict режима

Если strict включён, Economic Autonomy Layer обязана **блокировать исполнение**, если:

- отсутствует `world_state.capital`
- отсутствует `world_state.horizon_state`
- `capital_limit` (недостаточно капитала по правилам)
- `myopic_decision` (вето стратегического горизонта)

Это требование вводит “экономический закон” как часть chain-of-trust
между DecisionCore и RuntimeExecutor.

### Проверка

Закреплено тестами:

- `tests/test_economic_strict_prod.py`

## 6. Инвариант: SQLite не должен подтягиваться имплицитно в prod

### Требование

Импорты SQLite-реализаций **запрещены на уровне module import time**
для production entrypoint и инфраструктурных пакетов.

SQLite допускается только:

- в dev/test ветке wiring (ленивые импорты внутри функций)
- внутри конкретных backend-модулей (`.../sqlite_*.py`)

### Мотивация

Это устраняет класс ошибок “production процесс неожиданно использует SQLite”
из-за импорта по умолчанию.

---

## 7. Статус

Требования этого документа считаются **частью ТЗ** на уровне “закона”,
так как закреплены тест-инвариантами и предотвращают архитектурную деградацию.

## 8. Release hygiene (чистота релиза)

### Требование

Перед упаковкой любого релиза **обязательно** удаляются:

- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`

Наличие этих артефактов в релизном архиве считается:

**RELEASE BLOCKER: DIRTY RELEASE ARTIFACTS**

### Реализация

В репозитории обязаны существовать скрипты:

- `scripts/clean_artifacts.sh`
- `scripts/release_pack.sh`

где `release_pack.sh` выполняет: clean → tests → clean → pack.

## 9. Семантический bypass “вторых мозгов”

### Требование

В production-коде запрещены:

- любые определения `def decide(...)` вне `core/ai/decision_core.py`
- любые вызовы `.decide(...)` вне `core/ai/decision_core.py` и фасада-прокси (в текущей сборке допускается `main.py`).

Мотивация: устранить “шарнирность” и вторичные центры решений.

### Проверка

Закреплено AST-тестом:

- `tests/test_no_semantic_decide_bypass_ast.py`
