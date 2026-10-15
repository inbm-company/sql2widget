"""Plan and evaluate the original chat request; keep loop work bounded."""

import time

from app.intent_router import ANSWER_ROUTES
from app.llm import json_with_llm
from app.prompts import DATA_ACTION_HINT, EVALUATE_HINT, PLAN_HINT, ROUTE_CRITERIA

MAX_STEPS = 20
MAX_REPLANS = 5
LOOP_SECONDS = 180
SAFETY_STEPS = 100


class PlanError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def model_context(context, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BudgetExceeded("실행 시간 한도에 도달했습니다.")
    return {**context, "timeout": min(60, remaining)}


def _ask(hint, content, context, deadline):
    result = json_with_llm(hint, content, **model_context(context, deadline))
    if not isinstance(result.get("result"), dict):
        raise PlanError(f"{result.get('provider') or 'LLM'} request failed: "
                        f"{result.get('error') or 'invalid planning/evaluation response'}")
    return result["result"]


def _steps(raw, fallback_query):
    if not isinstance(raw, list) or len(raw) > MAX_STEPS:
        raise PlanError("계획 단계는 최대 20개인 배열이어야 합니다.")
    steps = []
    for item in raw:
        if not isinstance(item, dict) or item.get("route") not in ANSWER_ROUTES:
            raise PlanError("계획에 지원하지 않는 처리 경로가 있습니다.")
        query = item.get("query") or (fallback_query if len(raw) == 1 else None)
        if not isinstance(query, str) or not query.strip():
            raise PlanError("계획 단계의 질문이 비어 있습니다.")
        steps.append({"route": item["route"], "query": query.strip(),
                      "expect": str(item.get("expect") or "")})
    return steps


def single_step_plan(route, message):
    return {"goal": message, "steps": [{"route": route, "query": message, "expect": "사용자 요청에 답하기"}],
            "source": "user_choice"}


def make_plan(message, flow, context, deadline):
    data = _ask(PLAN_HINT, {"question": message, "recent_turns": flow["history"],
        "last_route": flow["last_route"], "route_criteria": ROUTE_CRITERIA, "max_steps": MAX_STEPS}, context, deadline)
    steps = _steps(data.get("steps"), message)
    if not steps:
        raise PlanError("실행할 계획 단계가 없습니다.")
    if len(steps) == 1:
        steps[0]["query"] = message
    return {"goal": str(data.get("goal") or message), "steps": steps, "source": "llm"}


def evaluate(plan, done, pending, replans, context, deadline, *, user_request):
    if done[-1]["status"] == "needs_user":
        return {"verdict": "pause", "reason": "사용자 확인이 필요한 단계"}
    if pending:
        return {"verdict": "next", "reason": "계획에 남은 단계"}
    selected = plan["steps"][0]["route"] if plan["source"] == "user_choice" else None
    data = _ask(EVALUATE_HINT, {"user_request": user_request, "goal": plan["goal"],
        "user_selected_route": selected, "route_criteria": ROUTE_CRITERIA,
        "max_steps": MAX_STEPS, "results": done}, context, deadline)
    reason = str(data.get("reason") or "요청 충족 여부 평가")[:200]
    if data.get("met") is True:
        return {"verdict": "done", "reason": reason}
    if data.get("met") is not False:
        raise PlanError("목표 평가에 달성 여부가 없습니다.")
    missing = _steps(data.get("missing") or [], user_request)
    if selected:
        missing = [step for step in missing if step["route"] == selected]
    if missing and replans < MAX_REPLANS:
        return {"verdict": "replan", "reason": reason, "steps": missing}
    limit = "재계획 횟수 한도에 도달했습니다." if replans >= MAX_REPLANS else "계속할 작업을 정하지 못했습니다."
    return {"verdict": "incomplete", "reason": f"{reason} {limit}"}


def choose_data_action(message, state, history, context, deadline, *, original_request=None):
    """Inspect actual tool outcomes and choose the next supported action."""
    data = _ask(DATA_ACTION_HINT, {"user_request": original_request or message, "task": message,
                                 "state": state, "history": history}, context, deadline)
    action = data.get("action")
    if action not in ("generate_sql", "execute_sql", "select_widgets", "create_widget", "finish", "incomplete"):
        raise PlanError("지원하지 않는 데이터 작업이 선택됐습니다.")
    result = {"action": action, "reason": str(data.get("reason") or "")[:200],
              "request": str(data.get("request") or message)}
    for key in ("query_id", "widget_id"):
        if data.get(key) is not None:
            if not isinstance(data[key], str):
                raise PlanError("데이터 작업의 참조 ID가 올바르지 않습니다.")
            result[key] = data[key]
    return result
