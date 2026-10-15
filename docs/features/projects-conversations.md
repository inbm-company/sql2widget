# 기능: 프로젝트 · 대화

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — 프로젝트 · 대화 |
| 기준일 | 2026-10-15 (질문·답변 개별 삭제) |
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
- 프로젝트 선택 후 빈 채팅 화면의 "New chat" 버튼을 누르면 선택한 프로젝트에 대화를 생성하고 해당 대화로 전환한다. 생성 실패 시 오류를 화면에 표시한다.
- viewer는 "New project" / "New chat" 버튼이 `disabled`.
- 대화 제목은 첫 메시지 전송 시 자동 갱신된다(§ [chat.md](chat.md) F-08).

## F-05 대화 이름 변경 / 삭제

- `PATCH /api/conversations/{id}` — 제목 변경(빈 문자열이거나 기존과 같으면 서버 호출 없이 취소).
- `DELETE /api/conversations/{id}` — 대화와 그 메시지만 삭제. **프로젝트 Stage에 이미 추가된 위젯은 유지**(Stage는 프로젝트 소유, 대화 소유가 아니므로).
- 활성 대화를 삭제하면 남은 대화 목록의 첫 번째로 자동 전환, 없으면 빈 채팅 화면.

### 프로젝트 삭제

- 프로젝트 행에 마우스를 올리거나 키보드 포커스를 두면 삭제(×) 버튼을 표시한다. 활성 프로젝트는 항상 표시하고, viewer에는 표시하지 않는다.
- 프로젝트 제목과 삭제 범위를 확인 창에 안내하며, 취소하면 삭제하지 않는다.
- `DELETE /api/projects/{id}` — 서비스 DB에서 본인 프로젝트와 모든 대화·메시지, Stage·위젯을 한 트랜잭션으로 삭제한다. 채팅 벡터 DB의 해당 대화 메시지 사본도 정리하며, 벡터 DB 정리 실패 시 서비스 DB 삭제를 롤백한다. 두 DB의 커밋은 별개이므로 서비스 DB의 최종 커밋이 실패하면 벡터 사본만 먼저 삭제될 수 있다. 다른 프로젝트는 유지된다.
- viewer 요청은 HTTP 403, 존재하지 않거나 다른 소유자·테넌트의 프로젝트는 HTTP 404다.
- 활성 프로젝트를 삭제하면 프로젝트·대화 선택과 입력을 초기화하고 관련 화면 캐시를 비운다. 삭제 실패 시 프로젝트 행에 오류를 표시한다. UI에서는 응답 생성 중인 활성 프로젝트의 삭제 버튼을 비활성화한다.

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
| PATCH/DELETE | `/api/projects/{id}` |
| GET | `/api/conversations?project_id={id}` |
| POST | `/api/conversations` |
| GET/PATCH/DELETE | `/api/conversations/{id}` |

## 질문·답변 개별 삭제

`DELETE /api/conversations/{conversation_id}/messages/{message_id}`는 로그인한 소유자·테넌트 범위의 선택한 메시지 **한 개만** 삭제한다. 사용자 질문과 어시스턴트 답변 모두 지원한다. viewer는 403, 대상이 없거나 다른 소유자/대화에 속하면 404다. 질문에는 “질문 삭제”, 답변마다 “답변 삭제”를 표시하고 대상 메시지만 삭제한다는 안내 후 확인한다.

- 질문을 삭제해도 연결된 답변·재생성 답변은 남는다. 과거 ID 연결이 없는 답변은 삭제 전에 원래 질문 ID를 기록해 다른 앞 질문에 잘못 붙지 않도록 한다. 질문이 사라진 답변은 독립적으로 표시하며 삭제할 수 있다. 원래 질문이 필요한 다시 생성/계속하기는 제공하지 않는다.
- 답변 한 개를 삭제해도 원래 질문·다른 재생성 답변·다음 질문은 유지한다. 해당 답변에 들어 있던 채팅 위젯·표·출처·처리 내역만 함께 사라진다.
- 대상 메시지를 잠근 뒤 삭제한다. 처리 중 원래 질문이 삭제되면 늦은 새 답변을 저장하지 않는다. 이미 저장된 답변은 삭제하지 않는다.
- 실제 사용자 메시지는 이번 구현 과정에서 삭제하지 않았다. 앱에서 사용자가 메시지 삭제를 확인할 때 실행된다.

Stage 위젯과 프로젝트는 유지한다. 삭제할 답변을 참조하던 과거 Stage 위젯에는 삭제 전에 SQL·DB 조회 참조만 보존한다(배치·표시 설정 유지). 검색용 벡터 사본도 삭제한 메시지 ID 한 개만 정리한다. 벡터 정리가 실패하면 서비스 DB 삭제는 롤백한다. 두 DB의 커밋은 별개이므로 서비스 DB 최종 커밋만 실패하면 벡터 사본이 먼저 지워질 수 있다. 삭제 후 늦은 임베딩 저장으로 사본이 되살아나지 않도록 메시지 잠금 안에서 저장한다.
