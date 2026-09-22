# invoke-tasklib

<p align="center">
    <a href="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml">
        <img alt="CI" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml/badge.svg">
    </a>
    <a href="https://codecov.io/gh/durandtibo/invoke-tasklib">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/invoke-tasklib/branch/main/graph/badge.svg">
    </a>
    <br/>
    <a href="https://durandtibo.github.io/invoke-tasklib/">
        <img alt="Documentation" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/release-docs.yaml/badge.svg">
    </a>
    <br/>
    <a href="https://github.com/astral-sh/ruff">
        <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff" style="max-width:100%;">
    </a>
    <br/>
    <a href="https://pypi.org/project/invoke-tasklib/">
        <img alt="PYPI version" src="https://img.shields.io/pypi/v/invoke-tasklib">
    </a>
    <a href="https://pypi.org/project/invoke-tasklib/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/invoke-tasklib.svg">
    </a>
    <a href="https://opensource.org/licenses/BSD-3-Clause">
        <img alt="BSD-3-Clause" src="https://img.shields.io/pypi/l/invoke-tasklib">
    </a>
    <br/>
</p>

Reusable [Invoke](https://www.pyinvoke.org/) tasks shared across Python
projects: formatting, linting, type-checking, testing, environment setup,
security auditing, releasing, documentation, and cleanup — all as a single
importable package instead of a `tasks.py` you copy-paste and let drift
between repositories.

:book: **Full documentation:** <https://durandtibo.github.io/invoke-tasklib/>

## Install

```shell
uv add --dev invoke-tasklib
```

or with `pip`:

```shell
pip install invoke-tasklib
```

## Quickstart

**1. Add a `tasks.py`** at the root of your project:

```python
# tasks.py
from invoke_tasklib import ns
```

**2. Add an `invoke.yaml`** with, at minimum, your package name:

```yaml
tasklib:
  package:
    name: my_package
```

**3. List and run the tasks:**

```shell
invoke --list
invoke format.check-python lint.check-lint
invoke test.unit
```

If a task fails because a tool like `ruff` or `pytest` isn't installed yet,
run `invoke env.install` first.

See the [Get Started guide](https://durandtibo.github.io/invoke-tasklib/get_started/)
for a full walkthrough.

## Tasks

Tasks are grouped into namespaces, one per module. Each task either
**checks/reports** (read-only, exits non-zero on violations) or
**mutates** (formats, builds, publishes) — the table below flags which.

| Namespace     | Task                          | Behavior                                                                                 | Mutates? |
| ------------- | ----------------------------- | ---------------------------------------------------------------------------------------- | :------: |
| `format`      | `format.check-python`         | Check Python formatting with ruff                                                        |    ❌    |
| `format`      | `format.fix-python`           | Format Python code with ruff                                                             |    ✅    |
| `format`      | `format.check-docstrings`     | Check docstring formatting with docformatter                                             |    ❌    |
| `format`      | `format.fix-docstrings`       | Format docstrings with docformatter                                                      |    ✅    |
| `format`      | `format.check-shell`          | Check shell scripts with shellcheck                                                      |    ❌    |
| `format`      | `format.fix-shell`            | Format shell scripts with shfmt                                                          |    ✅    |
| `lint`        | `lint.check-lint`             | Check linting with ruff                                                                  |    ❌    |
| `lint`        | `lint.fix`                    | Fix auto-fixable linting issues with ruff                                                |    ✅    |
| `types`       | `types.check`                 | Check type hints with pyright                                                            |    ❌    |
| `test`        | `test.doctest`                | Run doctests on source code and markdown files                                           |    ❌    |
| `test`        | `test.doctest-src`            | Run doctests on source code                                                              |    ❌    |
| `test`        | `test.doctest-markdown`       | Run doctests on Python examples in markdown files                                        |    ❌    |
| `test`        | `test.unit`                   | Run unit tests                                                                           |    ❌    |
| `test`        | `test.integration`            | Run integration tests                                                                    |    ❌    |
| `test`        | `test.functional`             | Run functional tests                                                                     |    ❌    |
| `test`        | `test.all`                    | Run unit, integration, and functional tests                                              |    ❌    |
| `test`        | `test.coverage-report`        | Generate an HTML/terminal report from existing coverage data                             |    ❌    |
| `test`        | `test.benchmark`              | Run performance benchmarks                                                               |    ❌    |
| `env`         | `env.create-venv`             | Create a virtual environment and install invoke                                          |    ✅    |
| `env`         | `env.install`                 | Install project dependencies and the package (editable)                                  |    ✅    |
| `env`         | `env.update`                  | Update dependencies and pre-commit hooks                                                 |    ✅    |
| `env`         | `env.show-installed-packages` | Show the installed packages                                                              |    ❌    |
| `env`         | `env.show-python-config`      | Show the Python configuration                                                            |    ❌    |
| `release`     | `release.build`               | Build the package and verify installation (`--check` also validates metadata with twine) |    ✅    |
| `release`     | `release.pypi`                | Build and publish the package to PyPI                                                    |    ✅    |
| `doc`         | `doc.publish-dev`             | Publish development (unstable) docs                                                      |    ✅    |
| `doc`         | `doc.publish-latest`          | Publish latest (stable) docs                                                             |    ✅    |
| `security`    | `security.audit`              | Audit installed dependencies for known vulnerabilities with pip-audit                    |    ❌    |
| _(top-level)_ | `clean`                       | Remove build artifacts and caches                                                        |    ✅    |

`format.*` and `lint.*` follow a naming convention: read-only checks are
named `check_<target>`, and the matching in-place fixer is named
`fix_<target>` (e.g. `check_python`/`fix_python`), so the counterpart of a
task is always easy to find. Follow this convention when adding new tasks
to these namespaces.

For task-by-task details, options (like `--cov` on `test.*` tasks), and the
tools each one wraps, see the
[User Guide](https://durandtibo.github.io/invoke-tasklib/uguide/).

## Configuration

Only `tasklib.package.name` is required — everything else has a sensible
default derived from it:

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

See the [Config reference](https://durandtibo.github.io/invoke-tasklib/uguide/config/)
for how each path default is derived.

## Composing a custom subset of tasks

Need a different set of tasks, or a one-off task alongside the shared ones?
Import individual task modules instead of the pre-built `ns`:

```python
from invoke import Collection
from invoke_tasklib import lint, test

from . import my_custom_task

ns = Collection(lint, test, my_custom_task)
```

Prefer adding a config knob to a shared task over forking it; reserve custom
composition for things that are genuinely one-off to a single project.

## API Stability

:warning: `invoke-tasklib` is under active development and its API is not
yet stable — pin a specific version in your project's dependencies for
consistent behavior across releases.

## Contributing

Contributions are welcome! Please open an issue first to discuss
significant changes. See the
[developer guide](https://durandtibo.github.io/invoke-tasklib/dev/development/)
for how to set up a development environment.

## License

`invoke-tasklib` is licensed under the BSD 3-Clause "New" or "Revised"
license available in
[LICENSE](https://github.com/durandtibo/invoke-tasklib/blob/main/LICENSE).
