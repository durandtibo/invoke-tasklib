# Format

:book: This page describes the `invoke_tasklib.format` module, which provides tasks for checking
and fixing code, docstring, and shell script formatting.

## Overview

Tasks follow a `check_<target>` / `fix_<target>` naming convention:

- `check_<target>` tasks are **read-only**: they fail with a non-zero exit code if formatting is
  wrong, but never modify files.
- `fix_<target>` tasks **modify files in place** to match the expected format.

| Task                      | Behavior                                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| `format.check-python`     | Checks Python formatting with [ruff](https://docs.astral.sh/ruff/) (read-only)                    |
| `format.fix-python`       | Formats Python code with ruff (in place)                                                          |
| `format.check-docstrings` | Checks docstring formatting with [docformatter](https://docformatter.readthedocs.io/) (read-only) |
| `format.fix-docstrings`   | Formats docstrings with docformatter (in place)                                                   |
| `format.check-shell`      | Checks shell scripts with [shellcheck](https://www.shellcheck.net/) (read-only)                   |
| `format.fix-shell`        | Formats shell scripts with [shfmt](https://github.com/mvdan/sh) (in place)                        |

## Checking Format

```shell
invoke format.check-python
invoke format.check-docstrings
invoke format.check-shell
```

These are safe to run anywhere, including in CI, since they never modify files.

## Fixing Format

```shell
invoke format.fix-python
invoke format.fix-docstrings
invoke format.fix-shell
```

!!! warning
`fix_*` tasks modify files in place. Ensure your work is committed before running them.

## Docstring Style

`format.check-docstrings` and `format.fix-docstrings` run `docformatter` against `paths.src` from
the [resolved config](config.md), using the `[tool.docformatter]` section of the consuming
project's `pyproject.toml` (via `--config ./pyproject.toml`).

## Shell Scripts

`format.check-shell` and `format.fix-shell` operate on every `*.sh` file in the project, excluding
`.git/`.

!!! note
`shellcheck` and `shfmt` are not Python packages, so they aren't installed by
[`env.install`](env.md). Install them with your system package manager, e.g.
`brew install shellcheck shfmt` on macOS or `apt install shellcheck` on Debian/Ubuntu
(`shfmt` there comes from the `golang-go` toolchain or a
[release binary](https://github.com/mvdan/sh/releases)).

## See Also

- [Config](config.md): where `paths.src` (used by the docstring tasks) comes from.
- [Lint](lint.md): the companion `lint.check-lint` task.
- [`invoke_tasklib.format` reference](../refs/format.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
