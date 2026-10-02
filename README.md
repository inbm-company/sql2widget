# sql2widget

고객 PostgreSQL에 자연어로 질문하고, 결과를 표·차트·KPI로 받아 프로젝트별 Stage에 배치하는 앱이다. 문서 업로드·엔티티 추출·문서 지식그래프 채팅은 별개 프로젝트 `doc2graph`로 분리했다. 두 앱은 같은 기본 UI를 사용하고 계정·설정·데이터는 독립 관리한다.

## 로컬 실행

```sh
# 파일이 없을 때만 생성. 기존 설정을 덮어쓰지 않는다.
cp -n .env.example .env.local
docker compose --env-file .env.local up -d --build
```

- UI: http://127.0.0.1:5175
- API: http://127.0.0.1:8011/api/health
- 기본 개발 로그인: `admin@example.com` / `demo-password`.
- 새 Compose 이름은 `sql2widget-local`이다. 이전 `sql2widget_*` 볼륨을 삭제하거나 이전하지 않고 새 로컬 데이터로 시작한다.
- 서비스 DB 5544, SOC 5546, Global 5547, Northwind 5548, SKAX NMS 5549, pgvector 5550. 포트는 Compose의 `*_PORT` 변수로 조정할 수 있다.
- `.env.local`은 A 전용이며 B 설정을 공유하지 않는다. 운영 파일은 별도의 강한 비밀번호·APP_SECRET과 이미지명을 요구한다.

## 기능과 설정

DB 연결·테이블 권한·예상 질문·DB 조회/구조 질문·위젯·Stage·Viewer를 제공한다. SOC와 Global Sales는 동등한 데모이고 Northwind·SKAX NMS 샘플도 준비한다. 고객 DB는 읽기 전용 SELECT만 실행한다.

AI 설정에서 Gemini/OpenAI 호환/로컬 모델을 지정하거나 `.env.local`의 LLM_PROVIDER/API_KEY/BASE_URL/MODEL을 설정한다. 로컬 서버는 OpenAI 호환 API를 별도로 제공해야 한다. 키가 없거나 호출이 실패하면 오류를 반환한다. 기존 메시지 임베딩과 예상 질문용 pgvector는 유지한다.

SQL 테이블 선택은 유사 예상 질문을 사용하고 매칭이 없으면 전체 허용 스키마를 전달한다. 문서 그래프를 조회하지 않는다. 기존 SOC 고정 데모 출처 보조 기능은 유지한다.

최소 그래프 연결·읽기 기반은 `backend/app/graph_backend.py`에 남겼다. 기본 `GRAPH_ENABLED=false`이고 서버 시작/DB 채팅에서 Neo4j에 접속하지 않는다. 그래프 UI·문서 API·문서 적재 기능은 없다.

상태관리: 서버 fetch는 useSWR, 전역 UI 슬롯은 useStore, 입력·드래그 로컬 상태는 useState. React JavaScript/FastAPI/psycopg 순수 SQL을 사용한다.

## 검증

```sh
docker compose --env-file .env.local exec -T backend pytest -q
docker compose --env-file .env.local exec -T -e SMOKE_API_BASE=http://127.0.0.1:8000 backend python scripts/smoke_eval.py --expect-ai-error
# 실모델 응답이 설정된 경우에만 질문부터 Stage까지 검증
docker compose --env-file .env.local exec -T backend python scripts/smoke_stage.py
cd frontend
npm ci
node --test tests/*.test.js
npm run build
```

실모델이 설정된 상태의 스모크는 `--expect-ai-error` 없이 수행한다. 이번 분리 검증의 모델 응답은 키 미설정 오류 경로 및 테스트 대역으로 확인했다. `smoke_stage.py`는 모델 응답을 필요로 하므로 키 미설정 상태에서 실패했다. 별도 API 검사로 실제 고객 DB SELECT·DML 거부와 Stage 추가/배치 수정/재조회/삭제를 확인했다.

[분리 설계와 결정 기록](docs/project-separation-proposal.md) · [기능 명세](docs/features/README.md) · [운영 배포](deployment/README.md)
