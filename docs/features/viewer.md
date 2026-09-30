# 기능: Viewer 화면

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Viewer 전용 화면 |
| 기준일 | 2026-09-21 (구현 기준) |
| 관련 문서 | [stage.md](stage.md), [auth.md](auth.md)(역할/권한) |
| 관련 코드 | `frontend/src/ViewerStagePage.jsx`, `frontend/src/StageCanvas.jsx`(`readOnly`/`variant` props), `frontend/src/main.jsx`(라우팅) |

---

## F-12 Viewer 화면

- 경로: `/p/{projectId}/view`. `viewer` 역할 전용 화면이 아니라 **누구나** 갈 수 있는 읽기 전용 뷰(§ [auth.md](auth.md) 화면 권한 표 — admin도 "Open viewer" 링크로 들어간다).
- `StageCanvas`를 `readOnly` + `variant="orion"`으로 감싸기만 하는 얇은 페이지(`ViewerStagePage.jsx`, 33줄).
- 헤더: `← Editor`(워크스페이스로 복귀), 프로젝트 Stage 제목, 기간 표시용 pill("Period: Last 12 months" — 고정 텍스트, 실제 기간 필터는 아직 없음), 로그인 사용자 이메일, Sign out.
- 본문은 Stage 그리드만 전체 화면으로 표시. 채팅 패널·사이드바 없음.

### `readOnly`가 실제로 끄는 것 (`StageCanvas.jsx`)

| 기능 | readOnly=false(기본) | readOnly=true(Viewer) |
|------|----------------------|--------------------------|
| 위젯 드래그 이동 | 가능 | `isDraggable={false}` |
| 위젯 리사이즈 | 가능 | `isResizable={false}` |
| 새 위젯 드롭 | 가능 | `isDroppable={false}`, `onDrop` 미연결 |
| 위젯 제거(×) | 가능 | 제거 버튼 자체를 렌더링하지 않음 |
| 저장 상태 표시줄 | 표시 | 표시 안 함 |
| 빈 Stage 안내 문구 | "대화의 결과 위젯을 여기로 드래그하세요" | "배치된 위젯이 없습니다." |

`variant="orion"`은 시각적 스타일 클래스만 바꾼다(어두운 톤의 레거시 뷰어 자리표시 — [DESIGN.md](../../DESIGN.md)는 이를 "정식 토큰이 아닌 잔재"로 명시하고 있다. 정리 필요 항목은 [progress.md](../progress.md)에서 추적 예정).

### 주의할 점

- `readOnly`는 **프론트엔드 렌더링 제어일 뿐**이다. 백엔드 Stage 쓰기 API는 role을 별도로 검사하지 않는다(§ [stage.md](stage.md) API 절). 즉 이 화면의 "읽기 전용"은 UI 차원의 보장이며, 서버가 role 기반으로 쓰기를 거부하는 것이 아니라는 점을 문서화해둔다.
- 채팅·프로젝트/대화 생성 기능은 이 라우트에 아예 없다 — 접근 자체가 안 된다(컴포넌트가 존재하지 않음).

---

## API

Viewer 화면이 쓰는 API는 Stage 조회 하나뿐이다.

| Method | Path |
|--------|------|
| GET | `/api/projects/{id}/stage` |
