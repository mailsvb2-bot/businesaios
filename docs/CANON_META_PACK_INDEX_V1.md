# CANON META PACK INDEX V1

CANON_META_PACK: TRUE

Цель:
дать один явный вход в архитектурную конституцию репозитория.

## Главный закон

Если новый архитектор, новый чат или новый проход не знает,
с чего начинать чтение канона,
он обязан начинать отсюда.

Этот файл — единый вход в canonical meta-pack.

## Что входит в canonical meta-pack в текущем staged-состоянии

### 1. Red flags
- `docs/CANON_RED_FLAGS_CHECKLIST_V1.md`

### 2. Decision-space
- `docs/CANON_DECISION_SPACE_LOCKS_V1.md`
- `docs/CANON_REMEDIATION_PATTERNS_V1.md`

### 3. Typestate / capabilities
- `docs/CANON_TYPESTATE_CAPABILITIES_V1.md`

### 4. Boot/runtime registry
- `docs/CANON_BOOT_RUNTIME_REGISTRY_AUDIT_V1.md`
- `docs/CANON_BOOT_RUNTIME_REGISTRY_REMEDIATION_V1.md`

### 5. Domain registry
- `docs/CANON_DOMAIN_REGISTRY_AUDIT_V1.md`
- `docs/CANON_DOMAIN_REGISTRY_REMEDIATION_V1.md`

### 6. Test quality
- `docs/CANON_TEST_QUALITY_AUDIT_V1.md`
- `docs/CANON_TEST_QUALITY_REMEDIATION_V1.md`

### 7. Exception registry
- `docs/CANON_EXCEPTION_REGISTRY_V1.md`
- `docs/CANON_EXCEPTION_REGISTRY_REMEDIATION_V1.md`
- `docs/CANON_EXCEPTION_REGISTRY_DATA_V1.yaml`

### 8. Migration / deprecation registry
- `docs/CANON_MIGRATION_DEPRECATION_REGISTRY_V1.md`
- `docs/CANON_MIGRATION_DEPRECATION_REMEDIATION_V1.md`
- `docs/CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml`

### 9. Audit layer
- `tests/arch/_canon_arch_audit_index.py`

### 10. Onboarding
- `docs/CANON_ONBOARDING_FOR_ARCHITECTS_V1.md`

### 11. Machine-readable manifest
- `docs/CANON_META_PACK_MANIFEST_V1.yaml`

## Обязательное правило для новых проходов

Любой новый архитектор, новый чат, новый патч-проход обязан:
1. начать с `CANON_META_PACK_INDEX_V1.md`
2. прочитать `CANON_ONBOARDING_FOR_ARCHITECTS_V1.md`
3. свериться с `CANON_META_PACK_MANIFEST_V1.yaml`
4. не добавлять новые канонические правила мимо meta-pack

## Важное staged-правило

Нельзя перечислять в meta-pack файлы, которых ещё нет в репозитории.
Сначала файл реально появляется,
потом попадает в manifest и audit index.
