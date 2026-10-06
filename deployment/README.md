# sql2widget 운영 배포

로컬은 `docker compose --env-file .env.local up --build`를 사용합니다. `.env.local` 준비는 루트 README를 참고합니다.
운영은 `compose.production.yml`로 별도 구성합니다. DB/API는 외부 포트를 열지 않으며,
프런트만 `127.0.0.1:3003`에서 정적 화면과 `/api` 프록시를 제공합니다.

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
