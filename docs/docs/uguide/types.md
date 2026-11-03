# Types

:book: This page describes the `invoke_tasklib.typecheck` module.

## Overview

| Task          | Behavior                                                            |
| ------------- | ------------------------------------------------------------------- |
| `types.check` | Checks type hints with [ty](https://docs.astral.sh/ty/) (read-only) |

## Usage

```shell
invoke types.check
```

This runs `ty check`.

Pass `--complete` to also run [pyright](https://microsoft.github.io/pyright/) after `ty` (slower,
more thorough):

```shell
invoke types.check --complete
```

`--args` is passed to `ty` only; `--paths` is passed to both tools (see
[Passing Arguments to the Tools](index.md#passing-arguments-to-the-tools)).

## See Also

- [`invoke_tasklib.typecheck` reference](../refs/types.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
