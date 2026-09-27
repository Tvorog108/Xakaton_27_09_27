"""
Проверка категоризации трат на трёх профилях.
Запуск: python tests/test_categories.py
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend", "tools"))
from categories import analyze_categories  # noqa: E402


def load_profile(name: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    for filename in ["profile_1.json", "profile_2.json", "profile_3.json"]:
        profile = load_profile(filename)
        result = analyze_categories(profile)

        print(f"\n=== {profile['name']} ({filename}) ===")
        if not result["ok"]:
            print(f"  ОТКАЗ: {result['reason']}")
            continue

        print(f"  Всего трат: {result['total']} ₽")
        print("  Топ категорий:")
        for cat in result["top"]:
            mark = " ⚠ ПЕРЕРАСХОД" if cat["over_limit"] else ""
            print(f"    {cat['name']}: {cat['total']} ₽ ({cat['count']} операций, доля {round(cat['share']*100)}%){mark}")

        if result["overspending"]:
            print("  Категории с перерасходом:")
            for cat in result["overspending"]:
                print(f"    {cat['name']}: лимит {round(cat['limit']*100)}%, факт {round(cat['share']*100)}%, превышение {cat['over_amount']} ₽")


if __name__ == "__main__":
    run()