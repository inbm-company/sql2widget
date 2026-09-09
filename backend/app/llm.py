"""LLM providers: mock fallback + OpenAI-compatible."""

from __future__ import annotations

import json
import secrets
from typing import Any

import httpx

from app import config
from app.db import execute


SCHEMA_HINT = """
You are a data analyst agent. Return ONLY valid JSON with this shape:
{
  "summary": "short Korean summary",
  "artifact_type": "widget|dashboard|report",
  "widgets": [
    {
      "component": "KpiStat|DataTable|RankList|BarChart|LineChart|PieChart|MarkdownBlock|SourceList|FilterBar|KpiSparkline|PieTable|BarTable",
      "title": "string",
      "sql": "optional SELECT only",
      "props": {}
    }
  ]
}
Composite props:
- KpiSparkline: {label,value,unit?,delta?,points:[{x,y}]}
- PieTable: {slices:[{label,value}], columns:[], rows:[]}
- BarTable: {categories:[], series:[{name,data}], columns:[], rows:[], value?, delta?, label?}
Rules:
- Customer DB is PostgreSQL. SQL must be a single read-only SELECT/WITH.
- Allowed tables only: servers, attack_events, incidents, vulnerability_findings, blocked_ips.
- Prefer aggregations suitable for charts.
- Do not invent document remediation without sources.
- Use only allowed component names.
"""


def log_usage(
    *,
    tenant_id: str,
    user_id: str | None,
    conversation_id: str | None,
    provider: str,
    model: str | None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    success: bool = True,
    error: str | None = None,
) -> None:
    execute(
        """
        INSERT INTO llm_usage (
            id, tenant_id, user_id, conversation_id, provider, model,
            prompt_tokens, completion_tokens, total_tokens, success, error
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            f"usage_{secrets.token_hex(8)}",
            tenant_id,
            user_id,
            conversation_id,
            provider,
            model,
            prompt_tokens,
            completion_tokens,
            prompt_tokens + completion_tokens,
            success,
            error,
        ),
    )


def effective_provider() -> str:
    provider = (config.LLM_PROVIDER or "mock").lower()
    api_key = getattr(config, "LLM_API_KEY", "") or ""
    if provider in {"openai", "openai_compatible", "compatible"} and not api_key.strip():
        return "mock"
    if provider == "openai_compatible":
        return "openai"
    return provider


def plan_with_llm(
    message: str,
    *,
    schema_text: str,
    tenant_id: str,
    user_id: str,
    conversation_id: str | None,
    repair_hint: str | None = None,
    runtime_provider: str | None = None,
    runtime_api_key: str | None = None,
    runtime_model: str | None = None,
    runtime_base_url: str | None = None,
) -> dict[str, Any]:
    provider = (runtime_provider or effective_provider()).lower()
    api_key = runtime_api_key or config.LLM_API_KEY
    if provider in {"gemini", "google"}:
        provider = "gemini"
        runtime_base_url = runtime_base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
        runtime_model = runtime_model or "gemini-2.5-flash"
    elif runtime_provider:
        if provider not in {"openai", "openai_compatible", "compatible", "mock"}:
            return {"provider": "mock", "plan": None, "error": "Unsupported AI provider"}
        provider = "openai" if provider != "mock" else provider
        runtime_base_url = "https://api.openai.com/v1"
    if not api_key.strip():
        provider = "mock"
    if provider == "mock":
        log_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            provider="mock",
            model="mock",
            success=True,
        )
        return {"provider": "mock", "plan": None}

    model = runtime_model or config.LLM_MODEL or "gpt-4o-mini"
    base = (runtime_base_url or config.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    user_content = {
        "question": message,
        "schema": schema_text,
        "repair_hint": repair_hint,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": SCHEMA_HINT},
                        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        usage = data.get("usage") or {}
        content = data["choices"][0]["message"]["content"]
        plan = json.loads(content)
        log_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            success=True,
        )
        return {"provider": provider, "plan": plan, "model": model}
    except Exception as exc:  # noqa: BLE001
        log_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            success=False,
            error=str(exc)[:500],
        )
        return {"provider": "mock", "plan": None, "error": str(exc)}
