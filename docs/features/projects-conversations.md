# 기능: 프로젝트 · 대화

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 프로젝트 · 대화 |
| 기준일 | 2026-09-21 (구현 기준) |
| 관련 문서 | [chat.md](chat.md), [stage.md](stage.md) |
| 관련 코드 | `backend/app/repositories/projects.py`, `backend/app/repositories/conversations.py`, `backend/app/main.py`, `frontend/src/App.jsx`(`Workspace`, `ProjectHeader`, `ConversationItem`) |

---

## 용어

| 용어 | 의미 |
|------|------|
| Project | 대화와 Stage를 묶는 최상위 작업 단위. 사용자당 여러 개 가능 |
| Conversation | 프로젝트 안의 개별 채팅 세션. 메시지와 Artifact를 가진다 |
| Stage | 프로젝트당 1개인 핀보드. [stage.md](stage.md) 참고 |

한 프로젝트 아래 여러 대화가 있고, Stage는 **프로젝트에 1개**(대화 단위가 아님)다.

---

## F-03 프로젝트·대화 목록

- `GET /api/projects` — 로그인 사용자의 프로젝트를 `updated_at DESC, created_at DESC` 순으로 반환.
- 사이드바에서 프로젝트를 펼치면 `GET /api/conversations?project_id={id}`로 해당 프로젝트의 대화 목록을 `updated_at DESC` 순으로 표시.
- 대화 행에 마우스를 올리면 이름 변경·삭제 아이콘이 뜬다(편집 가능 역할만, `readOnly={isViewer}`로 제어).

## F-04 프로젝트 / 대화 생성

| API | 입력 | 비고 |
|-----|------|------|
| `POST /api/projects` | `{ title }` | UI 기본값 "새 프로젝트" |
| `POST /api/conversations` | `{ project_id, title }` | UI 기본값 "New Chat" |

- 새 프로젝트를 만들면 즉시 활성 프로젝트로 전환되고 대화 선택은 초기화된다(`activeId = null`).
- viewer는 "New project" / "New chat" 버튼이 `disabled`.
- 대화 제목은 첫 메시지 전송 시 자동 갱신된다(§ [chat.md](chat.md) F-08).

## F-05 대화 이름 변경 / 삭제

- `PATCH /api/conversations/{id}` — 제목 변경(빈 문자열이거나 기존과 같으면 서버 호출 없이 취소).
- `DELETE /api/conversations/{id}` — 대화와 그 메시지만 삭제. **프로젝트 Stage에 이미 추가된 위젯은 유지**(Stage는 프로젝트 소유, 대화 소유가 아니므로).
- 활성 대화를 삭제하면 남은 대화 목록의 첫 번째로 자동 전환, 없으면 빈 채팅 화면.

## F-06 대화 상세

- `GET /api/conversations/{id}` — 메시지 배열 반환. `assistant` 메시지는 `artifact` JSON을 포함한다.

---

## 데이터 모델 (서비스 DB)

```text
projects(id, tenant_id, user_id, title, created_at, updated_at)
conversations(id, tenant_id, user_id, project_id, title, created_at, updated_at)
messages(id, conversation_id, role, content, artifact jsonb, created_at)
```

접근은 항상 `tenant_id` + `user_id`로 필터링된다(저장소 함수 시그니처 참고). 다른 사용자의 `project_id`/`conversation_id`를 넣어도 404.

---

## API 목록

인증: 로그인 필요, 본인 리소스만.

| Method | Path |
|--------|------|
| GET/POST | `/api/projects` |
| PATCH | `/api/projects/{id}` |
| GET | `/api/conversations?project_id={id}` |
| POST | `/api/conversations` |
| GET/PATCH/DELETE | `/api/conversations/{id}` |
