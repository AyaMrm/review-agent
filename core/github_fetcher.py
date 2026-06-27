from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChangedFile:
    filename: str
    status: str
    patch: str | None
    content: str | None
    changed_lines: set[int] = field(default_factory=set)


def _parse_changed_lines(patch: str) -> set[int]:
    changed_lines: set[int] = set()
    current_line = 0

    for line in patch.splitlines():
        try:
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                continue

            if line.startswith("+") and not line.startswith("+++"):
                changed_lines.add(current_line)
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                pass
            else:
                current_line += 1
        except (ValueError, IndexError):
            continue

    return changed_lines


def _fetch_file_content(session: requests.Session, url: str) -> str | None:
    resp = session.get(url, timeout=10)
    if resp.status_code == 200:
        return resp.text
    return None


SUPPORTED_EXTENSIONS = {".py", ".rs"}


def fetch_pr_files(pr_url: str, extensions: set[str] | None = None) -> list[ChangedFile]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is missing from .env")

    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        raise ValueError(
            f"Invalid pull request URL: {pr_url}\nExpected format: https://github.com/owner/repo/pull/42"
        )

    owner, repo, pr_number = match.group(1), match.group(2), match.group(3)
    api_base = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    pr_resp = session.get(api_base, timeout=10)
    if pr_resp.status_code == 404:
        raise RuntimeError(f"Pull request not found: {pr_url}")
    if pr_resp.status_code == 401:
        raise RuntimeError("GitHub token is invalid or expired.")
    pr_resp.raise_for_status()

    pr_data = pr_resp.json()
    print(f"Pull request found: #{pr_number} - {pr_data['title']}")
    print(f"  Branch: {pr_data['head']['ref']} -> {pr_data['base']['ref']}")

    files_url = f"{api_base}/files"
    all_files = []
    page = 1
    while True:
        resp = session.get(files_url, params={"per_page": 100, "page": page}, timeout=10)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_files.extend(batch)
        page += 1

    changed_files: list[ChangedFile] = []
    for f in all_files:
        filename = f["filename"]

        if extensions is not None and not any(filename.endswith(ext) for ext in extensions):
            continue
        if f["status"] == "removed":
            continue

        patch = f.get("patch")
        changed_lines = _parse_changed_lines(patch) if patch else set()
        content = _fetch_file_content(session, f["raw_url"]) if f.get("raw_url") else None

        changed_files.append(ChangedFile(
            filename=filename,
            status=f["status"],
            patch=patch,
            content=content,
            changed_lines=changed_lines,
        ))
        print(f"{filename} ({f['status']}, {len(changed_lines)} touched line(s))")

    print(f"\n-> {len(changed_files)} file(s) retrieved")
    return changed_files
