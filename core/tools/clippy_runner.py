from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from core.schema import Category, Issue, Severity, Source

CLIPPY_LEVEL_MAP: dict[str, Severity] = {
    "error": Severity.CRITICAL,
    "warning": Severity.MAJOR,
    "note": Severity.INFO,
    "help": Severity.INFO,
}


def _classify_rust(code: str) -> tuple[Category, Severity]:
    if code.startswith("E"):
        return Category.BUG, Severity.CRITICAL
    if "unused" in code or "dead_code" in code:
        return Category.MAINTAINABILITY, Severity.MINOR
    if "unsafe" in code or "transmute" in code:
        return Category.SECURITY, Severity.MAJOR
    if "perf" in code or "clone" in code:
        return Category.PERFORMANCE, Severity.MINOR
    if "style" in code or "pedantic" in code:
        return Category.STYLE, Severity.INFO
    if "correctness" in code:
        return Category.BUG, Severity.CRITICAL
    if "suspicious" in code:
        return Category.BUG, Severity.MAJOR
    return Category.BEST_PRACTICE, Severity.MINOR


def run_clippy(project_path: str) -> list[Issue]:
    path = Path(project_path)
    if path.is_file():
        current = path.parent
        while current != current.parent:
            if (current / "Cargo.toml").exists():
                project_path = str(current)
                break
            current = current.parent
        else:
            return _run_clippy_single_file(str(path))

    cmd = [
        "cargo", "clippy",
        "--message-format=json",
        "--all-targets",
        "--",
        "-W", "clippy::all",
        "-W", "clippy::pedantic",
        "-A", "clippy::missing_docs_in_private_items",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=project_path)
    return _parse_clippy_output(proc.stdout, base_path=project_path)


def _run_clippy_single_file(filepath: str) -> list[Issue]:
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()

        content = Path(filepath).read_text(encoding="utf-8")
        (src_dir / "main.rs").write_text(content, encoding="utf-8")
        (Path(tmpdir) / "Cargo.toml").write_text(
            '[package]\nname = "review_tmp"\nversion = "0.1.0"\nedition = "2021"\n',
            encoding="utf-8",
        )

        cmd = ["cargo", "clippy", "--message-format=json", "--", "-W", "clippy::all"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmpdir)

        issues = _parse_clippy_output(proc.stdout, base_path=tmpdir)
        for issue in issues:
            issue.file = filepath
        return issues


def _parse_clippy_output(ndjson_output: str, base_path: str) -> list[Issue]:
    issues: list[Issue] = []

    for line in ndjson_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if item.get("reason") != "compiler-message":
            continue

        msg = item.get("message", {})
        level = msg.get("level", "warning")
        spans = msg.get("spans", [])
        primary_spans = [s for s in spans if s.get("is_primary")]
        if not primary_spans:
            continue

        span = primary_spans[0]
        filename = span.get("file_name", "unknown")
        rel_path = os.path.relpath(filename, start=base_path) if os.path.isabs(filename) else filename

        code_obj = msg.get("code") or {}
        code = code_obj.get("code") or level
        category, severity = _classify_rust(code)

        if code == level:
            severity = CLIPPY_LEVEL_MAP.get(level, Severity.INFO)

        issues.append(Issue(
            file=rel_path,
            line=span["line_start"],
            end_line=span["line_end"],
            column=span["column_start"],
            severity=severity,
            category=category,
            source=Source.CLIPPY,
            rule_id=code,
            title=msg.get("message", "Clippy warning")[:80],
            explanation=msg.get("rendered", msg.get("message", "")).strip(),
            suggestion=None,
        ))

    return issues
