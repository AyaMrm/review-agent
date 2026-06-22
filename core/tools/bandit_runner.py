from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from core.schema import Category, Issue, Severity, Source

BANDIT_SEVERITY_MAP = {
    "LOW": Severity.MINOR,
    "MEDIUM": Severity.MAJOR,
    "HIGH": Severity.CRITICAL,
}


def run_bandit(filepath: str) -> list[Issue]:
    cmd = ["bandit", "-f", "json", "-q", filepath]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if not proc.stdout.strip():
        return []

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []

    issues: list[Issue] = []
    for item in data.get("results", []):
        rel_path = os.path.relpath(item["filename"], start=Path.cwd())
        severity = BANDIT_SEVERITY_MAP.get(item["issue_severity"], Severity.MINOR)

        issues.append(
            Issue(
                file=rel_path,
                line=item["line_number"],
                end_line=item["line_range"][-1] if item.get("line_range") else None,
                column=item.get("col_offset"),
                severity=severity,
                category=Category.SECURITY,
                source=Source.BANDIT,
                rule_id=item["test_id"],
                title=item["test_name"].replace("_", " ").capitalize(),
                explanation=item["issue_text"],
                suggestion=f"Voir CWE-{item['issue_cwe']['id']} : {item['issue_cwe']['link']}"
                if item.get("issue_cwe") else None,
            )
        )
    return issues