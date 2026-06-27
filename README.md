# Review Agent

Review Agent is a command-line code review tool that analyzes Python and Rust code and generates structured review feedback.

It combines:
- static analysis tools (`ruff`, `bandit`, `clippy`)
- an LLM review step powered by `GROQ_API_KEY`
- full-file review mode
- GitHub pull request review mode

## Features

- Analyze a local file with automatic language detection
- Analyze a GitHub pull request through the GitHub API
- Filter issues to lines changed in a pull request
- Optional LLM enrichment to identify logic bugs and deeper design problems
- Output in `terminal`, `markdown`, or `json`
- Post review comments automatically on a GitHub pull request
- Deduplicate issues across sources

## Supported Languages

- Python
- Rust

## Requirements

- Python 3.11+
- `ruff`
- `bandit`
- `clippy` via `cargo`
- A GitHub token set as `GITHUB_TOKEN`
- A Groq API key if you want LLM analysis

## Environment Variables

Create a `.env` file at the project root:

```env
GITHUB_TOKEN=your_github_token
GROQ_API_KEY=your_groq_api_key
```

An example is provided in `.env.example`.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

For Rust support, `cargo` must be installed to run `clippy`.

For development and tests:

```bash
pip install -e .[dev]
```

## Usage

### Analyze a local file

```bash
python cli.py --file path/to/file.py
```

### Analyze a file without the LLM step

```bash
python cli.py --file path/to/file.py --no-llm
```

### Analyze a GitHub pull request

```bash
python cli.py --pr https://github.com/owner/repo/pull/42
```

### Post comments on the pull request

```bash
python cli.py --pr https://github.com/owner/repo/pull/42 --post
```

### Simulate posting

```bash
python cli.py --pr https://github.com/owner/repo/pull/42 --dry-run
```

### Change the output format

```bash
python cli.py --file path/to/file.py --output json
python cli.py --file path/to/file.py --output markdown
python cli.py --file path/to/file.py --output terminal
```

## How It Works

1. The CLI detects the file language.
2. Static tools generate an initial issue list.
3. If LLM mode is enabled, Groq looks for subtler problems.
4. Issues are deduplicated and then printed or posted to GitHub.

For a pull request:

1. The bot fetches changed files.
2. It filters issues to touched lines.
3. It posts inline comments when possible.
4. It adds a global comment for issues outside the diff if needed.

## Project Structure

- `cli.py`: main entry point
- `core/schema.py`: `Issue` and `ReviewReport` models
- `core/language_detector.py`: language detection and static tool orchestration
- `core/llm_review.py`: Groq integration
- `core/github_fetcher.py`: pull request file and diff retrieval
- `core/github_commenter.py`: GitHub comment publishing
- `core/tools/ruff_runner.py`: Python analysis with `ruff`
- `core/tools/bandit_runner.py`: Python security analysis with `bandit`
- `core/tools/clippy_runner.py`: Rust analysis with `clippy`
- `tests/fixtures/`: intentionally broken sample files
- `.github/workflows/review.yml`: GitHub Actions workflow

## GitHub Actions Workflow

The `.github/workflows/review.yml` workflow runs automatically on pull requests that modify Python files.

## Output Format

Issues include:
- file and line
- severity
- category
- source (`ruff`, `bandit`, `llm`)
- title
- explanation
- fix suggestion when available

## Known Limits

- GitHub pull request review supports Python and Rust, but LLM analysis is currently limited to Python.
- LLM analysis depends on the Groq API being available.
- The project expects `ruff`, `bandit`, and `cargo clippy` to be installed on the system.

## Example Output

```markdown
# Code Review - `example.py`

**2 issue(s)** - 1 critical, 1 major, 0 minor, 0 info
```

## Quick Start

1. Fill in `.env`
2. Install the Python dependencies
3. Run `python cli.py --file your_file.py`
4. Add `--pr` if you want to analyze a pull request
