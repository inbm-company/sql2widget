#!/usr/bin/env python3
"""Render the project's Markdown subset into the dashboard and kanban, without dependencies."""

import argparse
import html
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATUSES = (("완료", "done"), ("진행 중", "wip"), ("검증 대기", "verify"), ("계획", "plan"))
REPOSITORY = "https://github.com/inbm-company/sql2widget"


def web_links(content, documents):
    """Annotate web destinations while preserving relative links for local HTML files."""
    def anchor(match):
        tag = match[0]
        attribute = re.search(r'href="([^"]+)"', tag)
        target = urlsplit(html.unescape(attribute[1]))
        if target.scheme or target.netloc or not target.path:
            return tag
        path = (DOCS / unquote(target.path)).resolve()
        if not path.is_relative_to(ROOT) or not path.exists():
            return tag
        if path in documents and "data-source-link" not in tag:
            identifier, headings = documents[path]
            heading = identifier + "--" + unquote(target.fragment)
            destination = "/docs#" + (heading if heading in headings else identifier)
        elif path.suffix == ".md" or path.is_dir():
            kind = "tree" if path.is_dir() else "blob"
            destination = f"{REPOSITORY}/{kind}/main/{quote(path.relative_to(ROOT).as_posix())}"
            if target.fragment:
                destination += "#" + target.fragment
        else:
            return tag
        return tag[:-1] + ' data-web-href="' + html.escape(destination, quote=True) + '">'

    return re.sub(r'<a\b[^>]*\bhref="[^"]+"[^>]*>', anchor, content)


def link_target(target, source):
    """Resolve Markdown-relative links from the generated HTML's docs directory."""
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return target
    if target.startswith("#"):
        return os.path.relpath(source, DOCS) + target
    path, separator, fragment = target.partition("#")
    return os.path.relpath(source.parent / path, DOCS) + (separator + fragment if separator else "")


def inline(value, source):
    tokens = []

    def keep(markup):
        tokens.append(markup)
        return f"\x00{len(tokens) - 1}\x00"

    value = re.sub(r"`([^`]+)`", lambda m: keep("<code>" + html.escape(m[1]) + "</code>"), value)

    def link(match):
        label = html.escape(match[1])
        target = html.escape(link_target(match[2], source), quote=True)
        return keep(f'<a href="{target}">{label}</a>')

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    # Insert placeholders inside link labels before replacing the outer link placeholder.
    for index in range(len(tokens) - 1, -1, -1):
        value = value.replace(f"\x00{index}\x00", tokens[index])
    for index, token in enumerate(tokens):
        value = value.replace(f"\x00{index}\x00", token)
    return value


def cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render(markdown, source, document_id=None):
    """Render headings, paragraphs, tables, lists, quotes and fenced code used in these docs."""
    lines = markdown.splitlines()
    output = []
    headings = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if source == DOCS / "progress.md" and (re.fullmatch(r"작업 ID: `([a-z][a-z0-9-]*)`", line)
                                                or re.fullmatch(r'<a id="[a-z][a-z0-9-]*"></a>', line)):
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            output.append(f'<pre><code class="language-{html.escape(language, quote=True)}">'
                          + html.escape("\n".join(code)) + "\n</code></pre>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6}) (.+)$", line)
        if heading:
            level = len(heading[1])
            attribute = ""
            if document_id:
                slug = re.sub(r"[^\w\- ]", "", heading[2].lower()).replace(" ", "-")
                if document_id == "progress" and level == 3:
                    task_id = re.search(r"^작업 ID: `([a-z][a-z0-9-]*)`", "\n".join(lines[i + 1:i + 5]), re.MULTILINE)
                    if task_id:
                        slug = task_id[1]
                count = headings.get(slug, 0)
                headings[slug] = count + 1
                anchor = f"{document_id}--{slug}" + (f"-{count}" if count else "")
                attribute = f' id="{html.escape(anchor, quote=True)}"'
            output.append(f"<h{level}{attribute}>{inline(heading[2], source)}</h{level}>")
            i += 1
            continue
        if re.fullmatch(r"\s*-{3,}\s*", line):
            output.append("<hr>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"[| :\-]+", lines[i + 1]):
            output.append("<table><thead><tr>" + "".join("<th>" + inline(c, source) + "</th>" for c in cells(line))
                          + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                output.append("<tr>" + "".join("<td>" + inline(c, source) + "</td>" for c in cells(lines[i])) + "</tr>")
                i += 1
            output.append("</tbody></table>")
            continue
        item = re.match(r"^(?:- |\d+\. )(.+)", line)
        if item:
            ordered = bool(re.match(r"^\d+\. ", line))
            tag = "ol" if ordered else "ul"
            pattern = r"^\d+\. (.+)" if ordered else r"^- (.+)"
            output.append(f"<{tag}>")
            while i < len(lines) and (item := re.match(pattern, lines[i])):
                output.append("<li>" + inline(item[1], source) + "</li>")
                i += 1
            output.append(f"</{tag}>")
            continue
        if line.startswith("> "):
            quote = []
            while i < len(lines) and lines[i].startswith("> "):
                quote.append(lines[i][2:])
                i += 1
            output.append("<blockquote><p>" + inline(" ".join(quote), source) + "</p></blockquote>")
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||> |- |\d+\. )", lines[i]):
            paragraph.append(lines[i])
            i += 1
        output.append("<p>" + inline(" ".join(paragraph), source) + "</p>")
    return "\n".join(output)


def feature_documents():
    """List feature docs from the index table, labelled by each document's first heading."""
    index = DOCS / "features/README.md"
    documents = []
    for target in re.findall(r"^\| \[[^\]]+\]\(([^)]+\.md)\) \|", index.read_text(), re.MULTILINE):
        path = DOCS / "features" / target
        heading = re.search(r"^# (.+)$", path.read_text(), re.MULTILINE)
        documents.append((heading[1].strip() if heading else path.stem, path))
    return documents


def task_details(body):
    """Read task details from progress.md; state and area stay in the status tables."""
    details = {}
    for block in re.split(r"(?=^### )", body, flags=re.MULTILINE):
        if not block.startswith("### "):
            continue
        title, _, content = block.partition("\n")
        identifier = re.search(r"^작업 ID: `([a-z][a-z0-9-]*)`\s*$", content, re.MULTILINE)
        if not identifier:
            raise SystemExit(f"작업 상세에 고유 작업 ID가 필요합니다: {title[4:]}")
        key = identifier[1]
        if key in details:
            raise SystemExit(f"중복 작업 ID: {key}")
        details[key] = (title[4:].strip(), content[:identifier.start()] + content[identifier.end():])
    return details


def task_reference(row, details):
    """Require an explicit link so a card cannot silently show another task's details."""
    link = re.fullmatch(r"\[([^\]]+)\]\(#([a-z][a-z0-9-]*)\)", row[1])
    if not link or link[2] not in details:
        raise SystemExit(f"표시 카드의 작업 상세 연결을 확인하세요: {row[1]}")
    if details[link[2]][0] != link[1]:
        raise SystemExit(f"카드와 상세의 제목이 다릅니다: {row[1]}")
    return link[1], link[2]


def progress_sections():
    source = DOCS / "progress.md"
    sections = {}
    for block in re.split(r"(?=^## )", source.read_text(), flags=re.MULTILINE):
        if block.startswith("## "):
            title, _, body = block.partition("\n")
            sections[title[3:]] = body
    return source, sections


def progress_rows(body):
    """Return status rows shown on the kanban; rows marked 미표시 in the 칸반 column stay in the Markdown only."""
    rows = [cells(line) for line in body.splitlines()
            if line.startswith("|") and not re.fullmatch(r"[| :\-]+", line)]
    for row in rows[1:]:
        if len(row) < 4 or row[3] not in ("표시", "미표시"):
            raise SystemExit(f"progress.md 행의 칸반 열은 표시/미표시여야 합니다: {row[:2]}")
    return [row for row in rows[1:] if row[0] != "없음" and row[3] == "표시"]


def area_order(sections):
    """Return feature areas in first-appearance order across the status columns."""
    order = []
    for title, _ in STATUSES:
        for row in progress_rows(sections[title]):
            if row[0] not in order:
                order.append(row[0])
    return order


def area_key(area, order):
    """Return a stable CSS-safe key for a feature area."""
    return f"a{order.index(area)}"


def outputs():
    features = feature_documents()
    progress, sections = progress_sections()
    details = task_details(sections.get("작업 상세", ""))
    counts = {title: len(progress_rows(sections[title])) for title, _ in STATUSES}
    entries = [("1. 메인규칙", [("overview", "프로젝트 목적·기능·규칙", ROOT / "AGENTS.md")]),
               ("2. 폴더 구조", [("structure", "디렉터리와 파일 역할", DOCS / "01-folder-structure.md")]),
               ("3. 기능", [("feature-index", "기능 색인", DOCS / "features/README.md")]
                + [(path.stem, label, path) for label, path in features]),
               ("4. 진행도", [("progress", "완료·진행·검증 대기·계획", progress)])]
    toc = []
    body = []
    documents_by_path = {}
    for group, documents in entries:
        toc.append('<div class="group-label">' + html.escape(group) + "</div>")
        for identifier, label, path in documents:
            toc.append(f'<a href="#{identifier}" data-id="{identifier}">{html.escape(label)}</a>')
            badges = ""
            if identifier == "progress":
                badges = " ".join(f'<span class="badge {key}">{title} {counts[title]}</span>' for title, key in STATUSES)
            rendered = render(path.read_text(), path, identifier)
            documents_by_path[path.resolve()] = (identifier, set(re.findall(r'<h[1-6] id="([^"]+)"', rendered)))
            body.append(f'<section id="{identifier}">{badges}\n{rendered}\n</section>')
    toc.append('<div class="group-label">5. 임시</div><a href="temp/">기록 폴더 ↗</a>')
    toc.append('<a href="kanban.html">칸반 ↗</a>')
    dashboard = (DOCS / "templates/dashboard.html").read_text().replace("{{toc}}", "\n".join(toc))
    dashboard = dashboard.replace("{{sections}}", "\n".join(body))
    kpis = []
    columns = []
    task_templates = []
    used_tasks = set()
    areas = area_order(sections)
    filters = ['<button type="button" class="chip on" data-area="all">전체</button>']
    filters += [f'<button type="button" class="chip {area_key(area, areas)}" data-area="{area_key(area, areas)}">'
                + html.escape(area) + '</button>' for area in areas]
    for title, key in STATUSES:
        count = counts[title]
        kpis.append(f'<div class="kpi {key}"><div class="label">{title}</div><div class="num">{count}</div></div>')
        cards = []
        rows = progress_rows(sections[title])
        for area in areas:
            grouped = [row for row in rows if row[0] == area]
            if not grouped:
                continue
            akey = area_key(area, areas)
            cards.append(f'<div class="group {akey}" data-area="{akey}"><div class="area">'
                         + html.escape(area) + f'<span>{len(grouped)}</span></div>')
            for row in grouped:
                label, task_id = task_reference(row, details)
                if task_id in used_tasks:
                    raise SystemExit(f"표시 카드가 작업 ID를 중복 사용합니다: {task_id}")
                used_tasks.add(task_id)
                cards.append(f'<button type="button" class="card" data-task="{task_id}" '
                             + 'aria-haspopup="dialog" aria-controls="taskDialog"><span class="t">'
                             + html.escape(label) + '</span><span class="n">'
                             + inline(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", row[2]), progress)
                             + '</span><span class="card-more">상세 보기 ↗</span></button>')
                task_templates.append(f'<template id="task-{task_id}" '
                                      + f'data-title="{html.escape(label, quote=True)}" '
                                      + f'data-area="{html.escape(area, quote=True)}" data-status="{title}">'
                                      + render(details[task_id][1], progress, "task-" + task_id) + '</template>')
            cards.append('</div>')
        if not cards:
            cards.append('<p class="mono">현재 기록된 항목 없음</p>')
        columns.append(f'<div class="col {key}"><div class="col-head"><span class="dot"></span>{title}'
                       + f'<span class="count">{count}</span></div>' + "\n".join(cards) + '</div>')
    summary = render("## 현재 상태\n" + sections["현재 상태"]
                     + "\n## 검증 기록\n" + sections["검증 기록"], progress)
    cards = ['<div class="box"><h3><a href="dashboard.html#' + path.stem + '">'
             + html.escape(label) + '</a></h3><a data-source-link href="features/' + path.name + '">원문 ↗</a></div>'
             for label, path in features]
    date = re.search(r"기준일(?::| \|) (\d{4}-\d{2}-\d{2})", progress.read_text())[1]
    kanban = (DOCS / "templates/kanban.html").read_text()
    for token, replacement in (("date", date), ("kpis", "\n".join(kpis)), ("filters", "\n".join(filters)),
                               ("board", "\n".join(columns)),
                               ("summary", summary), ("features", "\n".join(cards)),
                               ("task_details", "\n".join(task_templates))):
        kanban = kanban.replace("{{" + token + "}}", replacement)
    return {DOCS / "dashboard.html": web_links(dashboard, documents_by_path),
            DOCS / "kanban.html": web_links(kanban, documents_by_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check that generated files match without writing")
    args = parser.parse_args()
    stale = []
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(content)
            print("갱신:", path.relative_to(ROOT))
    if stale:
        parser.exit(1, "원본과 다른 HTML: " + ", ".join(stale) + "\n")
    if args.check:
        print("대시보드·칸반이 원본 Markdown과 일치합니다.")


if __name__ == "__main__":
    main()
