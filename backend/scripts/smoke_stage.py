#!/usr/bin/env python3
import os
import sys

import httpx

from app.config import ADMIN_EMAIL

BASE = os.getenv("SMOKE_API_BASE", "http://127.0.0.1:8000")


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=30.0)
    r = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": os.getenv("ADMIN_PASSWORD", "demo-password")},
    )
    r.raise_for_status()
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    projects = client.get("/api/projects", headers=headers).json()
    project_id = projects[0]["id"]
    conv = client.post(
        "/api/conversations", headers=headers, json={"project_id": project_id, "title": "stage smoke"}
    ).json()
    chat = client.post(
        "/api/chat",
        headers=headers,
        json={
            "conversation_id": conv["id"],
            "message": "심각도별 공격 현황을 보여줘.",
        },
    ).json()
    w = chat["artifact"]["widgets"][0]
    added = client.post(
        f"/api/projects/{project_id}/stage/widgets",
        headers=headers,
        json={
            "source_widget_id": w["widget_id"],
            "source_artifact_id": chat["artifact"]["artifact_id"],
            "component": w["component"],
            "title": w["title"],
            "props": w["props"],
            "layout": {"i": "a", "x": 0, "y": 0, "w": 4, "h": 4},
        },
    ).json()
    patched = client.patch(
        f"/api/projects/{project_id}/stage/widgets/{added['id']}",
        headers=headers,
        json={"layout": {"i": "a", "x": 2, "y": 1, "w": 6, "h": 5}},
    ).json()
    stage = client.get(
        f"/api/projects/{project_id}/stage", headers=headers
    ).json()
    ok = (
        len(stage["widgets"]) >= 1
        and patched["layout"]["x"] == 2
        and patched["layout"]["w"] == 6
    )
    print(
        {
            "ok": ok,
            "widgets": len(stage["widgets"]),
            "layout": patched["layout"],
            "component": stage["widgets"][0]["component"],
        }
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
