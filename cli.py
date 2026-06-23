from __future__ import annotations

import argparse
import os
import sys
import tempfile

from core.schema import ReviewReport
from core.tools.bandit_runner import run_bandit
from core.tools.ruff_runner import run_ruff


def review_full_file(filepath: str, use_llm: bool = True) -> ReviewReport:
    """Analyse un fichier complet : static analysis + LLM (optionnel)."""
    print(f"🔍 Analyse statique de {filepath}...")
    issues = run_ruff(filepath) + run_bandit(filepath)
    print(f"   → {len(issues)} issue(s) trouvée(s) par les outils statiques")

    report = ReviewReport(target=filepath, mode="full_file", issues=issues)

    if use_llm:
        from core.llm_review import review_with_llm
        with open(filepath, encoding="utf-8") as f:
            code = f.read()
        report = review_with_llm(report, code=code, filename=filepath)

    report.deduplicate()
    return report


def review_pr(pr_url: str, use_llm: bool = True) -> ReviewReport:
    """Récupère une PR GitHub et analyse chaque fichier Python modifié."""
    from core.github_fetcher import fetch_pr_files

    print(f"\n📡 Récupération de la PR : {pr_url}")
    changed_files = fetch_pr_files(pr_url, python_only=True)

    if not changed_files:
        print("⚠️  Aucun fichier Python trouvé dans cette PR.")
        return ReviewReport(target=pr_url, mode="diff", issues=[])

    report = ReviewReport(target=pr_url, mode="diff", issues=[])

    for changed_file in changed_files:
        if not changed_file.content:
            print(f"⚠️  Contenu non disponible pour {changed_file.filename}, ignoré.")
            continue

        print(f"\n🔍 Analyse statique de {changed_file.filename}...")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(changed_file.content)
            tmp_path = tmp.name

        try:
            static_issues = run_ruff(tmp_path) + run_bandit(tmp_path)
            for issue in static_issues:
                issue.file = changed_file.filename
            print(f"   → {len(static_issues)} issue(s) statique(s)")

            if changed_file.changed_lines:
                static_issues = [
                    i for i in static_issues
                    if i.line in changed_file.changed_lines
                ]
                print(f"   → {len(static_issues)} après filtre diff (lignes touchées seulement)")

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
        description="Reviewe du code Python comme un dev senior : style, sécurité, bugs logiques.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python cli.py --file mycode.py
  python cli.py --file mycode.py --no-llm
  python cli.py --pr https://github.com/owner/repo/pull/42
  python cli.py --pr https://github.com/owner/repo/pull/42 --output json
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Chemin vers un fichier Python à analyser en entier")
    group.add_argument("--pr", help="URL d'une PR GitHub (ex: https://github.com/owner/repo/pull/42)")

    parser.add_argument(
        "--output",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Format de sortie (default: terminal)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Désactive l'analyse LLM (plus rapide, static analysis uniquement)",
    )

    args = parser.parse_args()
    use_llm = not args.no_llm

    try:
        if args.file:
            report = review_full_file(args.file, use_llm=use_llm)
        else:
            report = review_pr(args.pr, use_llm=use_llm)
    except RuntimeError as e:
        print(f"\n❌ Erreur : {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ Paramètre invalide : {e}")
        sys.exit(1)

    print()
    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    main()