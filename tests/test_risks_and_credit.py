import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend", "tools"))
from detect_risks import detect_risks  # noqa: E402
from credit_risk import check_credit_risk  # noqa: E402
from daily_limit import calculate_daily_limit  # noqa: E402


def load_profile(name: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "backend", "data", name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    for filename in ["profile_1.json", "profile_2.json", "profile_3.json"]:
        profile = load_profile(filename)

        print(f"\n=== {profile['name']} ({filename}) ===")

        # Риски
        daily = calculate_daily_limit(profile)
        risks = detect_risks(profile, daily)
        if not risks["ok"]:
            print(f"  Риски: {risks['reason']}")
        else:
            print(f"  Найдено рисков: {risks['total_risks']}")
            for r in risks["risks"]:
                print(f"    [{r['severity']}] {r['message']}")

        # Кредитка
        credit = check_credit_risk(profile)
        if not credit["ok"]:
            print(f"  Кредитка: {credit['reason']}")
        else:
            print(f"  Кредитка: {credit['warning']}")


if __name__ == "__main__":
    run()