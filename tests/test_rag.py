import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from rag.retriever import find_term, list_terms  # noqa: E402


def main():
    print("Всего терминов в базе:", len(list_terms()))
    print()

    queries = [
        "Что такое льготный период?",
        "Объясни кредитку",
        "Что такое финансовая подушка?",
        "Расскажи про кэшбэк",
        "Что такое кэшбэк?",
        "Что такое инфляция?",
        "Что такое ПСК?",
        "Расскажи про автоплатёж",
        "Что такое кредитная история?",
        "Что такое foobar?",
    ]

    for q in queries:
        result = find_term(q)
        print(f"ЗАПРОС: {q}")
        if result:
            print(f"  ТЕРМИН: {result['term']}")
            print(f"  ОПРЕДЕЛЕНИЕ: {result['definition'][:80]}...")
            print(f"  ИСТОЧНИК: {result['source_name']} ({result['source_url']})")
        else:
            print("  НЕ НАЙДЕНО")
        print()


if __name__ == "__main__":
    main()