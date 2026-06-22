from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from core.schema import Category, Issue, Severity, Source

RULE_PREFIX_MAP: dict[str, tuple[Category, Severity]] = {
    "F821": (Category.BUG, Severity.CRITICAL),   # undefined name -> crash garanti
    "F811": (Category.BUG, Severity.MAJOR),       # redefinition
    "F841": (Category.MAINTAINABILITY, Severity.MINOR),  # unused variable
    "F401": (Category.STYLE, Severity.MINOR),     # unused import
    "F-": (Category.BUG, Severity.MAJOR),         # autres pyflakes par défaut
    "E9": (Category.BUG, Severity.CRITICAL),       # syntax error
    "E": (Category.STYLE, Severity.INFO),
    "W": (Category.STYLE, Severity.INFO),
    "C90": (Category.MAINTAINABILITY, Severity.MINOR),
    "B": (Category.BEST_PRACTICE, Severity.MAJOR),  # flake8-bugbear
    "S": (Category.SECURITY, Severity.MAJOR),       # flake8-bandit rules via ruff
}


def _classify(code: str) -> tuple[Category, Severity]:
    if code in RULE_PREFIX_MAP:
        return RULE_PREFIX_MAP[code]
    for prefix, value in RULE_PREFIX_MAP.items():
        if code.startswith(prefix):
            return value
    return Category.STYLE, Severity.INFO


def run_ruff(filepath: str, select: str = "ALL") -> list[Issue]:
    cmd = [
        "ruff", "check",
        "--output-format=json",
        f"--select={select}",
        "--ignore=D,ANN,PL,COM,EM,T20,TD,FIX", 
        filepath,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if not proc.stdout.strip():
        return []

    try:
        raw_issues = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    issues: list[Issue] = []
    for item in raw_issues:
        code = item.get("code") or "UNKNOWN"
        category, severity = _classify(code)
        rel_path = os.path.relpath(item["filename"], start=Path.cwd())

        issues.append(
            Issue(
                file=rel_path,
                line=item["location"]["row"],
                end_line=item["end_location"]["row"],
                column=item["location"]["column"],
                severity=severity,
                category=category,
                source=Source.RUFF,
                rule_id=code,
                title=item.get("name", code).replace("-", " ").capitalize(),
                explanation=item["message"],
                suggestion=item.get("fix", {}).get("message") if item.get("fix") else None,
            )
        )
    return issues