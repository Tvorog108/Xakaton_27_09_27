import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend", "tools"))
from goal_progress import get_goal_progress  # noqa: E402


def load_profile(name: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    for filename in ["profile_1.json", "profile_2.json", "profile_3.json"]:
        profile = load_profile(filename)
        result = get_goal_progress(profile)

        print(f"\n=== {profile['name']} ({filename}) ===")
        if not result["ok"]:
            print(f"  ОТКАЗ: {result['reason']}")
            continue

        print(f"  Цель: {result['name']}")
        print(f"  Накоплено: {result['saved']} из {result['target']} ₽ ({round(result['progress']*100)}%)")
        print(f"  Осталось: {result['remaining']} ₽")
        if result["needed_per_day"] is not None:
            print(f"  Нужно откладывать: {result['needed_per_day']} ₽/день до {result['days_left']} дн.")


if __name__ == "__main__":
    run()