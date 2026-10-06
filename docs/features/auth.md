# 기능: 로그인/세션

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 로그인/세션 |
| 기준일 | 2026-10-06 (구현 기준, 기획과 다르면 코드가 맞음) |
| 관련 문서 | [AGENTS.md](../../AGENTS.md), [01-folder-structure.md](../01-folder-structure.md) |
| 관련 코드 | `backend/app/auth.py`, `backend/app/main.py`(`/api/auth/*`), `frontend/src/App.jsx`(`LoginForm`, `App`), `frontend/src/api.js` |

---

## F-01 로그인

| 항목 | 내용 |
|------|------|
| 액터 | 모든 역할 |
| 입력 | `email`, `password` |
| 처리 | 이메일을 소문자·trim 후 조회 → `argon2`로 비밀번호 검증 → JWT access + refresh 발급 |
| 출력 | `access_token`, `refresh_token`, `user { id, email, role, tenant_id }` |
| 저장 | 브라우저 `localStorage` (`agent4any_access`, `agent4any_refresh`) |
| 실패 | 401 `Invalid credentials` |
| 입력란 초기값 | 개발 서버(`import.meta.env.DEV`)에서만 데모 계정(`admin.local@example.com`/`demo-password`)을 미리 채운다. 운영 빌드(`Dockerfile.production`의 `npm run build`)는 빈 값이며 해당 문자열이 번들에 포함되지 않는다. |

- Access 토큰 만료: 기본 30분(`JWT_ACCESS_MINUTES`)
- Refresh 토큰 만료: 기본 14일(`JWT_REFRESH_DAYS`)
- `LoginForm`은 개발 서버에서만 로컬 데모 값을 채우며, 운영 빌드는 빈 입력란으로 시작한다. 로컬 관리자 이메일을 바꾸면 Compose가 `VITE_DEV_ADMIN_EMAIL`로 전달한다.

## F-02 세션 복원 / 토큰 갱신

- 앱 시작 시 `access_token`이 있으면 `GET /api/auth/me` 호출 → 성공하면 워크스페이스, 실패하면 로그인 화면.
- API 응답이 401이고 `retry`가 참이며 refresh 토큰이 있고 경로가 `/auth/*`가 아니면, `frontend/src/api.js`가 `/api/auth/refresh`로 한 번 갱신 후 원 요청을 재시도한다. 동시에 여러 요청이 401을 받아도 refresh 호출은 1회로 합쳐진다(`refreshPromise` 공유).
- 갱신도 실패하면 토큰을 지우고 로그인 화면으로 돌아간다.
- 일반 API 요청 타임아웃은 15초(`timeoutMs` 기본값). `/api/chat`만 150초로 별도 지정한다(§ [chat.md](chat.md) 참고 — 실 LLM 응답 + SQL 재시도 여유).

## 역할과 권한

| 역할 | 로컬 시드 계정 | 요약 |
|------|-----------|------|
| `admin` | `admin.local@example.com` / `demo-password` | 채팅, Stage 편집, 대화/프로젝트 생성·수정·삭제, Admin 패널(연결·권한), Viewer 링크 |
| `user` | 로그인 계정 없음(권한 테이블 행만 존재) | API 상 일반 사용자. 연결 생성·권한 변경·SQL 프리뷰는 403 |
| `viewer` | `viewer.local@example.com` / `demo-password` | 본인 프로젝트의 Stage **조회만**. 채팅·DnD·리사이즈·프로젝트/대화 생성·수정·삭제 불가 |

- 프론트에서 `isViewer = user.role === "viewer"`, `canEdit = !isViewer`(`frontend/src/App.jsx` `Workspace`)로 화면 요소를 토글한다. 이건 UX 편의이며 진짜 방어선이 아니다 — 실제 권한은 백엔드 라우트(`require_admin` 등)와 `table_permissions`가 최종 판단한다.
- 모든 대화/프로젝트는 `tenant_id` + `user_id`로 격리된다. 남의 리소스 ID를 알아도 404.

## 화면 권한 요약 (프론트)

| 동작 | admin | viewer |
|------|-------|--------|
| New project / New chat | O | X (버튼 disabled) |
| 질문 전송 / 샘플 질문 | O | X |
| 위젯 드래그·Stage에 추가 | O | X |
| Stage 이동·리사이즈·삭제 | O | X |
| Stage 패널 숨기기 토글 | O | 버튼 자체가 없음(패널은 항상 보임, 편집 불가) |
| Admin 패널 열기 | O | 링크 없음 |
| Open viewer (`/p/{id}/view`) | O (프로젝트 선택 시) | O (프로젝트 선택 시) |
| 연결(Database) 선택 | O | O (조회용 셀렉트, 채팅에는 못 씀) |

---

## API

인증: `Authorization: Bearer <access_token>` (아래 두 엔드포인트만 인증 불필요)

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/auth/login` | 로그인 |
| POST | `/api/auth/refresh` | refresh 토큰으로 access 재발급 |
| GET | `/api/auth/me` | 현재 사용자 정보(세션 복원용) |
| GET | `/api/health` | 헬스체크. `{ ok, provider, effective_provider }`, 인증 불필요 |

## 독립 인증

이 앱의 JWT issuer는 `sql2widget`로 고정한다. 서명뿐 아니라 issuer를 검증하여 다른 앱의 토큰을 거부한다. 브라우저 토큰 키는 `sql2widget_access` / `sql2widget_refresh`다. 계정·세션·프로젝트는 앱별 서비스 DB에서 관리하고 통합 로그인이나 기존 토큰 이전은 제공하지 않는다.

## 로컬·운영 로그인 아이디 분리

로컬 `.env.local`의 기본 아이디는 `admin.local@example.com`·`viewer.local@example.com`, 운영 서버 `.env`의 기본 아이디는 `admin@example.com`·`viewer@example.com`이다. `ADMIN_EMAIL`·`VIEWER_EMAIL`로 지정하며 이메일은 소문자·trim 처리한다. 운영 비밀번호는 서버 설정에서 별도로 관리한다.

`backend/scripts/seed_dev.py`는 기존 `user_admin`·`user_viewer`의 이메일만 갱신한다. 비밀번호 해시·역할·tenant·내부 사용자 ID를 보존하므로 프로젝트·대화·Stage 소유권도 유지한다. 다른 사용자 이메일과 충돌하거나 기존 역할/tenant가 예상과 다르면 초기화를 중단한다.
