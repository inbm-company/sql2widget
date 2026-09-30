# agent4any

자연어로 **SOC 보안 데이터**를 조회하고, 차트·리스트 위젯을 **대화별 스테이지**에 배치하는 에이전트 MVP.

기획: [docs/PLAN.md](docs/PLAN.md) · UI: [docs/UI_BRIEF.md](docs/UI_BRIEF.md)

## Quick start (Docker)

```powershell
Copy-Item .env.example .env
```

`.env`의 `NEO4J_PASSWORD`에 임의의 비밀번호(최소 8자)를 설정한 뒤 실행한다.
기존 `.env`가 있으면 복사로 덮어쓰지 않고 이 항목만 추가한다.

```powershell
docker compose up --build
```

고객 DB 스키마를 바꾼 뒤 기존 볼륨이 남아 있으면:

```powershell
docker compose down -v
docker compose up --build
```

- Frontend: http://127.0.0.1:5173
- API: http://127.0.0.1:8001/api/health (host `8000` 충돌 시 `8001` 사용)
- Service DB host port: `5434` (container `5432`; host `5432`가 이미 쓰이면 충돌 방지)
- Sample customer DB host port: `5436` (if `5433` is already used)
- Full Northwind sample DB host port: `5437` (operational date fields are recentized across 2026-08-01 to 2026-09-10)
- SKAX NMS snapshot DB host port: `5438` (`cinamon` schema, including table data)

Login:

```text
admin@example.com
demo-password
```

## Sample questions (SOC)

1. 지난달 공격당한 서버들의 공격 순위, 방법, 해결 방안을 보여줘.
2. 공격 유형별 비중을 보여줘.
3. 심각도별 공격 현황을 보여줘.
4. 자산별 위험도 순위를 보여줘.
5. 최근 7일 공격 추이를 보여줘.
6. 열린 취약점 목록을 보여줘.
7. 차단된 IP 목록을 보여줘.
8. SOC 보안 현황을 보고서 형태로 만들어줘.

Full Northwind sample questions (Gemini key required for generic schema reasoning):

1. 고객별 총 주문 금액 순위를 보여줘.
2. 카테고리별 매출 비중을 보여줘.
3. 월별 주문 매출 추이를 보여줘.

SKAX NMS는 관리자 연결 목록의 `SKAX NMS DB`를 선택해 사용한다. 이 데이터베이스도
실제 AI 연결 설정(키)이 있어야 자연어 스키마 추론이 동작한다.

## State rules

1. Server fetch → `useSWR`
2. Global UI slots → `useStore` (no Provider / `SWRConfig`)
3. Immediate local UI → `useState`

## LLM

채팅은 항상 실모델 호출로만 응답한다:

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

키가 없거나 요청이 실패하면 추측해서 대신 답하지 않고 에러를 그대로 화면에 표시한다(HTTP 502). 사용량은 `llm_usage` 테이블에 기록.

브라우저 Admin의 Gemini 기본 모델은 `gemini-3.6-flash`다. 이전 `gemini-2.5-flash` 설정은 신규 Gemini API 사용자에게 제공되지 않아 앱이 자동으로 `3.6`으로 마이그레이션한다.

## Smoke

```powershell
docker compose exec backend pytest -q
docker compose exec backend python scripts/smoke_eval.py
docker compose exec backend python scripts/smoke_stage.py
```

## 예상 질문 유사도 DB

사용자 질문 → 선택한 DB의 유사 예상 질문 검색 → 연결된 SQL·위젯 정보를 참고해 답변을 생성합니다. 관리자에서 AI 설정 후 DB를 선택해 **예상 질문 생성**을 누르면 모든 테이블을 순회하며 질문을 생성합니다. 역할 선택이나 고정 생성 개수는 없습니다. 기존 실행 환경에는 `docker compose exec backend python scripts/migrate_chat_vector.py`를 적용합니다. [생성 절차·저장 구조·API](docs/features/similarity-search-design.md).

## Neo4j 로컬 설치 (Graph RAG 준비)

Neo4j Community `2026.09.0`을 독립 서비스로 실행한다. 이번 단계는 설치·인증·영속 저장·접속 확인까지이며, 데이터 소스 지정, 데이터 적재, 그래프 모델링, Graph RAG 검색 및 백엔드 연동은 아직 구현하지 않았다. Python 드라이버와 추가 플러그인도 설치하지 않는다.

`.env`에 `NEO4J_PASSWORD`를 설정한 뒤 기존 앱을 재시작하지 않고 Neo4j만 기동할 수 있다.

```sh
docker compose config --quiet
docker compose up -d --no-deps --wait --wait-timeout 300 neo4j
docker compose ps neo4j
```

- Neo4j Browser: http://127.0.0.1:7474/browser/
- 호스트 Bolt 주소: `bolt://127.0.0.1:7687`
- 같은 Compose 네트워크에서의 Bolt 주소: `bolt://neo4j:7687`
- 사용자 이름: `neo4j`, 비밀번호: 로컬 `.env`의 `NEO4J_PASSWORD`
- 두 호스트 포트는 `127.0.0.1`에만 바인딩한다.
- 데이터는 `neo4j_data` → `/data`, 로그는 `neo4j_logs` → `/logs` named volume에 보관한다.
- 로컬 메모리 설정: 초기 heap 256 MiB, 최대 heap 512 MiB, page cache 256 MiB. 실제 데이터 적재 규모에 따라 다음 단계에서 조정한다.

인증된 Bolt 연결은 노드 생성 없이 다음 명령으로 확인한다. Compose healthcheck도 같은 방식으로 `RETURN 1`을 실행한다.

```sh
docker compose exec -T neo4j sh -c 'cypher-shell -a bolt://localhost:7687 -u neo4j -p "${NEO4J_AUTH#*/}" "RETURN 1 AS connected;"'
```

`docker compose restart neo4j` 또는 컨테이너 재생성 시 named volume은 유지된다. `docker compose down -v`는 Neo4j를 포함한 모든 Compose DB 볼륨을 삭제하므로 데이터를 보존해야 할 때는 사용하지 않는다. 초기 비밀번호는 빈 데이터 볼륨에서만 적용된다. 기존 볼륨의 비밀번호는 `.env` 값 변경만으로 바뀌지 않는다.

설치 기준: [Neo4j 공식 Docker 문서](https://neo4j.com/docs/operations-manual/current/docker/introduction/), [Docker 환경변수 설정](https://neo4j.com/docs/operations-manual/current/docker/configuration/).
