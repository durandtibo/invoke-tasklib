# Lint

:book: This page describes the `invoke_tasklib.lint` module.

## Overview

| Task              | Behavior                                                                  |
| ----------------- | ------------------------------------------------------------------------- |
| `lint.check-lint` | Checks code linting with [ruff](https://docs.astral.sh/ruff/) (read-only) |

## Usage

```shell
invoke lint.check-lint
```

This runs `ruff check --output-format=github .`, which is well-suited for use in a GitHub Actions
workflow since ruff annotates violations directly on the diff.

## See Also

- [Format](format.md): `format.check-python`/`format.fix-python` for formatting (as opposed to
  linting) with ruff.
- [`invoke_tasklib.lint` reference](../refs/lint.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
