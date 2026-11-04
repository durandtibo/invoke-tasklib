# invoke-tasklib

<p align="center">
    <a href="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml">
        <img alt="CI" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/ci.yaml/badge.svg">
    </a>
    <a href="https://github.com/durandtibo/invoke-tasklib/actions/workflows/nightly-package.yaml">
        <img alt="Nightly Package Tests" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/nightly-package.yaml/badge.svg">
    </a>
    <a href="https://codecov.io/gh/durandtibo/invoke-tasklib">
        <img alt="Codecov" src="https://codecov.io/gh/durandtibo/invoke-tasklib/branch/main/graph/badge.svg">
    </a>
    <br/>
    <a href="https://durandtibo.github.io/invoke-tasklib/">
        <img alt="Documentation" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/release-docs.yaml/badge.svg">
    </a>
    <a href="https://durandtibo.github.io/invoke-tasklib/dev/">
        <img alt="Documentation" src="https://github.com/durandtibo/invoke-tasklib/actions/workflows/release-docs-dev.yaml/badge.svg">
    </a>
    <br/>
    <a href="https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings">
        <img alt="Doc style: google" src="https://img.shields.io/badge/%20style-google-3666d6.svg">
    </a>
    <a href="https://github.com/astral-sh/ruff">
        <img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json">
    </a>
    <a href="https://github.com/guilatrova/tryceratops">
        <img alt="try/except style: tryceratops" src="https://img.shields.io/badge/try%2Fexcept%20style-tryceratops%20%F0%9F%A6%96%E2%9C%A8-black">
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
    <a href="https://pepy.tech/project/invoke-tasklib">
        <img alt="Downloads" src="https://static.pepy.tech/badge/invoke-tasklib">
    </a>
    <a href="https://pepy.tech/project/invoke-tasklib">
        <img alt="Monthly downloads" src="https://static.pepy.tech/badge/invoke-tasklib/month">
    </a>
    <a href="https://github.com/durandtibo/invoke-tasklib/stargazers">
        <img alt="GitHub stars" src="https://img.shields.io/github/stars/durandtibo/invoke-tasklib">
    </a>
    <br/>
    <a href="https://www.bestpractices.dev/projects/14387">
        <img src="https://www.bestpractices.dev/projects/14387/badge">
    </a>
    <a href="https://scorecard.dev/viewer/?uri=github.com/durandtibo/invoke-tasklib">
        <img alt="OpenSSF Scorecard" src="https://img.shields.io/badge/dynamic/json?url=https://api.scorecard.dev/projects/github.com/durandtibo/invoke-tasklib&label=openssf%20scorecard&query=score">
    </a>
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

**Prerequisite:** most tasks (`env.*`, `release.*`, `security.audit`) run
[`uv`](https://docs.astral.sh/uv/getting-started/installation/), so install
it even if you install `invoke-tasklib` with `pip`.

**Platforms:** Linux and macOS. Windows is not supported: the tasks rely on
a POSIX shell (for the quoting of the commands), and `make_ns` emits a
`RuntimeWarning` on Windows.

## Quickstart

**1. Add a `tasks.py`** at the root of your project:

```python
# tasks.py
from invoke_tasklib import make_ns

ns = make_ns()
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
invoke format.check-python lint.check-python
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

| Namespace  | Task                          | Behavior                                                                                 | Mutates? |
| ---------- | ----------------------------- | ---------------------------------------------------------------------------------------- | :------: |
| `format`   | `format.check-python`         | Check Python formatting with ruff                                                        |    ❌    |
| `format`   | `format.fix-python`           | Format Python code with ruff                                                             |    ✅    |
| `format`   | `format.check-docstrings`     | Check docstring formatting with docformatter                                             |    ❌    |
| `format`   | `format.fix-docstrings`       | Format docstrings with docformatter                                                      |    ✅    |
| `format`   | `format.check-shell`          | Check shell scripts with shellcheck                                                      |    ❌    |
| `format`   | `format.check-shell-format`   | Check the format of shell scripts with shfmt                                             |    ❌    |
| `format`   | `format.fix-shell`            | Format shell scripts with shfmt                                                          |    ✅    |
| `lint`     | `lint.check-python`           | Check linting with ruff                                                                  |    ❌    |
| `lint`     | `lint.fix-python`             | Fix auto-fixable linting issues with ruff                                                |    ✅    |
| `lint`     | `lint.check-spelling`         | Check the spelling with codespell                                                        |    ❌    |
| `lint`     | `lint.pre-commit`             | Run all the pre-commit hooks                                                             |    ✅    |
| `imports`  | `imports.check-cycles`        | Check for cyclic import dependencies                                                     |    ❌    |
| `imports`  | `imports.check-isolated`      | Check that every module imports on its own                                               |    ❌    |
| `types`    | `types.check`                 | Check type hints with ty (`--complete` also runs pyright)                                |    ❌    |
| `test`     | `test.doctest`                | Run doctests on source code and markdown files                                           |    ❌    |
| `test`     | `test.doctest-src`            | Run doctests on source code                                                              |    ❌    |
| `test`     | `test.doctest-markdown`       | Run doctests on Python examples in markdown files                                        |    ❌    |
| `test`     | `test.unit`                   | Run unit tests                                                                           |    ❌    |
| `test`     | `test.integration`            | Run integration tests                                                                    |    ❌    |
| `test`     | `test.functional`             | Run functional tests                                                                     |    ❌    |
| `test`     | `test.all`                    | Run unit, integration, and functional tests                                              |    ❌    |
| `test`     | `test.coverage-report`        | Generate an HTML/terminal report from existing coverage data                             |    ❌    |
| `test`     | `test.benchmark`              | Run performance benchmarks                                                               |    ❌    |
| `env`      | `env.create-venv`             | Create a virtual environment and install the project                                     |    ✅    |
| `env`      | `env.install`                 | Install project dependencies and the package (editable)                                  |    ✅    |
| `env`      | `env.check-tools`             | Check which tools (ruff, pyright, ...) are available                                     |    ❌    |
| `env`      | `env.update`                  | Update dependencies and pre-commit hooks                                                 |    ✅    |
| `env`      | `env.show-installed-packages` | Show the installed packages                                                              |    ❌    |
| `env`      | `env.show-python-config`      | Show the Python configuration                                                            |    ❌    |
| `release`  | `release.build`               | Build the package and verify installation (`--check` also validates metadata with twine) |    ✅    |
| `release`  | `release.publish`             | Build and publish the package to PyPI                                                    |    ✅    |
| `doc`      | `doc.publish-dev`             | Publish development (unstable) docs                                                      |    ✅    |
| `doc`      | `doc.publish-latest`          | Publish latest (stable) docs                                                             |    ✅    |
| `doc`      | `doc.build`                   | Build the docs, failing on warnings (`mkdocs build --strict`)                            |    ❌    |
| `doc`      | `doc.serve`                   | Serve the docs locally                                                                   |    ❌    |
| `security` | `security.audit`              | Audit the locked dependencies for known vulnerabilities with pip-audit                   |    ❌    |
| `check`    | `check.all` (or `check`)      | Run the main read-only checks                                                            |    ❌    |
| `fix`      | `fix.all` (or `fix`)          | Fix the lint and format issues                                                           |    ✅    |
| `clean`    | `clean.all` (or `clean`)      | Remove build artifacts and caches                                                        |    ✅    |
| `clean`    | `clean.pycache`               | Remove all `__pycache__` directories                                                     |    ✅    |
| `config`   | `config.show`                 | Show the resolved config and where each value comes from                                 |    ❌    |

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
    import_name: my_package # default: <package.name> with - replaced by _
    python_version: "3.14" # used by env.create-venv (default: the version that uv chooses)
  paths:
    src: src/my_package # default: src/<package.import_name>
    tests: tests
    unit_tests: tests/unit # default: <tests>/unit
    integration_tests: tests/integration # default: <tests>/integration
    functional_tests: tests/functional # default: <tests>/functional
    benchmarks: tests/benchmarks # default: <tests>/benchmarks
    docs_config: docs/mkdocs.yml
  groups:
    install: dev # dependency groups of env.install
    update: dev,docs # dependency groups of env.update
  test:
    unit_timeout: 10 # seconds, also integration_timeout and functional_timeout
    xdoctest: true # pytest --xdoctest (needs xdoctest)
    timeout: true # pytest --timeout (needs pytest-timeout)
    cov_fail_under: 90 # threshold of --cov (default: not set)
    cov_reports: html,xml,term
  check:
    tasks: format-python,format-docstrings,lint,types,imports,unit # steps of check.all
    cov: false # run the unit step of check.all with --cov
  fix:
    tasks: lint,format-python,format-docstrings # steps of fix.all
```

`check.tasks` also accepts `doctest`, `shell`, `spelling`, `docs` and `audit`; `fix.tasks` also
accepts `shell`. `invoke config.show` prints the resolved values and where each one comes from.

See the [Config reference](https://durandtibo.github.io/invoke-tasklib/uguide/config/)
for how each path default is derived.

## Composing a custom subset of tasks

Need a different set of tasks, or a one-off task alongside the shared ones?
Use `make_ns`, which returns a new collection each time, so adding or removing tasks never affects
other importers. Leave out the tasks you do not use (for example the ones that publish):

```python
# tasks.py
from invoke import task
from invoke_tasklib import make_ns


@task
def my_custom_task(c):
    r"""Run a one-off command."""
    c.run("echo hello")


ns = make_ns(exclude=["release.publish", "doc"])
ns.add_task(my_custom_task)
```

`tasks.py` is imported by Invoke as a top-level module, so a task defined in another file of the
project is imported with an absolute import (`from my_tasks import my_custom_task`), not a
relative one (`from . import my_custom_task`), which fails with an `ImportError`.

or keep only some of them with `include`, e.g. `make_ns(include=["lint", "test.unit"])`. The names
are namespaces (`"doc"`) or tasks (`"release.publish"`); an unknown name raises a `ValueError`. The
`make_ns()` with no argument has all the tasks (the former pre-built `invoke_tasklib.ns`, one
collection shared by every importer, was removed). Individual task modules can also be composed by
hand:

```python
# tasks.py
from invoke import Collection, task
from invoke_tasklib import lint, testing


@task
def my_custom_task(c):
    r"""Run a one-off command."""
    c.run("echo hello")


ns = Collection(lint, Collection.from_module(testing, name="test"), my_custom_task)
```

The modules of the `format`, `types` and `test` namespaces are named `formatting`, `typecheck`
and `testing` so that they do not shadow the standard library (`types`, `test`) or a builtin
(`format`); pass `name=` to `Collection.from_module` to keep the task names.

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
