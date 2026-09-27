"""
Проверка риска по кредитной карте.

Логика:
1. Если в транзакциях есть операции по кредитке — считаем, сколько потрачено.
2. Проверяем, покрывает ли текущий баланс эти траты.
3. Если нет — предупреждаем о возможной переплате.
4. Показываем пользователю на цифрах, что произойдёт, если не погасить вовремя.

Все расчёты кодом. LLM только объясняет.
"""

from datetime import datetime


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


# Ставка по кредитке для примера (в реальности берётся из договора).
CREDIT_RATE_ANNUAL = 0.25  # 25% годовых

# Льготный период по умолчанию.
GRACE_PERIOD_DAYS = 120


def check_credit_risk(profile: dict) -> dict:
    """
    Проверяет риск по кредитной карте.

    Возвращает:
    - ok: bool
    - reason: str, если нет данных по кредитке
    - used: float — сколько потрачено с кредитки
    - balance: float — текущий баланс
    - can_repay: bool — хватает ли баланса на погашение
    - grace_period_days: int
    - daily_interest: float — примерная переплата за день просрочки
    - warning: str — текстовое предупреждение
    """

    transactions = profile.get("transactions", [])
    credit_tx = [tx for tx in transactions if tx.get("category") == "кредитка"]

    if not credit_tx:
        return {
            "ok": False,
            "reason": "Операций по кредитной карте не найдено.",
        }

    used = round(sum(float(tx["amount"]) for tx in credit_tx), 2)
    balance = float(profile.get("balance", 0))

    can_repay = balance >= used

    # Примерная переплата за один день просрочки.
    daily_interest = round(used * CREDIT_RATE_ANNUAL / 365, 2)

    if can_repay:
        warning = (
            f"Вы потратили с кредитки {used} ₽. "
            f"Баланса хватает, чтобы погасить долг полностью до конца льготного периода "
            f"({GRACE_PERIOD_DAYS} дней)."
        )
    else:
        shortfall = round(used - balance, 2)
        warning = (
            f"Вы потратили с кредитки {used} ₽. "
            f"Баланса не хватает: не хватает {shortfall} ₽. "
            f"Если не погасить до конца льготного периода, начнётся переплата "
            f"примерно {daily_interest} ₽ в день."
        )

    return {
        "ok": True,
        "used": used,
        "balance": round(balance, 2),
        "can_repay": can_repay,
        "grace_period_days": GRACE_PERIOD_DAYS,
        "daily_interest": daily_interest,
        "warning": warning,
    }