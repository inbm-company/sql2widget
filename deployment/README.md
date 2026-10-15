# sql2widget 운영 배포

로컬은 `docker compose --env-file .env.local up --build`를 사용합니다. `.env.local` 준비는 루트 README를 참고합니다.
운영은 `compose.production.yml`로 별도 구성합니다. DB/API는 외부 포트를 열지 않으며,
프런트만 `127.0.0.1:3003`에서 정적 화면과 `/api` 프록시를 제공합니다.

## Together AI 설정

배포 후 관리자 AI 설정에서 Together AI를 선택하고 전용 API 키를 입력·저장한다. 기본 URL은 `https://api.together.ai/v1`, 채팅 모델은 `Qwen/Qwen3.5-9B`다. 서버리스 임베딩은 미제공이므로 예상 질문 유사도 검색에는 전용 임베딩 모델이 필요하다. 상세 연결과 제한은 [관리 명세](../docs/features/admin.md#together-ai)를 따른다. 기존 운영 환경변수·키는 자동 변경하지 않는다.

## 서버 Northwind 연결

운영 sql2widget은 서버에 이미 실행 중인 `ai-performance-northwind:5432/northwind`를 사용한다.
백엔드는 기본 네트워크와 외부 `ai-performance_default` 네트워크에 함께 연결한다.
서버 `.env`의 `NORTHWIND_DATABASE_URL`을 Compose가 백엔드에 전달하므로
시작 시 시드가 연결을 로컬용 `127.0.0.1:5548`로 되돌리지 않는다.
접속정보는 서버의 기존 Northwind 설정을 사용하고 비밀번호를 문서·로그에 출력하지 않는다.
Northwind DB 생성·마이그레이션·샘플 재적재를 실행하지 않는다. 로컬 Compose와 앱 코드는 변경하지 않는다.
외부 네트워크와 기존 Northwind DB가 준비돼 있어야 운영 백엔드를 기동할 수 있다.

2026-10-15 서버 `.env`·운영 Compose·백엔드에 위 연결을 반영했다.
현재 이미지 그대로 백엔드만 재생성했으며 기존 DB·볼륨·프런트는 변경하지 않았다.
변경 전 설정·암호화된 연결 레코드는 서버의 접근 제한된 `.northwind-recovery-*`에 보관했다.
2026-10-15 사용자 요청으로 운영 백엔드의 테이블 목록 조회 함수를 1회 실행해 실제 Northwind 접속 및 테이블 14개 조회 성공을 확인했다. 브라우저·실모델·전체 테스트는 실행하지 않았다.

## SKAX NMS (`cinamon`) 운영 DB

운영 스택에는 `db-skax-nms`를 별도 PostgreSQL 서비스로 실행합니다.
Actions가 저장소의 `backend/sql/skax_nms/001_full_dump.sql.gz`와
`002_local_settings.sh`를 서버의 같은 상대 경로에 업로드합니다.
처음 생성하는 `pg_skax_nms_data` 볼륨에 전체 스냅샷(`cinamon` 및 의존하는 `etc` 스키마)을
복원하고, TCP healthcheck가 통과한 뒤 백엔드를 시작합니다. DB 포트는 외부에 공개하지 않습니다.

백엔드는 기존 운영 `POSTGRES_PASSWORD`로 접속하고, `seed_skax_nms.py`가
`SKAX NMS DB`(`dbconn_skax_nms`) 연결 및 admin/user/viewer의 `cinamon` 테이블·뷰 권한을 등록합니다.
배포 스크립트는 `smoke_skax_nms.py`로 등록된 연결의 읽기 전용 접속과 역할별 권한을 확인한 뒤
배포 완료를 기록합니다. 고객 데이터 행이나 비밀번호는 출력하지 않습니다.

재배포는 기존 볼륨을 재사용합니다. 스냅샷 파일 업로드만으로 기존 DB가 덮어써지지 않으며,
기존 서비스·SOC·Global DB 볼륨도 유지합니다. 스냅샷을 갱신하기 위해 볼륨을 삭제하지 마세요.

## GitHub Actions

`.github/workflows/deploy.yml`:
1. PR 및 main push: 프런트 빌드, 서비스/고객 PostgreSQL·pgvector를 포함한 백엔드 테스트, 로그인/채팅 smoke.
2. main push 또는 수동 실행: frontend/backend의 amd64 이미지를 GHCR에 커밋 SHA 태그로 게시.
3. production 환경의 VPS에 배포 파일·SKAX 스냅샷 업로드, 이미지 pull, health 및 SKAX 연결·권한 확인.
4. 배포 실패 시 직전 이미지로 복구. DB 마이그레이션은 자동 되돌리지 않습니다.

테스트 job은 체크아웃 직후 `.env.example`을 `.env.local`로 복사합니다. 환경 기동·테스트·정리는 모두 `--env-file .env.local`을 사용하며, Neo4j 서비스는 실행하지 않습니다. 로컬 및 운영 서버의 비밀번호는 변경하지 않습니다.
SKAX 샘플 DB의 healthcheck는 `127.0.0.1` TCP 접속을 검사해, 덤프 복원 중인 임시
Unix 소켓 서버를 준비 완료로 취급하지 않습니다. API 준비 대기가 실패하면 컨테이너 상태와
백엔드 최근 로그를 출력한 뒤 실패 처리합니다.
AI 키를 등록하지 않는 CI의 채팅 smoke는 `smoke_eval.py --expect-ai-error`로 실행하며,
로그인 성공과 AI 미설정 시 HTTP 502 반환을 검증합니다. 임의의 502 오류나 성공 위젯 응답은
이 모드에서 통과하지 않습니다. 실모델 위젯 생성 검증은 AI 연결을 설정한 뒤 기본 모드로 실행합니다.

필요한 production 환경 변수: `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `DEPLOY_PATH`.
필요한 비밀값: `VPS_SSH_PRIVATE_KEY`, `VPS_HOST_KEY`.
서버의 배포 경로는 배포 사용자가 쓸 수 있어야 합니다.

## 서버 초기 설정

배포 폴더의 `.env`에 아래 항목을 설정합니다. 파일 권한은 600으로 유지합니다.
비밀번호는 URL에 사용할 수 있는 긴 임의 문자열을 사용합니다.

```dotenv
POSTGRES_PASSWORD=<random-password>
APP_SECRET=<at-least-32-random-characters>
ADMIN_EMAIL=admin@example.com
VIEWER_EMAIL=viewer@example.com
ADMIN_PASSWORD=<at-least-16-random-characters>
VIEWER_PASSWORD=<at-least-16-random-characters>
PUBLIC_ORIGIN=https://your-domain
APP_PORT=3003
```

운영 기본 아이디는 `admin@example.com`, `viewer@example.com`이고, 로컬 기본 아이디는 `admin.local@example.com`, `viewer.local@example.com`입니다.
`ADMIN_EMAIL`·`VIEWER_EMAIL`을 바꾸면 기존 시드 계정의 이메일만 갱신하며 내부 사용자 ID·프로젝트·대화·비밀번호는 유지합니다. 다른 사용자가 이미 사용하는 이메일은 거부합니다.
비밀번호는 최초 생성 시 위 환경 변수로만 초기화하며 기존 계정 비밀번호를 덮어쓰지 않습니다. 운영에는 로컬 `.env.local`을 복사하지 마세요.
채팅 의도 라우팅에 쓰는 TypeSafe Jev 키는 서버 `.env`의 `TYPESAFE_API_KEY`에 넣습니다(선택). 비워 두면 Jev 없이 채팅 LLM이 경로를 판단합니다(`meta.route_source = llm_fallback`). `TYPESAFE_BASE_URL`, `TYPESAFE_MODEL`, `ROUTE_MIN_CONFIDENCE`는 compose가 전달하지 않으므로 코드 기본값을 씁니다. 키를 바꾼 뒤에는 백엔드 컨테이너를 재생성해야 합니다.
로그인 후 Admin → AI 연결에 Gemini API 키를 입력합니다.
현재 API 키는 해당 브라우저 localStorage에 저장됩니다. 채팅 요청에만 전달되고,
제공자별 고정 API 주소로 호출합니다. 사용자는 Gemini 모델을 직접 지정할 수 있습니다.
Gemini 기본 모델은 `gemini-3.8-flash`입니다. 이미 저장된 3.6 모델·사용자 지정 다른 모델·API 키는 유지합니다. 기존 2.5 모델의 기본값 전환 규칙은 유지합니다.

외부 접근에는 DNS와 호스트 Nginx HTTPS reverse proxy가 추가로 필요합니다.
Nginx는 해당 도메인을 `http://127.0.0.1:3003`으로 전달하고 응답 제한 시간을 180초로 둡니다.
운영에 개발용 기본 비밀번호를 사용하지 마세요.

## 현재 검증 상태

2026-10-01 격리된 새 Docker 환경에서 백엔드 전체 테스트 124개와
로그인·AI 미설정 오류 smoke 4개를 통과했습니다.
SKAX 운영 Compose도 격리 환경에서 초기 복원·API 연결 목록/연결 테스트·역할별 권한과
백엔드 재생성 후 동일 테이블·뷰 118개 유지까지 확인했습니다.
실제 LLM 위젯 생성은 유효한 사용자 키로 추가 확인해야 합니다.
GitHub Actions의 테스트·이미지 빌드·VPS 배포 결과는 각 실행 로그에서 확인합니다.

## 2026-10-02 기능 분리 반영

DB 앱에서 문서 그래프 라우터·기능·마이그레이션을 제거했고 최소 그래프 기반은 기본 미사용이다. 문서 앱은 doc2graph의 별도 운영 Compose를 사용한다. A 운영 구성에는 기존 SQL 채팅 임베딩/예상 질문에 필요한 db-chat-vector와 마이그레이션 명령을 포함했다. 운영 도메인·배포 경로·기존 볼륨은 이번 로컬 작업에서 변경하거나 재기동하지 않았다. 로컬 .env.local·sql2widget-local 실행은 운영 .env와 별개다. 기존 계정 토큰은 issuer 검증 추가에 따라 다시 로그인해야 한다.

2026-10-06 `6a88140` 운영 배포가 [GitHub Actions #37421027481](https://github.com/inbm-company/sql2widget/actions/runs/37421027481)에서 성공했습니다. 프로젝트 분리 및 로컬/운영 아이디 분리가 적용됐으며 HTTPS 화면·API 200, 모든 컨테이너 healthy, 기존 계정·비밀번호·프로젝트·대화 보존을 확인했습니다. 배포 당시 서버 환경변수 비밀번호와 DB 해시의 기존 불일치는 변경하지 않았으며, 아래 후속 조치로 해결했습니다.

같은 날 사용자 요청으로 기존 운영 관리자·Viewer 비밀번호를 서버 환경변수 값에 맞춰 DB에서 동기화했습니다. `.env` 값·로컬 계정·기존 프로젝트·대화는 유지했고 기존 갱신 토큰은 무효화했습니다. 공개 HTTPS 로그인·세션·프로젝트 조회 모두 200으로 확인했습니다. 이제 `/home/deploy/sql2widget/.env`의 ADMIN_PASSWORD·VIEWER_PASSWORD가 실제 운영 로그인 비밀번호와 일치합니다. 환경변수만 바꾸면 기존 DB 비밀번호가 자동 회전하는 구조는 아닙니다.

## 칸반·HTML 문서 공개

Actions는 `docs/kanban.html`과 `docs/dashboard.html`만 서버의 `public-docs/`에 업로드한다.
프런트는 이 폴더를 `/usr/share/nginx/html/docs`에 읽기 전용으로 연결해
`https://sql2widget.crudy.cloud/kanban`과 `https://sql2widget.crudy.cloud/docs`에서 제공한다.
`frontend/deployment/nginx.conf`가 두 주소에 HTML 파일을 직접 제공하며, 기존
`/docs/kanban.html`·`/docs/dashboard.html` 주소는 각각 `/kanban`·`/docs`로 301 연결한다.
`/kanban/`·`/docs/`도 끝 슬래시 없는 주소로 연결한다.
HTML은 짧은 운영 주소에서만 `/docs/`를 상대 링크 기준으로 설정해 문서 간 이동을 유지한다.
문서 대시보드 본문과 하단 안내는 880px 최대 폭 제한 없이 화면의 사용 가능한 너비를 채운다.
칸반의 표시 카드는 `progress.md` 상태 표의 짧은 요약을 보여주며, 카드 전체를 누르면 같은 문서의 고유 작업 ID로 연결된 상세를 사이드패널에서 읽는다. 상태·영역은 상태 표에서 가져오고 상세에는 범위·근거·미정 사항·완료 판단 기준을 구분한다. 닫기 버튼·Esc·패널 바깥 클릭으로 닫으면 원래 카드로 포커스가 돌아간다. 패널은 생성 HTML 안의 상세를 사용하므로 별도 API 호출이 필요하지 않다.
2026-10-15부터 칸반·대시보드의 기능·메인규칙·폴더 구조·진행도 링크는 공개 대시보드의 해당 항목으로 연결한다.
문서 안의 세부 제목 링크는 제목 앵커로 연결하며, 일치하는 제목이 없으면 해당 문서의 시작으로 이동한다.
`원문`·임시 기록·대시보드에 포함되지 않은 문서는 GitHub 저장소의 파일·폴더로 연결한다. 비공개 저장소는 GitHub 접근 권한이 필요하다.
로컬 HTML 파일 보기와 원본 파일명은 유지한다.
원본 Markdown·임시 기록·환경변수 파일은 공개 폴더에 포함하지 않는다.
HTML은 저장소의 최신 문서 보기를 사용하므로 원본 변경 시 기존 문서 동기화 규칙을 따른다.
HTML만 갱신할 때는 서버의 `public-docs/` 파일을 교체하며 앱 이미지 빌드나 백엔드 재기동은 필요하지 않다.
