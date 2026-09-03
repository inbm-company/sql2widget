# agent4any UI Brief

## Visual direction: Cursor Agent (Light)

Cursor Agent 패널의 **tone & manner** — 라이트, 컴팩트, 콘텐츠 우선.

| Token | Value |
|-------|--------|
| Background | `#FFFFFF` |
| Surface elevated | `#F6F6F6` |
| Text | `#3C3C3C` |
| Text bright | `#1E1E1E` |
| Muted | `#717171` |
| Accent | `#0066CC` |
| Border | `#E8E8E8` |
| User bubble | `#F4F4F5` |

**Fonts**

- UI: `system-ui` stack (Cursor 기본)
- Code / tables: system monospace

Avoid: serif brand fonts, teal palette, body gradients, heavy card chrome, uppercase section labels.

## Layout (3-pane)

```text
[History 240px] [Chat flex] [Stage flex]
```

- Left: compact history list, `+ New chat`, footer links (Admin / Stage / Sign out)
- Center: chat header (title), message thread, Cursor-style composer box
- Right: stage grid with subtle dot background

## Chat patterns (Cursor-like)

- User message: right-aligned subtle bubble
- Assistant: plain text flow + inline artifact section (Widget / JSON segmented toggle)
- Empty chat: **Suggested** prompt rows (not heavy cards)
- Composer: rounded box, hint text, blue send button (↑)

## Components (shell only)

- Artifact preview: thin header, text action buttons (`SQL`, `Add to stage`)
- Stage widget chrome: drag handle, title, × remove
- Composite widget **internals** — 별도 iteration

## Domain (demo)

SOC 보안 단일 도메인. 샘플 질문 — [`frontend/src/constants.js`](../frontend/src/constants.js)

## Legacy

- Control Room Light (Fraunces, teal, 패턴) — 폐기
- Tool Light Minimal (라이트 회색) — Cursor Agent Light로 통합
- Cursor Agent Dark — 사용하지 않음
