# Config

:book: This page describes the `invoke_tasklib.config` module, which resolves the shared config
that all `invoke-tasklib` tasks read from.

**Prerequisites:** You'll need to know a bit of Python and [Invoke](https://www.pyinvoke.org/).

## Overview

Every task in `invoke-tasklib` calls `get_config(c)` to read project-specific values from an
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
```

Only `tasklib.package.name` is required. Everything else has a default, and most of the `paths`
defaults are derived from `package.name` or from `paths.tests`.

## Defaults

| Key                        | Default                        |
| --------------------------- | --------------------------------- |
| `package.python_version`   | `"3.14"`                        |
| `paths.src`                | `src/<package.name>`            |
| `paths.tests`              | `tests`                         |
| `paths.unit_tests`         | `<paths.tests>/unit`            |
| `paths.integration_tests`  | `<paths.tests>/integration`     |
| `paths.functional_tests`   | `<paths.tests>/functional`      |
| `paths.benchmarks`         | `<paths.tests>/benchmarks`      |
| `paths.docs_config`        | `docs/mkdocs.yml`                |

If `tasklib.package.name` is missing, `get_config` raises a `ValueError`.

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

## Using `get_config` in a Custom Task

`get_config` is the same function every built-in task uses, so a project-specific task can read
the same config:

```python
from invoke.tasks import task
from invoke_tasklib.config import get_config


@task
def my_task(c):
    cfg = get_config(c)
    print(cfg["package"]["name"], cfg["paths"]["src"])
```

## See Also

- [Get Started](../get_started.md): setting up `invoke.yaml` in a new project.
- [`invoke_tasklib.config` reference](../refs/config.md)
