# Imports

:book: This page describes the `invoke_tasklib.imports` module.

## Overview

| Task                     | Behavior                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `imports.check-cycles`   | Checks for import cycles with a static import graph, and prints them (read-only)    |
| `imports.check-isolated` | Checks that every module imports on its own, one interpreter per module (read-only) |

## Checking for cycles

```shell
invoke imports.check-cycles
```

The import graph of `package.import_name` (from the [resolved config](config.md)) is built from the
source files with `ast`: nothing is imported, so the result is deterministic, does not depend on the
order of the imports, and needs no subprocess. `import a.b` is an edge to `a.b`, `from a import b`
is an edge to `a.b` if it is a module (else to `a`), and relative imports are resolved. Imports of
other packages are not edges. The strongly connected components of the graph are the cycles; each
one is printed as a path and the task exits with 1:

```text
Found 1 import cycle(s) in mypkg:
  mypkg.a -> mypkg.b -> mypkg.a
```

An import that does not run when a module is imported cannot cause a cycle, so by default the
imports under `if TYPE_CHECKING:` and the imports inside functions are ignored:

| Option            | Effect                                             |
| ----------------- | -------------------------------------------------- |
| `--lazy`          | Also follows the imports inside functions          |
| `--type-checking` | Also follows the imports under `if TYPE_CHECKING:` |

A syntax error is reported as such (with the module). So is a relative import that goes above the
top-level package (`from .. import x` in `pkg/a.py`), which Python rejects too. A missing optional
dependency is not reported at all, because neither is a cycle.

## Checking that every module imports on its own

```shell
invoke imports.check-isolated
```

This is the former behavior of `imports.check-cycles`. It discovers every module of the package
(`__main__` modules are skipped) without importing anything, then imports each one in its own
`python -c` process with the interpreter that runs Invoke. A module that fails to import on its own
depends on something that is only initialized as a side effect of importing another module first,
which is often the symptom of a cycle. It also fails on a missing dependency or a syntax error, and
it starts one interpreter per module, so it is slow for a package with heavy imports.

The commands are not echoed and their output is hidden. The task prints one line for the discovery,
one for the check, and then either one `✅` summary or one `❌ <module>: <last line of the traceback>`
line for each module that failed and the exit code 1. Every module is tried, so one run lists all
the failures.

## See Also

- [Config](config.md): where `package.name` and `package.import_name` come from.
- [`invoke_tasklib.imports` reference](../refs/imports.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
