# Development Guide

This guide covers setting up your development environment and common development tasks for
`invoke-tasklib` itself.

## Prerequisites

- Python 3.10 or higher
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- Git for version control

## Initial Setup

### 1. Fork and Clone

```shell
git clone https://github.com/YOUR-USERNAME/invoke-tasklib.git
cd invoke-tasklib
```

### 2. Set Up a Virtual Environment

```shell
uv venv --clear
source .venv/bin/activate
```

### 3. Install Dependencies

```shell
uv sync --group dev
```

### 4. Set Up Pre-commit Hooks

```shell
pre-commit install
```

## Development Workflow

### Running Tests

```shell
python -m pytest tests/
```

With coverage:

```shell
python -m pytest --cov=invoke_tasklib --cov-report term tests/
```

Since `invoke-tasklib` itself uses `invoke` as its build tool, the project's own `tasks.py` (which
composes tasks from `invoke_tasklib`) can also be used once the package is installed in editable
mode - see the [Makefile](https://github.com/durandtibo/invoke-tasklib/blob/main/Makefile) and
`invoke --list` for the available tasks.

### Code Quality

```shell
ruff format --check .   # format.check-python equivalent
ruff check .             # lint.check-lint equivalent
pyright --verifytypes invoke_tasklib --ignoreexternal
```

Or, once the package is installed:

```shell
invoke format.check-python
invoke lint.check-lint
invoke types.check
```

### Documentation

Build documentation locally:

```shell
mkdocs serve -f docs/mkdocs.yml
```

Then open <http://127.0.0.1:8000> in your browser.

Build without serving:

```shell
mkdocs build -f docs/mkdocs.yml
```

## Project Structure

```text
invoke-tasklib/
├── .github/                  # GitHub configuration (workflows, etc.)
├── docs/                     # Documentation
│   ├── docs/                # Documentation source
│   └── mkdocs.yml            # MkDocs configuration
├── src/
│   └── invoke_tasklib/
│       ├── __init__.py       # Public API: `ns` and individual task modules
│       ├── config.py         # Shared config resolution (`get_config`)
│       ├── format.py         # format.* tasks
│       ├── lint.py           # lint.* tasks
│       ├── types.py          # types.* tasks
│       ├── test.py           # test.* tasks
│       ├── env.py            # env.* tasks
│       ├── release.py        # release.* tasks
│       └── doc.py            # doc.* tasks
├── tests/                    # Test files, one module per task module
├── tasks.py                  # invoke-tasklib's own tasks.py (dogfoods `ns`)
├── invoke.yaml                # invoke-tasklib's own tasklib config
├── pyproject.toml             # Project configuration
└── README.md
```

## Adding a New Task

1. Pick the right module (`format.py`, `lint.py`, `types.py`, `test.py`, `env.py`, `release.py`,
   or `doc.py`), or create a new one if the task doesn't fit an existing namespace.
2. Follow the `check_<target>`/`fix_<target>` naming convention when applicable (see
   [Format](../uguide/format.md)).
3. Call `get_config(c)` if the task needs project-specific paths or the package name, rather than
   hardcoding them.
4. Write a docstring (Google style) describing the task; it is used both by `invoke --list --help`
   and by the [reference docs](../refs/format.md).
5. Add unit tests using `invoke.context.MockContext` (see existing tests for the pattern).
6. If the module is new, register it in `src/invoke_tasklib/__init__.py`'s `ns` and `__all__`.
7. Update the [README](https://github.com/durandtibo/invoke-tasklib/blob/main/README.md) task
   table and the corresponding [user guide](../uguide/format.md) page.

## Testing Guidelines

Tests use `invoke.context.MockContext` to capture the shell commands a task would run, without
actually running them:

```python
from invoke.config import Config
from invoke.context import MockContext

from invoke_tasklib import lint


def test_check_lint() -> None:
    c = MockContext(config=Config(overrides={"tasklib": {"package": {"name": "mypkg"}}}), run=True)
    lint.check_lint(c)
    assert c.run.call_args.args[0] == "ruff check --output-format=github ."
```

## Continuous Integration

CI runs on every push and PR: linting, type checking, and the test suite. Documentation is built
on every push and deployed via `doc.publish-dev`/`doc.publish-latest` from a release workflow.
