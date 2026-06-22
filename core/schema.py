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
    LLM = "llm"


class Issue(BaseModel):
    file: str = Field(..., description="Chemin du fichier concerné")
    line: int = Field(..., description="Ligne de début de l'issue")
    end_line: Optional[int] = Field(None, description="Ligne de fin si l'issue s'étend sur plusieurs lignes")
    column: Optional[int] = None

    severity: Severity
    category: Category
    source: Source

    rule_id: Optional[str] = Field(None, description="Code de la règle (ex: 'E501', 'B608')")
    title: str = Field(..., description="Résumé court de l'issue, une phrase")
    explanation: str = Field(..., description="Pourquoi c'est un problème, en clair")
    suggestion: Optional[str] = Field(None, description="Suggestion de fix, idéalement avec un snippet de code")

    def to_markdown(self) -> str:
        sev_emoji = {
            Severity.CRITICAL: "🔴",
            Severity.MAJOR: "🟠",
            Severity.MINOR: "🟡",
            Severity.INFO: "🔵",
        }
        loc = f"{self.file}:{self.line}"
        header = f"{sev_emoji[self.severity]} **{self.title}** — `{loc}` _(source: {self.source.value})_"
        body = f"\n  {self.explanation}"
        fix = f"\n  💡 *Suggestion :* {self.suggestion}" if self.suggestion else ""
        return f"{header}{body}{fix}"


class ReviewReport(BaseModel):
    target: str = Field(..., description="Fichier, PR ou diff analysé")
    mode: str = Field(..., description="'full_file' ou 'diff'")
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
        lines = [f"# Code Review — `{self.target}`\n"]
        s = self.summary()
        lines.append(
            f"**{len(self.issues)} issue(s)** — "
            f"🔴 {s['critical']} critique(s) · 🟠 {s['major']} majeure(s) · "
            f"🟡 {s['minor']} mineure(s) · 🔵 {s['info']} info\n"
        )
        for issue in self.sorted_issues():
            lines.append(issue.to_markdown())
            lines.append("")
        return "\n".join(lines)