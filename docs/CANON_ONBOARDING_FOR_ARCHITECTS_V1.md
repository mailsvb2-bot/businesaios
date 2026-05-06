# CANON ONBOARDING FOR ARCHITECTS V1

CANON_META_PACK: TRUE

Цель:
дать один жёсткий onboarding для любого нового архитектора, нового чата или нового прохода по проекту.

## Начинать только отсюда

Перед любыми:
- патчами
- рефакторингом
- добавлением доменов
- boot/runtime изменениями
- legacy cleanup
- AI/ML integration

обязательно прочитать:
1. `docs/CANON_META_PACK_INDEX_V1.md`
2. `docs/CANON_META_PACK_MANIFEST_V1.yaml`
3. `docs/CANON_RED_FLAGS_CHECKLIST_V1.md`
4. `docs/CANON_DECISION_SPACE_LOCKS_V1.md`
5. `docs/CANON_TYPESTATE_CAPABILITIES_V1.md`

## Главные запреты

Нельзя:
- second brain
- bypass DecisionCore
- hidden issuer
- distributed pre-decision
- runtime handlers with business decision power
- boot with decision/apply power
- domain drift outside canonical shape

## Главные разрешённые формы

Можно только:
- enrich
- explain
- score
- observe
- validate
- guard
- read
- write
- project
- build advisory payload

## Канонический shape нового домена

Минимум:
- `contracts.py`
- `types.py`
- `errors.py`
- `service.py`

## Канонический shape runtime

### runtime/handlers/*
- `CANON_THIN_HANDLER = True`
- только thin entrypoint
- parse / validate / map / call service / return dto

### runtime/boot/*
- `CANON_BOOT_WIRING_ONLY = True`
- только wiring / register / bind / assemble

## Если нужен отход от канона

Нельзя делать это молча.

Нужно:
1. оформить exception в `CANON_EXCEPTION_REGISTRY_DATA_V1.yaml`
2. если это migration — оформить в `CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml`
3. не делать бессрочных исключений
4. не делать исключений без owner и срока

## Главный operational rule

Если сомневаешься:
- не расширяй власть модуля
- не добавляй hidden selection
- не сужай action space
- не подсовывай default outcome
- не создавай новый центр координации
