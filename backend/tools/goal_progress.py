"""
Прогресс к финансовой цели.

Логика:
1. Если цели нет — сообщаем и предлагаем создать.
2. Если цель есть — считаем:
   - сколько уже накоплено,
   - сколько осталось,
   - какая доля пройдена,
   - сколько нужно откладывать в день, чтобы успеть к сроку.
"""

from datetime import datetime
from typing import Optional


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def get_goal_progress(profile: dict) -> dict:
    """
    Считает прогресс по цели накопления.

    Возвращает:
    - ok: bool
    - reason: str, если не удалось
    - name: str — название цели
    - target: float — целевая сумма
    - saved: float — уже накоплено
    - remaining: float — осталось накопить
    - progress: float — доля от 0 до 1
    - needed_per_day: float — сколько откладывать в день
    - days_left: int — сколько дней до срока
    """

    goal: Optional[dict] = profile.get("goal")
    if not goal:
        return {
            "ok": False,
            "reason": "Цель накопления не задана.",
        }

    target = float(goal.get("target", 0))
    saved = float(goal.get("saved", 0))

    if target <= 0:
        return {
            "ok": False,
            "reason": "Некорректная цель: сумма должна быть больше нуля.",
        }

    remaining = max(target - saved, 0.0)
    progress = round(min(saved / target, 1.0), 4)

    # Срок — до следующего дохода (для простоты MVP).
    next_income_raw = profile.get("next_income_date")
    days_left = None
    needed_per_day = None

    if next_income_raw:
        today = _parse_date(profile["today"])
        next_income = _parse_date(next_income_raw)
        days_left = (next_income - today).days
        if days_left > 0:
            needed_per_day = round(remaining / days_left, 2)

    # Проверяем, реалистичен ли темп накопления относительно дневного лимита.
    warning = None
    daily_limit = profile.get("_daily_limit")
    if daily_limit is None:
        try:
            from tools.daily_limit import calculate_daily_limit
            dl = calculate_daily_limit(profile)
            if dl.get("ok"):
                daily_limit = dl["daily_limit"]
        except Exception:
            daily_limit = None
    if needed_per_day and daily_limit is not None and needed_per_day > daily_limit:
        warning = (
            f"При текущем дневном лимите ({int(round(daily_limit))} ₽) "
            f"откладывать {int(round(needed_per_day))} ₽ в день не получится. "
            f"Можно продлить срок цели или сократить траты."
        )

    return {
        "ok": True,
        "name": goal.get("name", "цель"),
        "target": round(target, 2),
        "saved": round(saved, 2),
        "remaining": round(remaining, 2),
        "progress": progress,
        "days_left": days_left,
        "needed_per_day": needed_per_day,
        "warning": warning,
    }