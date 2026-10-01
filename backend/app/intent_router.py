"""Decide how a chat message is handled: Jev Choice, then the chat LLM, else fail."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app import config
from app.llm import _error_message, json_with_llm
from app.prompts import ROUTE_HINT
from app.providers import transport

ANSWER_ROUTES = ("data_query", "schema_qa", "knowledge_qa")
# 되묻기 버튼으로 제공하는 경로. 지식그래프 검색이 연결되면 knowledge_qa를 추가한다.
CHOICE_ROUTES = ("data_query", "schema_qa")
ROUTE_LABELS = {
    "data_query": "데이터를 조회해 차트·표로 보기",
    "schema_qa": "테이블 구조 설명 듣기",
    "knowledge_qa": "문서(지식그래프)에서 찾아 답하기",
}
JEV_CRITERIA = {
    "data_query": "DB의 데이터를 숫자·표·차트로 조회해 달라는 요청",
    "schema_qa": "DB의 테이블·컬럼·관계 같은 구조에 대한 질문",
    "knowledge_qa": "업로드된 문서나 지식그래프의 내용에 대한 질문",
    "other": "위 어디에도 맞지 않거나 무엇을 원하는지 알 수 없는 입력",
}
MAX_RETRIES = 2  # 첫 시도 이후 재시도 횟수
RETRYABLE_STATUS = {429, 529}
JEV_TIMEOUT = 10.0


class RouteError(RuntimeError):
    """Neither Jev nor the chat LLM could decide a route."""


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, httpx.RequestError)


def _jev_choice(state: dict[str, Any]) -> dict[str, Any]:
    """Call Jev once; 429/529/network errors are retried with exponential backoff."""
    payload = {
        "model": config.TYPESAFE_MODEL,
        "state": state,
        "questions": {"route": {
            "type": "choice",
            "instructions": "이 채팅 메시지를 어떤 방식으로 처리해야 하는가?",
            "criteria": JEV_CRITERIA,
        }},
    }
    for attempt in range(MAX_RETRIES + 1):
        try:
            data = transport.post_json(
                config.TYPESAFE_BASE_URL, "/v1/systemone",
                api_key=config.TYPESAFE_API_KEY, payload=payload, timeout=JEV_TIMEOUT,
            )
            break
        except Exception as exc:
            if attempt == MAX_RETRIES or not _retryable(exc):
                raise
            time.sleep(0.5 * 2 ** attempt)
    answer = data["answers"]["route"]
    if answer["choice"] not in JEV_CRITERIA:
        raise ValueError(f"Jev returned unknown route: {answer['choice']}")
    return answer


def route_with_jev(state: dict[str, Any]) -> dict[str, Any]:
    answer = _jev_choice(state)
    return {
        "route": answer["choice"],
        "confidence": float(answer["confidence"]),
        "probabilities": answer.get("probabilities") or {},
        "source": "jev",
    }


def route_with_llm(state: dict[str, Any], llm_context: dict[str, Any]) -> dict[str, Any]:
    result = json_with_llm(ROUTE_HINT, state, **llm_context)
    route = (result.get("result") or {}).get("route")
    if route not in JEV_CRITERIA:
        raise RouteError(result.get("error") or f"LLM returned unknown route: {route}")
    return {"route": route, "confidence": None, "probabilities": {}, "source": "llm_fallback"}


def choices_for(message: str, probabilities: dict[str, float] | None = None) -> list[dict[str, str]]:
    """Buttons offered when the intent is unclear: likeliest routes first."""
    ranked = sorted(
        CHOICE_ROUTES, key=lambda name: -(probabilities or {}).get(name, 0.0),
    )
    return [{"label": ROUTE_LABELS[name], "route": name, "message": message} for name in ranked]


def decide_route(
    message: str,
    *,
    tables: set[str],
    similar_matched: bool,
    forced_route: str | None,
    llm_context: dict[str, Any],
) -> dict[str, Any]:
    """Return {route, source, confidence, probabilities, clarify, jev_error?}.

    A user's own choice or a matched expected question needs no model call.
    Jev failures are recorded in the result, never hidden; if the chat LLM also
    fails a RouteError is raised.
    """
    if forced_route in ANSWER_ROUTES:
        return {"route": forced_route, "source": "user_choice", "clarify": False}
    if similar_matched:
        return {"route": "data_query", "source": "similarity", "clarify": False}

    state = {"question": message, "tables": sorted(tables), "has_similar_question": False}
    jev_error = None
    if config.TYPESAFE_API_KEY:
        try:
            decision = route_with_jev(state)
        except Exception as exc:
            jev_error = _error_message(exc, config.TYPESAFE_API_KEY)
    else:
        jev_error = "TYPESAFE_API_KEY is not configured"
    if jev_error:
        decision = route_with_llm(state, llm_context)
        decision["jev_error"] = jev_error

    confident = decision["confidence"] is None or decision["confidence"] >= config.ROUTE_MIN_CONFIDENCE
    decision["clarify"] = decision["route"] == "other" or not confident
    return decision
