# Imports

:book: This page describes the `invoke_tasklib.imports` module.

## Overview

| Task                   | Behavior                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| `imports.check-cycles` | Checks for cyclic import dependencies by importing each subpackage in isolation (read-only) |

## Usage

```shell
invoke imports.check-cycles
```

This discovers `package.name` (from the [resolved config](config.md)) and all of its subpackages
dynamically, then imports each one in its own `python -c` process. Importing a subpackage in
isolation fails if it depends on something that is only initialized as a side effect of importing
a sibling or parent module first, which is the usual symptom of a cyclic import dependency.

## See Also

- [Config](config.md): where `package.name` comes from.
- [`invoke_tasklib.imports` reference](../refs/imports.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
