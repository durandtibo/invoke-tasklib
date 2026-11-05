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
uv sync --group dev --group docs
```

The `docs` group is needed to build the documentation (`mkdocs`, `mike`).

### 4. Set Up Pre-commit Hooks

```shell
pre-commit install
```

## Development Workflow

### Running Tests

```shell
.venv/bin/pytest tests -q
```

With coverage:

```shell
.venv/bin/pytest tests --cov=invoke_tasklib --cov-report=term-missing
```

Since `invoke-tasklib` itself uses `invoke` as its build tool, the project's own `tasks.py` (which
composes tasks from `invoke_tasklib`) can also be used once the package is installed in editable
mode - see the [Makefile](https://github.com/durandtibo/invoke-tasklib/blob/main/Makefile) and
`invoke --list` for the available tasks.

### Code Quality

```shell
.venv/bin/ruff format --check src tests   # format.check-python equivalent
.venv/bin/ruff check src tests            # lint.check-python equivalent
.venv/bin/ty check
```

The doctests of the source and of the Markdown files are run with `.venv/bin/inv test.doctest`.

Or, once the package is installed:

```shell
invoke format.check-python
invoke lint.check-python
invoke types.check
invoke check          # the main checks in one command
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
├── dev/                      # Scripts used by the repository itself
├── docs/                     # Documentation
│   ├── docs/                 # Documentation source (`uguide/`, `refs/`, `dev/`, `schema.json`)
│   └── mkdocs.yml            # MkDocs configuration
├── src/
│   └── invoke_tasklib/
│       ├── __init__.py       # Public API: `make_ns` and individual task modules
│       ├── config/           # Config resolution: `_schema.py` (`SCHEMA`, dataclasses, JSON schema),
│       │                     # `_validate.py`, `_derive.py`, `_resolve.py` (`get_config`, `load_config`),
│       │                     # `_invoke.py` (the only reader of the Invoke privates), `__main__.py`
│       ├── runner.py         # Command runner (`run`, `capture`, `build_command`)
│       ├── tools.py          # Tool lookup and install hints (`find_tool`, `check_program`)
│       ├── output.py         # Progress messages (`say`, `step`, `report_failure`)
│       ├── _steps.py         # Step runner shared by `check.all` and `fix.all`
│       ├── _files.py         # File lookup of the format and test tasks
│       ├── _pyproject.py     # Reader of `pyproject.toml` (`read_pyproject`)
│       ├── _coverage.py      # Where the coverage reports are written
│       ├── _graph.py         # Static import graph of `imports.check-cycles`
│       ├── _discover.py      # Module discovery and `import_each` of `imports.check-isolated`
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
│       ├── check.py          # check.* tasks
│       ├── fix.py            # fix.* tasks
│       └── show.py           # config.* tasks
├── tests/
│   ├── helpers.py            # `make_context` and `commands`, shared by the tests
│   ├── unit/                 # Unit tests, one module per source module (`config/` for `config/`)
│   ├── integration/          # Tests that run the real tools (`helpers.py`: `subprocess_context`)
│   └── benchmarks/           # Benchmarks (`inv test.benchmark`), run once by `pytest tests`
├── review/                   # Review notes of the repository
├── tasks.py                  # invoke-tasklib's own tasks.py (dogfoods `make_ns`)
├── invoke.yaml               # invoke-tasklib's own tasklib config
├── pyproject.toml            # Project configuration
└── README.md
```

## Adding a New Task

1. Pick the right module (`formatting.py`, `lint.py`, `imports.py`, `typecheck.py`, `testing.py`,
   `env.py`, `release.py`, `doc.py`, `security.py`, `clean.py`, `check.py`, `fix.py` or
   `show.py`), or create a new one
   if the task doesn't fit an existing namespace (give it a `NAMESPACE` constant, and add it to
   `_MODULES` of `__init__.py`).
2. Follow the `check_<target>`/`fix_<target>` naming convention when applicable (see
   [Format](../uguide/format.md)).
3. Call `load_config(c)` if the task needs project-specific paths or the package name, rather than
   hardcoding them. Run the external commands with `invoke_tasklib.runner.run` and build them
   with `build_command` (a list of words that `run` quotes), and print the progress with
   `invoke_tasklib.output.say`; do not call `c.run` or `print` in a task.
4. Write a docstring (Google style) describing the task; its first line, one sentence, is the
   summary shown by `invoke --list`. Give each option a `help` entry in `@task`, and add
   `--args` (`ARGS_HELP`) and `--paths` (`PATHS_HELP`) when the tool accepts extra arguments or
   paths. The docstring is also used by the [reference docs](../refs/format.md).
5. Add unit tests using `invoke.context.MockContext` (see existing tests for the pattern), and an
   integration test in `tests/integration/` for what the unit tests patch.
6. If the module is new, register it in `src/invoke_tasklib/__init__.py` (`_MODULES` and
   `__all__`).
7. Update the [README](https://github.com/durandtibo/invoke-tasklib/blob/main/README.md) task
   table, `uguide/index.md`, `docs/index.md` and the corresponding
   [user guide](../uguide/format.md) page.

## Conventions

`CLAUDE.md` at the root of the repository is the complete list of the rules for code, tests and
pull requests. The main ones:

- Every function, public or private, has a Google-style docstring (at most 72 characters wide) and
  its own unit tests; the coverage of `src/` is 100%. Keep the docstrings and the documentation
  up to date when the behaviour, the signature or the options of the code change.
- A test checks one behaviour (one `assert` or one `pytest.raises` with a `match`). A test that
  patches a collaborator has a matching integration test in `tests/integration/` that runs the real
  thing.
- Lint, format and type check before committing: `.venv/bin/ruff check src tests`,
  `.venv/bin/ruff format src tests` and `.venv/bin/ty check`, then run the tests and the doctests
  (`.venv/bin/pytest tests -q` and `.venv/bin/inv test.doctest`).
- One branch and one pull request per logical change, named `<type>/<short-description>` (for
  example `feat/add-cache-option`), branched from an up to date `main`.

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
