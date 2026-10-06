#!/usr/bin/env python3
"""Smoke: login + SOC sample questions against running API."""

import argparse
import json
import os
import sys

import httpx

from app.config import ADMIN_EMAIL

BASE = os.getenv("SMOKE_API_BASE", "http://127.0.0.1:8000")

QUESTIONS = [
    "지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘.",
    "공격 유형별 비중을 보여줘.",
    "심각도별 공격 현황을 보여줘.",
    "SOC 보안 현황을 보고서 형태로 만들어줘.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-ai-error", action="store_true",
        help="Verify HTTP 502 with no AI provider configured, for CI without an AI key.",
    )
    args = parser.parse_args()
    client = httpx.Client(base_url=BASE, timeout=30.0)
    r = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": os.getenv("ADMIN_PASSWORD", "demo-password")},
    )
    r.raise_for_status()
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    projects = client.get("/api/projects", headers=headers).json()
    project_id = projects[0]["id"]

    results = []
    for q in QUESTIONS:
        conv = client.post(
            "/api/conversations", headers=headers, json={"project_id": project_id, "title": q[:30]}
        )
        conv.raise_for_status()
        conv_id = conv.json()["id"]
        chat = client.post(
            "/api/chat",
            headers=headers,
            json={"conversation_id": conv_id, "message": q},
        )
        if args.expect_ai_error:
            body = chat.json()
            ok = (
                chat.status_code == 502
                and "No AI provider configured" in str(body.get("detail", ""))
                and "artifact" not in body
            )
            results.append({"question": q, "ok": ok, "status_code": chat.status_code,
                            "expected_ai_error": True})
        else:
            chat.raise_for_status()
            artifact = chat.json()["artifact"]
            components = [w["component"] for w in artifact.get("widgets", [])]
            ok = len(components) > 0
            results.append({"question": q, "ok": ok, "components": components, "type": artifact.get("type")})
        print(json.dumps(results[-1], ensure_ascii=False))

    passed = sum(1 for r in results if r["ok"])
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
