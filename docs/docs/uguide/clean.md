# Clean

:book: This page describes the `invoke_tasklib.clean` module.

## Overview

| Task            | Behavior                                              |
| --------------- | ----------------------------------------------------- |
| `clean`         | Removes build artifacts and caches from the repo root |
| `clean-pycache` | Removes all `__pycache__` directories                 |

Unlike the other namespaces, the clean tasks are registered as single top-level tasks (not
`clean.something`), since they are one-off maintenance commands.

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

To remove only the `__pycache__` directories:

```shell
invoke clean-pycache
```

## See Also

- [`invoke_tasklib.clean` reference](../refs/clean.md)
- [Troubleshooting](../troubleshooting.md): fixes for "command not found" errors.
