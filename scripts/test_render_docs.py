"""Focused regressions for progress task identity and card/detail rendering."""

import unittest
from html.parser import HTMLParser

import render_docs as docs


class TaskMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = []
        self.templates = set()
        self.dialogs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "button" and "data-task" in attrs:
            self.cards.append(attrs["data-task"])
        if tag == "template":
            self.templates.add(attrs.get("id"))
        if tag == "dialog":
            self.dialogs.append(attrs.get("id"))


class TaskDetailTests(unittest.TestCase):
    def test_explicit_id_survives_title_change_and_is_not_displayed(self):
        source = "### 바뀐 제목\n\n작업 ID: `stable-task`\n\n#### 범위\n\n설명"
        details = docs.task_details(source)
        row = ["영역", "[바뀐 제목](#stable-task)", "요약", "표시"]
        self.assertEqual(docs.task_reference(row, details), ("바뀐 제목", "stable-task"))
        markup = docs.render(source, docs.DOCS / "progress.md", "progress")
        self.assertIn('id="progress--stable-task"', markup)
        self.assertNotIn("작업 ID:", markup)

    def test_duplicate_ids_are_rejected(self):
        source = "### A\n작업 ID: `same`\n내용\n### B\n작업 ID: `same`\n내용"
        with self.assertRaisesRegex(SystemExit, "중복 작업 ID"):
            docs.task_details(source)

    def test_missing_or_mismatched_details_are_rejected(self):
        details = docs.task_details("### 제목\n작업 ID: `item`\n내용")
        for title in ("연결 없는 제목", "[제목](#missing)", "[다른 제목](#item)"):
            with self.subTest(title=title), self.assertRaises(SystemExit):
                docs.task_reference(["영역", title, "요약", "표시"], details)

    def test_generated_cards_have_unique_detail_templates_and_dashboard_anchors(self):
        generated = docs.outputs()
        kanban = generated[docs.DOCS / "kanban.html"]
        dashboard = generated[docs.DOCS / "dashboard.html"]
        markup = TaskMarkup()
        markup.feed(kanban)
        self.assertTrue(markup.cards)
        self.assertEqual(len(markup.cards), len(set(markup.cards)))
        self.assertEqual(markup.dialogs, ["taskDialog"])
        for identifier in markup.cards:
            self.assertIn("task-" + identifier, markup.templates)
            self.assertIn('id="progress--' + identifier + '"', dashboard)
        self.assertNotIn("{{task_details}}", kanban)


if __name__ == "__main__":
    unittest.main()
