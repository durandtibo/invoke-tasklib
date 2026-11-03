# Check

:book: This page describes the `invoke_tasklib.check` module.

## Overview

| Task        | Behavior                                                |
| ----------- | ------------------------------------------------------- |
| `check.all` | Runs the main read-only checks of the project (default) |

`check.all` is the default task of the `check` namespace, so `invoke check` runs it.

## Usage

```shell
invoke check
```

Runs, in this order, and stops at the first failure:

1. [`format.check-python`](format.md)
2. [`format.check-docstrings`](format.md)
3. [`lint.check-python`](lint.md)
4. [`types.check`](types.md)
5. [`imports.check-cycles`](imports.md)
6. [`test.unit`](test.md)

None of them modifies a file. Use the tasks directly (with `--args` and `--paths`) to run only one
of them, or [`lint.pre-commit`](lint.md) to run the hooks of the project. To leave `check` out of a
collection, use `make_ns(exclude=["check"])`.

## See Also

- [`invoke_tasklib.check` reference](../refs/check.md)
