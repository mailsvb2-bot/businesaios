# CANON EXCEPTION REGISTRY V1

Цель:
сделать любые отступления от канона явными, ограниченными и проверяемыми.

## Главный закон

Если исключение из канона не внесено в exception registry,
то это не исключение, а нарушение архитектуры.

## Что считается исключением

Исключением считается любое осознанное отклонение от canonical rules, например:
- legacy module временно оставлен в активном дереве
- домен временно не соответствует canonical domain shape
- boot/runtime entrypoint временно требует нестандартной структуры
- import boundary временно ослаблен
- naming hotspot временно не устранён
- arch-test временно исключает конкретный файл или модуль
- capability rule временно ослаблен для одного пути

## Обязательные поля исключения

Каждое исключение обязано иметь:
1. `exception_id`
2. `scope`
3. `reason`
4. `owner`
5. `created_on`
6. `expires_on`
7. `canonical_rule`
8. `paths`
9. `status`

## Жёсткие правила

- без срока нельзя
- без owner нельзя
- без списка путей нельзя
- без canonical_rule нельзя
- expired exception = failure

## Разрешённые статусы

- `active`
- `expired`
- `closed`
