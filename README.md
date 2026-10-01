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

클라우드 키가 없거나 요청이 실패하면 추측해서 대신 답하지 않고 에러를 그대로 화면에 표시한다(HTTP 502). 사용량은 `llm_usage` 테이블에 기록.

브라우저 Admin의 Gemini 기본 모델은 `gemini-3.6-flash`다. 이전 `gemini-2.5-flash` 설정은 신규 Gemini API 사용자에게 제공되지 않아 앱이 자동으로 `3.6`으로 마이그레이션한다.

AI 설정 패널은 Gemini / OpenAI 호환 / 로컬 모델을 지원하며 Provider별로 모델·API 키·URL을 따로 저장한다. 백엔드 요청 처리는 `backend/app/providers/`, 공통 프롬프트는 `backend/app/prompts.py`에 있다.

로컬 모델은 별도로 실행한 **OpenAI 호환 API 서버**에 연결한다. AI 설정에서 로컬 모델을 선택하고 Base URL과 서버에 설치된 채팅 모델 이름을 입력한 뒤 저장한다. API 키는 선택 사항이다. Docker Desktop 백엔드에서 호스트의 Ollama 서버에 연결하는 URL 예시는 `http://host.docker.internal:11434/v1`; 백엔드를 직접 실행하면 `http://localhost:11434/v1`을 사용한다. 다른 서버의 포트는 직접 지정한다. 모델 설치나 서버 실행을 앱이 대신하지 않는다. [Ollama 호환 API](https://docs.ollama.com/api/openai-compatibility).

서버 환경변수로 설정할 수도 있다:

```env
LLM_PROVIDER=local
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=설치된-채팅-모델-이름
LLM_API_KEY=
LLM_EMBEDDING_MODEL=설치된-임베딩-모델-이름
```

`LLM_EMBEDDING_MODEL` 또는 로컬 패널의 Embedding model은 선택 사항이다. 비워 두면 유사도 검색 없이 채팅을 사용할 수 있다. 예상 질문 생성·저장에는 임베딩 모델이 필요하며 벡터 차원은 기존 `CHAT_EMBEDDING_DIM`(기본 1536)과 일치해야 한다. 설정 변경을 위해 기존 벡터 DB 차원을 임의로 바꾸지 않는다.

## Smoke

```powershell
docker compose exec backend pytest -q
docker compose exec backend python scripts/smoke_eval.py
docker compose exec backend python scripts/smoke_stage.py
```

## 예상 질문 유사도 DB

사용자 질문 → 선택한 DB의 유사 예상 질문 검색 → 연결된 SQL·위젯 정보를 참고해 답변을 생성합니다. 관리자에서 AI 설정 후 DB를 선택해 **예상 질문 생성**을 누르면 모든 테이블을 순회하며 질문을 생성합니다. 역할 선택이나 고정 생성 개수는 없습니다. 기존 실행 환경에는 `docker compose exec backend python scripts/migrate_chat_vector.py`를 적용합니다. [생성 절차·저장 구조·API](docs/features/similarity-search-design.md).

## Neo4j 로컬 설치 (Graph RAG 준비)

Neo4j Community `2026.09.0`을 독립 서비스로 실행한다. 설치·인증·영속 저장에 더해 아래의 로컬 문서 등록·적재 기능이 동작한다. 질문에서 그래프를 검색하는 연동과 LLM 개체·관계 추출은 아직 구현하지 않았다. 연결에는 공식 Python 드라이버 `neo4j==6.3.1`을 사용하며, 추가 Neo4j 플러그인은 설치하지 않는다.

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

## 문서 업로드·적재

사이드바에서 **프로젝트를 선택**한 뒤 **DB 관리 → Graph RAG 데이터 소스**에서 이름을 입력하고 **폴더 선택**(하위 폴더 포함) 또는 **파일 선택**으로 문서를 고른 뒤 **문서 올리기**를 누른다. 서버 경로나 공유 폴더 설정은 없으며, 어느 컴퓨터에서 접속해도 같은 방식으로 동작한다. 올린 문서는 서비스 DB에 보관되고, 업로드만으로는 적재하지 않는다. 목록의 **적재** 버튼을 눌러 Neo4j에 저장한다. 문서를 고쳤다면 **폴더/파일 다시 올리기**로 교체한 뒤 다시 적재한다. 상태·마지막 적재 결과는 테넌트·프로젝트별로 서비스 DB에 저장해 새로고침 후에도 유지한다.

현재 대상은 UTF-8 `.md`·`.txt`다. 숨김 파일·폴더(`.git`, `.obsidian` 등)와 이미지·PDF 등 미지원 파일은 올리지 않고 제외 개수를 표시한다. 빈 문서는 적재 결과에 제외 개수로 표시한다. 문서당 2 MiB, 한 번에 1,000개·20 MiB까지 지원한다. 운영 nginx는 이 업로드 API 경로에 한해 요청 본문 32 MB를 허용한다.

Neo4j에는 문서·본문 조각(4,000자, 겹침 400자)과 Obsidian `[[문서]]`·Markdown 상대 링크를 저장한다. 실제 적재된 문서 사이의 명시된 링크만 관계로 만든다. 재적재 시 기존 노드를 갱신하고 이전 본문 조각·링크·누락 문서는 `active=false`로 유지한다. 기존 그래프 기록을 삭제하지 않는다.

Stage 헤더의 **그래프**를 누르면 현재 프로젝트의 문서 노드·링크를 볼 수 있다. 노드를 선택하면 본문과 연결된 문서를 확인하고, 제목·경로 검색과 확대·이동도 가능하다. 기본 최대 200개 문서·1,000개 링크, 본문 처음 100,000자를 표시한다. Neo4j 서버는 하나이며 프로젝트별 데이터를 논리적으로 분리한다. 채팅 내부 설정과 질문 검색 연결은 다음 협의 대상이다.

[기능·API·저장 구조](docs/features/graph-rag-sources.md) · [공식 Python 드라이버 연결](https://neo4j.com/docs/python-manual/current/connect/)
