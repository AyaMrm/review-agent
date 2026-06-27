from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class Category(str, Enum):
    BUG = "bug"
    SECURITY = "security"
    STYLE = "style"
    PERFORMANCE = "performance"
    BEST_PRACTICE = "best_practice"
    MAINTAINABILITY = "maintainability"


class Source(str, Enum):
    RUFF = "ruff"
    BANDIT = "bandit"
    CLIPPY = "clippy"
    LLM = "llm"


class Issue(BaseModel):
    file: str = Field(..., description="Path to the affected file")
    line: int = Field(..., description="Starting line of the issue")
    end_line: Optional[int] = Field(None, description="Ending line if the issue spans multiple lines")
    column: Optional[int] = None

    severity: Severity
    category: Category
    source: Source

    rule_id: Optional[str] = Field(None, description="Rule identifier, for example: E501 or B608")
    title: str = Field(..., description="Short issue summary, one sentence")
    explanation: str = Field(..., description="Plain-language explanation of why this is a problem")
    suggestion: Optional[str] = Field(None, description="Suggested fix, ideally with a code snippet")

    def to_markdown(self) -> str:
        loc = f"{self.file}:{self.line}"
        header = f"**{self.title}** - `{loc}` _(source: {self.source.value})_"
        body = f"\n  {self.explanation}"
        fix = f"\n  Suggestion: {self.suggestion}" if self.suggestion else ""
        return f"{header}{body}{fix}"


class ReviewReport(BaseModel):
    target: str = Field(..., description="Analyzed file, pull request, or diff")
    mode: str = Field(..., description="'full_file' or 'diff'")
    issues: list[Issue] = Field(default_factory=list)

    def sorted_issues(self) -> list[Issue]:
        severity_order = {Severity.CRITICAL: 0, Severity.MAJOR: 1, Severity.MINOR: 2, Severity.INFO: 3}
        return sorted(self.issues, key=lambda i: (severity_order[i.severity], i.file, i.line))

    def summary(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for issue in self.issues:
            counts[issue.severity.value] += 1
        return counts

    def to_markdown(self) -> str:
        lines = [f"# Code Review - `{self.target}`\n"]
        s = self.summary()
        lines.append(
            f"**{len(self.issues)} issue(s)** - "
            f"critical: {s['critical']} | major: {s['major']} | "
            f"minor: {s['minor']} | info: {s['info']}\n"
        )
        for issue in self.sorted_issues():
            lines.append(issue.to_markdown())
            lines.append("")
        return "\n".join(lines)

    def deduplicate(self) -> "ReviewReport":
        source_priority = {
            Source.LLM: 0,
            Source.BANDIT: 1,
            Source.CLIPPY: 2,
            Source.RUFF: 3,
        }
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 1,
            Severity.MINOR: 2,
            Severity.INFO: 3,
        }

        seen: dict[tuple, Issue] = {}
        for issue in self.issues:
            key = (issue.file, issue.line, issue.category)
            if key not in seen:
                seen[key] = issue
            else:
                existing = seen[key]
                if severity_order[issue.severity] < severity_order[existing.severity]:
                    seen[key] = issue
                elif (
                    severity_order[issue.severity] == severity_order[existing.severity]
                    and source_priority[issue.source] < source_priority[existing.source]
                ):
                    seen[key] = issue

        self.issues = list(seen.values())
        return self
