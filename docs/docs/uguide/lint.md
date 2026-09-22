# Lint

:book: This page describes the `invoke_tasklib.lint` module.

## Overview

| Task              | Behavior                                                                  |
| ----------------- | ------------------------------------------------------------------------- |
| `lint.check-lint` | Checks code linting with [ruff](https://docs.astral.sh/ruff/) (read-only) |
| `lint.fix`        | Fixes auto-fixable linting issues in place with ruff                      |

## Usage

```shell
invoke lint.check-lint
```

This runs `ruff check --output-format=github .`, which is well-suited for use in a GitHub Actions
workflow since ruff annotates violations directly on the diff.

```shell
invoke lint.fix
```

This runs `ruff check --fix .`, which rewrites files in place for every auto-fixable violation.
Not every lint rule is auto-fixable, so `lint.check-lint` may still report violations afterwards
that need a manual fix.

!!! warning
`lint.fix` modifies files in place. Commit your work before running it.

## See Also

- [Format](format.md): `format.check-python`/`format.fix-python` for formatting (as opposed to
  linting) with ruff.
- [`invoke_tasklib.lint` reference](../refs/lint.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
