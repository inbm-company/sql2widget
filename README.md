# agent4any

자연어로 **SOC 보안 데이터**를 조회하고, 차트·리스트 위젯을 **대화별 스테이지**에 배치하는 에이전트 MVP.

기획: [docs/PLAN.md](docs/PLAN.md) · UI: [docs/UI_BRIEF.md](docs/UI_BRIEF.md)

## Quick start (Docker)

```powershell
Copy-Item .env.example .env
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

## 명령 유사도 DB

사용자 명령 → 선택한 DB의 유사 명령 검색 → 검색된 명령의 SQL·위젯 정보를 참조해 답변을 생성합니다. 관리자에서 AI 설정·역할별 테이블 권한을 저장한 뒤 **명령 유사도 DB → 초기 명령 3개 등록**으로 시작합니다. 기존 실행 환경에는 `docker compose exec backend python scripts/migrate_chat_vector.py`를 적용합니다. [저장 구조·등록 및 검색 API](docs/features/similarity-search-design.md).
