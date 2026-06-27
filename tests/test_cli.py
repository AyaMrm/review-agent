from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch

import cli
from core.schema import Category, Issue, ReviewReport, Severity, Source
from core.github_fetcher import ChangedFile


class CliEntryPointTests(TestCase):
    def test_main_prints_json_output(self) -> None:
        report = ReviewReport(
            target="sample.py",
            mode="full_file",
            issues=[
                Issue(
                    file="sample.py",
                    line=1,
                    severity=Severity.MINOR,
                    category=Category.STYLE,
                    source=Source.RUFF,
                    rule_id="F401",
                    title="Unused import",
                    explanation="This import is never used.",
                )
            ],
        )

        with patch.object(cli, "review_full_file", return_value=report), patch.object(
            sys, "argv", ["cli.py", "--file", "sample.py", "--output", "json", "--no-llm"]
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                cli.main()

        output = buffer.getvalue()
        payload = json.loads(output)

        self.assertEqual(payload["target"], "sample.py")
        self.assertEqual(payload["issues"][0]["title"], "Unused import")


class RustPrReviewTests(TestCase):
    def test_review_pr_processes_rust_files(self) -> None:
        changed_file = ChangedFile(
            filename="src/main.rs",
            status="modified",
            patch="@@ -1 +1 @@\n-fn main() {}\n+fn main() { let x = 1; }\n",
            content="fn main() { let x = 1; }\n",
            changed_lines={1},
        )
        rust_issue = Issue(
            file="src/main.rs",
            line=1,
            severity=Severity.MAJOR,
            category=Category.MAINTAINABILITY,
            source=Source.CLIPPY,
            rule_id="clippy::needless_return",
            title="Clippy issue",
            explanation="Example Rust issue.",
        )

        with patch("core.github_fetcher.fetch_pr_files", return_value=[changed_file]), patch(
            "core.language_detector.run_static_analysis", return_value=[rust_issue]
        ):
            report = cli.review_pr("https://github.com/owner/repo/pull/42", use_llm=False)

        self.assertEqual(report.target, "https://github.com/owner/repo/pull/42")
        self.assertEqual(len(report.issues), 1)
        self.assertEqual(report.issues[0].source, Source.CLIPPY)
        self.assertEqual(report.issues[0].file, "src/main.rs")
