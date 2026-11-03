# Imports

:book: This page describes the `invoke_tasklib.imports` module.

## Overview

| Task                   | Behavior                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| `imports.check-cycles` | Checks for cyclic import dependencies by importing each module in isolation (read-only) |

## Usage

```shell
invoke imports.check-cycles
```

This discovers every module of `package.name` (from the [resolved config](config.md)): the package
itself, its subpackages and all the modules, recursively (`__main__` modules are skipped). The
discovery walks the package directories and does not import anything, so it cannot fail with the
cycle it is meant to detect. Each module is then imported in its own `python -c` process, using the
interpreter that runs Invoke. Importing a module in isolation fails if it depends on something that
is only initialized as a side effect of importing a sibling or parent module first, which is the
usual symptom of a cyclic import dependency. For example, two sibling modules that do
`from pkg.b import y` and `from pkg.a import x` are reported even though neither is a package.

## See Also

- [Config](config.md): where `package.name` comes from.
- [`invoke_tasklib.imports` reference](../refs/imports.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
