# 기능 문서 목록

| 문서명 | 기준일 | 관련 문서 |
|--------|--------|-----------|
| 기능 문서 색인 (본 문서) | 2026-09-21 | [AGENTS.md](../../AGENTS.md), [01-folder-structure.md](../01-folder-structure.md) |

`docs/기능명세서.md`(F-01~F-15 통합본)를 기능 단위로 쪼개어 대체한다. 구현 기준으로 작성했으며, 코드와 다르면 코드가 맞다.

| 문서 | 다루는 F-코드 | 요약 |
|------|---------------|------|
| [auth.md](auth.md) | F-01, F-02 | 로그인, 세션 복원/토큰 갱신, 역할별 권한 |
| [projects-conversations.md](projects-conversations.md) | F-03 ~ F-06 | 프로젝트·대화 목록/생성/이름변경/삭제 |
| [chat.md](chat.md) | F-07, F-08 | DB 선택, 채팅(실 LLM 전용), SQL 규칙, 메시지 임베딩 |
| [widgets-artifact.md](widgets-artifact.md) | F-09 | Artifact 표시, 허용 위젯 카탈로그 |
| [stage.md](stage.md) | F-10, F-11 | Stage에 위젯 추가, 배치·자동 저장 |
| [viewer.md](viewer.md) | F-12 | `/p/{id}/view` 읽기 전용 화면 |
| [admin.md](admin.md) | F-13, F-14 | DB 연결 관리, 테이블 권한, AI 연결 설정 |
| [similarity-search-design.md](similarity-search-design.md) | — | DB별 예상 질문 유사도 검색, 전체 테이블의 다양한 예상 질문 생성 |
| [graph-rag-sources.md](graph-rag-sources.md) | — | 프로젝트별 문서 업로드·수동 Neo4j 적재, Stage 그래프·본문 조회 |

F-15(헬스체크)는 별도 문서 없이 [auth.md](auth.md)의 API 표에 포함했다.

전체 문서 지도는 [AGENTS.md](../../AGENTS.md) 3절을 본다.
