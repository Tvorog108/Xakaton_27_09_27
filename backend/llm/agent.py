"""
AI-агент «Дневной лимит».

Приоритет: GigaChat + Tool Calling, если задан GIGACHAT_CREDENTIALS.
Без ключа — fallback: tools + шаблонные ответы (чтобы MVP не падал на демо).
Все суммы всегда считает Python, не LLM.
"""

import os
import json
import re
from pathlib import Path

from dotenv import load_dotenv

# Подхватываем .env из корня проекта и из backend/
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
_ROOT = _BACKEND.parent
for _env_path in (_ROOT / ".env", _BACKEND / ".env", Path.cwd() / ".env"):
    if _env_path.is_file():
        load_dotenv(_env_path, override=True)

from rag.retriever import find_term
from llm.prompts import SYSTEM_PROMPT
from llm.tools_schema import ALL_TOOLS

from tools.daily_limit import calculate_daily_limit, what_if_spend
from tools.categories import analyze_categories
from tools.goal_progress import get_goal_progress
from tools.detect_risks import detect_risks
from tools.credit_risk import check_credit_risk


def _get_profile(profile_id: str) -> dict:
    data_dir = _BACKEND / "data"
    path = data_dir / f"{profile_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Профиль {profile_id} не найден")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _tool_calculate_daily_limit(profile_id: str) -> dict:
    return calculate_daily_limit(_get_profile(profile_id))


def _tool_analyze_categories(profile_id: str) -> dict:
    return analyze_categories(_get_profile(profile_id))


def _tool_get_goal_progress(profile_id: str) -> dict:
    profile = _get_profile(profile_id)
    daily = calculate_daily_limit(profile)
    if daily.get("ok"):
        profile["_daily_limit"] = daily["daily_limit"]
    return get_goal_progress(profile)


def _tool_what_if_spend(profile_id: str, amount: float) -> dict:
    return what_if_spend(_get_profile(profile_id), amount)


def _tool_detect_risks(profile_id: str) -> dict:
    profile = _get_profile(profile_id)
    daily = calculate_daily_limit(profile)
    return detect_risks(profile, daily)


def _tool_check_credit_risk(profile_id: str) -> dict:
    return check_credit_risk(_get_profile(profile_id))


def _tool_explain_term(query: str) -> dict:
    result = find_term(query)
    if not result:
        return {"ok": False, "reason": f"Термин не найден в базе источников. Запрос: {query}"}
    return {
        "ok": True,
        "term": result["term"],
        "definition": result["definition"],
        "source_name": result["source_name"],
        "source_url": result["source_url"],
    }


TOOL_REGISTRY = {
    "calculate_daily_limit": _tool_calculate_daily_limit,
    "analyze_categories": _tool_analyze_categories,
    "get_goal_progress": _tool_get_goal_progress,
    "detect_risks": _tool_detect_risks,
    "check_credit_risk": _tool_check_credit_risk,
    "explain_term": _tool_explain_term,
    "what_if_spend": _tool_what_if_spend,
}


REFUSAL_PATTERNS = [
    (
        r"(посоветуй|порекомендуй|какие|купить).*(акци|фонд|крипт|инвест|бумаг)",
        "Я не даю инвестиционных рекомендаций. Это ограничение продукта. "
        "Могу помочь с дневным лимитом, тратами, накоплениями или объяснить финансовый термин.",
    ),
    (
        r"(перевод|перевед|оплат|спис|отправ).*(деньг|руб|₽|сумм)",
        "Я не совершаю операций с деньгами. Это ограничение продукта. "
        "Могу посчитать дневной лимит или показать, куда уходят траты.",
    ),
    (
        r"(инвестиционн|куда вложить|куда положить деньги|доходност)",
        "Я не даю инвестиционных рекомендаций и не принимаю финансовых решений за вас. "
        "Могу объяснить термин или посчитать безопасный дневной лимит.",
    ),
]


def _check_refusal(message: str) -> str | None:
    low = message.lower()
    for pattern, answer in REFUSAL_PATTERNS:
        if re.search(pattern, low):
            return answer
    return None


def _postprocess_answer(answer: str, tool_name: str, tool_result: dict) -> str:
    replacements = {
        "Попробуй ": "Ты можешь ",
        "попробуй ": "ты можешь ",
        "Попробуйте ": "Вы можете ",
        "Тебе стоит ": "Ты можешь ",
        "тебе стоит ": "ты можешь ",
        "Вам стоит ": "Вы можете ",
        "Советую ": "Ты можешь ",
        "советую ": "ты можешь ",
        "Нужно ": "Можно ",
        "нужно ": "можно ",
        "Сделай ": "Ты можешь сделать ",
        "сделай ": "ты можешь сделать ",
    }
    for bad, good in replacements.items():
        answer = answer.replace(bad, good)

    if tool_name == "explain_term" and tool_result and tool_result.get("ok"):
        source_name = tool_result.get("source_name", "")
        if source_name and "Источник" not in answer and source_name not in answer:
            answer = answer.rstrip() + f" (Источник: {source_name})"

    stripped = answer.rstrip()
    if stripped.endswith("?"):
        sentences = stripped.split(".")
        for i in range(len(sentences) - 1, -1, -1):
            if "?" in sentences[i]:
                sentences = sentences[:i]
                break
        answer = ".".join(sentences).strip()
        if answer and not answer.endswith("."):
            answer += "."

    return answer.strip()


def _route_offline(message: str) -> tuple[str | None, dict]:
    """Fallback-маршрутизация, если GigaChat недоступен."""
    low = message.lower()

    if any(w in low for w in ("что такое", "объясни", "означает", "термин", "что значит")):
        return "explain_term", {"query": message}

    m = re.search(
        r"(что\s+если|если\s+я|потрачу|потратить|купи|куплю|возьму|суши|заказ).{0,40}?(\d[\d\s]*)",
        low,
    )
    if m:
        amount_str = re.sub(r"\s", "", m.group(2))
        try:
            return "what_if_spend", {"amount": float(amount_str)}
        except ValueError:
            pass

    # сумма в конце: «на 1000 рублей»
    m2 = re.search(r"(купи|потрат|возьм|суши|заказ).{0,40}?(\d[\d\s]*)\s*(руб|₽)?", low)
    if m2:
        try:
            return "what_if_spend", {"amount": float(re.sub(r"\s", "", m2.group(2)))}
        except ValueError:
            pass

    if any(
        w in low
        for w in (
            "лимит",
            "сколько можно",
            "сколько я могу",
            "сколько потратить",
            "потратить сегодня",
            "хватит ли",
            "бюджет на день",
            "на сегодня",
            "можно потратить",
        )
    ):
        return "calculate_daily_limit", {}

    if any(
        w in low
        for w in (
            "цел",
            "накоп",
            "копить",
            "коплю",
            "отклад",
            "прогресс",
            "сколько осталось",
            "успею",
            "сколько копить",
            "сколько откладывать",
            "ноутбук",
            "близко к",
        )
    ):
        return "get_goal_progress", {}

    if any(w in low for w in ("куда уход", "категор", "на что трач", "перерасход", "структур")):
        return "analyze_categories", {}

    if any(w in low for w in ("риск", "подписк", "подозритель", "импульс")):
        return "detect_risks", {}

    if any(w in low for w in ("кредитк", "переплат", "льготн период", "процент по кредит")):
        return "check_credit_risk", {}

    if "трат" in low or "расход" in low:
        return "analyze_categories", {}

    if any(w in low for w in ("деньг", "бюджет", "баланс", "остаток")):
        return "calculate_daily_limit", {}

    return None, {}


def _format_offline_answer(tool_name: str, result: dict) -> str:
    if tool_name == "calculate_daily_limit":
        if not result.get("ok"):
            return (
                result.get("reason", "Недостаточно данных.")
                + " Укажи дату следующего поступления, и я посчитаю лимит."
            )
        return (
            f"Безопасный дневной лимит — {result['daily_limit']} ₽. "
            f"До следующего поступления {result['days_left']} дн. "
            f"Из баланса {result['balance']} ₽ вычтены обязательные платежи "
            f"({result['subscriptions_total']} ₽) и резерв {result['reserve']} ₽. "
            f"Можно ориентироваться на эту сумму при тратах сегодня."
        )

    if tool_name == "analyze_categories":
        if not result.get("ok"):
            return result.get("reason", "Нет данных о тратах.")
        parts = [f"Всего трат: {result['total']} ₽."]
        top = result.get("top") or result.get("categories", [])[:3]
        for c in top:
            mark = " ⚠ перерасход" if c.get("over_limit") else ""
            parts.append(f"{c['name']}: {c['total']} ₽ ({round(c['share'] * 100)}%){mark}.")
        overs = result.get("overspending") or []
        if overs:
            parts.append("Есть перерасход в: " + ", ".join(o["name"] for o in overs) + ".")
        parts.append("Можно посмотреть детальнее на экране «Траты».")
        return " ".join(parts)

    if tool_name == "get_goal_progress":
        if not result.get("ok"):
            return result.get("reason", "Цель не задана.") + " Можешь задать цель накопления."
        pct = round(result.get("progress", 0) * 100)
        text = (
            f"Цель «{result['name']}»: накоплено {result['saved']} ₽ из {result['target']} ₽ ({pct}%). "
            f"Осталось {result['remaining']} ₽."
        )
        if result.get("needed_per_day"):
            text += f" Чтобы успеть к сроку, нужно откладывать около {result['needed_per_day']} ₽ в день."
        if result.get("warning"):
            text += " " + result["warning"]
        text += " Прогресс виден на экране «Цель»."
        return text

    if tool_name == "detect_risks":
        if not result.get("ok"):
            return result.get("reason", "Нет данных для анализа рисков.")
        risks = result.get("risks") or []
        if not risks:
            return "Явных финансовых рисков не найдено. Можно продолжать следить за дневным лимитом."
        parts = ["Найдены риски:"]
        for r in risks[:5]:
            parts.append(f"— {r.get('message', r.get('type', 'риск'))} ({r.get('severity', '')}).")
        parts.append("Подробности — на экране «Риски».")
        return " ".join(parts)

    if tool_name == "check_credit_risk":
        if not result.get("ok"):
            return result.get("reason", "Нет операций по кредитке.")
        return result.get("warning", f"Потрачено с кредитки: {result.get('used')} ₽.") + (
            f" Льготный период — до {result.get('grace_period_days')} дней. "
            "Проценты начисляются только если не погасить полностью в срок."
        )

    if tool_name == "explain_term":
        if not result.get("ok"):
            return result.get("reason", "Термин не найден.") + " Попробуй переформулировать вопрос."
        return result.get("definition", "")

    if tool_name == "what_if_spend":
        if not result.get("ok"):
            return result.get("reason", "Не удалось посчитать.")
        text = result.get("verdict") or (
            f"Если потратить {result['amount']} ₽ сейчас: "
            f"дневной лимит станет {result['new_limit']} ₽ "
            f"(сейчас {result['current_limit']} ₽)."
        )
        gi = result.get("goal_impact")
        if gi and gi.get("days_at_new_rate"):
            text += (
                f" До цели «{gi['name']}» при новом лимите "
                f"примерно {gi['days_at_new_rate']} дн. "
                f"(это оценка «если каждый день откладывать весь дневной лимит»)."
            )
        return text

    return "Не удалось сформировать ответ. Спроси про дневной лимит, траты или цель."


class DailyLimitAgent:
    """Агент только через GigaChat + Tool Calling. Без API — ошибка."""

    def __init__(self):
        credentials = (os.getenv("GIGACHAT_CREDENTIALS") or "").strip().strip('"').strip("'")
        model = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro")
        self.client = None
        self.model = model
        self.mode = "unavailable"
        self.error = None

        if not credentials:
            self.error = (
                "GIGACHAT_CREDENTIALS не задан. "
                "Вставь ключ в .env в корне проекта и перезапусти сервер."
            )
            print(f"[agent] {self.error}")
            return

        try:
            from gigachat import GigaChat

            self.client = GigaChat(
                credentials=credentials,
                scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
                model=model,
                verify_ssl_certs=os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower()
                not in ("0", "false", "no"),
            )
            self.mode = "gigachat"
            print(f"[agent] GigaChat подключён, model={model}")
        except Exception as e:
            self.client = None
            self.mode = "unavailable"
            self.error = f"Не удалось подключить GigaChat: {e}"
            print(f"[agent] {self.error}")

    @property
    def offline(self) -> bool:
        """Совместимость: True, если нейросеть недоступна."""
        return self.mode != "gigachat" or self.client is None

    def chat(self, user_message: str, profile_id: str) -> dict:
        if self.mode != "gigachat" or self.client is None:
            return {
                "answer": (
                    "Сейчас нет доступа к GigaChat — чат недоступен. "
                    "Проверь ключ в настройках и перезапусти сервер."
                ),
                "tool_used": None,
                "tool_result": None,
                "mode": "unavailable",
                "error": self.error or "gigachat_unavailable",
            }

        refusal = _check_refusal(user_message)
        if refusal:
            return {"answer": refusal, "tool_used": None, "tool_result": None, "mode": "gigachat"}

        # Однозначный intent → tool кодом, GigaChat только формулирует
        tool_name, extra_args = _route_offline(user_message)
        if tool_name:
            try:
                result = self._chat_with_forced_tool(user_message, profile_id, tool_name, extra_args)
                result["mode"] = "gigachat"
                return result
            except Exception as e:
                print(f"[agent] ошибка GigaChat (forced tool): {e}")
                return {
                    "answer": (
                        "Не удалось получить ответ от GigaChat. Попробуй ещё раз чуть позже."
                    ),
                    "tool_used": tool_name,
                    "tool_result": None,
                    "mode": "error",
                    "error": str(e),
                }

        try:
            result = self._chat_gigachat(user_message, profile_id)
            result["mode"] = "gigachat"
            return result
        except Exception as e:
            print(f"[agent] ошибка GigaChat: {e}")
            return {
                "answer": "Не удалось связаться с GigaChat. Проверь подключение и ключ, затем попробуй снова.",
                "tool_used": None,
                "tool_result": None,
                "mode": "error",
                "error": str(e),
            }


    def _profile_context(self, profile_id: str) -> str:
        """Краткий контекст профиля для LLM — чтобы не спрашивала «какая цель?»."""
        try:
            prof = _get_profile(profile_id)
        except Exception:
            return f"profile_id={profile_id}"
        goal = prof.get("goal") or {}
        lines = [
            f"profile_id={profile_id}",
            f"Имя: {prof.get('name', '')}",
            f"Баланс: {prof.get('balance')} руб.",
            f"Дата сегодня в данных: {prof.get('today')}",
            f"Следующее поступление: {prof.get('next_income_date') or 'не указано'}",
        ]
        if goal:
            lines.append(
                f"Цель накопления УЖЕ задана: «{goal.get('name')}», "
                f"накоплено {goal.get('saved')} из {goal.get('target')} руб."
            )
        else:
            lines.append("Цель накопления в профиле не задана.")
        return "\n".join(lines)

    def _chat_with_forced_tool(
        self, user_message: str, profile_id: str, tool_name: str, extra_args: dict
    ) -> dict:
        """Считаем tool сами, GigaChat только формулирует ответ по результату."""
        from gigachat.models import Chat, Messages, MessagesRole

        tool_fn = TOOL_REGISTRY.get(tool_name)
        if not tool_fn:
            return {
                "answer": f"Инструмент {tool_name} не найден.",
                "tool_used": None,
                "tool_result": None,
                "mode": "error",
            }

        try:
            if tool_name == "explain_term":
                tool_result = tool_fn(query=extra_args.get("query", user_message))
            elif tool_name == "what_if_spend":
                tool_result = tool_fn(
                    profile_id=profile_id, amount=float(extra_args.get("amount", 0))
                )
            else:
                tool_result = tool_fn(profile_id=profile_id)
        except Exception as e:
            return {
                "answer": f"Ошибка при расчёте: {e}",
                "tool_used": tool_name,
                "tool_result": None,
            }

        context = self._profile_context(profile_id)
        system = (
            SYSTEM_PROMPT
            + "\n\nКонтекст пользователя:\n"
            + context
            + "\n\nТебе УЖЕ передан результат инструмента. "
            "Сформулируй короткий ответ с цифрами из JSON. Не вызывай tools. Не задавай встречных вопросов."
        )
        user = (
            f"Вопрос пользователя: {user_message}\n\n"
            f"Инструмент: {tool_name}\n"
            f"Результат (JSON): {json.dumps(tool_result, ensure_ascii=False)}"
        )

        response = self.client.chat(
            Chat(
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content=system),
                    Messages(role=MessagesRole.USER, content=user),
                ]
            )
        )
        answer = response.choices[0].message.content or ""
        answer = _postprocess_answer(answer, tool_name, tool_result)
        if not answer.strip():
            answer = _format_offline_answer(tool_name, tool_result)
        return {
            "answer": answer,
            "tool_used": tool_name,
            "tool_result": tool_result,
        }

    def _chat_offline(self, user_message: str, profile_id: str) -> dict:
        tool_name, extra_args = _route_offline(user_message)
        if not tool_name:
            return {
                "answer": (
                    "Могу помочь с дневным лимитом («сколько можно потратить сегодня»), "
                    "тратами («куда уходят деньги»), целью накопления («сколько копить»), "
                    "рисками, кредиткой или объяснить термин. Все расчёты выполняются кодом."
                ),
                "tool_used": None,
                "tool_result": None,
            }

        tool_fn = TOOL_REGISTRY.get(tool_name)
        if not tool_fn:
            return {"answer": f"Инструмент {tool_name} не найден.", "tool_used": None, "tool_result": None}

        try:
            if tool_name == "explain_term":
                tool_result = tool_fn(query=extra_args.get("query", user_message))
            elif tool_name == "what_if_spend":
                tool_result = tool_fn(profile_id=profile_id, amount=float(extra_args.get("amount", 0)))
            else:
                tool_result = tool_fn(profile_id=profile_id)
        except Exception as e:
            return {"answer": f"Ошибка при расчёте: {e}", "tool_used": tool_name, "tool_result": None}

        return {
            "answer": _format_offline_answer(tool_name, tool_result),
            "tool_used": tool_name,
            "tool_result": tool_result,
        }

    def _chat_gigachat(self, user_message: str, profile_id: str) -> dict:
        from gigachat.models import Chat, Messages, MessagesRole

        context = self._profile_context(profile_id)
        system = SYSTEM_PROMPT + "\n\nКонтекст пользователя:\n" + context
        messages = [
            Messages(role=MessagesRole.SYSTEM, content=system),
            Messages(role=MessagesRole.USER, content=user_message),
        ]

        response = self.client.chat(
            Chat(
                messages=messages,
                functions=ALL_TOOLS,
                function_call="auto",
            )
        )

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "function_call" and choice.message.function_call:
            tool_name = choice.message.function_call.name
            raw_args = choice.message.function_call.arguments
            if isinstance(raw_args, str):
                tool_args = json.loads(raw_args or "{}")
            elif isinstance(raw_args, dict):
                tool_args = raw_args
            else:
                tool_args = {}

            if tool_name != "explain_term" and "profile_id" not in tool_args:
                tool_args["profile_id"] = profile_id

            tool_fn = TOOL_REGISTRY.get(tool_name)
            if not tool_fn:
                return {
                    "answer": f"Инструмент {tool_name} не найден.",
                    "tool_used": None,
                    "tool_result": None,
                }

            try:
                tool_result = tool_fn(**tool_args)
            except Exception as e:
                return {
                    "answer": f"Ошибка при вызове инструмента: {e}",
                    "tool_used": tool_name,
                    "tool_result": None,
                }

            messages.append(
                Messages(
                    role=MessagesRole.ASSISTANT,
                    content="",
                    function_call=choice.message.function_call,
                )
            )
            messages.append(
                Messages(
                    role=MessagesRole.FUNCTION,
                    name=tool_name,
                    content=json.dumps(tool_result, ensure_ascii=False),
                )
            )

            final_response = self.client.chat(Chat(messages=messages))
            answer = final_response.choices[0].message.content or ""
            answer = _postprocess_answer(answer, tool_name, tool_result)

            return {"answer": answer, "tool_used": tool_name, "tool_result": tool_result}

        return {
            "answer": choice.message.content or "",
            "tool_used": None,
            "tool_result": None,
        }

    def close(self):
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
