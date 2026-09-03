<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/baby_1f476.png" width="80" />
</p>

<h1 align="center">eli5-compress</h1>

<p align="center">
  <strong>Simplify your memory files. Save tokens every session.</strong>
</p>

---

A Claude Code skill that compresses your project memory files (`CLAUDE.md`, todos, preferences) into plain, simple language — so every session loads fewer tokens automatically.

Claude reads `CLAUDE.md` on every session start. If the file is big, it costs more tokens. ELI5 Compress makes it smaller and simpler. The cost goes down for every future session.

## What It Does

```
/eli5-compress CLAUDE.md
```

```
CLAUDE.md          <- compressed (Claude reads this — fewer tokens every session)
CLAUDE.original.md <- human-readable backup (you edit this)
```

Your original is never lost. You can read and edit `.original.md`. Run the skill again to re-compress after edits.

## Benchmarks

Real results on real project files:

| File | Original | Compressed | Saved |
|------|----------:|----------:|------:|
| `claude-md-preferences.md` | 900 | 409 | **54.6%** |
| `project-notes.md` | 1592 | 854 | **46.4%** |
| `todo-list.md` | 995 | 698 | **29.8%** |
| `claude-md-project.md` | 1784 | 1274 | **28.6%** |
| `mixed-with-code.md` | 1680 | 1248 | **25.7%** |
| **Average** | **1390** | **897** | **36%** |

All validations passed — headings, code blocks, URLs, file paths preserved exactly.

## Before / After

<table>
<tr>
<td width="50%">

### Original (900 tokens)

> "I strongly prefer TypeScript with strict mode enabled for all new code. Please don't use `any` type unless there's genuinely no way around it, and if you do, leave a comment explaining the reasoning. I find that taking the time to properly type things catches a lot of bugs before they ever make it to runtime."

</td>
<td width="50%">

### Simplified (409 tokens)

> "TypeScript strict mode. No `any` unless unavoidable — comment why."

</td>
</tr>
</table>

**Same instructions. 55% fewer tokens. Every session.**

## Install

Install the full eli5 toolkit (includes eli5-compress):

```bash
npx skills add nathanksou/eli5
```

Or manually copy from the repo:

```bash
cp -r eli5-compress ~/.claude/skills/eli5-compress
```

**Requires:** Python 3.10+

## Usage

```
/eli5-compress <filepath>
```

Examples:
```
/eli5-compress CLAUDE.md
/eli5-compress docs/preferences.md
/eli5-compress todos.md
```

### What files work

| Type | Compress? |
|------|-----------|
| `.md`, `.txt`, `.markdown`, `.rst` | Yes |
| Extensionless natural language | Yes |
| `.py`, `.js`, `.ts`, `.json`, `.yaml` | No (code/config) |
| `*.original.md` | No (backup files) |

## How It Works

```
/eli5-compress CLAUDE.md
        |
detect file type        (no tokens)
        |
Claude simplifies       (tokens — one call)
        |
validate output         (no tokens)
  checks: headings, code blocks, URLs, file paths, bullets
        |
if errors: Claude fixes only the broken parts   (tokens — targeted fix)
  does NOT recompress — only patches what failed
        |
retry up to 2 times
        |
write simplified -> CLAUDE.md
write original   -> CLAUDE.original.md
```

Only two things use tokens: initial compression + targeted fix if validation fails. Everything else is local Python.

## What Gets Preserved

ELI5 Compress only simplifies natural language. It never touches:

- Code blocks (fenced or indented)
- Inline code (backtick content)
- URLs and links
- File paths
- Commands (`npm install`, `git commit`)
- Technical terms, library names, API names
- Headings (exact text preserved)
- Tables (structure preserved, cell text simplified)
- Dates, version numbers, numeric values

## Why This Matters

`CLAUDE.md` loads on **every session start**. A 1000-token project memory file costs tokens every single time you open a project. Over 100 sessions that's 100,000 tokens of overhead — just for context you already wrote.

ELI5 Compress cuts that by ~36% on average. Same instructions. Same accuracy. Less waste.

## Part of ELI5

This skill is part of the [eli5](https://github.com/nathanksou/eli5) toolkit — inspired by [Caveman](https://github.com/JuliusBrussee/caveman) by Julius Brussee.

- **eli5** — makes Claude explain things simply (saves output tokens)
- **eli5-compress** — makes Claude read less (saves input tokens)
