"""
    python cli.py --file path/to/code.py
    python cli.py --pr https://github.com/user/repo/pull/42   (à venir, étape suivante)
"""

from __future__ import annotations

import argparse
import sys

from core.schema import ReviewReport
from core.tools.bandit_runner import run_bandit
from core.tools.ruff_runner import run_ruff


def review_full_file(filepath: str) -> ReviewReport:
    issues = run_ruff(filepath) + run_bandit(filepath)
    return ReviewReport(target=filepath, mode="full_file", issues=issues)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="review-agent",
        description="Reviewe du code Python comme un dev senior : style, sécurité, bugs.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Chemin vers un fichier Python à analyser en entier")
    group.add_argument("--pr", help="URL d'une PR GitHub à analyser (bientôt disponible)")

    parser.add_argument(
        "--output",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Format de sortie du rapport",
    )

    args = parser.parse_args()

    if args.pr:
        print("⚠️  Le mode --pr arrive à l'étape suivante (récupération de diff GitHub). Utilise --file pour l'instant.")
        sys.exit(1)

    report = review_full_file(args.file)

    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    main()