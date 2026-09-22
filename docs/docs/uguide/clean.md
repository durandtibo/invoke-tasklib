# Clean

:book: This page describes the `invoke_tasklib.clean` module.

## Overview

| Task    | Behavior                                              |
| ------- | ----------------------------------------------------- |
| `clean` | Removes build artifacts and caches from the repo root |

Unlike the other namespaces, `clean` is registered as a single top-level task (not
`clean.something`), since it's a one-off maintenance command.

## Usage

```shell
invoke clean
```

Removes, if present, at the repository root:

- Directories: `build`, `dist`, `.pytest_cache`, `.ruff_cache`, `.coverage_html`, `htmlcov`,
  `.benchmarks`, `site`
- Glob-matched directories: `*.egg-info`, `**/__pycache__`
- Files: `.coverage`, `coverage.xml`

Nothing is removed if the corresponding directory or file doesn't exist, so `clean` is safe to run
repeatedly (it's idempotent) and doesn't fail on an already-clean checkout.

## See Also

- [`invoke_tasklib.clean` reference](../refs/clean.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
