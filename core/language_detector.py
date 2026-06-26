from __future__ import annotations

from pathlib import Path

from core.schema import Issue

SUPPORTED_LANGUAGES = {
    "python": [".py"],
    "rust": [".rs"],
}


def detect_language(filepath: str) -> str | None:
    ext = Path(filepath).suffix.lower()
    for lang, extensions in SUPPORTED_LANGUAGES.items():
        if ext in extensions:
            return lang
    return None


def run_static_analysis(filepath: str, language: str) -> list[Issue]:
    if language == "python":
        from core.tools.ruff_runner import run_ruff
        from core.tools.bandit_runner import run_bandit
        return run_ruff(filepath) + run_bandit(filepath)

    if language == "rust":
        from core.tools.clippy_runner import run_clippy
        return run_clippy(filepath)

    return []


def get_llm_language_hint(language: str) -> str:
    return {"python": "Python", "rust": "Rust"}.get(language, "unknown")