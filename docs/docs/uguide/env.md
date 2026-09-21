# Env

:book: This page describes the `invoke_tasklib.env` module, which provides tasks to set up and
inspect a project's Python environment using [`uv`](https://docs.astral.sh/uv/).

## Overview

| Task                          | Behavior                                                 |
| ------------------------------ | ------------------------------------------------------------- |
| `env.create-venv`             | Creates a virtual environment and installs invoke         |
| `env.install`                 | Installs project dependencies and the package (editable)  |
| `env.update`                  | Updates dependencies and pre-commit hooks                  |
| `env.show-installed-packages` | Shows the installed packages                                |
| `env.show-python-config`      | Shows the Python configuration                              |

## Creating a Virtual Environment

```shell
invoke env.create-venv
```

Creates (or recreates) a `.venv` using the `package.python_version` from the
[resolved config](config.md), and installs `invoke` into it via `uv tool install`.

!!! warning
    This clears any existing `.venv`.

## Installing Dependencies

```shell
invoke env.install
```

Runs `uv sync --frozen` and installs the package in editable mode. By default this installs
optional (extras) and dev dependencies; documentation dependencies are opt-in:

```shell
invoke env.install --no-optional-deps --no-dev-deps
invoke env.install --docs-deps
```

## Updating Dependencies

```shell
invoke env.update
```

Runs `uv sync --upgrade`, upgrades all `uv` tools, updates pre-commit hooks
(`pre-commit autoupdate`), and reinstalls the project with documentation dependencies.

!!! warning
    Updating dependencies may introduce breaking changes. Review the changes and run the test
    suite afterward.

## Inspecting the Environment

```shell
invoke env.show-installed-packages
invoke env.show-python-config
```

`env.show-python-config` prints the installed Python versions known to `uv`, the interpreter `uv`
would select, and the interpreter currently on `PATH`.

## See Also

- [Config](config.md): where `package.python_version` comes from.
- [`invoke_tasklib.env` reference](../refs/env.md)
