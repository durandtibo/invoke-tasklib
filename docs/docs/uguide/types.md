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

`--args` is passed to `ty` only, and `--pyright-args` to `pyright` only (it is used with
`--complete`); `--paths` is passed to both tools (see
[Passing Arguments to the Tools](index.md#passing-arguments-to-the-tools)):

```shell
invoke types.check --complete --args "--python-version 3.12" --pyright-args "--pythonversion 3.12"
```

Without `--paths`, `ty` checks the project and `pyright` the files of its own `include` setting (in
`pyproject.toml` or `pyrightconfig.json`), so the two tools can look at different files. Set the
same files in both, or pass `--paths`, to keep them aligned.

## See Also

- [`invoke_tasklib.typecheck` reference](../refs/types.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
