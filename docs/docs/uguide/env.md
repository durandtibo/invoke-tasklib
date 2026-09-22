# Env

:book: This page describes the `invoke_tasklib.env` module, which provides tasks to set up and
inspect a project's Python environment using [`uv`](https://docs.astral.sh/uv/).

## Overview

| Task                          | Behavior                                                 |
| ----------------------------- | -------------------------------------------------------- |
| `env.create-venv`             | Creates a virtual environment and installs invoke        |
| `env.install`                 | Installs project dependencies and the package (editable) |
| `env.update`                  | Updates dependencies and pre-commit hooks                |
| `env.show-installed-packages` | Shows the installed packages                             |
| `env.show-python-config`      | Shows the Python configuration                           |

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

Runs `uv sync --frozen` and installs the package in editable mode.

| Flag              | Default                          | Adds to `uv sync`                               |
| ----------------- | -------------------------------- | ----------------------------------------------- |
| `--optional-deps` | on                               | `--all-extras`                                  |
| `--groups`        | `groups.install` (default `dev`) | `--group <name>` for each comma-separated group |

`--groups` takes a comma-separated list of [dependency groups](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups)
to install, e.g. `dev,docs`. Pass an empty string to skip installing any group.

Disable the on-by-default optional deps, or override the groups, with:

```shell
invoke env.install --no-optional-deps --groups ""
invoke env.install --groups dev,docs
```

The default value of `--groups` comes from the [resolved config](config.md)'s
`groups.install` (`"dev"` unless overridden in `invoke.yaml`), so a project with more groups
than `dev`/`docs` can change the default once instead of passing `--groups` on every call.

## Updating Dependencies

```shell
invoke env.update
```

Runs `uv sync --upgrade`, upgrades all `uv` tools, updates pre-commit hooks
(`pre-commit autoupdate`), and reinstalls the project with the groups from `--groups` (default:
the [resolved config](config.md)'s `groups.update`, `"dev,docs"` unless overridden).

```shell
invoke env.update --groups dev,docs,test
```

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
- [Troubleshooting](../troubleshooting.md): fixes for common install/update errors.
