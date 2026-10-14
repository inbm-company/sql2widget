# 기능: Artifact / 위젯 카탈로그

| 항목 | 내용 |
|------|------|
| 문서명 | 기능 문서 — Artifact 표시 및 위젯 카탈로그 |
| 기준일 | 2026-10-14 (설명 답변 본문 표시·채팅 프리뷰 320px·SOC 문서 출처 제거) |
| 관련 문서 | [chat.md](chat.md)(Artifact 생성), [stage.md](stage.md)(Stage로 이동) |
| 관련 코드 | `backend/app/config.py`(`ALLOWED_COMPONENTS`), `backend/app/agent.py`(`sanitize_artifact`), `backend/app/agent_service.py`(`_materialize_plan`), `backend/app/widget_queries.py`, `backend/app/catalog_props.py`, `backend/app/widget_props.py`(`rows_to_props`), `frontend/src/widgets/QueryWidget.jsx`, `frontend/src/widgets/widgetData.js`, `frontend/src/widgets/catalogSettings.js`, `frontend/src/widgets/DataTable.jsx`, `frontend/src/widgets/tableData.js`, `frontend/src/widgets/CatalogCards.jsx`, `frontend/src/widgets/tanstackCatalogCharts.js`, `frontend/src/widgets/WidgetRenderer.jsx`, `frontend/src/widgets/tanstackBarChart.js`, `frontend/src/widgets/tanstackAnalyticalCharts.js`, `frontend/src/sqlHelpers.js`, `frontend/src/App.jsx`(`AssistantAnswer`, `ArtifactPreviewCard`) |

---

## 용어

| 용어 | 의미 |
|------|------|
| Artifact | 채팅 한 번의 답변에 묶인 위젯 집합. `artifact_id`, `type`(`widget`/`dashboard`/`report`), `widgets[]` |
| Widget | 허용 컴포넌트 하나. `widget_id`, `component`, `title`, 표시 설정 `props`, SQL 위젯의 `sql`·`query_ref` |
| Furniture | 에이전트가 내는 닫힌 카탈로그 JSON을 부르는 제품 용어. 모르는 키/타입은 버려진다 |

---

## F-09 Artifact 표시

채팅은 필요한 SQL 데이터셋을 먼저 생성·실행하고 실제 컬럼·타입·행 수를 받은 뒤 여러 위젯을 선택한다. 같은 결과를 여러 위젯이 공유할 수 있으며 위젯마다 `column_map`으로 역할을 연결한다. 예를 들어 국가·제품·매출 조회 하나로 원본 DataTable과 국가별 매출 BarChart를 만들 수 있다. 실제 도구 호출마다 결과를 받아 다음 작업을 결정하고 각 위젯을 별도로 생성한다. 여러 단계 결과는 하나의 Artifact로 모으며 아래 데이터 없는 정의·위젯별 현재 조회 방식은 유지한다. 자세한 흐름은 [채팅 명세](chat.md#위젯-선택과-sql-생성-분리)를 따른다.

- `MarkdownBlock` 설명을 본문으로 옮긴 뒤 표시할 위젯이 남아 있을 때만 **Widget / JSON** 세그먼트 토글이 뜬다(`AssistantAnswer`). `artifact_id`만 있는 빈 Artifact에는 표시하지 않는다. JSON 복사는 화면에 남은 위젯 정의를 대상으로 한다.
- 테이블 구조 설명은 전체 채팅 본문으로 반환하며 테이블별 설명·컬럼 표를 본문에서 읽는다. 새 설명 답변은 `MarkdownBlock`을 생성하지 않는다. 과거 채팅의 `MarkdownBlock`은 본문에 표시하고, 이미 Stage에 저장된 항목은 호환성을 위해 기존 렌더러로 표시한다. 기존 저장 데이터는 수정하지 않는다.
- Widget 뷰: 위젯마다 `ArtifactPreviewCard` — 제목, 렌더러, (가능하면) SQL 보기 토글, "Add to stage" 버튼.
- 채팅 미리보기 카드는 테두리·제목을 포함해 높이 320px로 고정한다. 제목 아래 남은 공간을 조회 영역·정적 위젯·SQL 패널이 채우며 새로고침 버튼은 조회 영역 안에 포함된다. Stage·Viewer 위젯은 기존 배치 높이를 따른다.
- JSON 뷰: Artifact의 위젯 정의를 pretty-print. 조회 결과 행·차트 데이터·KPI 값은 포함하지 않는다.
- JSON 뷰의 "JSON 복사" 버튼은 화면에 표시한 Artifact JSON 전체를 들여쓰기와 함께 클립보드에 복사한다. 복사 중에는 중복 클릭을 막고 성공·실패 안내를 복사 버튼 바로 왼쪽에 10px 글자로 표시한다. 클립보드 접근이 불가능하면 JSON을 선택해 직접 복사하도록 안내한다. 읽기 전용 사용자도 복사할 수 있다.
- SQL 보기 가능 여부(`canShowSql`)는 `widget.sql`/`widget.query_ref.sql`/`widget.props.__query_ref.sql`/`widget.props.__sql` 중 하나가 있거나, 컴포넌트가 SQL 지원 목록(KpiStat, DataTable, RankList, BarChart, LineChart, PieChart, FilterBar, KpiSparkline, PieTable, BarTable, StackedBarChart, Heatmap, ScatterChart, Histogram, CompareCard, PivotTable, StatusSummary, EventTimeline, KpiGroup, DetailCard, HorizontalBarChart, ComboChart, BoxPlot, Treemap)에 속할 때다. `MarkdownBlock`/`SourceList`는 SQL 없음.
- 실제 SQL 문자열은 `resolveWidgetSql()`이 반환한다: 위젯에 백엔드가 직접 붙인 `sql`/`query_ref.sql`/`props.__query_ref.sql`/`props.__sql`만 보여준다 — 없으면 빈 문자열이고 SQL 토글이 숨는다. 추측한 SQL을 대신 보여주지 않는다(2026-09-22, 옛 `FALLBACK_BY_TITLE`/`FALLBACK_BY_COMPONENT` 하드코딩 테이블 삭제).
- 미리보기 카드는 `draggable`(SQL 보기 중이거나 viewer면 제외). viewer는 드래그 핸들도, "Add to stage" 버튼도 없다.

---

## 위젯별 데이터 조회 (2026-10-13)

- SQL 위젯 정의는 `component`, `title`, `sql`, `query_ref: {connection_id, sql}`, 표시 설정 `props`와 ID만 저장한다. `rows`, `categories`, `series`, `points`, `cells`, `bins`, KPI `value` 등 조회 결과는 Artifact·Stage에 새로 저장하지 않는다. `MarkdownBlock`·`SourceList`의 본문/출처와 SQL 없는 과거 `FilterBar`의 칩은 유지한다. 새 `FilterBar`는 SQL 조회 위젯이다.
- 생성 루프는 실행한 SQL 결과를 요청 메모리에서 공유한다. `_materialize_plan`은 이 결과에 컬럼 연결을 적용해 각 위젯의 데이터 형식을 확인하며 같은 SQL을 위젯마다 다시 실행하지 않는다. 실제 행은 저장하지 않는다. 실제 표시 데이터는 각 `QueryWidget`이 SWR로 별도 조회한다. 화면을 열거나 새로고침 버튼을 누르면 현재 데이터를 가져오며, 주기적인 폴링은 없다.
- `props.column_map`은 데이터 값이 아닌 컬럼 연결 설정이다. 예: `{"label":"country","value":"product_revenue"}`. Artifact·Stage·Viewer·JSON 복사에서 이를 보존하고 조회 API가 현재 SQL 결과에 적용한다. 같은 SQL을 참조하는 여러 위젯도 서로 다른 연결을 사용할 수 있다. 기존 연결 정보 없는 위젯은 원래 별칭 변환을 유지한다.
- 채팅 미리보기는 `GET /api/conversations/{conversation_id}/widgets/{widget_id}/data`, Stage·Viewer는 `GET /api/projects/{project_id}/stage/widgets/{widget_id}/data`를 호출한다. 응답은 `{props, count}`이며 브라우저 메모리 캐시에만 보관하고 HTTP 캐시는 `no-store`다.
- 서버가 저장된 위젯의 SQL·원본 DB로 조회한다. 브라우저가 SQL·DB를 요청 인자로 보내지 않으며 현재 DB 선택창 변경도 기존 위젯의 조회 DB를 바꾸지 않는다. 소유자·tenant·현재 역할의 테이블 권한을 매 요청 검사하고 기존 SELECT 검증·1000행 제한·10초 SQL 제한을 적용한다. 테이블 권한이 없으면 403이고 데모 권한으로 대체하지 않는다.
- 위젯마다 로딩·빈 결과·조회 오류·다시 조회를 표시한다. DB 연결 오류의 원문/접속 자격증명은 응답하지 않는다. 데이터 새로고침은 LLM을 호출하지 않는다.
- 기존 저장 결과는 DB 일괄 마이그레이션 없이 읽을 때 데이터 필드를 제외한다. 채팅은 메시지 meta의 DB ID, Stage는 소유한 원본 Artifact·위젯의 같은 SQL에서 DB ID를 복원한다. SQL이나 원본 DB를 확인할 수 없으면 409로 질문 재실행을 안내하며 다른 DB로 추측 조회하지 않는다. Stage를 새로 저장하거나 수정하면 데이터 없는 정의로 저장한다.

## 허용 위젯 카탈로그

서버 `ALLOWED_COMPONENTS`(`backend/app/config.py`)가 유일한 진실. 프론트 `WidgetRenderer`의 `REGISTRY`도 정확히 이 26개와 1:1로 대응한다.

아래 props는 조회 API가 반환하는 **실행 시점의 데이터 형태**다. SQL 위젯의 저장 JSON에는 이 데이터 대신 `query_ref`와 표시 설정만 들어간다.

| 컴포넌트 | 용도 | 실행 시점 props |
|----------|------|------------|
| `KpiStat` | 단일 수치 | `label, value, unit?, delta?` |
| `DataTable` | 검색·정렬·페이지 이동이 있는 표 | `columns[{key,label}], rows[]` |
| `RankList` | 순위 목록 | `items[{rank,label,value,meta?}]` |
| `BarChart` | 막대 | `categories[], series[0]{name,data[]}` |
| `LineChart` | 여러 시리즈 추이 비교 | `series[]{name,points[{x,y}]}` |
| `PieChart` | 비중 | `slices[{label,value}]` |
| `MarkdownBlock` | 기존 Stage 설명·보고서 호환용 (채팅은 본문 표시) | `markdown, citations[]` |
| `SourceList` | 문서 출처 | `sources[{title,version?,section?}]` |
| `FilterBar` | 조회 결과의 컬럼별 값 필터·검색·정렬 | `columns[], rows[]` (과거 SQL 없는 위젯은 `filters[]`) |
| `KpiSparkline` | KPI + 미니 추이 | `label,value,unit?,delta?,points[{x,y}]` |
| `PieTable` | 파이 + 표 (컨테이너 쿼리로 레이아웃 전환) | `slices[], columns?, rows?` |
| `BarTable` | 막대 + 표 (+선택 KPI 헤더) | `label?,value?,categories[],series[],columns?,rows?` |
| `StackedBarChart` | 시리즈별 기여도를 누적한 막대 | `categories[], series[{name,data[]}], xLabel?, yLabel?` |
| `Heatmap` | 두 범주 축의 수치 강도 | `cells[{x,y,value}], xLabel?, yLabel?` |
| `ScatterChart` | 두 수치의 관계·이상치 | `points[{x,y,label?}], xLabel?, yLabel?` |
| `Histogram` | 숫자 구간별 빈도 | `bins[{start,end,count}], xLabel?, yLabel?` |
| `CompareCard` | 두 기간/기준의 값·증감 비교 | `label,current,previous,delta,changeRate,unit?` |
| `PivotTable` | 행·열 교차 표와 합계 | `columns[],rows[],totals` |
| `StatusSummary` | 상태별 건수·비율 | `total,items[{label,value,share}]` |
| `EventTimeline` | 실제 사건을 최신순으로 표시 | `items[{occurredAt,title,description?}]` |
| `KpiGroup` | 여러 지표를 한 카드에 표시 | `items[{label,value,unit?}]` |
| `DetailCard` | 한 레코드의 주요 속성 | `fields[{label,value}]` |
| `HorizontalBarChart` | 이름이 긴 항목의 순위/수치 비교 | `categories[],series[0].data[]` |
| `ComboChart` | 별도 좌우 축의 막대·선 | `points[{x,bar,line}],xLabel?,yLabel?,secondaryYLabel?,barLabel?,lineLabel?` |
| `BoxPlot` | 사분위·중앙값·수염·이상치 | `boxes[{label,minimum,q1,median,q3,maximum,outliers[]}]` |
| `Treemap` | 그룹·항목별 비중 | `nodes[{id,parentId,label,group,value}]` |

`BarChart`·`StackedBarChart`·`Heatmap`·`ScatterChart`·`Histogram`·`HorizontalBarChart`·`ComboChart`·`BoxPlot`·`Treemap`은 TanStack Charts 1.1.0의 React/SVG 렌더러를 사용한다. 나머지 차트와 합성 위젯은 Recharts(`WidgetRenderer.jsx`)를 사용한다. `PieTable`/`BarTable`/`KpiSparkline`은 자체 CSS(`cq-composite`)로 두 서브뷰를 하나의 위젯 안에 쌓는 합성 컴포넌트다.

### TanStack Charts 적용 범위 (2026-10-13)

- 기존 `BarChart`의 `categories[]`, `series[0].data[]` 실행 시점 props 계약을 유지하며 첫 번째 시리즈만 표시한다. 저장 JSON은 위젯별 조회 정의로 바뀌었다. 여러 시리즈의 기여도는 신규 `StackedBarChart`로 표시한다.
- `tanstackBarChart.js`·`tanstackAnalyticalCharts.js`·`tanstackCatalogCharts.js`가 고정된 차트 정의를 만든다. LLM이 임의의 TanStack 정의·색상·차트 타입을 생성하는 경로는 없다.
- 채팅 미리보기·Stage·Viewer가 같은 렌더러를 공유한다. 카드의 너비와 높이 변화는 라이브러리의 ResizeObserver가 처리하고, 툴팁은 포인터와 키보드로 확인할 수 있다.
- 중복 항목명은 별도 막대로 유지한다. 0·음수·소수·숫자 문자열을 표시하고, 누락된 값은 기존처럼 0으로 처리한다. 숫자가 아닌 값은 막대에서 제외한다.
- 프런트 테스트 14개, 신규 위젯 백엔드 테스트 26개, Vite 빌드와 브라우저 화면의 크기 변경·빈 결과·키보드 툴팁·StrictMode 재마운트를 확인했다. 로컬 Compose를 띄운 뒤 백엔드 전체 124개 테스트가 통과했다. 실제 Global Sales 데모 DB의 SELECT 결과로 신규 4종을 만들고 Stage 추가/재조회 API 및 Viewer 화면을 확인했다(6개월 누적 매출, 지역·제품 24셀, 판매량·매출 288관측, 매출 9구간). 이 실데이터 화면은 SQL 직접 검증 결과이며 AI가 생성한 응답이 아니다. 서버·현재 브라우저에 AI 키가 없어 실 LLM 호출은 아직 미검증이다.
- Recharts와 함께 사용하므로 빌드의 압축 JS는 최초 적용 전 218.59KB에서 4종 추가 후 264.54KB로 증가했다. 기존 BarChart 적용 대비 추가 증가는 약 4.2KB다.

공식 자료: [개요](https://tanstack.com/charts/latest/docs/overview), [React 빠른 시작](https://tanstack.com/charts/latest/docs/framework/react/quick-start).

### 신규 분석 위젯의 SQL 계약

채팅 계획과 DB별 예상 질문 생성 모두 다음 별칭을 사용한다. 예상 질문의 SQL 위젯 목록은 24개이며 `MarkdownBlock`·`SourceList`를 제외한다.

| 컴포넌트 | SQL 결과 별칭 | 변환 규칙 |
|---|---|---|
| `StackedBarChart` | `category`, `series`, `value` | 같은 범주·시리즈를 합산하고 누락된 조합은 0으로 채운다. 음수는 0 아래에 별도 누적한다. |
| `Heatmap` | `x`, `y`, `value` | 같은 좌표를 합산한다. 수치의 최솟값~최댓값을 고정 파란색 강도와 범례로 표시하며, 누락된 좌표는 빈 공간으로 남긴다. |
| `ScatterChart` | 숫자 `x`, 숫자 `y`, 선택적 `label` | 같은 행의 좌표 쌍을 유지하고 중복 좌표도 보존한다. |
| `Histogram` | `bin_start`, `bin_end`, `count` | DB가 계산한 `[start,end)` 구간을 시작값 순으로 표시한다. 동일 구간은 합산한다. 겹친 구간·폭 0 이하·음수 또는 소수 빈도는 오류다. |

- 필수 별칭이 없거나 유한한 숫자가 아닌 값이 있으면 오류를 반환해 기존 계획 복구 경로로 전달한다. NULL 관측은 제외하며 임의의 0으로 대체하지 않는다.
- 표시 설정은 `catalog_props.DISPLAY_KEYS`의 허용 문자열만 유지한다(축 이름, 복합 차트의 지표/오른쪽 축 이름, 비교 카드의 현재/이전 이름). 데이터 props는 위젯 조회 API에서 SQL 결과로 새로 만든다.
- 히스토그램은 PostgreSQL에서 구간별 집계를 수행한다. 상수 데이터에도 양의 구간 폭을 쓰며, 사용자가 요청하면 빈 구간을 0건으로 포함한다. 원시 관측을 프런트에서 임의로 구간화하지 않는다.


### 카드·목록·새 차트 10종 및 기존 위젯 보강 (2026-10-13)

신규 10종도 조회 정의만 저장하고 현재 데이터는 위젯별 GET으로 가져온다. 기본 Stage 추가 크기는 `w:6 h:7`이며 기존 저장 배치는 유지한다.

| 컴포넌트 | SQL 별칭 | 처리 규칙 |
|---|---|---|
| `CompareCard` | `current`, `previous`, 선택적 `label/unit` | 1행만 허용. 증감액과 증감률을 서버에서 계산하고 이전 값 0/NULL이면 증감률은 계산 불가로 표시한다. 음수 기준은 절댓값을 분모로 쓴다. |
| `PivotTable` | `row`, `column`, `value` | 같은 조합을 합산하고 빈 조합은 0. 행·열·전체 합계를 계산한다. 검색/페이지 이동 중에도 아래 전체 합계는 원래 조회 결과 기준이다. |
| `StatusSummary` | `status`, `count` | 음수가 아닌 정수 건수만 허용. 상태별 건수·전체 대비 비율 표시. |
| `EventTimeline` | `occurred_at`, `title`, 선택적 `description` | 실제 ISO 날짜/시간만 허용하고 최신순으로 정렬. 날짜만 있는 데이터에 시간을 만들어 붙이지 않는다. |
| `KpiGroup` | `label`, `value`, 선택적 `unit` | 지표별 1행. 독립 집계를 UNION ALL 등으로 묶는다. NULL은 알 수 없는 값으로 표시. |
| `DetailCard` | 의미 있는 임의 컬럼 | 0~1행만 허용. 2행 이상은 목록을 임의로 잘라 표시하지 않고 오류. |
| `HorizontalBarChart` | `label`, `value` | SQL 정렬 순서를 유지하고 음수도 표시. |
| `ComboChart` | `x`, `bar_value`, `line_value` | 같은 x 기준의 두 지표. 막대는 왼쪽 축, 선은 독립적인 오른쪽 축. |
| `BoxPlot` | `label`, `minimum`, `q1`, `median`, `q3`, `maximum`, 선택적 `outliers` 배열 | DB에서 전체 자료의 사분위와 Tukey 수염/이상치를 계산한다. 수염~사분위 순서와 이상치 범위를 검증. 제한된 원시 1000행으로 통계를 다시 계산하지 않는다. |
| `Treemap` | `group`, `label`, `value` | 음수 값 거부, 0은 면적 없음. 그룹/항목 합계를 서버의 고정 트리 ID로 구성해 표시. |

- `LineChart`는 모든 시리즈를 표시한다. SQL에 선택적 `series` 별칭을 추가하고 `x/y/series` 쌍은 유일해야 한다. 누락된 관측은 0이 아닌 끊긴 선으로 표시한다. 기존 단일 `x/y` 계약은 유지한다.
- `DataTable`은 컬럼 제목 클릭으로 오름/내림 정렬, 전체 컬럼 검색, 10/25/50행 페이지 이동을 지원한다. 합성 위젯 내부의 표도 같은 기능을 사용한다.
- 새 `FilterBar`는 SQL이 반환한 표의 컬럼과 값을 선택해 해당 위젯 내부 데이터를 필터링한다. 검색·정렬·페이지 이동과 같이 적용되며 기존 SQL 없는 필터 칩은 계속 표시한다.
- 표/필터 동작은 서버가 조회한 최대 1000행의 브라우저 메모리 데이터에 적용된다. DB 전체 검색·서버 페이지 이동·다른 위젯에 적용하는 전역 필터는 아니다. 필터링은 SQL을 재작성하거나 LLM을 호출하지 않는다.
- 신규 컴포넌트는 서버 허용 목록·위젯 선택 프롬프트·SQL 생성 프롬프트·예상 질문 프롬프트·SQL 보기·Stage 복사 경로에 모두 등록한다.

### 화이트리스트 위반 시 동작이 다르다

| 경로 | 목록 밖 컴포넌트 처리 |
|------|------------------------|
| 채팅 Artifact (`sanitize_artifact`) | `DataTable`로 치환. SQL이 있으면 표 데이터로 조회하며 SQL이 없으면 조회 정보 누락 오류를 표시 |
| Stage 저장 (`stages.add_widget` / `replace_stage_widgets`) | `ValueError` → API가 **400**으로 거부. 폴백 없음 |

### 빈 결과일 때 실행 시점 props (`rows_to_props`, 위젯 조회 API)

SQL 실행 결과가 0행이면 컴포넌트별로 빈 상태 props를 만든다: `KpiStat`은 `value: 0`, `DataTable`은 "결과 없음" 안내 행, `BarChart`/`LineChart`/`RankList`/`PieChart`는 빈 배열. 신규 분석 위젯은 각각 빈 `categories/series`, `cells`, `points`, `bins`를 만들고 "결과 없음"을 표시한다.

---

## 관련 자료

- LLM이 Artifact JSON을 만드는 프롬프트 규격(`SCHEMA_HINT`)은 [chat.md](chat.md)에서 다룬다.
- Stage에 위젯을 올리는 절차는 [stage.md](stage.md) F-10을 본다.
