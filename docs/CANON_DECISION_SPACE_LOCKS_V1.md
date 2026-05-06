# CANON DECISION SPACE LOCKS V1

Цель:
защищать не только final issuer boundary, но и само пространство решения до входа в DecisionCore.

## Главный закон

Нельзя проверять только:
- кто выпускает final decision

Нужно также проверять:
- кто сужает пространство решений
- кто скрыто выбирает победителя
- кто подсовывает outcome-determining default
- кто заранее превращает множество вариантов в один

## Что разрешено

Чувствительные домены (`ml`, `reward`, `growth`, `economics`) могут только:
- enrich
- explain
- score
- observe
- read
- write
- project
- validate
- guard

## Что запрещено

Чувствительные домены и чувствительные runtime handlers не имеют права:
- silently filter action space
- auto-select winner
- define `default_action`
- define `fallback_action`
- define `recommended_action`
- define `final_action`
- define `resolved_action`
- use `sorted(...)[0]`, `max(...)`, `min(...)`, `next(...)` to preselect candidate-like sets
- import runtime/apply/execution/issuer flow
- import legacy implementations into active flow
