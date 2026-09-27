"""
Простой поиск термина по базе sources.json.

Работает без векторных баз — ищет по ключевым словам.
Для MVP этого достаточно: терминов немного, запросы простые.
"""

import json
import os
from typing import Optional


# Загружаем базу один раз при импорте.
_DATA_PATH = os.path.join(os.path.dirname(__file__), "sources.json")
with open(_DATA_PATH, "r", encoding="utf-8") as f:
    _DATA = json.load(f)


# Словарь источников: id → {name, url, description}
SOURCES = {s["id"]: s for s in _DATA["sources"]}

# Список терминов.
TERMS = _DATA["terms"]


def _normalize(text: str) -> str:
    """Приводит текст к нижнему регистру и убирает лишние пробелы."""
    return " ".join(text.lower().strip().split())


def find_term(query: str) -> Optional[dict]:
    """
    Ищет термин в базе.

    Возвращает словарь с полями:
    - term, definition, source_name, source_url, source_id
    или None, если термин не найден.
    """
    q = _normalize(query)
    if not q:
        return None

    # Ищем точное вхождение термина или алиаса в запрос.
    for term in TERMS:
        candidates = [term["term"]] + term.get("aliases", [])
        for cand in candidates:
            if _normalize(cand) in q:
                source = SOURCES.get(term["source_id"], {})
                source_name = source.get("name", "источник")
                return {
                    "term": term["term"],
                    "definition": f"{term['definition']} (Источник: {source_name})",
                    "source_id": term["source_id"],
                    "source_name": source_name,
                    "source_url": source.get("url", ""),
                }

    # Если точного вхождения нет — попробуем по отдельным словам.
    words = [w for w in q.split() if len(w) > 3]
    for term in TERMS:
        text = _normalize(term["term"] + " " + " ".join(term.get("aliases", [])))
        if any(w in text for w in words):
            source = SOURCES.get(term["source_id"], {})
            return {
                "term": term["term"],
                "definition": term["definition"],
                "source_id": term["source_id"],
                "source_name": source.get("name", "источник"),
                "source_url": source.get("url", ""),
            }

    return None


def list_terms() -> list:
    """Список всех терминов (для отладки или подсказки в чате)."""
    return [t["term"] for t in TERMS]