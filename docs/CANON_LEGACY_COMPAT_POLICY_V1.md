# CANON LEGACY COMPAT POLICY V1

Цель:
разрешить временные compat/shim слои, но не дать им снова превратиться в параллельную архитектуру.

## Правила

Compat / shim слой может:
- re-export
- bridge import paths
- preserve backwards compatibility
- delegate to canonical implementation

Compat / shim слой не может:
- содержать новую бизнес-логику
- принимать финальные решения
- выбирать победителя
- иметь собственный execution-path
- расходиться по поведению с canonical surface

## Обязательное правило

Если модуль является compat/shim-слоем, это должно быть явно обозначено:
- в docstring
или
- в CANON marker
или
- в namespace role doc
