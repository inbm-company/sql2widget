# 기능: Stage (핀보드)

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Stage 배치 |
| 기준일 | 2026-09-21 (구현 기준) |
| 관련 문서 | [widgets-artifact.md](widgets-artifact.md)(위젯 카탈로그), [viewer.md](viewer.md)(읽기 전용 표시) |
| 관련 코드 | `backend/app/repositories/stages.py`, `backend/app/main.py`(`/api/projects/{id}/stage*`), `frontend/src/StageCanvas.jsx` |

Stage는 프로젝트당 정확히 1개인 핀보드다. 채팅에서 나온 위젯을 사용자가 직접 배치·저장한다 — 에이전트가 완성된 대시보드를 자동 생성하지 않는다([AGENTS.md](../../AGENTS.md) 제품 규칙 2).

---

## F-10 Stage에 위젯 추가

두 가지 경로 모두 최종적으로 `POST /api/projects/{id}/stage/widgets`를 호출한다.

1. **드래그**: `ArtifactPreviewCard`가 `dataTransfer`에 MIME 타입 `application/x-agent4any-widget`로 위젯 JSON을 싣는다. `StageCanvas`의 그리드가 `onDrop`에서 이를 파싱해 드롭 좌표(`layoutItem.x/y`)에 추가한다.
2. **버튼**: 카드의 "Add to stage" 클릭 → `addWidgetToStage()` 헬퍼가 현재 Stage의 최대 `y`값 아래(`yMax`)에 이어 붙인다.

공통 처리:

- `component`가 화이트리스트 밖이면 **400**으로 거부(채팅 쪽 `DataTable` 폴백과는 다르다 — § [widgets-artifact.md](widgets-artifact.md)).
- 위젯에 SQL이 있었으면 `props.__sql`에 실어 함께 저장(나중에 Stage에서도 SQL 보기가 가능하도록).
- 합성 위젯(`BarTable`, `PieTable`, `KpiSparkline`)은 기본 크기 `w:6 h:7`, 그 외는 `w:4 h:4`(버튼 경로 기준. 드래그 경로는 그리드가 준 드롭 크기를 그대로 쓰고 기본값은 `w:4 h:4`).
- `source_widget_id` / `source_artifact_id`로 어떤 채팅 응답에서 왔는지 추적.

## F-11 Stage 배치 / 저장

- 프로젝트당 Stage 1행. `GET .../stage` 호출 시 없으면 생성(`get_or_create_stage`).
- 레이아웃 엔진은 `react-grid-layout`(12열, `rowHeight: 36`, `margin: [12,12]`, `compactType: "vertical"`).
- 이동·리사이즈(`onLayoutChange`)는 **500ms 디바운스** 후 변경된 위젯들만 `PATCH .../stage/widgets/{id}`로 저장(`persistLayout`). 저장 중에는 로컬 상태(`localWidgets`)를 먼저 갱신해 즉시 반영하고, 실패하면 저장 상태를 `error`로 표시한다.
- 전체 교체: `PUT .../stage` `{ widgets: [...] }` (현재 UI는 이 경로를 안 쓰고 있으나 API는 열려 있음).
- 단건 수정: `PATCH` — `title`/`props`/`layout` 중 보낸 필드만 갱신.
- 삭제: `DELETE .../stage/widgets/{id}`.
- 새로고침해도 SWR 캐시(`storeKeys.stage(projectId)`)를 통해 서버 상태로 복원.
- 빈 Stage 안내: 편집 가능 역할 "대화의 결과 위젯을 여기로 드래그하세요", viewer "배치된 위젯이 없습니다."
- 저장 상태 표시줄(`대기` / `저장 중…` / `저장됨` / `저장 실패`)은 전역 슬롯 `storeKeys.ui`(`useStore`)에 있다. 편집 불가 역할(`readOnly`)에는 표시하지 않는다.
- 위젯 크기는 `minW:2, minH:2`로 제한.

---

## 데이터 모델 (서비스 DB)

```text
stages(id, project_id UNIQUE, tenant_id, user_id, updated_at)
stage_widgets(
  id, stage_id, source_widget_id?, source_artifact_id?,
  component, title, props jsonb,
  layout_i, layout_x, layout_y, layout_w, layout_h,
  updated_at
)
```

- `stages.project_id`가 유니크 — 프로젝트당 1행이라는 규칙이 DB 레벨에서도 강제된다.
- `stage_widgets`는 `layout_y ASC, layout_x ASC` 순으로 조회된다.
- `props`는 `jsonb`로 저장되며 화이트리스트 검증은 저장소 함수(`add_widget`/`replace_stage_widgets`)에서 `ALLOWED_COMPONENTS`로 수행.

---

## API

| Method | Path | 권한 |
|--------|------|------|
| GET/PUT | `/api/projects/{id}/stage` | 본인(프로젝트 소유자) |
| POST | `/api/projects/{id}/stage/widgets` | 본인 |
| PATCH/DELETE | `/api/projects/{id}/stage/widgets/{widget_id}` | 본인 |

viewer도 GET은 호출되지만(읽기 전용 페이지가 Stage를 불러와야 하므로), 쓰기 경로는 프론트에서 버튼 자체를 렌더링하지 않아 도달하지 않는다. 서버 쪽에서 role로 쓰기를 막는 별도 검사는 없다 — `StageCanvas`의 `readOnly` prop이 유일한 방어선이라는 점에 주의(§ [viewer.md](viewer.md)).
