"""
Проверка расчёта дневного лимита на трёх профилях.
Запуск: python tests/test_daily_limit.py
"""

import json
import os
import sys

# Чтобы импортировать модуль из backend/tools
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend", "tools"))
from daily_limit import calculate_daily_limit  # noqa: E402


def load_profile(name: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    for filename in ["profile_1.json", "profile_2.json", "profile_3.json"]:
        profile = load_profile(filename)
        result = calculate_daily_limit(profile)

        print(f"\n=== {profile['name']} ({filename}) ===")
        if not result["ok"]:
            print(f"  ОТКАЗ: {result['reason']}")
            continue

        print(f"  Баланс:            {result['balance']} ₽")
        print(f"  Подписки:          {result['subscriptions_total']} ₽")
        print(f"  Резерв (10%):      {result['reserve']} ₽")
        print(f"  Доступно:          {result['available']} ₽")
        print(f"  Дней до дохода:    {result['days_left']}")
        print(f"  Дневной лимит:     {result['daily_limit']} ₽")


if __name__ == "__main__":
    run()