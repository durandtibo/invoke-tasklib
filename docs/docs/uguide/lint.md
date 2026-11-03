# Lint

:book: This page describes the `invoke_tasklib.lint` module.

## Overview

| Task                  | Behavior                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| `lint.check-python`   | Checks code linting with [ruff](https://docs.astral.sh/ruff/) (read-only)                        |
| `lint.fix-python`     | Fixes auto-fixable linting issues in place with ruff                                             |
| `lint.check-spelling` | Checks the spelling with [codespell](https://github.com/codespell-project/codespell) (read-only) |
| `lint.pre-commit`     | Runs all the [pre-commit](https://pre-commit.com/) hooks on all the files                        |

## Usage

```shell
invoke lint.check-python
```

This runs `ruff check .`. In GitHub Actions (`GITHUB_ACTIONS=true`) it adds
`--output-format=github`, so ruff annotates violations directly on the diff; locally the readable
default output is used. Pass `--output-format` to choose the format explicitly:

```shell
invoke lint.check-python --output-format=concise
```

```shell
invoke lint.fix-python
```

This runs `ruff check --fix .`, which rewrites files in place for every auto-fixable violation.
Not every lint rule is auto-fixable, so `lint.check-python` may still report violations afterwards
that need a manual fix.

<!-- prettier-ignore -->
!!! warning
    `lint.fix-python` modifies files in place. Commit your work before running it.

## Spelling and Pre-commit Hooks

```shell
invoke lint.check-spelling
```

This runs `codespell .` (the configuration is read from `pyproject.toml`). `--args` and `--paths`
work as for the other tasks.

```shell
invoke lint.pre-commit
```

This runs `pre-commit run --all-files`. Pass `--args` to select a hook, e.g.
`--args ruff-format`. The hooks may modify files.

## See Also

- [Format](format.md): `format.check-python`/`format.fix-python` for formatting (as opposed to
  linting) with ruff.
- [`invoke_tasklib.lint` reference](../refs/lint.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
