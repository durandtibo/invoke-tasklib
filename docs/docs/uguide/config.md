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
```

Only `tasklib.package.name` (the distribution name, as on PyPI) is required. Everything else has a default, and most of the `paths`
defaults are derived from `package.name` or from `paths.tests`.

## Defaults

| Key                        | Default                                                                               |
| -------------------------- | ------------------------------------------------------------------------------------- |
| `package.import_name`      | `<package.name>` with `-` replaced by `_`                                             |
| `package.python_version`   | `"3.14"`                                                                              |
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
| `test.cov_fail_under`      | not set                                                                               |

The `test` section sets the per-test timeout in seconds of each test scope, whether `pytest` runs
with `--xdoctest` (it requires the `xdoctest` package, so set `xdoctest: false` if the project does
not have it), and a coverage threshold: with `--cov`, `cov_fail_under` is forwarded as
`--cov-fail-under`. Timeouts and `cov_fail_under` are integers, `xdoctest` is a boolean.

`package.import_name` is the name used to import the package. It is used by `imports.check-cycles`,
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
