# Types

:book: This page describes the `invoke_tasklib.types` module.

## Overview

| Task          | Behavior                                                                           |
| ------------- | ---------------------------------------------------------------------------------- |
| `types.check` | Checks type hints with [pyright](https://microsoft.github.io/pyright/) (read-only) |

## Usage

```shell
invoke types.check
```

This runs `pyright --verifytypes <package.name> --ignoreexternal`, using `package.name` from the
[resolved config](config.md). `--ignoreexternal` excludes type completeness issues that originate
from third-party dependencies rather than from the project's own code.

## See Also

- [Config](config.md): where `package.name` comes from.
- [`invoke_tasklib.types` reference](../refs/types.md)
