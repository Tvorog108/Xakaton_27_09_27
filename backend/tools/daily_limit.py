"""
Расчёт безопасного дневного лимита трат до следующего поступления.

Логика:
1. Берём текущий баланс.
2. Вычитаем все регулярные платежи, которые будут списаны до следующего дохода.
3. Оставляем часть баланса нетронутой — "подушку" (по умолчанию 10%).
4. Остаток делим на количество дней до следующего дохода.

Этот модуль НЕ использует LLM. Все расчёты выполняются кодом.
"""

from datetime import date, datetime
from typing import Optional


# Доля баланса, которую не трогаем — оставляем на непредвиденное.
RESERVE_SHARE = 0.10


def _parse_date(value: str) -> date:
    """Преобразует строку 'YYYY-MM-DD' в объект date."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def calculate_daily_limit(profile: dict) -> dict:
    """
    Считает безопасный дневной лимит для профиля.

    Возвращает словарь с результатом:
    - ok: bool — удалось ли посчитать
    - reason: str — если не удалось, объяснение
    - daily_limit: float — безопасная сумма на день
    - days_left: int — сколько дней осталось до следующего дохода
    - balance: float — текущий баланс
    - subscriptions_total: float — сумма обязательных платежей
    - reserve: float — отложенная "подушка"
    - available: float — доступно к тратам всего
    """

    # Проверяем, есть ли дата следующего дохода.
    next_income_raw: Optional[str] = profile.get("next_income_date")
    if not next_income_raw:
        return {
            "ok": False,
            "reason": "Недостаточно данных для расчёта дневного лимита. Укажите дату следующего поступления.",
        }

    next_income = _parse_date(next_income_raw)
    today = _parse_date(profile["today"])

    days_left = (next_income - today).days
    if days_left <= 0:
        return {
            "ok": False,
            "reason": "Дата следующего дохода уже прошла или совпадает с сегодняшним днём. Уточните данные.",
        }

    balance = float(profile.get("balance", 0))

    # Считаем все обязательные платежи до следующего дохода.
    subscriptions_total = 0.0
    for sub in profile.get("subscriptions", []):
        payment_date = _parse_date(sub["next_payment"])
        if today <= payment_date <= next_income:
            subscriptions_total += float(sub["amount"])

    # Откладываем резерв — 10% от баланса.
    reserve = round(balance * RESERVE_SHARE, 2)

    # Свободные деньги = баланс - обязательные платежи - резерв.
    available = balance - subscriptions_total - reserve
    if available < 0:
        available = 0.0

    daily_limit = round(available / days_left, 2)

    return {
        "ok": True,
        "daily_limit": daily_limit,
        "days_left": days_left,
        "balance": balance,
        "subscriptions_total": round(subscriptions_total, 2),
        "reserve": reserve,
        "available": round(available, 2),
    }


def _fmt_money(x) -> str:
    return str(int(round(float(x))))


def what_if_spend(profile: dict, amount: float) -> dict:
    """
    Считает, что будет с дневным лимитом и целью, если пользователь
    потратит amount рублей прямо сейчас.

    Возвращает:
    - ok: bool
    - reason: str, если не удалось
    - amount: float — сколько планируется потратить
    - current_limit: float — текущий дневной лимит
    - new_limit: float — новый дневной лимит после траты
    - limit_diff: float — на сколько уменьшится лимит
    - goal_impact: dict | None — влияние на цель
    """

    if amount <= 0:
        return {"ok": False, "reason": "Сумма траты должна быть больше нуля."}

    # Текущий лимит.
    current = calculate_daily_limit(profile)
    if not current.get("ok"):
        return {"ok": False, "reason": current.get("reason", "Не удалось посчитать лимит.")}

    current_limit = current["daily_limit"]
    days_left = current["days_left"]

    # Считаем новый лимит: как будто трата уже произошла.
    # Баланс уменьшается на amount, остальное по той же формуле.
    new_balance = profile["balance"] - amount
    if new_balance < 0:
        new_balance = 0.0

    # Копируем профиль и подменяем баланс.
    simulated = dict(profile)
    simulated["balance"] = new_balance
    new_result = calculate_daily_limit(simulated)
    new_limit = new_result["daily_limit"] if new_result.get("ok") else 0.0
    limit_diff = round(current_limit - new_limit, 2)

    # Влияние на цель.
    goal_impact = None
    goal = profile.get("goal")
    if goal:
        saved = float(goal.get("saved", 0))
        target = float(goal.get("target", 0))
        remaining = target - saved
        new_saved = saved  # трата уменьшает баланс, но не накопления напрямую
        # Трата уменьшает возможность откладывать.
        # Считаем, сколько дней потребуется, чтобы добрать остаток при новом лимите.
        if new_limit > 0:
            days_at_new_rate = round(remaining / new_limit, 1) if new_limit > 0 else None
        else:
            days_at_new_rate = None

        goal_impact = {
            "name": goal.get("name", "цель"),
            "remaining": round(remaining, 2),
            "days_at_new_rate": days_at_new_rate,
        }

    # Уже потрачено сегодня (если есть операции на profile["today"])
    today = profile.get("today")
    today_spent = 0.0
    if today:
        today_spent = round(
            sum(float(t["amount"]) for t in profile.get("transactions", []) if t.get("date") == today),
            2,
        )
    planned_total_today = round(today_spent + amount, 2)
    overspend_today = round(planned_total_today - current_limit, 2)
    exceeds_today = planned_total_today > current_limit

    # Сколько «съедает» из бюджета на оставшиеся дни (пересчёт лимита)
    per_day_hit = round(limit_diff, 2) if limit_diff > 0 else 0.0

    parts = []
    # 1) Факт про СЕГОДНЯ
    if exceeds_today:
        parts.append(
            f"Лимит на сегодня — {_fmt_money(current_limit)} ₽, а трата {_fmt_money(amount)} ₽ "
            f"{('(плюс уже потрачено сегодня ' + _fmt_money(today_spent) + ' ₽) ') if today_spent else ''}"
            f"превышает его на {_fmt_money(overspend_today)} ₽. Сегодня лимит будет исчерпан с перерасходом."
        )
    else:
        left_today = round(current_limit - planned_total_today, 2)
        parts.append(
            f"Трата {_fmt_money(amount)} ₽ укладывается в сегодняшний лимит {_fmt_money(current_limit)} ₽ "
            f"(останется ~{_fmt_money(left_today)} ₽ на день)."
        )

    # 2) Влияние на следующие дни
    if new_limit <= 0:
        parts.append(
            f"После этой траты свободных денег до поступления ({days_left} дн.) по расчёту не останется — "
            f"дневной лимит станет 0 ₽."
        )
    else:
        parts.append(
            f"После списания {_fmt_money(amount)} ₽ из баланса безопасный лимит "
            f"на каждый из оставшихся {days_left} дн. пересчитается: "
            f"{_fmt_money(new_limit)} ₽/день (было {_fmt_money(current_limit)} ₽/день)."
        )

    verdict = " ".join(parts)

    return {
        "ok": True,
        "amount": round(amount, 2),
        "current_limit": current_limit,
        "new_limit": new_limit,
        "limit_diff": limit_diff,
        "per_day_hit": per_day_hit,
        "days_left": days_left,
        "today_spent": today_spent,
        "planned_total_today": planned_total_today,
        "overspend_today": overspend_today if exceeds_today else 0.0,
        "exceeds_today": exceeds_today,
        "goal_impact": goal_impact,
        "verdict": verdict,
    }