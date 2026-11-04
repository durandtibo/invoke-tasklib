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
| [Lint](lint.md)         | `lint.check-python`           | Check code linting with ruff                        |    ❌    |
| [Lint](lint.md)         | `lint.fix-python`             | Fix auto-fixable linting issues with ruff           |    ✅    |
| [Lint](lint.md)         | `lint.check-spelling`         | Check the spelling with codespell                   |    ❌    |
| [Lint](lint.md)         | `lint.pre-commit`             | Run all the pre-commit hooks                        |    ✅    |
| [Imports](imports.md)   | `imports.check-cycles`        | Check for cyclic import dependencies                |    ❌    |
| [Imports](imports.md)   | `imports.check-isolated`      | Check that every module imports on its own          |    ❌    |
| [Types](types.md)       | `types.check`                 | Check type hints with ty (`--complete`: + pyright)  |    ❌    |
| [Test](test.md)         | `test.doctest`                | Run doctests on source code and markdown files      |    ❌    |
| [Test](test.md)         | `test.doctest-src`            | Run doctests on source code                         |    ❌    |
| [Test](test.md)         | `test.doctest-markdown`       | Run doctests on Python examples in markdown         |    ❌    |
| [Test](test.md)         | `test.unit`                   | Run unit tests                                      |    ❌    |
| [Test](test.md)         | `test.integration`            | Run integration tests                               |    ❌    |
| [Test](test.md)         | `test.functional`             | Run functional tests                                |    ❌    |
| [Test](test.md)         | `test.all`                    | Run unit, integration, and functional tests         |    ❌    |
| [Test](test.md)         | `test.coverage-report`        | Generate an HTML/terminal report from coverage data |    ❌    |
| [Test](test.md)         | `test.benchmark`              | Run performance benchmarks                          |    ❌    |
| [Env](env.md)           | `env.create-venv`             | Create a virtual environment and install the project    |    ✅    |
| [Env](env.md)           | `env.install`                 | Install project dependencies and the package        |    ✅    |
| [Env](env.md)           | `env.check-tools`             | Check which tools are available                     |    ❌    |
| [Env](env.md)           | `env.update`                  | Update dependencies and pre-commit hooks            |    ✅    |
| [Env](env.md)           | `env.show-installed-packages` | Show installed packages                             |    ❌    |
| [Env](env.md)           | `env.show-python-config`      | Show the Python configuration                       |    ❌    |
| [Release](release.md)   | `release.build`               | Build the package and verify installation           |    ✅    |
| [Release](release.md)   | `release.publish`             | Build and publish the package to PyPI               |    ✅    |
| [Doc](doc.md)           | `doc.build`                   | Build the docs, failing on warnings                 |    ❌    |
| [Doc](doc.md)           | `doc.serve`                   | Serve the docs locally                              |    ❌    |
| [Doc](doc.md)           | `doc.publish-dev`             | Publish development (unstable) docs                 |    ✅    |
| [Doc](doc.md)           | `doc.publish-latest`          | Publish latest (stable) docs                        |    ✅    |
| [Security](security.md) | `security.audit`              | Audit dependencies for known vulnerabilities        |    ❌    |
| [Check](check.md)       | `check.all` (or `check`)      | Run the main read-only checks                       |    ❌    |
| [Clean](clean.md)       | `clean.all` (or `clean`)      | Remove build artifacts and caches                   |    ✅    |
| [Clean](clean.md)       | `clean.pycache`               | Remove all `__pycache__` directories                |    ✅    |
| [Config](config.md)     | `config.show`                 | Show the resolved config and its origins            |    ❌    |
| [Config](config.md)     | _(none — shared config)_      | Config resolution used by all tasks above           |    —     |

## Everyday Workflow

A typical local development loop looks like this:

```shell
invoke format.fix-python format.fix-docstrings   # auto-fix formatting
invoke lint.check-python imports.check-cycles types.check  # check quality
invoke test.unit --cov                            # run tests with coverage
```

To run the main read-only checks (format, lint, types, imports and the unit tests) in one command:

```shell
invoke check
```

See [Check](check.md) for the steps and the options.

And what CI typically runs (nothing should modify the working tree):

```shell
invoke format.check-python format.check-docstrings lint.check-python imports.check-cycles types.check
invoke test.all --cov
```

Since Invoke lets you chain multiple task names in one command, all of the above run as a single
`invoke` call each.

## Passing Arguments to the Tools

Every task that runs an external tool takes `--args`, and the tasks that run on files also take
`--paths`:

- `--args` adds arguments to the command. The value is one string, split like a shell does.
- `--paths` runs the tool on these files or directories instead of the default ones (the
  project for `ruff`, `paths.src` for `docformatter` and the source doctests, the scope directory
  for `pytest`, every `*.sh` file for `shellcheck` and `shfmt`, every markdown file for the
  markdown doctests).

| Tasks                                                                            | `--args` goes to      | `--paths` |
| -------------------------------------------------------------------------------- | --------------------- | :-------: |
| `test.all`, `test.unit`, `test.integration`, `test.functional`, `test.benchmark` | `pytest`              |    ✅     |
| `test.doctest-src`                                                               | `pytest`              |    ✅     |
| `test.doctest-markdown`                                                          | `python -m doctest`   |    ✅     |
| `test.coverage-report`                                                           | `coverage report`     |    ❌     |
| `format.*-python`, `lint.check-python`, `lint.fix-python`                        | `ruff`                |    ✅     |
| `format.*-docstrings`                                                            | `docformatter`        |    ✅     |
| `format.check-shell`, `format.fix-shell`                                         | `shellcheck`, `shfmt` |    ✅     |
| `lint.check-spelling`                                                            | `codespell`           |    ✅     |
| `lint.pre-commit`                                                                | `pre-commit`          |    ❌     |
| `types.check`                                                                    | `ty` (only)           |    ✅     |
| `security.audit`                                                                 | `pip-audit`           |    ❌     |
| `doc.build`, `doc.serve`                                                         | `mkdocs`              |    ❌     |
| `release.build`                                                                  | `uv build`            |    ❌     |
| `release.publish`                                                                | `uv publish`          |    ❌     |

The tasks that have no option are the composite tasks (`check.all`, `test.doctest`), the tasks
that run no external tool (`clean.*`, `imports.*`) and the tasks with their own options
(`env.*`, `doc.publish-*`).

```shell
invoke test.unit --args "-k foo -x" --paths tests/unit/test_foo.py
invoke lint.check-python --args "--select E" --paths "src/a.py src/b.py"
invoke format.check-python --paths src/a.py
invoke security.audit --args "--ignore-vuln PYSEC-2024-1"
invoke doc.serve --args "--dev-addr 127.0.0.1:8001"
invoke test.coverage-report --args "--fail-under=90"
```

For `types.check`, `--args` goes to `ty` only and `--paths` goes to `ty` and `pyright`. The
arguments and the paths are quoted, so they are never interpreted by the shell.

## External Tools

Tasks are thin wrappers around external command-line tools. Each is expected to be available on
`PATH` (or installed via [`env.install`](env.md)/[`env.create-venv`](env.md)):

| Tool                                                              | Used by                                                         |
| ----------------------------------------------------------------- | --------------------------------------------------------------- |
| [`ruff`](https://docs.astral.sh/ruff/)                            | `format.check-python`, `format.fix-python`, `lint.check-python` |
| [`docformatter`](https://docformatter.readthedocs.io/)            | `format.check-docstrings`, `format.fix-docstrings`              |
| [`shellcheck`](https://www.shellcheck.net/)                       | `format.check-shell`                                            |
| [`shfmt`](https://github.com/mvdan/sh)                            | `format.fix-shell`                                              |
| [`ty`](https://docs.astral.sh/ty/)                                | `types.check`                                                   |
| [`pyright`](https://microsoft.github.io/pyright/)                 | `types.check --complete`                                        |
| [`pytest`](https://docs.pytest.org/)                              | `test.*` except `test.doctest` and `test.doctest-markdown`      |
| [`pytest-timeout`](https://pypi.org/project/pytest-timeout/)      | `test.unit`, `test.integration`, `test.functional`, `test.all`  |
| [`pytest-cov`](https://pytest-cov.readthedocs.io/)                | the `--cov` option of the `test.*` tasks                        |
| [`coverage`](https://coverage.readthedocs.io/)                    | `test.coverage-report`                                          |
| [`xdoctest`](https://github.com/Erotemic/xdoctest)                | `test.*` (unless `test.xdoctest` is false), `test.doctest-src`  |
| [`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/)    | `test.benchmark`                                                |
| [`uv`](https://docs.astral.sh/uv/)                                | `env.*`, `release.*`                                            |
| [`twine`](https://twine.readthedocs.io/) (via `uvx`)              | `release.build --check`                                         |
| [`codespell`](https://github.com/codespell-project/codespell)     | `lint.check-spelling`                                           |
| [`pre-commit`](https://pre-commit.com/)                           | `lint.pre-commit`                                               |
| [`mkdocs`](https://www.mkdocs.org/)                               | `doc.build`, `doc.serve`                                        |
| [`mkdocs-material`](https://squidfunk.github.io/mkdocs-material/) | the theme of the docs built by `doc.build`, `doc.serve`         |
| [`mike`](https://github.com/jimporter/mike)                       | `doc.publish-dev`, `doc.publish-latest`                         |
| [`git`](https://git-scm.com/)                                     | `doc.publish-latest`                                            |
| [`pip-audit`](https://github.com/pypa/pip-audit) (via `uvx`)      | `security.audit`                                                |

Most of these come from your project's own dev/docs dependency groups; see
[Env](env.md#installing-dependencies) for how `env.install` wires them up, and the
[Troubleshooting guide](../troubleshooting.md) if a task fails with a "command not found" error.

## See Also

- [Get Started](../get_started.md): installing `invoke-tasklib` and wiring up a new project.
- [Config](config.md): the shared configuration all tasks read from.
- [Writing a Custom Task](custom_tasks.md): the helpers to write a task like the shared ones.
- [Troubleshooting](../troubleshooting.md): common errors and how to fix them.
