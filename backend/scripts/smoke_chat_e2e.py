#!/usr/bin/env python3
"""End-to-end chat smoke against running API."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{BASE}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc


def main() -> int:
    _, login = req(
        "POST",
        "/api/auth/login",
        body={"email": "admin@example.com", "password": "demo-password"},
    )
    token = login["access_token"]
    _, conns = req("GET", "/api/database-connections", token=token)
    names = {c["id"]: c["name"] for c in conns}
    print("connections:", names)
    assert "dbconn_demo" in names
    assert "dbconn_global" in names

    cases = [
        ("dbconn_global", "지역별 매출 순위를 보여줘."),
        ("dbconn_global", "제품별 매출 비중을 보여줘."),
        ("dbconn_global", "최근 12개월 매출 추이를 보여줘."),
        ("dbconn_global", "글로벌 매출 현황을 보고서 형태로 만들어줘."),
        ("dbconn_demo", "공격 유형별 비중을 보여줘."),
        ("dbconn_demo", "심각도별 공격 현황을 보여줘."),
        ("dbconn_demo", "열린 취약점 목록을 보여줘."),
        ("dbconn_demo", "지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘."),
    ]

    failures: list[str] = []
    for connection_id, question in cases:
        _, conv = req(
            "POST",
            "/api/conversations",
            token=token,
            body={"title": f"smoke {connection_id}"},
        )
        status, chat = req(
            "POST",
            "/api/chat",
            token=token,
            body={
                "conversation_id": conv["id"],
                "message": question,
                "connection_id": connection_id,
            },
        )
        if status != 200:
            failures.append(f"{connection_id}: HTTP {status} for {question}")
            continue

        _, detail = req("GET", f"/api/conversations/{conv['id']}", token=token)
        assistant = [m for m in detail["messages"] if m["role"] == "assistant"]
        if not assistant:
            failures.append(f"{connection_id}: no assistant for {question}")
            continue
        artifact = assistant[-1].get("artifact") or {}
        widgets = artifact.get("widgets") or []
        # Ensure JSON round-trip already happened (no Decimal leftovers)
        json.dumps(artifact)
        ok = bool(widgets)
        print(
            f"{'OK' if ok else 'FAIL'} [{connection_id}] widgets={len(widgets)} :: {question}"
        )
        if not ok:
            failures.append(f"{connection_id}: empty widgets for {question}")
            continue

        # Stage add first widget
        w0 = widgets[0]
        _, created = req(
            "POST",
            f"/api/conversations/{conv['id']}/stage/widgets",
            token=token,
            body={
                "source_widget_id": w0.get("widget_id"),
                "source_artifact_id": artifact.get("artifact_id"),
                "component": w0["component"],
                "title": w0.get("title") or "",
                "props": w0.get("props") or {},
                "layout": {"i": "tmp_smoke", "x": 0, "y": 0, "w": 4, "h": 4},
            },
        )
        if not created.get("id"):
            failures.append(f"{connection_id}: stage add failed for {question}")

    # Second pass: repeat global region question 3 times to catch flakiness
    for i in range(3):
        _, conv = req(
            "POST",
            "/api/conversations",
            token=token,
            body={"title": f"repeat-{i}"},
        )
        req(
            "POST",
            "/api/chat",
            token=token,
            body={
                "conversation_id": conv["id"],
                "message": "지역별 매출 순위를 보여줘.",
                "connection_id": "dbconn_global",
            },
        )
        _, detail = req("GET", f"/api/conversations/{conv['id']}", token=token)
        asst = [m for m in detail["messages"] if m["role"] == "assistant"][-1]
        widgets = (asst.get("artifact") or {}).get("widgets") or []
        print(f"OK repeat[{i}] widgets={len(widgets)}")
        if not widgets:
            failures.append(f"repeat[{i}] failed")

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print(f"ALL PASSED ({len(cases)} cases + 3 repeats)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
