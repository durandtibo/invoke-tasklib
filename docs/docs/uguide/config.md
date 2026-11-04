# Config

:book: This page describes the `invoke_tasklib.config` module, which resolves the shared config
that all `invoke-tasklib` tasks read from.

**Prerequisites:** You'll need to know a bit of Python and [Invoke](https://www.pyinvoke.org/).

## Overview

Every task in `invoke-tasklib` calls `load_config(c)` (`get_config(c)` with a clean exit on an
invalid config, see below) to read project-specific values from an
`invoke.yaml` at the root of the consuming project, under a `tasklib` key:

```yaml
tasklib:
  package:
    name: my_package
    python_version: "3.14"
  paths:
    src: src/my_package
    tests: tests
    unit_tests: tests/unit
    integration_tests: tests/integration
    functional_tests: tests/functional
    benchmarks: tests/benchmarks
    docs_config: docs/mkdocs.yml
  groups:
    install: dev
    update: dev,docs
  test:
    unit_timeout: 10
    xdoctest: true
    cov_reports: html,xml,term
  check:
    tasks: format-python,format-docstrings,lint,types,imports,unit
  fix:
    tasks: lint,format-python,format-docstrings
```

Only `tasklib.package.name` (the distribution name, as on PyPI) is required. Everything else has a default, and most of the `paths`
defaults are derived from `package.name` or from `paths.tests`.

## Defaults

| Key                        | Default                                                                               |
| -------------------------- | ------------------------------------------------------------------------------------- |
| `package.name`             | required                                                                              |
| `package.import_name`      | `<package.name>` with `-` replaced by `_`                                             |
| `package.python_version`   | the `.python-version` file, else the `requires-python` lower bound, else `"3.14"`     |
| `paths.src`                | `src/<package.import_name>`, or `<package.import_name>` if only that directory exists |
| `paths.tests`              | `tests`                                                                               |
| `paths.unit_tests`         | `<paths.tests>/unit`                                                                  |
| `paths.integration_tests`  | `<paths.tests>/integration`                                                           |
| `paths.functional_tests`   | `<paths.tests>/functional`                                                            |
| `paths.benchmarks`         | `<paths.tests>/benchmarks`                                                            |
| `paths.docs_config`        | `docs/mkdocs.yml`                                                                     |
| `groups.install`           | `dev`                                                                                 |
| `groups.update`            | `dev,docs`                                                                            |
| `test.unit_timeout`        | `10`                                                                                  |
| `test.integration_timeout` | `60`                                                                                  |
| `test.functional_timeout`  | `60`                                                                                  |
| `test.xdoctest`            | `true`                                                                                |
| `test.timeout`             | `true`                                                                                |
| `test.cov_fail_under`      | not set                                                                               |
| `test.cov_reports`         | `html,xml,term`                                                                       |
| `check.tasks`              | `format-python,format-docstrings,lint,types,imports,unit`                             |
| `check.cov`                | `false`                                                                               |
| `fix.tasks`                | `lint,format-python,format-docstrings`                                                |

The `test` section sets the per-test timeout in seconds of each test scope, whether `pytest` runs
with `--xdoctest` (it requires the `xdoctest` package, so set `xdoctest: false` if the project does
not have it; `test.doctest-src` ignores it and always uses the plugin), whether it runs with
`--timeout` (it requires the `pytest-timeout` package, so set `timeout: false` if the project does
not have it; the `unit_timeout`, `integration_timeout` and `functional_timeout` values are then
unused), and a coverage threshold:
with `--cov`, `cov_fail_under` is forwarded as `--cov-fail-under`. Timeouts and `cov_fail_under` are integers, `xdoctest` is a boolean.
`cov_reports` is a comma-separated string or a list of the `--cov-report` values of pytest-cov
(`html`, `xml`, `json`, `lcov`, `annotate`, `term`, `term-missing`) that `--cov` generates. A value
can have the argument of pytest-cov after a colon, for example `term-missing:skip-covered` or
`html:cov_html` (the directory or file of the report). The value is quoted in the command. An empty
value passes no `--cov-report`, so pytest-cov uses its default.

`check.cov` is a boolean. If true, the `unit` step of `check.all` runs with `--cov`, so
`test.cov_fail_under` is enforced there too (the coverage reports are generated).

`check.tasks` is a comma-separated string or a list of the steps of `check.all`, run in that order:
`format-python`, `format-docstrings`, `lint`, `types`, `imports`, `unit`, `doctest`, `shell`,
`spelling`, `docs` and `audit`. It must have at least one step and no unknown step.

`fix.tasks` is the same for the steps of `fix.all`: `lint`, `format-python`, `format-docstrings` and
`shell`, run in that order (the lint fixes first, so that the formatting has the last word on the
layout).

`package.import_name` is the name used to import the package. It is used by `imports.check-cycles`, `imports.check-isolated`,
`release.build` (the import check of the built artifacts) and the `--cov` option of the test tasks.
Set it when it is not the distribution name with `-` replaced by `_`. It must be a Python module
name.

If `tasklib.package.name` is missing, `get_config` raises a `ValueError`; the tasks use
`load_config`, which turns it into an `invoke.exceptions.Exit` with the same message and the exit
code 2 (no traceback).

Unknown keys in `tasklib` itself (typically a typo of a section such as `path`) and in the
`package`, `paths`, `groups` or `test` sections (such as `paths.unit_test`) also raise a
`ValueError` that lists the valid keys and suggests the closest one, instead of being silently
ignored. Each section must be a mapping, `package.name` and every `paths.*` value must be a
non-empty string, and `test.cov_fail_under` must be between 0 and 100.

`package.python_version` must be a quoted string such as `"3.10"` or `"3.10.4"`. YAML reads an
unquoted `3.10` as the number `3.1`, so `get_config` raises a `ValueError` for any non-string or
malformed value instead of silently creating a virtual environment with the wrong Python.

When the key is not set, the version is read from the project, in this order:

1. the first line of the `.python-version` file, if it is a version such as `3.12` or `3.12.1`
   (an implementation name such as `pypy3.10` is ignored);
2. the lower bound of `project.requires-python` in `pyproject.toml` (`">=3.11"` gives `3.11`);
3. `3.14`.

## Showing the Resolved Config

```shell
invoke config.show
```

Prints the `tasklib` section as the tasks see it, with every key and a comment with its origin. It
answers "which value is used, and why" without reading the code:

```yaml
tasklib:
  package:
    name: demo # project file
    import_name: demo # derived
  paths:
    src: lib # project file
    tests: zz # environment variable INVOKE_TASKLIB_PATHS_TESTS
    unit_tests: zz/unit # derived
    docs_config: docs/mkdocs.yml # default
```

The origin is the source with the highest priority that sets the key: `default` (the default of
the library, or no value for an optional key), `project file` (`invoke.yaml`),
`environment variable INVOKE_TASKLIB_...`, `system config file`, `user config file`,
`runtime config file` or `override` (set from the command line or by code). `derived` is a value
that no source sets, computed from other values or from the project (`import_name`, `src`, the test
paths and the Python version). The config is validated first, so an invalid one stops the task with
the usual one-line message. The task reads nothing but the config and the two project files of
[`package.python_version`](#defaults), and changes nothing.

## Editor Completion (JSON Schema)

The keys, the defaults and the descriptions are declared once, in `invoke_tasklib.config.SCHEMA`
(one `Option` per key: default, validation and JSON schema). The defaults, the key checks, the
error messages and the JSON schema are all generated from it, so they cannot drift. Print the
schema of the `tasklib` section of `invoke.yaml` with:

```shell
python -m invoke_tasklib.config > invoke-tasklib.schema.json
```

The same file is published with the documentation. Point your editor to it with a comment at the
top of `invoke.yaml` to get completion and validation of the keys:

```yaml
# yaml-language-server: $schema=https://durandtibo.github.io/invoke-tasklib/schema.json
tasklib:
  package:
    name: my_package
```

A test checks that the published `docs/docs/schema.json` equals the schema printed by the command
(regenerate it with `python -m invoke_tasklib.config > docs/docs/schema.json`).

## Working Directory

Run `inv` from the directory of `tasks.py` (the project root). Invoke finds `tasks.py` and
`invoke.yaml` in the parents of the current directory, but the tasks use paths relative to the
current directory, so any task that reads the config exits with code 2 and a message when the
current directory is another one (see [Troubleshooting](../troubleshooting.md)).

## Environment Variables

Every key can also be set with an `INVOKE_TASKLIB_<SECTION>_<KEY>` environment variable, for example
`INVOKE_TASKLIB_PATHS_SRC=lib` or `INVOKE_TASKLIB_TEST_UNIT_TIMEOUT=30`. This is handy in CI. It
works because `make_ns` registers the defaults of the `tasklib` section with Invoke,
which only reads the environment variables of the keys that it knows. The usual Invoke order
applies: the environment variables win over `invoke.yaml`.

Invoke reads an environment variable as a string, and tasklib parses it:

- a boolean (`INVOKE_TASKLIB_TEST_XDOCTEST`, `..._TEST_TIMEOUT`, `..._CHECK_COV`) is one of `true`,
  `false`, `1`, `0`, `yes`, `no`, `on` and `off`, in any case. Any other text is an error;
- an integer (the timeouts, `test.cov_fail_under`) is a string of digits. Any other text is an
  error.

An invalid value exits with code 2 and a one-line message, like an invalid `invoke.yaml`. The same
spellings work for a string value in `invoke.yaml`. A collection built by hand (`Collection(lint, ...)`) has no defaults, so it does
not read the environment variables unless you call
`ns.configure({"tasklib": invoke_tasklib.config.default_config()})`.

## Minimal Config

The smallest valid `invoke.yaml` only sets the package name:

```yaml
tasklib:
  package:
    name: my_package
```

With this, `paths.src` resolves to `src/my_package`, `paths.unit_tests` resolves to
`tests/unit`, and so on.

## Overriding Paths

Override any individual path without affecting the others' defaults, for example when tests live
outside `tests/`:

```yaml
tasklib:
  package:
    name: my_package
  paths:
    tests: test
    benchmarks: test/perf
```

Here `paths.unit_tests` still resolves to `<paths.tests>/unit`, i.e. `test/unit`, since it is
derived from the overridden `paths.tests`.

## Overriding Dependency Groups

[`env.install`](env.md) and [`env.update`](env.md) install `uv` dependency groups by name.
Projects that define more groups than `dev`/`docs` (e.g. `test`, `lint`) can change the defaults
those tasks use, instead of passing `--groups` on every invocation:

```yaml
tasklib:
  package:
    name: my_package
  groups:
    install: dev,test
    update: dev,test,docs
```

Each value can also be written as a YAML list, which is joined with commas:

```yaml
tasklib:
  groups:
    install: [dev, test]
    update: [dev, test, docs]
```

The `--groups` flag of the tasks stays a comma-separated string (`--groups dev,docs`).

## Using `get_config` in a Custom Task

`get_config` returns frozen dataclasses (`cfg.package`, `cfg.paths`, `cfg.groups`, `cfg.test`), so the
values are read as attributes and cannot be modified. It raises a `ValueError` on an invalid config;
use `load_config` in a task to exit with a message instead. `get_config` is the same function every built-in task uses, so a project-specific task can read
the same config:

```python
from invoke.tasks import task
from invoke_tasklib.config import get_config


@task
def my_task(c):
    cfg = get_config(c)
    print(cfg.package.name, cfg.paths.src)
```

## See Also

- [Get Started](../get_started.md): setting up `invoke.yaml` in a new project.
- [`invoke_tasklib.config` reference](../refs/config.md)
