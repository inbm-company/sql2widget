# 기능: Artifact / 위젯 카탈로그

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Artifact 표시 및 위젯 카탈로그 |
| 기준일 | 2026-09-21 (구현 기준) |
| 관련 문서 | [chat.md](chat.md)(Artifact 생성), [stage.md](stage.md)(Stage로 이동) |
| 관련 코드 | `backend/app/config.py`(`ALLOWED_COMPONENTS`), `backend/app/agent.py`(`sanitize_artifact`), `backend/app/agent_service.py`(`rows_to_props`), `frontend/src/widgets/WidgetRenderer.jsx`, `frontend/src/sqlHelpers.js`, `frontend/src/App.jsx`(`AssistantAnswer`, `ArtifactPreviewCard`) |

---

## 용어

| 용어 | 의미 |
|------|------|
| Artifact | 채팅 한 번의 답변에 묶인 위젯 집합. `artifact_id`, `type`(`widget`/`dashboard`/`report`), `widgets[]` |
| Widget | 허용 컴포넌트 하나. `widget_id`, `component`, `title`, `props`, 선택적 `sql` |
| Furniture | 에이전트가 내는 닫힌 카탈로그 JSON을 부르는 제품 용어. 모르는 키/타입은 버려진다 |

---

## F-09 Artifact 표시

- 어시스턴트 메시지에 Artifact가 있으면(`artifact.widgets.length` 또는 `artifact_id` 존재) **Widget / JSON** 세그먼트 토글이 뜬다(`AssistantAnswer`).
- Widget 뷰: 위젯마다 `ArtifactPreviewCard` — 제목, 렌더러, (가능하면) SQL 보기 토글, "Add to stage" 버튼.
- JSON 뷰: Artifact 전체를 pretty-print.
- SQL 보기 가능 여부(`canShowSql`)는 `widget.sql`/`widget.query_ref.sql`/`widget.props.__sql` 중 하나가 있거나, 컴포넌트가 SQL 지원 목록(KpiStat, DataTable, RankList, BarChart, LineChart, PieChart, FilterBar, KpiSparkline, PieTable, BarTable)에 속할 때다. `MarkdownBlock`/`SourceList`는 SQL 없음.
- 실제 SQL 문자열은 `resolveWidgetSql()`이 반환한다: 위젯에 백엔드가 직접 붙인 `sql`/`query_ref.sql`/`props.__sql`만 보여준다 — 없으면 빈 문자열이고 SQL 토글이 숨는다. 추측한 SQL을 대신 보여주지 않는다(2026-09-22, 옛 `FALLBACK_BY_TITLE`/`FALLBACK_BY_COMPONENT` 하드코딩 테이블 삭제).
- 미리보기 카드는 `draggable`(SQL 보기 중이거나 viewer면 제외). viewer는 드래그 핸들도, "Add to stage" 버튼도 없다.

---

## 허용 위젯 카탈로그

서버 `ALLOWED_COMPONENTS`(`backend/app/config.py`)가 유일한 진실. 프론트 `WidgetRenderer`의 `REGISTRY`도 정확히 이 12개와 1:1로 대응한다.

| 컴포넌트 | 용도 | 대표 props |
|----------|------|------------|
| `KpiStat` | 단일 수치 | `label, value, unit?, delta?` |
| `DataTable` | 표 | `columns[{key,label}], rows[]` |
| `RankList` | 순위 목록 | `items[{rank,label,value,meta?}]` |
| `BarChart` | 막대 | `categories[], series[0]{name,data[]}` |
| `LineChart` | 추이 | `series[]{name,points[{x,y}]}` |
| `PieChart` | 비중 | `slices[{label,value}]` |
| `MarkdownBlock` | 설명·보고서 텍스트 | `markdown, citations[]` |
| `SourceList` | 문서 출처 | `sources[{title,version?,section?}]` |
| `FilterBar` | 필터 칩 UI(카탈로그 예약) | `filters[{label,value}]` |
| `KpiSparkline` | KPI + 미니 추이 | `label,value,unit?,delta?,points[{x,y}]` |
| `PieTable` | 파이 + 표 (컨테이너 쿼리로 레이아웃 전환) | `slices[], columns?, rows?` |
| `BarTable` | 막대 + 표 (+선택 KPI 헤더) | `label?,value?,categories[],series[],columns?,rows?` |

렌더링은 Recharts(`WidgetRenderer.jsx`). `PieTable`/`BarTable`/`KpiSparkline`은 자체 CSS(`cq-composite`)로 두 서브뷰를 하나의 위젯 안에 쌓는 합성 컴포넌트다.

### 화이트리스트 위반 시 동작이 다르다

| 경로 | 목록 밖 컴포넌트 처리 |
|------|------------------------|
| 채팅 Artifact (`sanitize_artifact`) | `DataTable`로 치환. 원래 `props`에 `columns`가 없으면 "Unsupported component fell back to table" 안내 행으로 대체 |
| Stage 저장 (`stages.add_widget` / `replace_stage_widgets`) | `ValueError` → API가 **400**으로 거부. 폴백 없음 |

### 빈 결과일 때 props (`rows_to_props`, 실 LLM 경로)

SQL 실행 결과가 0행이면 컴포넌트별로 빈 상태 props를 만든다: `KpiStat`은 `value: 0`, `DataTable`은 "결과 없음" 안내 행, `BarChart`/`LineChart`/`RankList`/`PieChart`는 빈 배열.

---

## 관련 자료

- LLM이 Artifact JSON을 만드는 프롬프트 규격(`SCHEMA_HINT`)은 [chat.md](chat.md)에서 다룬다.
- Stage에 위젯을 올리는 절차는 [stage.md](stage.md) F-10을 본다.
