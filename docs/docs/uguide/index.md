# User Guide

:book: `invoke-tasklib` groups its tasks into namespaces, one per module. Each namespace maps to
one page in this guide.

## All Tasks at a Glance

Each task either **checks/reports** (read-only, exits non-zero on violations) or **mutates**
(formats, builds, publishes) — the `Mutates?` column below flags which.

| Namespace               | Task                          | Behavior                                            | Mutates? |
| ----------------------- | ----------------------------- | --------------------------------------------------- | :------: |
| [Format](format.md)     | `format.check-python`         | Check Python formatting with ruff                   |    ❌    |
| [Format](format.md)     | `format.fix-python`           | Format Python code with ruff                        |    ✅    |
| [Format](format.md)     | `format.check-docstrings`     | Check docstring formatting with docformatter        |    ❌    |
| [Format](format.md)     | `format.fix-docstrings`       | Format docstrings with docformatter                 |    ✅    |
| [Format](format.md)     | `format.check-shell`          | Check shell scripts with shellcheck                 |    ❌    |
| [Format](format.md)     | `format.fix-shell`            | Format shell scripts with shfmt                     |    ✅    |
| [Lint](lint.md)         | `lint.check-lint`             | Check code linting with ruff                        |    ❌    |
| [Lint](lint.md)         | `lint.fix`                    | Fix auto-fixable linting issues with ruff           |    ✅    |
| [Imports](imports.md)   | `imports.check-cycles`        | Check for cyclic import dependencies                |    ❌    |
| [Types](types.md)       | `types.check`                 | Check type hints with pyright                       |    ❌    |
| [Test](test.md)         | `test.doctest`                | Run doctests on source code and markdown files      |    ❌    |
| [Test](test.md)         | `test.doctest-src`            | Run doctests on source code                         |    ❌    |
| [Test](test.md)         | `test.doctest-markdown`       | Run doctests on Python examples in markdown         |    ❌    |
| [Test](test.md)         | `test.unit`                   | Run unit tests                                      |    ❌    |
| [Test](test.md)         | `test.integration`            | Run integration tests                               |    ❌    |
| [Test](test.md)         | `test.functional`             | Run functional tests                                |    ❌    |
| [Test](test.md)         | `test.all`                    | Run unit, integration, and functional tests         |    ❌    |
| [Test](test.md)         | `test.coverage-report`        | Generate an HTML/terminal report from coverage data |    ❌    |
| [Test](test.md)         | `test.benchmark`              | Run performance benchmarks                          |    ❌    |
| [Env](env.md)           | `env.create-venv`             | Create a virtual environment and install invoke     |    ✅    |
| [Env](env.md)           | `env.install`                 | Install project dependencies and the package        |    ✅    |
| [Env](env.md)           | `env.update`                  | Update dependencies and pre-commit hooks            |    ✅    |
| [Env](env.md)           | `env.show-installed-packages` | Show installed packages                             |    ❌    |
| [Env](env.md)           | `env.show-python-config`      | Show the Python configuration                       |    ❌    |
| [Release](release.md)   | `release.build`               | Build the package and verify installation           |    ✅    |
| [Release](release.md)   | `release.pypi`                | Build and publish the package to PyPI               |    ✅    |
| [Doc](doc.md)           | `doc.publish-dev`             | Publish development (unstable) docs                 |    ✅    |
| [Doc](doc.md)           | `doc.publish-latest`          | Publish latest (stable) docs                        |    ✅    |
| [Security](security.md) | `security.audit`              | Audit dependencies for known vulnerabilities        |    ❌    |
| [Clean](clean.md)       | `clean`                       | Remove build artifacts and caches                   |    ✅    |
| [Config](config.md)     | _(none — shared config)_      | Config resolution used by all tasks above           |    —     |

## Everyday Workflow

A typical local development loop looks like this:

```shell
invoke format.fix-python format.fix-docstrings   # auto-fix formatting
invoke lint.check-lint imports.check-cycles types.check  # check quality
invoke test.unit --cov                            # run tests with coverage
```

And what CI typically runs (nothing should modify the working tree):

```shell
invoke format.check-python format.check-docstrings lint.check-lint imports.check-cycles types.check
invoke test.all --cov
```

Since Invoke lets you chain multiple task names in one command, all of the above run as a single
`invoke` call each.

## External Tools

Tasks are thin wrappers around external command-line tools. Each is expected to be available on
`PATH` (or installed via [`env.install`](env.md)/[`env.create-venv`](env.md)):

| Tool                                                            | Used by                                                       |
| --------------------------------------------------------------- | ------------------------------------------------------------- |
| [`ruff`](https://docs.astral.sh/ruff/)                          | `format.check-python`, `format.fix-python`, `lint.check-lint` |
| [`docformatter`](https://docformatter.readthedocs.io/)          | `format.check-docstrings`, `format.fix-docstrings`            |
| [`shellcheck`](https://www.shellcheck.net/)                     | `format.check-shell`                                          |
| [`shfmt`](https://github.com/mvdan/sh)                          | `format.fix-shell`                                            |
| [`pyright`](https://microsoft.github.io/pyright/)               | `types.check`                                                 |
| [`pytest`](https://docs.pytest.org/)                            | `test.*` except `test.doctest` and `test.doctest-markdown`    |
| [`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/)  | `test.benchmark`                                              |
| [`uv`](https://docs.astral.sh/uv/)                              | `env.*`, `release.*`                                          |
| [`twine`](https://twine.readthedocs.io/) (via `uvx`)            | `release.build --check`                                       |
| [`mike`](https://github.com/jimporter/mike)                     | `doc.*`                                                       |
| [`feu`](https://github.com/durandtibo/feu) + `packaging`        | `doc.publish-latest`                                          |
| [`pip-audit`](https://github.com/pypa/pip-audit) (via `uv run`) | `security.audit`                                              |

Most of these come from your project's own dev/docs dependency groups; see
[Env](env.md#installing-dependencies) for how `env.install` wires them up, and the
[Troubleshooting guide](../troubleshooting.md) if a task fails with a "command not found" error.

## See Also

- [Get Started](../get_started.md): installing `invoke-tasklib` and wiring up a new project.
- [Config](config.md): the shared configuration all tasks read from.
- [Troubleshooting](../troubleshooting.md): common errors and how to fix them.
