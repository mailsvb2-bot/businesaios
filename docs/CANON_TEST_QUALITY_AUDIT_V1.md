# CANON_TEST_QUALITY_AUDIT_V1

Цель:
не дать canonical arch-tests деградировать из реальных архитектурных замков в декоративные файлы.

## Главный закон

Arch-test считается настоящим только если он реально проверяет архитектурное свойство.

## Минимальные признаки качественного arch-test

Arch-test должен делать хотя бы одно из:
- анализировать AST
- анализировать imports
- анализировать filesystem/path presence
- проверять canonical marker presence
- проверять helper-driven predicates

## Architectural meaning

Если test quality audit соблюдён:
- lock-tests труднее тихо ослабить
- CI проверяет реальную архитектуру, а не ритуальные файлы
