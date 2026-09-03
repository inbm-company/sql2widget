"""External document provider — Mock first, local chunks for P4 scaffold."""

from __future__ import annotations

from typing import Any, Protocol

from app.db import fetch_all


class DocumentProvider(Protocol):
    def search(self, query: str, *, tenant_id: str, limit: int = 5) -> list[dict[str, Any]]:
        ...


class MockExternalDocumentProvider:
    DOCS = [
        {
            "doc_id": "doc_ssh",
            "title": "SSH Hardening Guide",
            "version": "1.4",
            "section": "3.2 Brute force",
            "page": "12",
            "content": (
                "SSH 무차별 대입 완화: fail2ban 활성화, 비밀번호 로그인 비활성화, "
                "키 기반 인증만 허용하고 관리 대역에서만 접근을 허용한다."
            ),
            "attack_methods": ["Brute Force SSH", "SSH"],
        },
        {
            "doc_id": "doc_ransomware",
            "title": "Incident Playbook",
            "version": "2.0",
            "section": "Ransomware",
            "page": "8",
            "content": (
                "랜섬웨어 대응: 감염 호스트 격리, 백업 복구 가능성 검증, "
                "네트워크 세그먼트 분리와 권한 최소화를 수행한다."
            ),
            "attack_methods": ["Ransomware"],
        },
        {
            "doc_id": "doc_ddos",
            "title": "Edge Defense Notes",
            "version": "1.1",
            "section": "DDoS",
            "page": "3",
            "content": (
                "DDoS 완화: 엣지 레이트리밋, scrubbing 서비스 연동, "
                "비정상 트래픽 ACL을 적용한다."
            ),
            "attack_methods": ["DDoS"],
        },
    ]

    def search(self, query: str, *, tenant_id: str, limit: int = 5) -> list[dict[str, Any]]:
        q = (query or "").lower()
        hits = []
        for doc in self.DOCS:
            blob = " ".join(
                [
                    doc["title"],
                    doc["section"],
                    doc["content"],
                    " ".join(doc.get("attack_methods") or []),
                ]
            ).lower()
            score = sum(1 for token in q.split() if token and token in blob)
            if score or any(m.lower() in q for m in doc.get("attack_methods") or []):
                hits.append({**doc, "score": score})
        hits.sort(key=lambda d: d["score"], reverse=True)
        return [
            {
                "doc_id": h["doc_id"],
                "title": h["title"],
                "version": h["version"],
                "section": h["section"],
                "page": h["page"],
                "excerpt": h["content"],
            }
            for h in hits[:limit]
        ]


class DatabaseDocumentProvider:
    """Search tenant document_chunks stored internally (originals stay external)."""

    def search(self, query: str, *, tenant_id: str, limit: int = 5) -> list[dict[str, Any]]:
        rows = fetch_all(
            """
            SELECT id, doc_id, title, version, section, page, content
            FROM document_chunks
            WHERE tenant_id = %s
              AND (
                content ILIKE %s OR title ILIKE %s OR section ILIKE %s
              )
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant_id, f"%{query}%", f"%{query}%", f"%{query}%", limit),
        )
        return [
            {
                "doc_id": r["doc_id"],
                "title": r["title"],
                "version": r.get("version"),
                "section": r.get("section"),
                "page": r.get("page"),
                "excerpt": r["content"][:500],
            }
            for r in rows
        ]


def get_document_provider() -> DocumentProvider:
    # Prefer DB chunks when present; Mock covers demo attack guidance.
    return MockExternalDocumentProvider()


def build_solution_from_sources(sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return MarkdownBlock props only when sources exist — never invent."""
    if not sources:
        return {
            "markdown": "근거 문서를 찾지 못해 해결 방안을 제시하지 않았습니다.",
            "citations": [],
        }
    lines = ["### 해결 방안 (문서 근거)", ""]
    citations = []
    for s in sources:
        lines.append(f"- **{s['title']}** ({s.get('section') or 'section n/a'}): {s['excerpt']}")
        citations.append(
            {
                "title": s["title"],
                "section": s.get("section"),
                "ref": f"doc://{s['doc_id']}",
            }
        )
    return {"markdown": "\n".join(lines), "citations": citations}
