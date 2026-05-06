# CANON_DOMAIN_REGISTRY_AUDIT_V1

Цель:
зафиксировать канонический шаблон домена и не дать новым каноническим доменам появляться в произвольной форме.

## Staged canonical scope

В этом проекте audit применяется в первую очередь к явным canonical domains:
- доменам с `__canon_domain__.py`
- доменам, которые уже оформлены как canonical surface

## Минимальный канонический каркас домена

Каждый canonical domain должен иметь:
- `contracts.py`
- `types.py`
- `errors.py`
- `service.py`

## Architectural meaning

Если canonical domain registry audit соблюдён:
- новые канонические домены появляются читаемо
- каркас домена остаётся предсказуемым
- второй мозг труднее спрятать в структуре
