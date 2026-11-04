# Env

:book: This page describes the `invoke_tasklib.env` module, which provides tasks to set up and
inspect a project's Python environment using [`uv`](https://docs.astral.sh/uv/).

## Overview

| Task                          | Behavior                                                 |
| ----------------------------- | -------------------------------------------------------- |
| `env.create-venv`             | Creates a virtual environment and installs the project   |
| `env.install`                 | Installs project dependencies and the package (editable) |
| `env.update`                  | Updates dependencies and pre-commit hooks                |
| `env.check-tools`             | Checks which tools of the tasks are available            |
| `env.show-installed-packages` | Shows the installed packages                             |
| `env.show-python-config`      | Shows the Python configuration                           |

## Creating a Virtual Environment

```shell
invoke env.create-venv
```

Creates (or recreates) a `.venv` using the `package.python_version` from the
[resolved config](config.md) (by default the version of `.python-version` or the lower bound of
`requires-python`), and then runs [`env.install`](#installing-dependencies) (`uv sync --locked`), so
the environment has `invoke` within the bounds of the project and the packages that `tasks.py`
imports, such as `invoke-tasklib`. The task is run with `invoke`, so `invoke` must already be
available (for example through `uv tool install invoke`) to run it. Use `env.install` to choose
the dependency groups.

<!-- prettier-ignore -->
!!! warning
    This clears any existing `.venv`, so the task asks for a confirmation when the directory exists
    (`--yes` turns it off, and is needed without a terminal). `--dry-run` prints what would be done
    and does nothing. The `invoke` that runs the task often lives in that `.venv`: run it from
    another environment.

## Installing Dependencies

```shell
invoke env.install
```

Runs `uv sync --locked`, which also installs the package itself in editable mode. `--locked` fails if `uv.lock`
is out of date with `pyproject.toml` instead of silently using it (run `uv lock` to refresh it).

| Flag              | Default                          | Adds to `uv sync`                               |
| ----------------- | -------------------------------- | ----------------------------------------------- |
| `--optional-deps` | on                               | `--all-extras`                                  |
| `--groups`        | `groups.install` (default `dev`) | `--group <name>` for each comma-separated group |

`--groups` takes a comma-separated list of [dependency groups](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups)
to install, e.g. `dev,docs`. A group listed twice is installed once. Pass an empty string to skip
installing any group.

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

Runs `uv lock --upgrade`, updates the pre-commit hooks (`pre-commit autoupdate`, only if the
project has a `.pre-commit-config.yaml` file), and reinstalls the project with the groups from `--groups` (default:
the [resolved config](config.md)'s `groups.update`, `"dev,docs"` unless overridden).

```shell
invoke env.update --groups dev,docs,test
```

<!-- prettier-ignore -->
!!! warning
    Updating dependencies may introduce breaking changes. Review the changes and run the test
    suite afterward.

## Inspecting the Environment

```shell
invoke env.show-installed-packages
invoke env.show-python-config
```

`env.show-python-config` prints the installed Python versions known to `uv`, the interpreter `uv`
would select, and the interpreter currently on `PATH`. It does not fail when no `python` is on
the `PATH`.

## Checking the Tools

```shell
invoke env.check-tools
```

`env.check-tools` gives a single view of the tools that the tasks run: the programs (`uv`, `uvx`,
`git`, `ruff`, `ty`, `pyright`, `docformatter`, `codespell`, `pre-commit`, `shellcheck`, `shfmt`,
`mkdocs`, `mike`) and the Python modules of the interpreter (`pytest`, `coverage`, `xdoctest`,
`pytest_timeout`, `pytest_cov`). Each tool has one line, with its path when it is available:

```text
✅ ruff: /project/.venv/bin/ruff
❌ shfmt: program not found. Install shfmt with your system package manager, ...
```

All the tools are listed, so one run shows everything that is missing. The task does not read the
config, so it can be run before `invoke.yaml` is set up. It exits with the code 127 if a tool is
missing, so it can also gate a CI job. It does not install anything: see `env.install`.

## See Also

- [Config](config.md): where `package.python_version` comes from.
- [`invoke_tasklib.env` reference](../refs/env.md)
- [Troubleshooting](../troubleshooting.md): fixes for common install/update errors.
