---
name: agent4any
description: Conversation pinboard — ask in chat, pin widgets to a Stage.
colors:
  primary: "#0066cc"
  primary-dim: "rgba(0, 102, 204, 0.1)"
  on-primary: "#ffffff"
  ink: "#3c3c3c"
  ink-bright: "#1e1e1e"
  muted: "#717171"
  muted-dim: "#9a9a9a"
  bg: "#ffffff"
  surface: "#ffffff"
  surface-elevated: "#f6f6f6"
  hover: "#f0f0f0"
  user-bg: "#f4f4f5"
  stage-canvas: "#fafafa"
  border: "#e8e8e8"
  border-subtle: "#ebebeb"
  danger: "#e51400"
typography:
  display:
    fontFamily: "Pretendard, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  headline:
    fontFamily: "Pretendard, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: "normal"
  title:
    fontFamily: "Pretendard, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Pretendard, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Pretendard, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.04em"
  mono:
    fontFamily: "ui-monospace, Cascadia Code, SF Mono, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  kpi:
    fontFamily: "ui-monospace, Cascadia Code, SF Mono, Menlo, Consolas, monospace"
    fontSize: "1.75rem"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  pill: "999px"
spacing:
  2: "2px"
  4: "4px"
  6: "6px"
  8: "8px"
  10: "10px"
  12: "12px"
  14: "14px"
  16: "16px"
  20: "20px"
  24: "24px"
  32: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
  button-send:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    size: "28px"
    width: "28px"
    height: "28px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-bright}"
    rounded: "{rounded.sm}"
    padding: "8px 10px"
  composer:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-bright}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24px"
  widget-card:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
  user-bubble:
    backgroundColor: "{colors.user-bg}"
    textColor: "{colors.ink-bright}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  chip-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.sm}"
    padding: "3px 8px"
---

# Design System: agent4any

## Overview

**Creative North Star: "The Conversation Pinboard"**

A question becomes a card. A useful card gets pinned. The interface is a workbench, not a poster: chat on the left, a dotted Stage on the right, widgets you can grab. Density is high and decoration is absent. Pretendard at 13px, one link-blue accent, hairline borders, and two whites (paper and a slightly cooler wash) do all the sorting.

The mood is restrained operator UI. Gradients, glass, dashboard-hero layouts, and ornamental illustration are out. Filled blue is for the one action that commits (login, send). It does not paint backgrounds.

**Key Characteristics:**

- White paper + `#f6f6f6` wash; almost no shadow
- Cursor Link Blue used for focus, links, and the commit control only
- 11–13px type, 6–8px corners, 240px sidebar
- Stage is a pinboard (dot grid), not a designed dashboard canvas
- Motion is a 3px rise or a 2% drop-in — notice, then stop

## Colors

One accent on a warm-neutral paper desk. Neutrals do the work; blue only points.

### Primary

- **Cursor Link Blue**: focus rings, text links, save-in-progress, KPI deltas, and filled commit buttons. Never a page wash, never a Stage background.
- **Cursor Link Blue wash** (`primary-dim`): 1px focus halo and the grid-drop placeholder.

### Neutral

- **Paper White** (`bg` / `surface`): app chrome, chat pane, cards at rest
- **Cool Wash** (`surface-elevated`): Stage widgets and artifact headers — the only “lift”
- **Stage Dust** (`stage-canvas`): `#fafafa` pinboard under an 18px dot grid
- **Hover Veil** (`hover`): `#f0f0f0` on ghost buttons and list rows
- **User Chip** (`user-bg`): `#f4f4f5` outgoing bubbles
- **Working Ink** (`ink`): default 13px body
- **Title Ink** (`ink-bright`): titles, values, composer text
- **Quiet Ink** (`muted`): labels, Stage header, secondary copy
- **Faint Ink** (`muted-dim`): hints, drag handles, empty Stage
- **Rule** (`border`): `#e8e8e8` pane splits and card edges
- **Hairline** (`border-subtle`): quieter dividers

### Named Rules

**The Link-Only Blue Rule.** Cursor Link Blue is a pointer, not a material. If a surface is larger than a button, it stays paper or wash.

**The Two-White Rule.** Depth is paper vs cool wash. Do not invent a third gray family for “cards.”

## Typography

**Display Font:** Pretendard (system-ui, Segoe UI)
**Body Font:** Pretendard
**Label/Mono Font:** Cascadia / SF Mono / ui-monospace

**Character:** A Korean-first UI face at tool size. Headlines barely exist; the loudest number is a mono KPI, not a marketing display.

### Hierarchy

- **Display** (600, 15px): login brand, viewer title — the largest wordmark
- **Headline** (500, 15px): empty-state titles
- **Title** (500, 13px): chat title, widget titles
- **Body** (400, 13px / 1.5): messages, composer, table cells
- **Label** (400, 11–12px, 0.04em on uppercase): field labels, Stage “STAGE”, artifact type tags
- **Mono** (400, 11px): SQL, JSON, type tags
- **KPI** (500, 1.75rem, mono): the only large figure on a card

### Named Rules

**The No-Poster Type Rule.** Do not introduce a display size above 15px for chrome. Large type is for data (KPI), not for the shell.

## Layout

Three columns on desktop: conversation list (`240px`), chat (flexible), Stage (`minmax(340px, 1.1fr)`). Below `960px` they stack: slim conversation strip, chat, Stage at `minmax(260px, 40vh)`.

Rhythm is 4px. Common steps: 8 / 12 / 16 / 24. Chat messages stack at 20px. Artifact cards stack at 8px. Login card is `min(360px)` with 24px padding.

The Stage canvas is a pinboard: `#fafafa` + radial 1px dots every 18px, 8px inset. Widgets live on `react-grid-layout`. Do not turn the canvas into a designed dashboard grid with hero regions.

## Elevation & Depth

Almost flat. Zones are paper vs cool wash vs hairline border. Shadows appear only as a faint rest state on the user bubble (`0 1px 2px rgba(0,0,0,0.04)`) and the composer (`0 1px 3px rgba(0,0,0,0.06)`). Focus uses a 1px accent ring, not a drop shadow.

### Shadow Vocabulary

- **Bubble rest** (`0 1px 2px rgba(0, 0, 0, 0.04)`): outgoing user message
- **Composer rest** (`0 1px 3px rgba(0, 0, 0, 0.06)`): the input box at rest
- **Focus halo** (`0 0 0 1px` + Cursor Link Blue wash): composer and selected widget

### Named Rules

**The Flat-By-Default Rule.** New chrome gets a border, not a shadow. Shadows stay on the two existing resting objects.

## Shapes

Gently squared. Controls and widgets use 6px; larger chrome (login card, composer, user bubble) uses 8px. Icon-only text buttons may use 4px. Pills (`999px`) are reserved for scrollbar thumbs and any true chip; do not pill the primary button.

Borders are 1px `{colors.border}`. No inner glow, no clipped photography, no squircle.

## Components

Small, tactile, and committal. The filled blue control is the verb. Everything else is a ghost or a paper card.

### Buttons

- **Shape:** 6px corners; 12px label; no uppercase on the primary
- **Primary:** Cursor Link Blue fill, white text, `8px 12px`. Hover brightens 8%. Disabled at 45% opacity
- **Send:** 28×28 filled circle-square; gray wash when empty, blue when the composer has text
- **Ghost:** transparent, 1px border, `6px 10px`. Hover → hover veil
- **Text / icon:** no border; muted ink; 4px radius. Hover adds veil

### Chips

- **Segmented:** paper fill, 1px border, 6px outer radius, 11px muted labels. Active segment uses hover veil + title ink
- **Artifact type:** mono 10px, uppercase, 0.04em, muted — a caption, not a badge pile

### Cards / Containers

- **Login card:** paper, 8px, 1px border, 24px padding, 12px gap. No shadow
- **Artifact preview:** paper, 6px, 1px border, grab cursor. Header strip is cool wash
- **Stage widget:** cool wash, 6px, 1px border. Chrome bar is paper with a hairline under it. Body fills the remaining cell
- **User bubble:** user-chip fill, 8px, 1px border, faint rest shadow, max `min(85%, 640px)`

### Inputs / Fields

- **Login field:** paper, 6px, 1px border, `8px 10px`. Focus: 1px accent outline + accent border
- **Composer:** 8px paper box, faint rest shadow. Focus-within: accent border + 1px blue wash halo. Textarea 13px, placeholder faint ink. No inner outline

### Navigation

- **Sidebar:** 240px, paper, right hairline. Conversation rows 12px/500. Active row is hover veil
- **Chat header / Stage header:** 10–14px padding, bottom hairline. Stage title is 12px uppercase muted
- **<960px:** sidebar collapses to 160px max height; Stage becomes a bottom band

### Signature: Stage pinboard

The product’s distinctive surface. Dotted dust canvas, empty-state 12px faint ink, widgets that drop in at 98% scale. Viewer-only chrome hides drag handles. The dark `/viewer` page currently in CSS is a leftover placeholder and is **not** a token source.

## Do's and Don'ts

### Do:

- **Do** keep chrome at 11–15px Pretendard and put large type only on KPI values.
- **Do** separate zones with paper / cool wash / `#e8e8e8` — not with new shadow tiers.
- **Do** use Cursor Link Blue for the commit control, focus, and links.
- **Do** treat Stage as a pinboard the user fills. Empty dotted canvas is correct.

### Don't:

- **Don't** paint large surfaces with `#0066cc` or gradients.
- **Don't** introduce display type, glass, or a designed dashboard hero on Stage.
- **Don't** copy the dark Orion viewer placeholder (`#060d18`) into the operator UI.
- **Don't** add a third gray family or a second accent.
