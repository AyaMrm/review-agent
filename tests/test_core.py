from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from core.language_detector import detect_language
from core.schema import Category, Issue, ReviewReport, Severity, Source
from core.tools.clippy_runner import _parse_clippy_output


class LanguageDetectorTests(TestCase):
    def test_detect_language_python(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".py") as tmp:
            self.assertEqual(detect_language(tmp.name), "python")

    def test_detect_language_rust(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".rs") as tmp:
            self.assertEqual(detect_language(tmp.name), "rust")

    def test_detect_language_unsupported(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            self.assertIsNone(detect_language(tmp.name))


class ReviewReportTests(TestCase):
    def test_deduplicate_prefers_clippy_over_ruff_on_tie(self) -> None:
        report = ReviewReport(
            target="example.py",
            mode="full_file",
            issues=[
                Issue(
                    file="example.py",
                    line=10,
                    severity=Severity.MAJOR,
                    category=Category.STYLE,
                    source=Source.RUFF,
                    rule_id="RUF001",
                    title="Ruff issue",
                    explanation="Ruff explanation",
                ),
                Issue(
                    file="example.py",
                    line=10,
                    severity=Severity.MAJOR,
                    category=Category.STYLE,
                    source=Source.CLIPPY,
                    rule_id="CLP001",
                    title="Clippy issue",
                    explanation="Clippy explanation",
                ),
            ],
        )

        report.deduplicate()

        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].source, Source.CLIPPY)

    def test_to_markdown_is_plain_text(self) -> None:
        report = ReviewReport(
            target="example.py",
            mode="full_file",
            issues=[
                Issue(
                    file="example.py",
                    line=3,
                    severity=Severity.CRITICAL,
                    category=Category.BUG,
                    source=Source.BANDIT,
                    rule_id="B608",
                    title="SQL injection risk",
                    explanation="The query is built from user input.",
                    suggestion="Use parameterized queries.",
                )
            ],
        )

        markdown = report.to_markdown()

        self.assertIn("# Code Review - `example.py`", markdown)
        self.assertIn("critical: 1", markdown)
        self.assertIn("SQL injection risk", markdown)
        self.assertNotIn("⚠", markdown)
        self.assertNotIn("🔍", markdown)


class ClippyParserTests(TestCase):
    def test_parse_clippy_output_uses_clippy_source(self) -> None:
        payload = {
            "reason": "compiler-message",
            "message": {
                "level": "warning",
                "message": "unused variable: `x`",
                "code": {"code": "clippy::needless_return"},
                "spans": [
                    {
                        "is_primary": True,
                        "file_name": "src/main.rs",
                        "line_start": 10,
                        "line_end": 10,
                        "column_start": 5,
                        "column_end": 6,
                    }
                ],
                "rendered": "warning: unused variable: `x`",
            },
        }

        issues = _parse_clippy_output(json.dumps(payload), base_path=str(Path.cwd()))

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].source, Source.CLIPPY)
        self.assertEqual(issues[0].rule_id, "clippy::needless_return")
