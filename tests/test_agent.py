"""
Тест AI-агента: пользователь → GigaChat → tool call → ответ.
Запуск: python tests/test_agent.py
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from llm.agent import DailyLimitAgent  # noqa: E402


def main():
    agent = DailyLimitAgent()

    test_questions = [
        ("Сколько я могу потратить сегодня?", "profile_1"),
        ("Куда уходят мои деньги?", "profile_1"),
        ("Что такое льготный период?", "profile_1"),
        ("Объясни, что такое финансовая подушка", "profile_1"),
        ("Что такое кэшбэк?", "profile_1"),
        ("Как я иду к цели?", "profile_1"),
        ("Посоветуй акции для инвестиций", "profile_1"),
        ("Что если я потрачу 5000 на кроссовки?", "profile_1"),
    ]

    try:
        for question, profile_id in test_questions:
            print(f"\n{'='*60}")
            print(f"ПОЛЬЗОВАТЕЛЬ: {question}")
            print(f"ПРОФИЛЬ: {profile_id}")
            print(f"{'-'*60}")

            result = agent.chat(question, profile_id)

            print(f"ИНСТРУМЕНТ: {result['tool_used']}")
            print(f"ОТВЕТ АГЕНТА:\n{result['answer']}")

    finally:
        agent.close()


if __name__ == "__main__":
    main()