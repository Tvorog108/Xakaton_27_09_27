"""
Backend MVP «Дневной лимит».

Отдаёт данные профилей и результаты расчётов через HTTP.
Все расчёты — код, без LLM. LLM только формулирует объяснения.
"""
import json
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from tools.daily_limit import calculate_daily_limit
from tools.categories import analyze_categories
from tools.goal_progress import get_goal_progress
from tools.detect_risks import detect_risks
from tools.credit_risk import check_credit_risk
from llm.agent import DailyLimitAgent


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
PROFILES = [
    "profile_1.json",
    "profile_2.json",
    "profile_3.json",
    "profile_4.json",
    "profile_5.json",
]

app = FastAPI(
    title="Дневной лимит — API",
    description="AI-ассистент для студентов с нерегулярным доходом. Кейс 1, Т-Банк.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_profile(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Профиль {filename} не найден")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api")
def root():
    return {
        "status": "ok",
        "service": "Дневной лимит",
        "version": "0.2.0",
    }


@app.get("/profiles")
def list_profiles() -> List[dict]:
    result = []
    for filename in PROFILES:
        profile = load_profile(filename)
        result.append({
            "id": profile["profile_id"],
            "name": profile["name"],
            "segment": profile["segment"],
            "file": filename,
        })
    return result


@app.get("/profile/{profile_id}")
def get_profile(profile_id: str) -> dict:
    for filename in PROFILES:
        profile = load_profile(filename)
        if profile["profile_id"] == profile_id:
            return profile
    raise HTTPException(status_code=404, detail="Профиль не найден")


@app.get("/profile/{profile_id}/daily-limit")
def daily_limit(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    return calculate_daily_limit(profile)


@app.get("/profile/{profile_id}/categories")
def categories(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    return analyze_categories(profile)


@app.get("/profile/{profile_id}/goal")
def goal(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    return get_goal_progress(profile)


@app.get("/profile/{profile_id}/risks")
def risks(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    daily = calculate_daily_limit(profile)
    return detect_risks(profile, daily)


@app.get("/profile/{profile_id}/credit")
def credit(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    return check_credit_risk(profile)


class ChatRequest(BaseModel):
    message: str


_agent = None


def get_agent() -> DailyLimitAgent:
    global _agent
    if _agent is None:
        _agent = DailyLimitAgent()
    return _agent


@app.post("/profile/{profile_id}/chat")
def chat(profile_id: str, request: ChatRequest) -> dict:
    get_profile(profile_id)
    try:
        agent = get_agent()
        result = agent.chat(request.message, profile_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка агента: {e}")

    return {
        "profile_id": profile_id,
        "user_message": request.message,
        "answer": result["answer"],
        "tool_used": result.get("tool_used"),
        "mode": result.get("mode"),
    }


@app.get("/profile/{profile_id}/summary")
def summary(profile_id: str) -> dict:
    profile = get_profile(profile_id)
    daily = calculate_daily_limit(profile)
    proactive_hint = _build_proactive_hint(profile, daily)

    cats = analyze_categories(profile)
    profile_for_goal = dict(profile)
    if daily.get("ok"):
        profile_for_goal["_daily_limit"] = daily["daily_limit"]
    goal = get_goal_progress(profile_for_goal)
    risks = detect_risks(profile, daily)
    credit = check_credit_risk(profile)
    ai_insights = _build_ai_insights(profile, daily, cats, goal, risks)

    return {
        "profile": {
            "id": profile["profile_id"],
            "name": profile["name"],
            "balance": profile["balance"],
            "next_income_date": profile["next_income_date"],
        },
        "daily_limit": daily,
        "goal": goal,
        "categories": cats,
        "risks": risks,
        "credit": credit,
        "proactive_hint": proactive_hint,
        "ai_insights": ai_insights,
    }


def _build_proactive_hint(profile: dict, daily: dict) -> dict:
    if not daily.get("ok"):
        return {
            "ok": False,
            "text": daily.get("reason", "Недостаточно данных для подсказки."),
        }

    today = profile["today"]
    today_tx = [t for t in profile.get("transactions", []) if t["date"] == today]
    today_spent = round(sum(float(t["amount"]) for t in today_tx), 2)

    daily_limit_val = daily["daily_limit"]
    remaining = round(daily_limit_val - today_spent, 2)
    days_left = daily["days_left"]

    if today_spent == 0:
        text = f"Сегодня ещё не было трат. Лимит на день — {daily_limit_val} ₽."
    elif remaining >= 0:
        text = (
            f"Сегодня потрачено {today_spent} ₽ из {daily_limit_val} ₽. "
            f"Остаток на день — {remaining} ₽."
        )
    else:
        over = abs(remaining)
        text = (
            f"Сегодня потрачено {today_spent} ₽, это на {over} ₽ больше лимита. "
            f"Имеет смысл сократить траты в ближайшие дни."
        )

    if today_spent > 0 and daily_limit_val > 0:
        days_at_rate = round(daily["available"] / today_spent, 1)
        if days_at_rate < days_left:
            text += (
                f" Если так пойдёт дальше, свободные деньги кончатся "
                f"через {days_at_rate} дн., а до поступления ещё {days_left} дн."
            )

    return {"ok": True, "text": text, "today_spent": today_spent}


def _r(x):
    try:
        return int(round(float(x)))
    except Exception:
        return x


def _build_ai_insights(profile: dict, daily: dict, cats: dict, goal: dict, risks: dict) -> dict:
    """
    AI-разбор без чата: выводы собираются кодом из результатов tools.
    Это и есть «AI как инструмент», а не декоративный диалог.
    """
    cards = []

    # 1. Главный результат — безопасный лимит
    if daily.get("ok"):
        cards.append({
            "id": "limit",
            "kind": "result",
            "title": "Безопасный дневной лимит",
            "body": (
                f"{_r(daily['daily_limit'])} ₽ на сегодня. "
                f"До поступления {daily['days_left']} дн.; "
                f"из баланса вычтены платежи {_r(daily['subscriptions_total'])} ₽ "
                f"и резерв {_r(daily['reserve'])} ₽."
            ),
            "tool": "calculate_daily_limit",
        })
    else:
        cards.append({
            "id": "limit",
            "kind": "warning",
            "title": "Лимит не посчитан",
            "body": daily.get("reason", "Недостаточно данных."),
            "tool": "calculate_daily_limit",
        })

    # 2. Структура трат
    if cats.get("ok") and cats.get("categories"):
        top = cats["categories"][0]
        overs = cats.get("overspending") or []
        if overs:
            names = ", ".join(o["name"] for o in overs[:3])
            cards.append({
                "id": "cats",
                "kind": "warning",
                "title": "Перерасход по категориям",
                "body": f"Всего трат {cats['total']} ₽. Перерасход: {names}.",
                "tool": "analyze_categories",
            })
        else:
            cards.append({
                "id": "cats",
                "kind": "info",
                "title": "Куда уходят деньги",
                "body": (
                    f"Всего {cats['total']} ₽. Крупнее всего «{top['name']}» — "
                    f"{top['total']} ₽ ({round(top['share'] * 100)}%)."
                ),
                "tool": "analyze_categories",
            })

    # 3. Цель
    if goal.get("ok"):
        pct = round((goal.get("progress") or 0) * 100)
        body = (
            f"«{goal['name']}»: {goal['saved']} из {goal['target']} ₽ ({pct}%). "
            f"Осталось {goal['remaining']} ₽."
        )
        if goal.get("needed_per_day"):
            body += f" Чтобы успеть — около {goal['needed_per_day']} ₽ в день."
        if goal.get("warning"):
            body += " " + goal["warning"]
        cards.append({
            "id": "goal",
            "kind": "warning" if goal.get("warning") else "info",
            "title": "Прогресс цели",
            "body": body,
            "tool": "get_goal_progress",
        })
    elif goal.get("reason"):
        cards.append({
            "id": "goal",
            "kind": "info",
            "title": "Цель",
            "body": goal.get("reason", "Цель не задана."),
            "tool": "get_goal_progress",
        })

    # 4. Риски (топ-2)
    if risks.get("ok") and risks.get("risks"):
        for r in risks["risks"][:2]:
            cards.append({
                "id": f"risk_{r.get('type')}",
                "kind": "warning" if r.get("severity") in ("medium", "high") else "info",
                "title": r.get("title") or "Риск",
                "body": r.get("message", ""),
                "tool": "detect_risks",
            })

    # 5. Итоговый вывод для сегмента (нерегулярный доход)
    if daily.get("ok"):
        conclusion = (
            f"При нерегулярном доходе ориентир на сегодня — {_r(daily['daily_limit'])} ₽. "
            "Это не «бюджет на месяц», а безопасная сумма до следующего поступления."
        )
    else:
        conclusion = (
            "Не хватает данных для дневного лимита. "
            "Укажите дату следующего поступления — и расчёт появится."
        )

    return {
        "ok": True,
        "problem": "Сколько безопасно тратить до следующего поступления",
        "segment": "18–25, нерегулярный доход / студенты с подработкой",
        "conclusion": conclusion,
        "cards": cards,
        "calc_note": "",
    }


# Раздача frontend (если папка существует)
if os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/style.css")
    def serve_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

    @app.get("/app.js")
    def serve_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))
