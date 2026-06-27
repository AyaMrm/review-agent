from __future__ import annotations

import os
import re

import requests
from dotenv import load_dotenv

from core.schema import ReviewReport, Severity

load_dotenv()


def _get_session() -> requests.Session:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is missing from .env")
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return session


def _parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError(f"Invalid pull request URL: {pr_url}")
    return match.group(1), match.group(2), match.group(3)


def _get_pr_head_sha(session: requests.Session, owner: str, repo: str, pr_number: str) -> str:
    resp = session.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["head"]["sha"]


def _get_diff_position(session, owner, repo, pr_number, filename, line) -> int | None:
    resp = session.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
        timeout=10,
    )
    resp.raise_for_status()

    for file_data in resp.json():
        if file_data["filename"] != filename:
            continue
        patch = file_data.get("patch", "")
        if not patch:
            return None

        position = 0
        current_line = 0
        try:
            for patch_line in patch.splitlines():
                position += 1
                hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", patch_line)
                if hunk_match:
                    current_line = int(hunk_match.group(1))
                    continue
                if patch_line.startswith("+") and not patch_line.startswith("+++"):
                    if current_line == line:
                        return position
                    current_line += 1
                elif patch_line.startswith("-") and not patch_line.startswith("---"):
                    pass
                else:
                    if current_line == line:
                        return position
                    current_line += 1
        except (ValueError, IndexError):
            return None
    return None


def _severity_badge(severity: Severity) -> str:
    return {
        Severity.CRITICAL: "CRITICAL",
        Severity.MAJOR: "MAJOR",
        Severity.MINOR: "MINOR",
        Severity.INFO: "INFO",
    }[severity]


def post_review(report: ReviewReport, pr_url: str, dry_run: bool = False) -> None:
    owner, repo, pr_number = _parse_pr_url(pr_url)
    session = _get_session()

    if dry_run:
        print(f"[DRY RUN] Simulating posting on {pr_url}")
        print(f"[DRY RUN] {len(report.issues)} issues to post\n")
        for issue in report.sorted_issues():
            print(f"  [{issue.severity.value.upper()}] {issue.file}:{issue.line} - {issue.title}")
        return

    head_sha = _get_pr_head_sha(session, owner, repo, pr_number)
    print(f"Posting on pull request #{pr_number} (sha: {head_sha[:8]}...)")

    inline_posted = 0
    fallback_issues = []

    for issue in report.sorted_issues():
        position = _get_diff_position(session, owner, repo, pr_number, issue.file, issue.line)

        if position is None:
            fallback_issues.append(issue)
            continue

        body = f"**{_severity_badge(issue.severity)} - {issue.title}**\n\n"
        body += f"{issue.explanation}\n"
        if issue.suggestion:
            body += f"\nSuggestion: {issue.suggestion}\n"
        body += f"\n<sub>Source: `{issue.source.value}`{f' | Rule: `{issue.rule_id}`' if issue.rule_id else ''}</sub>"

        resp = session.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments",
            json={
                "body": body,
                "commit_id": head_sha,
                "path": issue.file,
                "position": position,
            },
            timeout=10,
        )
        if resp.status_code == 422:
            fallback_issues.append(issue)
        else:
            resp.raise_for_status()
            inline_posted += 1
            print(f"  Inline: {issue.file}:{issue.line} - {issue.title}")

    if fallback_issues:
        lines = ["## Code Review - Additional Issues\n"]
        lines.append(f"*{len(fallback_issues)} issue(s) outside the diff.*\n")
        for issue in fallback_issues:
            lines.append(f"### {_severity_badge(issue.severity)} - `{issue.file}:{issue.line}` - {issue.title}")
            lines.append(f"\n{issue.explanation}")
            if issue.suggestion:
                lines.append(f"\nSuggestion: {issue.suggestion}")
            lines.append(f"\n<sub>Source: `{issue.source.value}`</sub>\n")

        resp = session.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": "\n".join(lines)},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"  Global comment posted ({len(fallback_issues)} issues)")

    print(f"\nDone - {inline_posted} inline + {len(fallback_issues)} global")
