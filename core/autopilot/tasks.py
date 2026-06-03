from __future__ import annotations

"""Human tasks generator (deterministic).

Autopilot should always output 1-3 concrete tasks for the owner.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
from collections.abc import Mapping


@dataclass(frozen=True)
class TaskItem:
    task_id: str
    title: str
    details: str
    priority: int = 1


def build_tasks_from_diagnostics(diag: Mapping[str, Any]) -> list[TaskItem]:
    """Build 1-3 tasks based on the diagnostic answers."""

    offer = str(diag.get("offer") or "").strip()
    channel = str(diag.get("channel") or "internal").strip() or "internal"

    tasks: list[TaskItem] = []
    # Task 1: make the offer concrete
    if not offer:
        tasks.append(
            TaskItem(
                task_id="task_offer",
                title="Сформулировать оффер",
                details="Напиши 1-2 предложения: что продаём, для кого, результат, цена/условия.",
                priority=1,
            )
        )
    # Task 2: collect proof
    tasks.append(
        TaskItem(
            task_id="task_proof",
            title="Собрать доказательства",
            details="Сделай 1 кейс/отзыв: фото/текст + короткий результат. Это поднимет конверсию без бюджета.",
            priority=1,
        )
    )
    # Task 3: inbox hygiene if internal
    if channel == "internal":
        tasks.append(
            TaskItem(
                task_id="task_speed",
                title="Ответить быстрее",
                details="Сегодня ответь на 5 входящих быстрее 5 минут. Скорость ответа — самый дешёвый рост.",
                priority=2,
            )
        )
    tasks.sort(key=lambda t: int(t.priority))
    return tasks[:3]


def serialize_tasks(tasks: list[TaskItem]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tasks:
        out.append({"task_id": t.task_id, "title": t.title, "details": t.details, "priority": int(t.priority)})
    return out
