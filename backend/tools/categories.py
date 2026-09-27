"""
Категоризация трат и поиск перерасхода.

Все расчёты выполняются кодом. В каждой категории — список операций
(дата, сумма, описание), чтобы на UI можно было раскрыть детали.
"""

from collections import defaultdict


CATEGORY_LIMITS = {
    "еда": 0.40,
    "транспорт": 0.15,
    "кофе": 0.08,
    "доставка": 0.15,
    "маркетплейс": 0.20,
    "развлечения": 0.15,
    "кредитка": 0.25,
    "прочее": 0.20,
}


def _fmt_date_ru(value: str) -> str:
    try:
        y, m, d = value.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return value or ""


def analyze_categories(profile: dict, top_n: int = 3) -> dict:
    transactions = profile.get("transactions", [])
    if not transactions:
        return {
            "ok": False,
            "reason": "Нет данных о тратах.",
        }

    by_category = defaultdict(float)
    count_by_category = defaultdict(int)
    txs_by_category = defaultdict(list)

    for tx in transactions:
        cat = tx.get("category", "прочее")
        amount = float(tx.get("amount", 0))
        by_category[cat] += amount
        count_by_category[cat] += 1
        txs_by_category[cat].append({
            "date": tx.get("date"),
            "date_ru": _fmt_date_ru(tx.get("date", "")),
            "amount": amount,
            "description": tx.get("description") or cat,
            "category": cat,
        })

    total = sum(by_category.values())
    if total <= 0:
        return {
            "ok": False,
            "reason": "Сумма трат равна нулю, анализировать нечего.",
        }

    categories = []
    for name, amount in by_category.items():
        share = round(amount / total, 4)
        limit = CATEGORY_LIMITS.get(name, 0.20)
        over = share > limit
        over_amount = round((share - limit) * total, 2) if over else 0.0
        items = sorted(
            txs_by_category[name],
            key=lambda t: t.get("date") or "",
            reverse=True,
        )

        categories.append({
            "name": name,
            "total": round(amount, 2),
            "count": count_by_category[name],
            "share": share,
            "limit": limit,
            "over_limit": over,
            "over_amount": over_amount,
            "transactions": items,
        })

    categories.sort(key=lambda c: c["total"], reverse=True)
    overspending = [c for c in categories if c["over_limit"]]
    top = categories[:top_n]

    return {
        "ok": True,
        "total": round(total, 2),
        "categories": categories,
        "overspending": overspending,
        "top": top,
    }
