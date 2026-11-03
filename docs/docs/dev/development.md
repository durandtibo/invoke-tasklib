# Development Guide

This guide covers setting up your development environment and common development tasks for
`invoke-tasklib` itself.

## Prerequisites

- Python 3.11 or higher
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
ruff check .             # lint.check-python equivalent
ty check
```

Or, once the package is installed:

```shell
invoke format.check-python
invoke lint.check-python
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
│       ├── __init__.py       # Public API: `make_ns` and individual task modules
│       ├── config.py         # Shared config resolution (`get_config`, `load_config`)
│       ├── runner.py         # Shared command runner (`run`, `build_command`)
│       ├── output.py         # Progress messages (`say`, `step`)
│       ├── formatting.py     # format.* tasks
│       ├── lint.py           # lint.* tasks
│       ├── imports.py        # imports.* tasks
│       ├── typecheck.py      # types.* tasks
│       ├── testing.py        # test.* tasks
│       ├── env.py            # env.* tasks
│       ├── release.py        # release.* tasks
│       ├── doc.py            # doc.* tasks
│       ├── security.py       # security.* tasks
│       ├── clean.py          # clean.* tasks
│       └── check.py          # check.* tasks
├── tests/
│   ├── unit/                 # Unit tests, one module per source module
│   └── integration/          # Tests that run the real tools
├── tasks.py                  # invoke-tasklib's own tasks.py (dogfoods `make_ns`)
├── invoke.yaml                # invoke-tasklib's own tasklib config
├── pyproject.toml             # Project configuration
└── README.md
```

## Adding a New Task

1. Pick the right module (`formatting.py`, `lint.py`, `imports.py`, `typecheck.py`, `testing.py`,
   `env.py`, `release.py`, `doc.py`, `security.py`, `clean.py` or `check.py`), or create a new one
   if the task doesn't fit an existing namespace.
2. Follow the `check_<target>`/`fix_<target>` naming convention when applicable (see
   [Format](../uguide/format.md)).
3. Call `get_config(c)` if the task needs project-specific paths or the package name, rather than
   hardcoding them.
4. Write a docstring (Google style) describing the task; it is used both by `invoke --list --help`
   and by the [reference docs](../refs/format.md).
5. Add unit tests using `invoke.context.MockContext` (see existing tests for the pattern).
6. If the module is new, register it in `src/invoke_tasklib/__init__.py` (`_MODULES` and
   `__all__`).
7. Update the [README](https://github.com/durandtibo/invoke-tasklib/blob/main/README.md) task
   table and the corresponding [user guide](../uguide/format.md) page.

## Testing Guidelines

Tests use `invoke.context.MockContext` to capture the shell commands a task would run, without
actually running them. Two helpers of `tests/helpers.py` are shared by the test modules:
`make_context` builds a `MockContext` with an optional `tasklib` config, and `commands` returns the
commands passed to `c.run` (`run=True` makes `MockContext` record the calls in a `Mock`). Import
them instead of defining a copy in the test module:

```python
from tests.helpers import commands, make_context

from invoke_tasklib import lint


def test_check_python() -> None:
    c = make_context({"package": {"name": "mypkg"}})
    lint.check_python(c)
    assert commands(c) == ["ruff check ."]
```

The `tests/unit/conftest.py` fixture makes every program look available on the `PATH`, so the unit
tests do not depend on the tools installed on the machine. Tests that run the real tools go in
`tests/integration/`.

## Continuous Integration

CI runs on every push and PR: linting, type checking, and the test suite. Documentation is built
on every push and deployed via `doc.publish-dev`/`doc.publish-latest` from a release workflow.
