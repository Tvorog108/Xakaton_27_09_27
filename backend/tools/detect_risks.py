"""
Поиск финансовых рисков.

Все расчёты выполняются кодом. В details — конкретные операции,
чтобы на UI можно было раскрыть «из каких трат сложилось».
"""

from collections import defaultdict
from datetime import datetime
from statistics import mean


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _fmt_date_ru(value: str) -> str:
    """2026-09-15 → 15.09.2026"""
    try:
        d = _parse_date(value)
        return d.strftime("%d.%m.%Y")
    except Exception:
        return value


LARGE_TX_MULTIPLIER = 3.0
IMPULSIVE_COUNT_THRESHOLD = 3
SMALL_TX_LIMIT = 500


def _tx_item(tx: dict) -> dict:
    return {
        "date": tx.get("date"),
        "date_ru": _fmt_date_ru(tx.get("date", "")),
        "category": tx.get("category", "прочее"),
        "amount": float(tx.get("amount", 0)),
        "description": tx.get("description") or tx.get("category", "операция"),
    }


def detect_risks(profile: dict, daily_limit_result: dict | None = None) -> dict:
    transactions = profile.get("transactions", [])
    subscriptions = profile.get("subscriptions", [])

    if not transactions and not subscriptions:
        return {
            "ok": False,
            "reason": "Нет данных для анализа рисков.",
        }

    risks = []

    # 1. Крупные траты
    if transactions:
        amounts = [float(tx["amount"]) for tx in transactions]
        avg_amount = mean(amounts)
        threshold = avg_amount * LARGE_TX_MULTIPLIER

        for tx in transactions:
            amount = float(tx["amount"])
            if amount >= threshold and amount >= SMALL_TX_LIMIT:
                item = _tx_item(tx)
                risks.append({
                    "type": "large_transaction",
                    "severity": "medium",
                    "title": "Крупная трата",
                    "message": (
                        f"«{item['description']}» — {amount:.0f} ₽ "
                        f"({item['date_ru']}). Средний чек у вас ≈ {avg_amount:.0f} ₽."
                    ),
                    "details": {
                        "date": item["date"],
                        "date_ru": item["date_ru"],
                        "category": item["category"],
                        "amount": amount,
                        "average": round(avg_amount, 2),
                        "why": (
                            f"Сумма в {amount / avg_amount:.1f} раза больше среднего чека. "
                            "Такие траты сильнее бьют по дневному лимиту."
                        ),
                        "transactions": [item],
                    },
                })

    # 2. Импульсивный день — много мелких покупок
    by_day = defaultdict(list)
    for tx in transactions:
        if float(tx["amount"]) < SMALL_TX_LIMIT:
            by_day[tx["date"]].append(tx)

    for day, txs in sorted(by_day.items()):
        if len(txs) >= IMPULSIVE_COUNT_THRESHOLD:
            total = round(sum(float(t["amount"]) for t in txs), 2)
            items = [_tx_item(t) for t in txs]
            date_ru = _fmt_date_ru(day)
            risks.append({
                "type": "impulsive_day",
                "severity": "low",
                "title": "Много мелких трат за день",
                "message": (
                    f"{len(txs)} мелких покупок {date_ru} на {total:.0f} ₽. "
                    "По отдельности незаметно, вместе — заметная дыра в бюджете."
                ),
                "details": {
                    "date": day,
                    "date_ru": date_ru,
                    "count": len(txs),
                    "total": total,
                    "categories": sorted({t["category"] for t in txs}),
                    "why": (
                        "За один день несколько мелких трат (кофе, еда, транспорт). "
                        "Именно из таких дней часто «непонятно, куда ушли деньги»."
                    ),
                    "transactions": items,
                },
            })

    # 3. Подписки
    today = _parse_date(profile["today"])
    seen_names = set()
    for sub in subscriptions:
        name = sub["name"]
        if name in seen_names:
            risks.append({
                "type": "duplicate_subscription",
                "severity": "medium",
                "title": "Похожая подписка",
                "message": f"Подписка «{name}» встречается больше одного раза.",
                "details": {
                    "name": name,
                    "why": "Дубли подписок часто забывают отключить.",
                    "transactions": [],
                },
            })
        seen_names.add(name)

        payment_date = _parse_date(sub["next_payment"])
        days_until = (payment_date - today).days
        if 0 <= days_until <= 3:
            risks.append({
                "type": "upcoming_subscription",
                "severity": "low",
                "title": "Скоро спишется подписка",
                "message": (
                    f"«{name}» — {sub['amount']} ₽ "
                    f"({_fmt_date_ru(sub['next_payment'])}, через {days_until} дн.)."
                ),
                "details": {
                    "name": name,
                    "amount": sub["amount"],
                    "date": sub["next_payment"],
                    "date_ru": _fmt_date_ru(sub["next_payment"]),
                    "days_until": days_until,
                    "why": "Учтено в обязательных платежах при расчёте дневного лимита.",
                    "transactions": [],
                },
            })

    # 4. Нет свободных денег
    if daily_limit_result and daily_limit_result.get("ok"):
        daily_limit = daily_limit_result["daily_limit"]
        if daily_limit <= 0:
            risks.append({
                "type": "no_money_left",
                "severity": "high",
                "title": "Лимит исчерпан",
                "message": "Свободных денег до следующего дохода по расчёту не осталось.",
                "details": {
                    "daily_limit": daily_limit,
                    "why": "Баланс после подписок и резерва не покрывает оставшиеся дни.",
                    "transactions": [],
                },
            })

    return {
        "ok": True,
        "risks": risks,
        "total_risks": len(risks),
    }
