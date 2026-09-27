# Lint

:book: This page describes the `invoke_tasklib.lint` module.

## Overview

| Task                | Behavior                                                                  |
| ------------------- | ------------------------------------------------------------------------- |
| `lint.check-python` | Checks code linting with [ruff](https://docs.astral.sh/ruff/) (read-only) |
| `lint.fix-python`   | Fixes auto-fixable linting issues in place with ruff                      |

## Usage

```shell
invoke lint.check-python
```

This runs `ruff check --output-format=github .`, which is well-suited for use in a GitHub Actions
workflow since ruff annotates violations directly on the diff.

```shell
invoke lint.fix-python
```

This runs `ruff check --fix .`, which rewrites files in place for every auto-fixable violation.
Not every lint rule is auto-fixable, so `lint.check-python` may still report violations afterwards
that need a manual fix.

!!! warning
`lint.fix-python` modifies files in place. Commit your work before running it.

## See Also

- [Format](format.md): `format.check-python`/`format.fix-python` for formatting (as opposed to
  linting) with ruff.
- [`invoke_tasklib.lint` reference](../refs/lint.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
