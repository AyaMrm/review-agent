from __future__ import annotations

import json
import os
import re

import groq
from dotenv import load_dotenv

from core.schema import Category, Issue, ReviewReport, Severity, Source

load_dotenv()

ISSUE_JSON_SCHEMA = """
{
  "issues": [
    {
      "line": <int>,
      "end_line": <int or null>,
      "severity": <"critical" | "major" | "minor" | "info">,
      "category": <"bug" | "security" | "style" | "performance" | "best_practice" | "maintainability">,
      "title": <string, a short sentence>,
      "explanation": <string, why this is a problem>,
      "suggestion": <string, how to fix it, with a snippet if possible>
    }
  ]
}
"""

SYSTEM_PROMPT = """You are a senior software engineer performing a thorough code review.
Your job is to identify issues that static analysis tools CANNOT detect:
- Logic bugs (missing edge cases, off-by-one errors, silent None returns, division by zero)
- Semantic problems (misleading names, broken abstractions, wrong assumptions)
- Security issues requiring context (hardcoded secrets, fragile auth logic, unsafe defaults)
- Performance problems (unnecessary loops, missing caching, O(n^2) where O(n) is trivial)
- Maintainability issues (overly complex logic, missing error handling, unclear intent)

Rules:
- DO NOT repeat issues already found by the static analysis tools (provided below).
- Focus on what REQUIRES reading and understanding the code, not mechanical checks.
- Be specific: always reference the exact line number.
- Be constructive: always provide a concrete suggestion or fix.
- If the code is clean and you find nothing significant, return {"issues": []}.
- Respond ONLY with valid JSON matching the schema. No prose, no markdown, no explanation outside the JSON.
"""


def _build_prompt(code: str, filename: str, existing_issues: list[Issue]) -> str:
    if existing_issues:
        lines = [f"- Line {i.line}: [{i.rule_id}] {i.title} - {i.explanation}" for i in existing_issues]
        existing_summary = "ALREADY FOUND BY STATIC ANALYSIS (do not repeat these):\n" + "\n".join(lines)
    else:
        existing_summary = "ALREADY FOUND BY STATIC ANALYSIS: none"

    return f"""Review the following Python file: `{filename}`

{existing_summary}

CODE TO REVIEW:
```python
{code}
```

Respond with JSON matching this schema:
{ISSUE_JSON_SCHEMA}"""


def run_llm_review(
    code: str,
    filename: str,
    existing_issues: list[Issue] | None = None,
    changed_lines: set[int] | None = None,
) -> list[Issue]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from .env")

    client = groq.Groq(api_key=api_key)
    prompt = _build_prompt(code, filename, existing_issues or [])

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    raw_text = message.choices[0].message.content.strip()

    if raw_text.startswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[1:])
    if raw_text.endswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[:-1])

    data = None
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    if data is None:
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    if data is None:
        print("WARNING: invalid JSON after two attempts; LLM issues ignored.")
        print(f"  Raw response: {raw_text[:200]}")
        return []

    issues: list[Issue] = []
    for item in data.get("issues", []):
        line = item.get("line", 1)

        if changed_lines is not None and line not in changed_lines:
            continue

        try:
            issue = Issue(
                file=filename,
                line=line,
                end_line=item.get("end_line"),
                severity=Severity(item["severity"]),
                category=Category(item["category"]),
                source=Source.LLM,
                rule_id=None,
                title=item["title"],
                explanation=item["explanation"],
                suggestion=item.get("suggestion"),
            )
            issues.append(issue)
        except (KeyError, ValueError) as e:
            print(f"WARNING: ignoring invalid LLM issue: {e} - {item}")

    return issues


def review_with_llm(
    report: ReviewReport,
    code: str,
    filename: str,
    changed_lines: set[int] | None = None,
) -> ReviewReport:
    """Enrich an existing ReviewReport with issues found by the LLM."""
    print(f"Running LLM analysis for {filename}...")
    llm_issues = run_llm_review(
        code=code,
        filename=filename,
        existing_issues=report.issues,
        changed_lines=changed_lines,
    )
    print(f"  -> {len(llm_issues)} additional issue(s) found by the LLM")
    report.issues.extend(llm_issues)
    return report
