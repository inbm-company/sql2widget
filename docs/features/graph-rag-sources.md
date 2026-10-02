# 기능: 최소 그래프 기반과 문서 기능 분리

| 항목 | 내용 |
|------|------|
| 문서명 | 기능: 최소 그래프 기반과 문서 기능 분리 |
| 기준일 | 2026-10-02 (분리 후 구현 기준) |
| 관련 문서 | [README](../../README.md), [기능 색인](README.md) |

문서 업로드·스키마 협의·엔티티 추출·문서 질의응답·그래프 화면은 독립 프로젝트 `doc2graph`로 이동했다. sql2widget에는 문서 그래프 API/테이블/화면이 없다.

`backend/app/graph_backend.py`에 선택적 Neo4j 연결·읽기 실행·종료·오류 처리만 남겼다. 기본 `GRAPH_ENABLED=false`이며 SQL 채팅과 서버 시작에서 접속하지 않는다. 별도 UI나 공개 그래프 API는 제공하지 않는다.

필요 시 내부 기능에서 사용할 연결 설정은 `GRAPH_ENABLED`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`다. 사용 대상을 새로 정의한 것은 아니므로 그래프 서버 없이도 DB 앱 전체가 실행된다.
