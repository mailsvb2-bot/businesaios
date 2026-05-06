# CANON_DOMAIN_REGISTRY_REMEDIATION_V1

Цель:
исправлять структуру canonical domains без god-domain и без semantic hotspots.

## Типовое исправление

Если canonical domain оформляется официально:
- boundary contracts -> `contracts.py`
- dataclass/value types -> `types.py`
- domain exceptions -> `errors.py`
- узкая service-role -> `service.py`

## Staged rule

Исторические домены не ломаются массовым переименованием.
Сначала audit применяется к canonical domains, затем исторические зоны постепенно переводятся в canonical shape.
