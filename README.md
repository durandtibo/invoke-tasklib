# invoke-tasklib

Reusable [Invoke](https://www.pyinvoke.org/) tasks shared across Python
projects.

## Installation

Add `invoke-tasklib` as a dev dependency.

## Usage

In your project's `tasks.py`:

```python
from invoke_tasklib import ns
```

Set the required config in `invoke.yaml` at the project root:

```yaml
tasklib:
  package:
    name: my_package
```

Then list the available tasks:

```shell
invoke --list
```

## Tasks

Tasks are organized into namespaces: `format.*`, `lint.*`, `types.*`,
`test.*`, `env.*`, `release.*`, `doc.*`.

### `format.*` and `lint.*`

Tasks that check or verify something (never modify files, exit non-zero on
violations) are named `check_<target>`. Tasks that modify files in place are
named `fix_<target>`. Both share the same `<target>` (e.g. `python`, `shell`,
`docstrings`) so the read-only/mutating counterpart of a task is easy to find:

| Task                      | Behavior                                                  |
| ------------------------- | --------------------------------------------------------- |
| `format.check-python`     | Checks Python formatting with ruff (read-only)            |
| `format.check-docstrings` | Checks docstring formatting with docformatter (read-only) |
| `format.check-shell`      | Checks shell scripts with shellcheck (read-only)          |
| `format.fix-python`       | Formats Python code with ruff (in place)                  |
| `format.fix-docstrings`   | Formats docstrings with docformatter (in place)           |
| `format.fix-shell`        | Formats shell scripts with shfmt (in place)               |
| `lint.check-lint`         | Checks linting with ruff (read-only)                      |

When adding a new task to these namespaces, follow this convention: pick
`check_` or `fix_` based on whether the task mutates files, and use a
`<target>` name that matches its read-only/mutating counterpart if one
exists.

### `types.*`

| Task          | Behavior                                   |
| ------------- | ------------------------------------------ |
| `types.check` | Checks type hints with pyright (read-only) |

### `test.*`

| Task                     | Behavior                                            |
| ------------------------ | ---------------------------------------------------- |
| `test.doctest`           | Runs doctests on source code and markdown files      |
| `test.doctest-python`    | Runs doctests on source code                         |
| `test.doctest-markdown`  | Runs doctests on Python examples in markdown files   |
| `test.unit`              | Runs unit tests                                      |
| `test.integration`       | Runs integration tests                               |
| `test.functional`        | Runs functional tests                                |
| `test.all`               | Runs all tests (unit, integration, and functional)   |
| `test.benchmark`         | Runs performance benchmarks                          |

### `env.*`

| Task                          | Behavior                                                 |
| ----------------------------- | -------------------------------------------------------- |
| `env.create-venv`             | Creates a virtual environment and installs invoke        |
| `env.install`                 | Installs project dependencies and the package (editable) |
| `env.update`                  | Updates dependencies and pre-commit hooks                |
| `env.show-installed-packages` | Shows the installed packages                             |
| `env.show-python-config`      | Shows the Python configuration                           |

### `release.*`

| Task            | Behavior                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------- |
| `release.build` | Builds the package and verifies installation (`--check` also validates metadata with twine) |
| `release.pypi`  | Builds and publishes the package to PyPI                                                    |

### `doc.*`

| Task                 | Behavior                              |
| -------------------- | ------------------------------------- |
| `doc.publish-dev`    | Publishes development (unstable) docs |
| `doc.publish-latest` | Publishes latest (stable) docs        |

## Config

Only `tasklib.package.name` is required. Everything else has a default
derived from it. Full schema:

```yaml
tasklib:
  package:
    name: my_package # required
    python_version: "3.14" # used by env.create-venv
  paths:
    src: src/my_package # default: src/<package.name>
    tests: tests
    unit_tests: tests/unit # default: <tests>/unit
    integration_tests: tests/integration # default: <tests>/integration
    functional_tests: tests/functional # default: <tests>/functional
    benchmarks: tests/benchmarks # default: <tests>/benchmarks
    docs_config: docs/mkdocs.yml
```

## Composing a custom subset of tasks

If a project needs a different set of tasks, or a one-off task alongside the
shared ones, import individual task modules instead of the pre-built `ns`:

```python
from invoke import Collection
from invoke_tasklib import lint, test

from . import my_custom_task

ns = Collection(lint, test, my_custom_task)
```

Prefer adding a config knob to a shared task over forking it; reserve custom
composition for things that are genuinely one-off to a single project.
