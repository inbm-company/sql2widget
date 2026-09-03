# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are non-technical operators who ask questions in natural language and pin useful results. Two demo audiences are equal, not a primary plus a side case:

- SOC / security staff asking about attacks, vulnerabilities, and incidents
- Sales / analysts asking about revenue, attainment, and regions

A `viewer` role can look at a conversation Stage without moving or resizing widgets. An `admin` role can chat, drag, move, and resize.

## Product Purpose

agent4any turns a natural-language question into catalog widget artifacts (charts, lists, tables, KPI). The user reviews those widgets in chat, then drags a few onto a per-conversation Stage. The Stage auto-saves.

A session succeeds when the right widgets appear in chat and the user pins a few to Stage. A reusable, shareable dashboard is not the success definition for this MVP.

## Positioning

The agent proposes candidate widgets from a closed catalog. The user composes the Stage. There is no finished dashboard template the agent fills in. Neighboring “ask a database” tools can return an answer; this product’s difference is conversation-scoped pinning onto a Stage, not a generated poster dashboard.

## Operating Context

- Local evaluation is Docker Compose: Vite frontend on port 5173, FastAPI on port 8010.
- Login demos: `admin@example.com` / `demo-password`, and `viewer@example.com`.
- Two customer connections: `dbconn_demo` (SOC) and `dbconn_global` (Global Sales).
- LLM is Mock only for this MVP. Real LLM, RAG, and production deploy are out of scope (P2+).
- Planning source: `docs/PLAN.md`.

## Capabilities and Constraints

Confirmed:

- One Stage per conversation (`conversation_id`).
- Stage layout is `react-grid-layout`; layout persists and restores.
- Widgets must be on the server whitelist. Unknown component names are rejected or fall back to `DataTable`. Current catalog includes KPI, tables, rank lists, bar/line/pie (and table companions), markdown, sources, filters, sparklines.
- Customer DBs are read-only `SELECT`.
- Agent JSON is closed furniture: unknown keys/types dropped; no invented chart types, free layout strings, hex/CSS/HTML. Data values are open; column shapes are closed.
- Density caps apply (for example stack max 3). Recommended fail: drop the bad slot, do not blank the whole widget.

Explicitly undecided:

- Whether a later version should add dashboard templates that reproduce a designed Orion poster (for example Hexagon planet). Current product rule: no templates.
- Question-similarity tuning so paraphrases emit the same furniture (test harness not built).
- Composed Circle catalog (ring × size × repeat × companion) as runtime furniture.

## Brand Commitments

Product name: agent4any. No binding visual identity was recorded in init. The incumbent UI exists in `frontend/` and must be treated as evidence, not as a locked brand system, until DESIGN.md documents it.

## Evidence on Hand

- Product plan and scenarios: `docs/PLAN.md`
- Runnable app: `frontend/` (Vite React JavaScript) and FastAPI backend
- Demo data lives in the two sample customer databases. Figures used in conversation (for example APAC attainment) are fake-but-realistic demo numbers.
- Do not invent testimonials, customers, benchmarks, pricing, or production case studies.

## Product Principles

1. Equal demo worlds: SOC and Global Sales are both first-class.
2. Pin, don’t poster: success is the right widgets in chat, then a few on Stage.
3. Catalog furniture, user layout: the agent proposes; the user composes.
4. Closed types, open values: invent no charts or chrome; keep data honest.
5. Conversation-scoped: one Stage per chat, not a global dashboard library.
