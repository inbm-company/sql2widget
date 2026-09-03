import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import GridLayout from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { api } from "./api";
import { setStore, storeKeys, useSWR, useStore } from "./store";
import WidgetRenderer from "./widgets/WidgetRenderer.jsx";

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

export default function StageCanvas({ conversationId, readOnly = false, variant = "default" }) {
  const { data: ui } = useStore(storeKeys.ui);
  const { data: stage, mutate } = useSWR(
    storeKeys.stage(conversationId),
    () => api.getStage(conversationId),
    { revalidateOnFocus: false }
  );
  const [width, setWidth] = useState(480);
  const wrapRef = useRef(null);
  const [localWidgets, setLocalWidgets] = useState([]);

  useEffect(() => {
    if (stage?.widgets) {
      setLocalWidgets(stage.widgets);
    } else {
      setLocalWidgets([]);
    }
  }, [stage]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setWidth(Math.max(280, Math.floor(w)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [conversationId]);

  const layout = useMemo(
    () =>
      localWidgets.map((w) => ({
        i: w.layout?.i || w.id,
        x: w.layout?.x ?? 0,
        y: w.layout?.y ?? 0,
        w: w.layout?.w ?? 4,
        h: w.layout?.h ?? 4,
        minW: 2,
        minH: 2,
      })),
    [localWidgets]
  );

  const persistLayout = useMemo(
    () =>
      debounce(async (nextLayout) => {
        if (!conversationId) return;
        setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "saving" }));
        try {
          await Promise.all(
            nextLayout.map((item) => {
              const widget = localWidgets.find(
                (w) => (w.layout?.i || w.id) === item.i
              );
              if (!widget) return null;
              return api.patchStageWidget(conversationId, widget.id, {
                layout: {
                  i: item.i,
                  x: item.x,
                  y: item.y,
                  w: item.w,
                  h: item.h,
                },
              });
            })
          );
          setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "saved" }));
          mutate();
        } catch {
          setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "error" }));
        }
      }, 500),
    [conversationId, localWidgets, mutate]
  );

  const onLayoutChange = useCallback(
    (next) => {
      if (readOnly) return;
      setLocalWidgets((prev) =>
        prev.map((w) => {
          const item = next.find((n) => n.i === (w.layout?.i || w.id));
          if (!item) return w;
          return {
            ...w,
            layout: {
              i: item.i,
              x: item.x,
              y: item.y,
              w: item.w,
              h: item.h,
            },
          };
        })
      );
      persistLayout(next);
    },
    [persistLayout, readOnly]
  );

  const onDrop = useCallback(
    async (layoutArr, layoutItem, event) => {
      if (readOnly) return;
      event.preventDefault();
      const raw = event.dataTransfer.getData("application/x-agent4any-widget");
      if (!raw || !conversationId) return;
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch {
        return;
      }
      setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "saving" }));
      try {
        const dropProps = { ...(payload.props || {}) };
        if (payload.sql) dropProps.__sql = payload.sql;
        const created = await api.addStageWidget(conversationId, {
          source_widget_id: payload.widget_id,
          source_artifact_id: payload.artifact_id,
          component: payload.component,
          title: payload.title || "",
          props: dropProps,
          layout: {
            i: `tmp_${Date.now()}`,
            x: layoutItem?.x ?? 0,
            y: layoutItem?.y ?? Infinity,
            w: layoutItem?.w ?? 4,
            h: layoutItem?.h ?? 4,
          },
        });
        await mutate();
        setLocalWidgets((prev) => [...prev, created]);
        setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "saved" }));
      } catch {
        setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "error" }));
      }
    },
    [conversationId, mutate, readOnly]
  );

  async function removeWidget(widgetId) {
    if (!conversationId) return;
    await api.deleteStageWidget(conversationId, widgetId);
    setLocalWidgets((prev) => prev.filter((w) => w.id !== widgetId));
    mutate();
  }

  if (!conversationId) {
    return (
      <div className="stage-empty pane-pad">
        <p>대화를 선택하면 스테이지가 열립니다.</p>
      </div>
    );
  }

  const status = ui?.saveStatus || "idle";
  const statusLabel =
    status === "saving"
      ? "저장 중…"
      : status === "saved"
        ? "저장됨"
        : status === "error"
          ? "저장 실패"
          : "대기";

  return (
    <div className={`stage-root ${variant === "orion" ? "stage-root--orion" : ""}`}>
      <header className="stage-header">
        <h2>{variant === "orion" ? "Orion Stage" : "Stage"}</h2>
        {!readOnly ? <span className={`save-status ${status}`}>{statusLabel}</span> : null}
      </header>
      <div
        className={`stage-canvas ${variant === "orion" ? "stage-canvas--orion" : ""}`}
        ref={wrapRef}
        onDragOver={readOnly ? undefined : (e) => e.preventDefault()}
      >
        {localWidgets.length === 0 ? (
          <div className="stage-empty">
            <p>{readOnly ? "배치된 위젯이 없습니다." : "대화의 결과 위젯을 여기로 드래그하세요"}</p>
          </div>
        ) : null}
        <GridLayout
          className="layout"
          layout={layout}
          cols={12}
          rowHeight={36}
          width={width}
          onLayoutChange={readOnly ? undefined : onLayoutChange}
          onDrop={readOnly ? undefined : onDrop}
          isDroppable={!readOnly}
          isDraggable={!readOnly}
          isResizable={!readOnly}
          droppingItem={readOnly ? undefined : { i: "__dropping__", w: 4, h: 4 }}
          draggableHandle={readOnly ? undefined : ".widget-drag-handle"}
          compactType="vertical"
          margin={[12, 12]}
          style={{ minHeight: "100%" }}
        >
          {localWidgets.map((w) => (
            <div key={w.layout?.i || w.id} className="stage-widget">
              {!readOnly ? (
                <div className="widget-chrome">
                  <span className="widget-drag-handle" title="Move">
                    ⠿
                  </span>
                  <span className="widget-title">{w.title || w.component}</span>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => removeWidget(w.id)}
                    aria-label="제거"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <div className="widget-chrome widget-chrome--viewer">
                  <span className="widget-title">{w.title || w.component}</span>
                </div>
              )}
              <WidgetRenderer component={w.component} props={w.props} />
            </div>
          ))}
        </GridLayout>
      </div>
    </div>
  );
}

export async function addWidgetToStage(conversationId, widgetPayload, mutateStage) {
  const stage = await api.getStage(conversationId);
  const yMax = (stage.widgets || []).reduce(
    (max, w) => Math.max(max, (w.layout?.y || 0) + (w.layout?.h || 4)),
    0
  );
  const props = { ...(widgetPayload.props || {}) };
  if (widgetPayload.sql) props.__sql = widgetPayload.sql;
  const composite = ["BarTable", "PieTable", "KpiSparkline"].includes(
    widgetPayload.component
  );
  await api.addStageWidget(conversationId, {
    source_widget_id: widgetPayload.widget_id,
    source_artifact_id: widgetPayload.artifact_id,
    component: widgetPayload.component,
    title: widgetPayload.title || "",
    props,
    layout: {
      i: `tmp_${Date.now()}`,
      x: 0,
      y: yMax,
      w: composite ? 6 : 4,
      h: composite ? 7 : 4,
    },
  });
  if (mutateStage) await mutateStage();
  setStore(storeKeys.ui, (u) => ({ ...u, saveStatus: "saved" }));
}
