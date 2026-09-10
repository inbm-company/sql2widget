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
- Northwind-style sample DB host port: `5437`

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

Northwind-style sample questions (Gemini key required for generic schema reasoning):

1. 고객별 총 주문 금액 순위를 보여줘.
2. 카테고리별 매출 비중을 보여줘.
3. 월별 주문 매출 추이를 보여줘.

## State rules

1. Server fetch → `useSWR`
2. Global UI slots → `useStore` (no Provider / `SWRConfig`)
3. Immediate local UI → `useState`

## LLM (P2)

기본은 Mock. 실모델:

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

키가 없으면 Mock을 사용한다. 키가 설정된 실모델 요청의 오류는 Mock으로 숨기지 않고 화면에 표시한다. 사용량은 `llm_usage` 테이블에 기록.

브라우저 Admin의 Gemini 기본 모델은 `gemini-3.6-flash`다. 이전 `gemini-2.5-flash` 설정은 신규 Gemini API 사용자에게 제공되지 않아 앱이 자동으로 `3.6`으로 마이그레이션한다.

## Smoke

```powershell
docker compose exec backend pytest -q
docker compose exec backend python scripts/smoke_eval.py
docker compose exec backend python scripts/smoke_stage.py
```
