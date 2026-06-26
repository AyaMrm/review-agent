from __future__ import annotations

import argparse
import os
import sys
import tempfile

from core.schema import ReviewReport
from core.tools.bandit_runner import run_bandit
from core.tools.ruff_runner import run_ruff


def review_full_file(filepath: str, use_llm: bool = True) -> ReviewReport:
    from core.language_detector import detect_language, run_static_analysis, get_llm_language_hint

    language = detect_language(filepath)
    if not language:
        print(f"⚠️  Unsupported language for {filepath}. Supported languages: Python, Rust")
        return ReviewReport(target=filepath, mode="full_file", issues=[])

    print(f"🔍 Running static analysis for {filepath} ({get_llm_language_hint(language)})...")
    issues = run_static_analysis(filepath, language)
    print(f"   → {len(issues)} issue(s) found by static analysis")

    report = ReviewReport(target=filepath, mode="full_file", issues=issues)

    if use_llm:
        from core.llm_review import review_with_llm
        with open(filepath, encoding="utf-8") as f:
            code = f.read()
        report = review_with_llm(report, code=code, filename=filepath)

    report.deduplicate()
    return report


def review_pr(pr_url: str, use_llm: bool = True) -> ReviewReport:
    from core.github_fetcher import fetch_pr_files

    print(f"\n📡 Fetching pull request: {pr_url}")
    changed_files = fetch_pr_files(pr_url, python_only=True)

    if not changed_files:
        print("⚠️  No Python files were found in this pull request.")
        return ReviewReport(target=pr_url, mode="diff", issues=[])

    report = ReviewReport(target=pr_url, mode="diff", issues=[])

    for changed_file in changed_files:
        if not changed_file.content:
            print(f"⚠️  Content unavailable for {changed_file.filename}; skipping.")
            continue

        print(f"\n🔍 Running static analysis for {changed_file.filename}...")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(changed_file.content)
            tmp_path = tmp.name

        try:
            static_issues = run_ruff(tmp_path) + run_bandit(tmp_path)
            for issue in static_issues:
                issue.file = changed_file.filename
            print(f"   → {len(static_issues)} static issue(s)")

            if changed_file.changed_lines:
                static_issues = [
                    i for i in static_issues
                    if i.line in changed_file.changed_lines
                ]
                print(f"   → {len(static_issues)} after diff filter (touched lines only)")

            file_report = ReviewReport(
                target=changed_file.filename,
                mode="diff",
                issues=static_issues,
            )

            if use_llm:
                from core.llm_review import review_with_llm
                file_report = review_with_llm(
                    file_report,
                    code=changed_file.content,
                    filename=changed_file.filename,
                    changed_lines=changed_file.changed_lines or None,
                )

            report.issues.extend(file_report.issues)

        finally:
            os.unlink(tmp_path)

    report.deduplicate()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="review-agent",
        description="Review Python code like a senior engineer: style, security, and logic bugs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --file mycode.py
  python cli.py --file mycode.py --no-llm
  python cli.py --pr https://github.com/owner/repo/pull/42
  python cli.py --pr https://github.com/owner/repo/pull/42 --output json
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a Python file to analyze in full")
    group.add_argument("--pr", help="GitHub pull request URL (for example: https://github.com/owner/repo/pull/42)")

    parser.add_argument(
        "--output",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable the LLM step (faster, static analysis only)",
    )
    
    parser.add_argument(
        "--post",
        action="store_true",
        help="Post issues as comments on the GitHub pull request (requires --pr)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate posting without calling the GitHub API (useful for testing)",
    )

    args = parser.parse_args()
    use_llm = not args.no_llm

    try:
        if args.file:
            report = review_full_file(args.file, use_llm=use_llm)
        else:
            report = review_pr(args.pr, use_llm=use_llm)
    except RuntimeError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Invalid argument: {e}")
        sys.exit(1)

    print()
    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(report.to_markdown())
        
        if getattr(args, "post", False) or getattr(args, "dry_run", False):
            if not args.pr:
                print(" !! --post and --dry-run require --pr")
                sys.exit(1)
            from core.github_commenter import post_review
            post_review(report, pr_url=args.pr, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
