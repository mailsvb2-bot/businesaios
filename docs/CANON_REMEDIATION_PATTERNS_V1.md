# CANON REMEDIATION PATTERNS V1

Цель:
исправлять падения decision-space arch-lock тестов без появления второго мозга.

## Основной remediation-паттерн

Если модуль в `growth`, `reward`, `economics`, `ml` сейчас:
- выбирает победителя
- фильтрует кандидатов
- подставляет `default_action`
- делает `sorted(...)[0]`
- делает `max(...)` / `min(...)` / `next(...)`
- возвращает один "лучший" business outcome

его нужно переделывать не в "умнее select", а в одну из ролей:
- score
- observe
- explain
- enrich

## Главный смысл

Sensitive domains не имеют права уменьшать пространство решения до DecisionCore.

Они могут делать пространство решения более информированным, но не более узким.
