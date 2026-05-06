# CI/CD Canon V7 Project

Этот контур подстроен под текущий проект и добавляет matrix/hardening для GitHub Actions.

## Уже учтено под проект
- существующие `ci-guard` и `ci-locks` в `Makefile`
- существующий `pytest.ini`
- существующий `ruff.toml`
- существующие shell-проверки `ci/check_prod_strict.sh` и `ci/check_locks.sh`
- существующие `tests/arch`, `tests/lock`, `tests/unit`, `tests/runtime`
- существующий `requirements.lock.txt`

## Один центр принятия решений
Единственная внешняя точка входа:
- `scripts/ci/cli.py`

Единственная orchestration-точка:
- `scripts/ci/execution.py`

Единственный источник порядка шагов:
- `scripts/ci/plan_registry.py`

## Новый self-check слой
- `scripts/ci/doctor.py`
- gate `doctor`
- step `doctor-check`

## GitHub Actions hardening
- отдельный workflow `ci-doctor.yml`
- matrix Python `3.11` и `3.12`
- `fail-fast: false`
- `cache-dependency-path` с:
  - `requirements.txt`
  - `requirements.optional.txt`
  - `requirements.lock.txt`

## Gate-контуры
- `doctor`
- `fast`
- `full`
- `release`
- `pre-push`
- `pre-release`

## Marker discipline
- `asyncio`
- `gate`
- `lock`
- `slow`
- `integration`
- `arch`

## Make targets
- `make ci-bootstrap`
- `make ci-doctor`
- `make ci-fast`
- `make ci-full`
- `make ci-release`
- `make ci-pre-push`
- `make ci-pre-release`
- `make ci-install-hooks`
